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

## A real bug this caught

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

## Status

**Current:** Fully implemented and run — gear sizing, bearing selection,
housing, assembly, and BOM generation all working, verified via solid
counts and STEP reimport checks (not just "the script didn't crash").

---

See: [[01-Hydraulic-Actuator]] | [[03-Thermal-Duct]] | [[04-DFM-Optimizer]]
