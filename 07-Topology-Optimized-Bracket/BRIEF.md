# 07 — Topology-Optimized Equipment Bracket

**Status:** brief only. Nothing built yet.

The first project here whose *point* is the year it belongs to. Projects
01–05 sized and verified conventionally manufactured parts — machined,
formed, cast in the ordinary sense. This one takes a part this portfolio
has already built, sized and verified — CAD-05's equipment bracket — and
asks what an additive-constrained optimizer does with the same load case,
then holds the answer to the same standard CAD-05 was held to.

## Why this one, and why now

`Job-Search-2026/.../GT-Design/` and the live market check in
`resume/knowledge/01-target-role.md` (2026-09-04) agree on the same finding
from opposite directions: design-for-additive-manufacturing and topology
optimization are genuinely current in gas turbine design offices — GE holds
patent families on additive-first generative design for turbine parts and
nozzles, and published research extends the method to cooled blades and
engine mounts under AM process constraints — and **nothing in this
portfolio touches it.** Every CAD project so far is conventionally
manufactured. This is the gap, not an assumption about it.

## Why it stays in Python, unlike CAD-06

CAD-06 deliberately left code behind, because that project's whole point is
tool literacy in CATIA or NX. This project's point is the opposite: the
*method*, not the software it runs in. Topology optimization is naturally
a numerical procedure — a compliance minimization over a density field —
and doing it as a script keeps this project inside the portfolio's real
differentiator: the result is diffable, the algorithm can be checked against
a published benchmark before it is trusted on the real part, and the
comparison against CAD-05 is a comparison of numbers, not of screenshots.

## The part, and why this baseline and not a new one

**CAD-05's bracket, under the identical 9g equipment crash load, same
boundary conditions, same design envelope.** Not a new part, on purpose:
CAD-05 already has a converged, verified, independently cross-checked
answer — 2.0 mm gauge, 126.1 MPa peak, 193 MPa yield, +53% margin — and that
answer is the control this experiment needs. A topology-optimized result
with nothing conventional to compare it to is a picture. One with a
same-load, same-constraint conventional baseline sitting next to it is a
result.

## Scope, in three stages

Each stage produces something checkable. Do not start the next until the
current one has a number that closes.

### Stage 1 — Reproduce the method on a known benchmark

Implement SIMP (Solid Isotropic Material with Penalization) compliance
minimization from the published algorithm — Bendsøe & Sigmund, or the
88-line Python/MATLAB reference implementation (Andreassen et al. 2011) —
and run it on the standard MBB-beam benchmark before touching the real part.

*Checks that close this stage:* converged compliance value against the
published benchmark result, to a stated tolerance; visually correct
topology (the MBB beam's arch is a known shape — if the optimizer does not
find it, the implementation is wrong, not the physics).

### Stage 2 — Optimize the bracket's load case

Set up CAD-05's exact design domain, material (2024-T3 or 5052-H32 — state
which and why), boundary conditions and the 9g load case as the topology
optimization problem, with a volume-fraction constraint chosen to target a
mass saving against the 2.0 mm baseline. Extract a manufacturable solid from
the resulting density field — this step is where most student topology
optimization work stops, and stopping here is the failure mode this project
exists to avoid.

Apply named, sourced additive-manufacturing design rules to the extracted
geometry, not assumed ones: minimum wall thickness for the target
powder-bed-fusion process (typically ~0.4–1.0 mm depending on the alloy and
machine), self-supporting overhang angle (~45° from vertical is the common
figure; state the source and the process it is quoted for), and minimum
feature size relative to laser spot size.

*Checks that close this stage:* volume fraction achieved against the target;
every named DfAM rule checked against the extracted geometry with a
pass/fail, not asserted; mass of the extracted, cleaned-up solid, read from
the model.

### Stage 3 — Verification (the part that makes it a portfolio piece, not a render)

Everything above is optimization. This is the design engineering, and it
follows CAD-05's own pattern exactly.

- **Mesh the extracted geometry in CalculiX and run the identical 9g load
  case** CAD-05 ran, with the same mesh-convergence discipline: multiple
  densities, watch for a peak that never settles.
- **Expect a specific, named failure mode before you find it:** raw
  density-field boundaries are jagged by construction, and the sharp
  reentrant corners left by a naive extraction are geometric stress
  concentrations that are not a property of the optimized shape — they are
  an artefact of not smoothing it. If the peak stress in the optimized part
  climbs with mesh refinement the way CAD-05's fixed-constraint singularity
  did, that is very likely this, and the fix is smoothing the boundary
  before re-meshing, not accepting the raw number.
- **Report the comparison as a table, not a claim:** mass, peak stress, and
  margin against yield, optimized versus CAD-05's 2.0 mm baseline, both
  converged the same way. If the optimizer's saving survives convergence,
  say by how much. If it does not — if the real margin is worse than
  CAD-05's once both are checked to the same standard — **that is the
  correct result to publish**, not a reason to keep tuning until it looks
  better.
- **Cross-check the converged mass saving against a hand estimate** of where
  material was removed (which regions carry the least load path in the
  original bracket), the same role CAD-05's independent beam-theory check
  played.

*The deliverable is the disagreement, if there is one* — CAD-05's was "the
peak stress is a boundary condition, the part fails marginally"; this
project's, on current evidence from adjacent literature, is likely to be
"the raw optimized shape's stress riser is not real, and the smoothed shape
saves less mass than the naive density plot implied."

## What would make this weak

- **A pretty organic shape with no mass number and no recomputed margin.**
  This is the single most common failure mode in student topology
  optimization work, and it is exactly the "activity, not outcome" pattern
  every other project in this portfolio was written to avoid.
- **Claiming the part is 3D-printable without checking a named process's
  actual wall-thickness and overhang limits against the extracted geometry.**
  "Optimized for additive manufacturing" with no DfAM check behind it is a
  slogan.
- **Skipping the reverse mesh-convergence check on the new shape.** This is
  the one failure this portfolio has already demonstrated it knows how to
  catch (CAD-05's constraint singularity); repeating that discipline here is
  the whole point of choosing this baseline.
- **Comparing an unconverged optimized result against CAD-05's converged
  one.** Both sides of the comparison must be held to the same standard or
  the comparison is meaningless.

## Prerequisite

None external — unlike CAD-06, this does not wait on tool access. Every
piece (CadQuery/pyOCC for the design domain, a Python SIMP implementation,
CalculiX via FreeCAD for verification) is already in this portfolio's
toolchain. It can start whenever CAD-06 or other priorities allow.

## Reading, before and during

| Stage | Read |
|---|---|
| Before | Bendsøe & Sigmund, *Topology Optimization: Theory, Methods and Applications* — the SIMP formulation and its assumptions |
| Stage 1 | Andreassen et al., *Efficient topology optimization in MATLAB using 88 lines of code* (2011) — the reference implementation to reproduce and port |
| Stage 2 | ISO/ASTM 52911 (design for powder bed fusion) or the equivalent process guide for the target machine/alloy — for the overhang and wall-thickness figures, cited rather than assumed |
| Stage 2 | `Job-Search-2026/.../GT-Design/06-Manufacturing-DFM/` — the same DFM habit CAD-04's checker already encodes, one manufacturing route over |
| Stage 3 | `CAD-Projects/05-Sheet-Metal-Bracket/` itself — re-read the mesh-convergence writeup before starting, since this project's Stage 3 is that stage run again on different geometry |

---

See: [[05-Sheet-Metal-Bracket]] for the baseline and the verification pattern
this follows · `resume/knowledge/01-target-role.md` (2026-09-04) for why this
project was prioritised over other candidates.
