# 06 — HP Turbine Blade

**Status:** brief only. Nothing built yet.

The first project here whose *point* is the tool it is built in. Every other
CAD project in this repository was written in CadQuery or pyOCC because code
is reproducible and diffable, and that argument still holds. It does not
hold for this one, and the reason is worth stating plainly rather than
hidden in a commit message.

## Why this one is not written in Python

Projects 01–05 chose code over a GUI deliberately, and the READMEs say so:
geometry clicked into existence is not reviewable in a diff. That reasoning
is about *verification*.

This project is about *employability*, and the constraint is different. Gas
turbine design offices screen on CATIA V5 or Siemens NX, and a portfolio of
CadQuery cannot answer "have you modelled in the tool we use". So this one
gets built by hand, in whichever of the two the target employers name —
**check the job ads before choosing; for gas turbine OEMs that is more often
NX with Teamcenter than CATIA.** See
`Job-Search-2026/.../GT-Design/00-Start-Here.md`.

What carries across is the habit, not the language: **every dimension gets a
number to check against, and the model is interrogated rather than
admired.** That is what projects 01–05 actually demonstrate, and it does not
depend on Python.

## The part

A single high-pressure turbine rotor blade — aerofoil, platform, shank, and
fir-tree root — sized for a representative HP stage. Not a copy of a real
engine part (those geometries are proprietary and mostly export-controlled),
but a plausible one built from published aerofoil definitions and open
correlations.

The blade is the canonical gas turbine design artefact. It is where
aerodynamics, stress, heat transfer, materials and manufacturing all
collide, and every one of those disciplines constrains its shape.

## Scope, in three stages

Each stage produces something checkable. Do not start the next until the
current one has a number that closes.

### Stage 1 — Aerofoil and stacking (surface modelling)

Build the aerofoil as a **surface-driven** model: sections at several radii,
lofted, not an extruded 2D profile. This is the part that distinguishes
someone who knows CATIA GSD or NX Shape Studio from someone who knows
extrude-and-fillet, and it is the single most transferable skill in the
project.

- Sections from a published definition, or generated from a
  camber-line-plus-thickness construction (the same maths as
  `projects/01-airfoil-analysis/src/geometry.py`, one dimension up).
- Radial stacking about the centre of area, so the centrifugal load runs
  through the section centroids and does not induce a bending moment at
  the root. **Stacking about the leading edge instead is a classic error
  and produces a blade that bends itself apart.**
- Twist from hub to tip, following the free-vortex condition
  (`r · c_θ = constant`), so the incidence is right along the span.

*Checks that close this stage:* section area against the value used in the
stress calculation; blade mass and centre of gravity read from the model;
throat area between adjacent blades against the value the stage mass flow
requires.

### Stage 2 — Root, platform and shank (solid modelling and interfaces)

- Fir-tree root, sized so the bearing stress on each flank and the tensile
  stress in each neck is within allowable. **This is where centrifugal load
  leaves the blade and enters the disc, and it is the interface a real
  design engineer owns.**
- Platform, with the gas path surface on top and the disc cavity below.
- Shank between them, carrying the load and providing space for the cooling
  feed.

*Checks:* neck tensile stress and flank bearing stress by hand, against the
centrifugal load Stage 1's mass gives; root contact area; and that the
platform tessellates around the disc without overlap at the given blade
count.

### Stage 3 — Verification (the part that makes it a portfolio piece)

Everything above is modelling. This is the design engineering.

- **Centrifugal root stress by hand first.** For a blade of roughly constant
  section, `σ_root ≈ ρ·ω²·(r_tip² − r_hub²)/2`, which is independent of
  section area — a fact worth internalising, because it means a heavier
  blade is not a more highly stressed one. Taper reduces it.
- **Then FEA**, and interrogate it exactly as CAD-05's bracket was
  interrogated: mesh convergence, and scepticism about any peak sitting on
  a constraint or a sharp corner. **You already know that a peak stress that
  climbs with refinement is a singularity, not a stress.** That lesson
  transfers directly, and most graduates have never met it.
- **Creep check**, since an HP blade is creep-limited, not yield-limited.
  A Larson–Miller parameter for the alloy at the operating metal
  temperature, against the root stress and a target life.
- **Campbell diagram**, first few blade modes against engine-order
  excitation across the running range, to show no resonance crossing sits in
  the operating band.

*The deliverable is the disagreement, if there is one.* CAD-05's value was
not "the bracket is fine", it was "the peak stress is a boundary condition
and the part fails marginally". Expect the same shape of result here.

## What would make this weak

Worth writing down now, so it is not discovered at the end.

- **A pretty render and no numbers.** The whole portfolio's differentiator
  is verification. A blade with a nice contour plot and no hand calculation
  behind it is worth less than the bracket.
- **Claiming a real engine's geometry.** Use published or self-generated
  aerofoil definitions and say which.
- **Ignoring manufacture.** A blade that cannot be cast is not a design.
  Minimum wall thickness around cooling passages, ceramic core support, and
  the fact that core shift is the dominant wall-thickness error all
  constrain the shape. See `GT-Design/06-Manufacturing-DFM/`.
- **Skipping the creep check.** Sizing an HP blade against yield is the
  single clearest signal that someone has not worked in this field.

## Prerequisite

**Access to CATIA or NX.** Until the Cranfield VDI catalogue question is
settled, this project cannot start, and that makes settling it the highest-
priority action in the whole learning plan.

Do project 1 (rebuild the hydraulic cylinder body by hand, target
**113,588.21 mm³**, 7 faces, 1 solid) first in the same tool. It is the same
skill at a tenth of the scope, and it has a number that closes.

## Reading, before and during

Ordered by when it becomes useful. Full list with links in
`GT-Design/Resources/`.

| Stage | Read |
|---|---|
| Before | Glassman, *Turbine Design and Application* (NASA SP-290, all three volumes, public domain) — chapters on blade aerodynamic design and stacking |
| Stage 1 | `GT-Design/01-Turbomachinery-Aero/` — velocity triangles, degree of reaction, free-vortex twist |
| Stage 2 | `GT-Design/02-Mechanical-Integrity/` — centrifugal load paths, fir-tree sizing |
| Stage 3 | `GT-Design/02-Mechanical-Integrity/` (creep, Larson–Miller) and `GT-Design/08-Vibration-Rotordynamics/` (Campbell) |
| Throughout | `GT-Design/03-Materials/` — why it is a Ni superalloy and what that buys |

---

See: [[05-Sheet-Metal-Bracket]] for the verification pattern this follows ·
`GT-Design/00-Start-Here.md` for where this sits in the wider plan.
