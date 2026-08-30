# 04 — DFM Checker

Design-for-manufacture checks that read a STEP file and report what a shop
would raise about it.

**Status:** Complete — four checks, four process presets, a survey across
every part in this repository, 14 tests.
**Environment:** `conda activate pyocc_env` (pythonocc-core 7.9.0).

```bash
conda run -n pyocc_env python build.py       # survey every part here
conda run -n pyocc_env python -m pytest -q   # 14 tests
```

## What makes this different from project 05's rule engine

The sheet-metal checks in project 05 validate **parameters** — numbers the
designer hands over. That works only when the design and the check share an
author. This reads a **solid it did not create**, which is the situation a
real DFM review is in: a supplier's model, another team's part, or your own
from six months ago.

Everything here is measured off the B-rep:

| Check | How |
|---|---|
| **Minimum wall** | Fires rays inward from sampled surface points and measures the distance to the far side. Thickness is measured, not declared. |
| **Draft angle** | Face normals against the pull direction. Any wall closer to parallel than the minimum locks the part in the tool. |
| **Hole aspect ratio** | Finds concave cylinders that sweep a full turn, and divides depth by diameter. |
| **Internal radius** | Concave cylinders that sweep *less* than a half turn — corners, judged against the smallest cutter that could reach them. |

**No cost or lead-time estimate.** The scaffold for this project proposed
both, quoting "$500 against $5,000 per part". Those numbers had no source,
and projects 01 and 02 already removed exactly that kind of invented figure
for exactly that reason. "This hole is 5.7:1 and needs gun-drilling" is
useful. "This costs $5,000" is a guess wearing a number.

## Process is the thing that matters

Getting the process right matters more than any individual limit, and the
first version of this got it wrong in a way worth keeping in the record.

Run casting rules over a turned part and **every bore fails on draft** —
which is true of a mould and meaningless on a lathe, where a bore has no
draft by definition and needs none. The actuator cylinder body came back
with three confident failures and nothing wrong with it.

So `checks_draft` is a property of the process, not a switch:

| Process | Min wall | Draft | Hole aspect | Min ⌀ |
|---|---|---|---|---|
| `machined` | 1.5 mm | not checked | 5:1 | 2.0 mm |
| `sand-cast` | 4.0 mm | 2° | 3:1 | 6.0 mm |
| `investment-cast` | 2.0 mm | 1° | 4:1 | 3.0 mm |
| `formed-tube` | 0.4 mm | not checked | — | 1.0 mm |

The same actuator cylinder **passes as machined and fails as cast**. That
is the checker working, not a bug.

## The survey

`build.py` runs every part in this repository under the process it is
actually made by:

| Part | Process | | Thinnest wall |
|---|---|---|---|
| Actuator cylinder body | machined | **PASS** | 3.00 mm |
| Actuator piston rod | machined | **PASS** | 1.50 mm |
| Actuator clevis end | machined | **PASS** | 4.00 mm |
| Gearbox housing | sand-cast | **17 failures** | 1.75 mm |
| Bleed duct | formed-tube | **PASS** | 0.60 mm |
| Sheet-metal bracket | machined | **PASS** | 1.60 mm |

### The gearbox housing result is the good one

17 failures — no draft anywhere and a 1.75 mm wall against the 4 mm sand
casting wants. Project 02's own README says, under known simplifications:

> *Explicitly NOT modelled: casting draft angles, stepped bearing pockets,
> fillets for stress concentration*

The checker found that **from the geometry, having never read the README**.
That is what separates a check from a restatement, and it is the closest
thing here to a controlled experiment: a known defect, independently
recovered.

### And one finding that was about me

The survey first ran the bleed duct as `machined` and failed it on a
0.60 mm wall. The check was right — you cannot machine a 0.60 mm wall from
solid. The **process was wrong**: a duct is rolled and welded tube, not
milled from billet. Hence the `formed-tube` preset, and the reason the
table above lists a process for every part rather than assuming one.

A DFM answer is only ever as good as the process behind it, and
`machined` is not a safe default.

## Two bugs the tests caught

**Normals were being flipped twice.** `BRepGProp_Face.Normal` already
accounts for face orientation. Flipping reversed faces again — the obvious
defensive move — turned every bore into a boss, and would have inverted
every draft angle. Caught by building a tube with a known bore and asserting
one face of each kind.

**A bend fillet was reported as a deep hole.** The sheet-metal bracket's R3
bend is concave and runs 50 mm across the part, so it came back as
"⌀6 × 50 deep, needs gun-drilling" — a confident recommendation about a
feature that does not exist. A hole sweeps a full turn around its axis; a
fillet sweeps a quarter. Both checks now test the angular sweep, and the
test asserts the fillet is silent *and* the actuator's real 5.7:1 bore is
still flagged.

## Figures

```bash
conda run -n pyocc_env python figures.py   # matrix + housing scene
python ../render.py dfm                    # renders that scene in VTK
```

- `figures/dfm-findings.png` — the gearbox housing with all seventeen
  failures marked **at the coordinate each check returned**. The renderer
  reads those positions from JSON and never recomputes one, so the marks
  are measurements rather than annotations.
- `figures/dfm-matrix.png` — six parts against four processes. Every part
  is clean as machined or formed tube, and accumulates failures as a
  casting.

Both are published at <https://vinaykumar.is-a.dev>.

## Validation

- **Ray thickness against a known cube** — a 10 mm box must return exactly
  10.00 mm.
- **Ray thickness against a known tube** — 20 mm outer, 15 mm bore, must
  return 5.00 mm.
- **Against a design constant.** The actuator sets `wall_thickness = 3`
  in its generator; ray-casting the exported STEP returns **3.00 mm**
  without ever reading that code. The strongest check available here,
  because the two paths share nothing.

## Files

| | |
|---|---|
| `geometry.py` | Face typing, outward normals, bore/boss classification, ray casting. |
| `dfm.py` | The four checks, process presets, findings and report. |
| `build.py` | Survey across every part in this repository. |
| `test_dfm.py` | 14 tests. |

## Outstanding

- **No tool-accessibility check.** Whether a cutter can physically reach a
  face is the check a shop most wants and the hardest to do properly — it
  needs a swept-tool collision test, not a normal.
- **Wall thickness is sampled, not exhaustive.** A 3×3 UV grid per face
  finds thin regions but could miss a narrow one between samples. A medial
  axis would be exact and far slower.
- **Undercuts are not detected.** Faces with draft can still be
  unreachable if something else is in the way.
- **Rules are representative, not a shop's.** Every limit is a parameter
  for that reason.

---

See: [[01-Hydraulic-Actuator]] | [[02-Gearbox-Family]] | [[03-Thermal-Duct]] | [[05-Sheet-Metal-Bracket]]
