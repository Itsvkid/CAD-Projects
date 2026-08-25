# 05 — Formed Sheet-Metal Bracket

An equipment mounting bracket: a base that bolts to structure, an upright
that bolts to the equipment, one 90° fold between them. Parametric, checked
against manufacturability rules before it is built, and drawn as both a
formed part and a flat pattern.

**Status:** Complete — forming arithmetic, DFM rule set, parametric solid,
flat pattern, STEP/DXF export, a detail drawing with a bend table, and 29
tests.
**Environment:** `pip install cadquery matplotlib pytest` (CadQuery 2.8,
Python 3.13). No pyOCC environment needed — CadQuery brings its own kernel.

```bash
python bracket.py        # build, run the DFM checks, export
python drawing.py        # drawings/SMB-001-bracket.png
python -m pytest -q      # 29 tests
```

## Why this part, when the portfolio already has machined ones

Sheet metal is its own discipline and nothing else here covers it. A
machined part is defined by what is cut away; a folded part is defined by
what the material will *survive being bent into*, and by the fact that the
shape a shop cuts is not the shape that gets installed. Every constraint
that makes it different is present in a part this simple:

- a minimum bend radius set by the alloy, not by the designer
- a minimum flange the press brake can physically grip
- holes that have to stay clear of the bend or be dragged oval by it
- fastener edge distances that decide whether a joint tears out
- a flat blank that is **shorter** than the finished part's legs added up

## The one calculation that matters

Bending stretches the outside of the material and compresses the inside.
Between the two is a neutral axis whose length does not change, and it sits
nearer the inside surface than the middle — at `K·T` from the inside face,
where K runs from about 0.33 on a tight bend to 0.45 on an open one.

```
bend allowance   BA = θ · (R + K·T)          material consumed by the fold
outside setback  OSSB = tan(θ/2) · (R + T)   tangent line to the sharp apex
bend deduction   BD = 2·OSSB − BA
flat length      L = Σ(outside legs) − Σ(BD)
```

For the reference bracket — 60 and 45 outside, 1.6 thick, R3, one 90° fold:

| | |
|---|---|
| Bend allowance | 5.718 mm |
| Outside setback | 4.600 mm |
| Bend deduction | 3.482 mm |
| **Flat length** | **101.52 mm** |
| Summed outside legs | 105.00 mm |

Cut the blank at 105 and every part in the batch is 3.5 mm long, in the
same direction, and nobody notices until assembly. That is the classic
sheet-metal error, and it is why the drawing dimensions the formed part and
puts the flat pattern alongside it rather than leaving the shop to guess.

## Validation: forming conserves volume

The flat-pattern arithmetic gets an independent check that owes nothing to
the formula it is testing. **Bending moves metal; it does not create or
destroy it**, so the blank and the formed part must have the same volume.

| | |
|---|---|
| Formed solid | 8076.15 mm³ |
| Flat blank | 7990.68 mm³ |
| Difference | **+1.07%** |

That residual is the K-factor model showing its size — a single linear
neutral axis against the exact toroidal geometry of the fillet — not an
error. For contrast, a blank cut to the summed outside legs would be
**5.12%** oversize, so the check discriminates comfortably between a right
answer and the obvious wrong one. It runs as a test.

## Design for manufacture

`sheet_metal.py` holds the rules; `AngleBracket.violations()` returns every
one the design breaks, as a list rather than raising on the first, so a
design that is wrong three ways reports three problems instead of making
the designer fix and re-run three times.

| Rule | Requirement | This design |
|---|---|---|
| Minimum bend radius | ≥ material factor × T | R3 vs 1.6 required |
| Minimum flange | ≥ max(4T, R + 2T) | 45 vs 6.4 required |
| Hole edge to bend | ≥ R + 2T | 40.9 vs 6.2 required |
| Fastener edge distance | ≥ 2 × ⌀ | 12.0 vs 10.2 required |
| Minimum hole ⌀ | ≥ T | 5.1 vs 1.6 required |

### Why 5052-H32 and not 2024-T3

This is the material trade the bracket exists to demonstrate. 2024-T3 is
nearly twice as strong (435 vs 228 MPa) and is the obvious airframe choice
— but its minimum bend radius is **4T against 5052's 1T**. At 1.6 mm
thickness that is R6.4 rather than R1.6, which makes the specified R3 fold
impossible: it would crack the outside fibre.

A bracket like this is limited by stiffness and by the fasteners at its
ends, not by the sheet's tensile strength, so the strength is worth nothing
and the formability is worth a great deal. Ask for 2024-T3 anyway and the
DFM check says so:

```
MIN BEND RADIUS: 2024-T3 needs 4T (is 3.00, needs 6.40)
```

## Files

| | |
|---|---|
| `sheet_metal.py` | Forming arithmetic, material table, DFM rules. No CAD dependency. |
| `bracket.py` | Parametric formed solid and flat pattern. |
| `drawing.py` | Detail sheet: formed views, flat pattern, bend table, notes. |
| `test_sheet_metal.py` | 29 tests. |
| `exports/` | `bracket-formed.step`, `bracket-flat.step`, `bracket-flat.dxf` |
| `drawings/SMB-001-bracket.png` | The drawing. |

The DXF is the flat profile only — the shape a laser or waterjet cuts.

## Outstanding

- **One bend.** A second fold (a Z or a channel) would exercise multiple
  bend deductions in series, which is where flat-pattern arithmetic
  actually gets error-prone.
- **No bend relief.** Not needed here, because the fold runs the full
  width. A partial-width flange needs relief notches at the ends of the
  bend or it tears at the corners.
- **No forming simulation** — springback is not modelled. Real press work
  overbends to compensate, by an amount that depends on the alloy, and this
  drawing does not tell the shop by how much.
- **Grain direction is a note, not a constraint.** Note 7 asks for bending
  with the grain; the geometry has no concept of it, so nothing enforces it.
- **Static design only.** No FEA — the section is not sized against a load
  case, it is sized to be foldable. A real bracket would be checked for
  stiffness and for bearing at the fastener holes.

---

See: [[01-Hydraulic-Actuator]] | [[02-Gearbox-Family]] | [[04-DFM-Optimizer]]
