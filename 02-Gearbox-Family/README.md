# Parametric Gearbox Family Generator

**Programmatic CAD design for engine accessory gearbox scaling**

## Overview

Generates parametric gearbox designs (pinion + gear + housing) that scale
with engine accessory drive power rating. One script sizes the gear mesh
via the Lewis bending equation, selects bearings, builds the 3D geometry,
and exports a family of 5-50 kW gearboxes with a real bill of materials.

```
python3 gearbox_family.py
```

### Features

✅ **Real involute gear teeth** — built from the involute function
(`inv(alpha) = tan(alpha) - alpha`), not a stand-in shape; verified to
extrude cleanly with min/max radius matching the computed dedendum/
addendum radii exactly.
✅ **Lewis-equation module sizing** — solves the standard bending-stress
equation for the minimum module, using a textbook Lewis Y-factor table
(20° full-depth), then rounds up to a standard module size.
✅ **Bearing selection** — sizes each shaft from pure-torsion shear
stress, then selects the smallest standard 60xx-series deep-groove ball
bearing whose bore fits.
✅ **Housing** — a single-solid CAD body (base flange + bearing-boss
towers + corner mounting pads + drain plug boss), verified via
solid-count and STEP reimport checks.
✅ **Real BOM** — component masses computed from each part's actual
generated solid volume (not an approximate formula — see "Known
simplifications" below for what *is* approximated).

## Aerospace Application

Engine accessory gearbox powers:
- Hydraulic pump (flight control actuation)
- Fuel pump (fuel flow control)
- Oil pump (lubrication)
- Generator (electrical power)

**Typical specification:**
- Power: 5-50 kW
- Speed ratio: 1:3 to 1:8 (gearbox reduction)
- Material: Aluminum (housing), Steel (gears/shafts)
- Efficiency: 92-96% (this generator assumes a single representative 94%)

## Known simplifications

Stated explicitly rather than silently assumed away (also in
`BOM.json`'s `known_simplifications`):

- Single spur stage only — no helical or planetary option.
- Overload factor, dynamic factor, and allowable bending stress are
  representative typical values, not an AGMA material+duty-class
  selection.
- Bearing selection matches shaft diameter to a standard bore size only —
  no dynamic load rating / L10 life calculation (would need real
  manufacturer catalog data this project doesn't have).
- Housing has no casting draft angles or stepped bearing pockets — a
  plain through-bore stands in for a bearing seat.
- No cost estimate — no real supplier/cost data source available;
  fabricating one would misrepresent it as real (the same reasoning
  [[01-Hydraulic-Actuator]] applies to its own BOM).

## Real bugs this caught

The housing was first built by extruding each feature (bosses, ribs,
pads, drain boss) separately and `union()`-ing the solids. The two
bearing bosses don't actually reach each other across the center
distance, and the connecting "ribs" only touched them at a tangent point
rather than a genuine volumetric overlap — CadQuery's `union()` doesn't
error on this, it just silently returns multiple disjoint solids. Caught
by checking `.solids()` count in isolation (6, not 1) before assuming the
geometry was right. Fixed by switching to a "base flange + boss towers"
pattern, where every feature sits on one common flange footprint by
construction. A second real bug: the BOM's housing mass used a
hand-rolled formula written before that redesign, which never accounted
for the flange at all — it undershot the real solid's actual OCC volume
by 3.4x. Fixed by computing every component's mass from its real
generated solid volume instead of an approximate formula.

Three more, all found by rendering the assembly rather than by reading
the code — a picture of the geometry asks questions a solid count does
not.

**The involute was mirrored.** The half tooth angle at radius r is
`pi/(2N) + inv(alpha) - inv(alpha_r)`; the code had the two involute
terms the other way round. That still gives exactly the right tooth
thickness at the pitch circle, where the two terms cancel, so it passes
any check of pitch dimensions — but everywhere else the tooth flares
*outward*, into an hourglass whose flanks cross. The resulting wire
self-intersected, the extruded solid failed `BRepCheck_Analyzer`, and
its end face would not triangulate: the 22,345 mm² face got 281
triangles and rendered, and exported to any mesh format, with holes
through it. The earlier "verified no self-intersecting wire" claim was
checking min/max radius, which an hourglass tooth satisfies perfectly.

Now checked properly, at four tooth counts: polygon area within 0.3% of
the pitch-circle area, exactly 2N crossings of the pitch circle (two per
tooth, one per flank), no segment pair intersecting, `BRepCheck_Analyzer`
valid, and tooth thickness at the pitch circle within 0.2% of `pi*m/2` —
which is the polygon-chord error of sampling a curve with straight
segments, and nothing else.

**The housing did not enclose its own gear.** The flange footprint was
sized from the bearing-boss diameters plus a pad margin, which has
nothing to do with how big the gear is: bearing OD grows with shaft
torque, gear OD grows with the module the Lewis equation asks for, and
those are not the same curve. The gear overhung the casing by 8 mm at
5 kW and 84 mm at 50 kW. The footprint is now the larger of the two
requirements on each edge.

**The bearing bosses ran through the gears.** Bosses were extruded to
`face_width + 20` and both gears sat at z = 10, so a 47 mm boss passed
through a gear whose bore is 25 mm. Bosses are now one bearing-seat tall
(flange + widest bearing width, so both finish level and the gears stay
coplanar and still mesh) and the gears sit on top of them. Verified by
pairwise boolean intersection across all five power ratings: zero volume
shared between any two components.

## Tests

`python -m pytest test_gearbox_family.py` — **78 tests**. This project went
longest without any, and it is the one where the most defects turned up.
That is not a coincidence, and writing them found another.

### The meshing teeth occupied the same space

Both tooth profiles are drawn with a tooth centred on their own +X axis, so
the pinion always presents a *tooth* toward the gear. Whether the gear
presents a tooth or a gap back depends on parity — and with an even tooth
count it has one at 180° too, pointing straight at the pinion's. The two
solids overlapped by **424 mm³, 2.1% of the pinion's volume**.

Every member of the shipped family has an even gear (70, 80, 90, 100, 110),
so **every exported assembly had it**, and the STEP files have been
regenerated. `assembly()` now offsets the gear by half a tooth pitch, which
drives the interference to exactly zero.

The parity matters and the rule is not "always rotate": an odd gear already
presents a gap, and rotating it causes precisely the clash it was meant to
avoid. Both directions are verified — 90 teeth clash unrotated and are clean
at half pitch; 91 teeth are clean unrotated and clash at half pitch.

The Status section below claimed pairwise clash checks. They evidently did
not cover the gear-against-pinion pair in the assembled position, which is
the one pair that has to be right for the thing to be a gearbox.

### A valid solid is not a correct one

The tests were checked by reintroducing the original involute sign error and
confirming the suite goes red. It does — but only through *one* test, and
the two obvious candidates both stay green:

- **Tooth thickness at the pitch circle passes.** The mirrored sign gives
  the correct half-angle of π/2N there. That is why the bug survived
  whatever pitch-dimension checking it first met.
- **`BRepCheck_Analyzer` validity passes too.** Mirrored, `psi_tip` reaches
  0.125 rad on the 20-tooth pinion against a half-sector of 0.157 — the
  tooth is the wrong shape, but its flanks still stay inside their own
  sector, so the wire does not cross and the solid is genuinely valid. At
  none of the tooth counts this project ships (18, 20, 35, 90) does the
  mirrored profile self-intersect.

Only checking that the half-angle *decreases* from root to tip catches it.
Verifying that geometry is well-formed is a different question from
verifying it is correct, and only the second one would have caught this.

### What else is covered

Involute geometry (closed counter-clockwise outline, every point between
root and tip circles, one tip land per tooth, pointed teeth refused);
contact ratio above 1.2 across the family and recomputed independently;
the Lewis table returned exactly, interpolated, clamped and monotone;
module rounding never downward; bearing bores always taking their shaft and
always the smallest that does; torque from power and speed, shaft diameter
from the torsion equation, and tooth stress under allowable for every
family member; the housing a single valid solid with the gear inside its
own footprint; and BOM masses recomputed from the solids' own volumes.

One gap the tests documented rather than fixed: `total_mass_kg` covers only
the three modelled solids. Bearings, seals and bolts are listed with
quantities but carry no mass, so the figure is the manufactured mass, not
the assembly's. That is now stated in `known_simplifications` — a test
fails if the total starts excluding parts without saying so.

## Status

**Current:** Implemented and run — gear sizing, bearing selection,
housing, assembly and BOM generation all working, and now covered by 78
tests. Geometry is verified by solid counts, `BRepCheck_Analyzer` validity,
pairwise clash checks and the tooth-profile checks listed above, not by
"the script didn't crash" — though see Tests above for a clash check that
was claimed here and was not actually being made.

Masses moved when the tooth profile was corrected, since the old solid
was self-intersecting and under-measured: the 5 kW pinion went 0.032 →
0.068 kg and its gear 0.848 → 0.978 kg. Any figure quoted from a BOM
generated before that fix is wrong.

**Outstanding:**

- Bearings are selected on bore size alone — no L10 life calculation.
- Housing is a base flange with open bosses: no cover, no split line, no
  casting draft, no stepped bearing seats.
- Gears are cantilevered on a single bearing boss each. A real accessory
  drive carries each shaft between two bearings, which needs the housing
  to grow walls — the natural next piece of work here.
- Root fillets are a plain dedendum-circle arc, not the trochoid a
  hobbing cutter actually leaves.
- The mesh phase is set for the assembly's static pose only. There is
  no rotation, so nothing here checks that the teeth stay clear
  *through* a mesh cycle — only that they do at one angle.

## Figures

`../render.py` builds these from the same generator this README
describes — tessellated on the OpenCASCADE kernel and rendered offscreen
through VTK, so no CAD GUI, browser or screenshot is involved:

```bash
python ../render.py gearbox
```

- `figures/gearbox-assembly.png` — the 20 kW design, housing, pinion and
  gear in mesh.
- `figures/gearbox-sizing.png` — standard module and tooth bending stress
  against power rating across the family.

Both are written in light and dark variants, in the portfolio site's own
colour tokens, and are the versions published at
<https://vinaykumar.is-a.dev>.

---

See: [[01-Hydraulic-Actuator]] | [[03-Thermal-Duct]] | [[04-DFM-Optimizer]]
