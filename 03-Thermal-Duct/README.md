# 03 — Bleed Air Duct

A hot bleed duct sized from real engine conditions, routed in 3D, and
checked against the structure it has to share a bay with.

**Status:** Complete — sizing, material selection, swept geometry, clearance
study, STEP export, 37 tests.
**Environment:** `conda activate pyocc_env` (Python 3.10, pythonocc-core
7.9.0 — the same environment projects 04, 06 and 07 of the analysis
portfolio use).

```bash
conda run -n pyocc_env python build.py            # size, route, check, export
conda run -n pyocc_env python -m pytest -q        # 37 tests
```

28 of those 37 need no pyOCC at all — `test_sizing.py` is the engineering
and runs on any Python with pytest. Only `test_duct.py` needs the kernel.

## Why pyOCC here, when the other CAD projects use CadQuery

Two things this needs that CadQuery does not expose directly:

- **A sweep along a general 3D curve.** A routed duct follows a spline
  through waypoints, not a sequence of planar operations.
  `BRepOffsetAPI_MakePipe` does that.
- **Distance queries against arbitrary solids.**
  `BRepExtrema_DistShapeShape` returns the true minimum distance between two
  B-rep shapes. That is the question a routing study exists to answer, and
  it cannot be eyeballed from any single view.

## Where the numbers come from

Station 3 — HPC exit — of the twin-spool cycle model in the analysis
portfolio, at its reference design point (40 kg/s core, OPR 35.8, TET
1650 K, FL350 / M0.78):

| | |
|---|---|
| Total temperature | 759.5 K |
| Total pressure | 12.52 bar |
| Offtake | 1.0 kg/s — 2.5% of core flow |

That station is not chosen for convenience. It is where a real engine takes
customer bleed for cabin air and wing anti-ice. **Change the cycle design
point and this sizes a different duct** — nothing here is a hard-coded
answer.

## The four questions, asked in order

A duct is not a tube with a diameter. It is four questions where each
answer constrains the next:

1. **How big must the bore be?** Continuity at a chosen velocity. 50 m/s
   gives ⌀66.6 mm, at Mach 0.091 — comfortably inside where the
   incompressible sizing is defensible.
2. **What material survives 759.5 K?** Aluminium is out by 300 K.
   Titanium — lighter, and the one you want — is out by 60 K. **Stainless
   321** is the lightest survivor. Inconel would also work and weighs 7%
   more for nothing.
3. **How thick must the wall be?** See below.
4. **How tightly can it be bent?** The outside of a bend stretches and
   thins. That feeds straight back into question 3.

## The result worth reporting

| Constraint | Demands |
|---|---|
| Hoop stress at 12.52 bar | 0.447 mm |
| Minimum handling gauge | 0.500 mm |
| **Surviving a 2D bend** | **0.558 mm** |

**Bend thinning governs, not pressure.** The wall goes to the next standard
gauge at 0.60 mm, and after 20% thinning on the outside of the bend it
still carries 0.480 mm — clear of the 0.447 mm the pressure needs.

Everyone assumes a pressure vessel is sized by pressure. At these
proportions it is sized by what surviving the bend leaves behind, and by
what a person can weld without burning through.

### And a stronger version of that, found by writing a test

The bend requirement is the hoop requirement divided by a thinning factor
that is always below one. So it **always** exceeds hoop stress, at any
pressure. No bent duct is ever sized by pressure alone — only a straight
run can be, which is why `size_duct` takes `bend_diameters=None` for that
case. The test that asserts this is `test_hoop_can_only_govern_a_straight_duct`,
and it was written to check the opposite before it failed.

## Clearance, with the duct hot

A duct routed to a cold drawing touches its neighbours the first time the
engine runs. Stainless 321 over a 960 mm route, from a 288 K build to
759.5 K running, **grows 7.6 mm**.

So the clearance requirement is thermal growth plus 3 mm for vibration and
build tolerance — **10.5 mm**, not a number anyone would have guessed by
looking.

Two routes are kept in `build.py` on purpose:

| Route | Core casing | Bracket | Verdict |
|---|---|---|---|
| Initial — hugs the core, shortest run | **0.00 mm** | 9.40 mm | **rejected** |
| Revised — lifted and outboard | 14.97 mm | 48.48 mm | passes |

The obvious route fouls the casing outright and leaves the bracket inside
the growth allowance. Keeping the rejected one in the file matters: a
routing study that only ever shows the answer that worked looks like luck
rather than method.

## Figures

```bash
conda run -n pyocc_env python figures.py   # chart + STL scene
python ../render.py duct                   # renders that scene in VTK
```

Two commands and two environments, deliberately. `pyocc_env` has the
kernel but no VTK; the base environment has VTK but not pythonocc.
Rather than install VTK twice, the project tessellates beside the kernel
that built the solid and writes STL, and `../render.py` draws it. The
clearance numbers always come from the B-rep, never from that mesh.

- `figures/duct-constraints.png` — what each constraint demanded of the
  wall, and which one won.
- `figures/duct-clearance.png` — the accepted route and the rejected one
  together, past the structure both had to clear.

Both are published at <https://vinaykumar.is-a.dev>.

## Validation

- **Continuity, backwards.** The bore is fed back through `ρAV` and must
  return the mass flow it was sized for.
- **Swept volume against closed form.** A straight run's swept wall volume
  must equal `π(r_o² − r_i²)L`. It matches to 1 part in 10⁶ — an
  independent check that `MakePipe` produced what was asked for.
- **Thin-wall validity.** `t/d` is asserted below 0.05, the bound the hoop
  formula needs.
- **Mach below 0.3**, the bound the incompressible sizing needs.
- **Valid solid** by `BRepCheck_Analyzer`.

## Files

| | |
|---|---|
| `sizing.py` | Flow, hoop stress, bend thinning, material selection, thermal growth. No CAD. |
| `duct.py` | Spline route, swept solid, flanges, distance queries. pyOCC. |
| `build.py` | Design point, route, clearance study, STEP export. |
| `test_sizing.py` | 28 tests, no pyOCC needed. |
| `test_duct.py` | 9 geometry tests, pyOCC. |

## Outstanding

- **No insulation.** A 760 K duct in an accessory bay needs lagging, and
  the thickness follows from a radial conduction balance against a
  touch-temperature or adjacent-structure limit. Sized here, it would be
  another constraint feeding the same chain.
- **No bellows or sliding joint.** 7.6 mm of growth has to go somewhere.
  This design assumes the route is compliant enough to absorb it, which is
  an assumption, not a calculation.
- **No pressure loss.** Bends and length cost pressure, and bleed pressure
  is expensive — it was paid for in the cycle. A K-factor sum would say
  how much this route costs the engine.
- **No brackets.** The duct is checked against structure but not attached
  to it. Support spacing is a vibration problem.
- **Clearance is checked against two simplified obstructions**, not a real
  installation. The method is the deliverable; the bay is a stand-in.

---

See: [[01-Hydraulic-Actuator]] | [[02-Gearbox-Family]] | [[05-Sheet-Metal-Bracket]]
