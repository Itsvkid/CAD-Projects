# Learning path: from generated geometry to CAD you drive yourself

Everything in this repository so far was written, not modelled. That was
the right way to build it — parametric, testable, diffable — but it leaves
one thing unevidenced, and it is the thing a design office screens for
first: **can you actually sit in a CAD package and produce a part?**

These six projects close that. Each is small, each produces a portfolio
deliverable, and — the useful part — **each one has an answer already in
this repository to check your work against.** That is what makes them
exercises rather than tutorials: you can be wrong and find out.

## What is installed

| Tool | State | Notes |
|---|---|---|
| **FreeCAD 1.1.3** | Installed, arm64 native | PartDesign, Sketcher, Assembly, TechDraw, FEM (CalculiX). Enough for all six projects. |
| **SheetMetal workbench** | Installed 2026-08-27 | v0.8.22, at `~/Library/Application Support/FreeCAD/v1-1/Mod/SheetMetal`. Adds unfold / flat pattern. |
| **ParaView 6.1** | Installed | CFD post-processing. |
| **Onshape** | Account needed, nothing to install | Browser-based, renders server-side, so 8 GB RAM is irrelevant. Free plan makes documents public — which for a portfolio is a feature, not a limit. |
| **Autodesk Fusion** | Installed 2026-08-27, **education licence** | At `~/Applications/Autodesk Fusion.app`. The education licence unlocks what personal use does not: full drawings, simulation, and STEP export. It is the primary tool for projects 1–3 and 5. Output is marked educational — check before publishing a drawing. |
| **CATIA / ANSYS / SolidWorks** | Possibly available already | `Omnissa Horizon Client` on this machine is configured for `desktops.apps.cranfield.ac.uk`. Check that catalogue before anything else — it likely serves the exact commercial packages this portfolio cannot otherwise show. |

## The machine, and what it means

MacBook Air M2, 8 GB RAM, 8 cores. Single parts and small assemblies are
comfortable. Large assemblies and any serious FEA are not — the same limit
that pushed project 02 of the analysis portfolio onto SimScale's cloud.
Plan around it: model parts locally, use Onshape or the Cranfield VDI when
a job gets heavy.

---

## 1 · Rebuild the cylinder body from its own drawing

**Tool:** FreeCAD PartDesign, or Onshape
**Input:** `01-Hydraulic-Actuator/drawings/ACT-001-cylinder-body.png`
**Skills:** sketch constraints, revolve or pad, pocket, datum planes

Work from the drawing, not the script. Sketch the profile, revolve it,
pocket the bore from the rod end and the cap cavity from the base.

**Check yourself against the generated solid:**

| | Target |
|---|---|
| Volume | 113 588.21 mm³ |
| Mass (Al 6061-T6, 2.70 g/cm³) | 0.30669 kg |
| Surface area | 59 581.88 mm² |
| Bounding box | 41.00 × 41.00 × 250.00 mm |
| Faces / edges / solids | 7 / 9 / 1 |

FreeCAD gives you all of these under **Edit → Preferences → General →
Units** and the *Measure* workbench; volume and area are in the model's
property panel. If your volume is out by more than a few mm³, you have
mis-read a dimension — find which one before moving on. Matching the face
count matters too: extra faces mean you have modelled a feature the
original does not have.

## 2 · Draw the clevis in TechDraw, with real GD&T

**Tool:** FreeCAD TechDraw
**Input:** `01-Hydraulic-Actuator/drawings/ACT-003-clevis-end.png`
**Skills:** view placement, dimensioning, annotation, feature control frames

You have already *chosen* the datum scheme and the geometric tolerances —
datum A the back face, B the pin bore axis, C the side face; position
⌀0.3 at MMC on the bolt holes. This project is about placing them in a CAD
package's own annotation tools rather than drawing them with matplotlib.

Target: your sheet should carry the same callouts as ACT-003. Volume check
on the solid first: **18 870.08 mm³**, 9 faces, 54 × 8 × 54 mm.

## 3 · Assemble the three parts

**Tool:** FreeCAD Assembly workbench (built in since 1.0)
**Skills:** joints, degrees of freedom, interference checking, exploded views

Rod into bore, clevis onto rod tip. Constrain it properly — coincident
axes, an offset that sets the extension — rather than dragging parts into
place.

**Check:** the pin-bore axis should sit **390.0 mm** above the cylinder's
base face. That is the nominal from the tolerance stack on ACT-100, and it
is what the Python assembly builds. Then run an interference check: it
should report **zero clashes**, which is what `test_tolerances.py` asserts
by boolean intersection.

## 4 · Sheet metal — the one that tests your own maths

**Tool:** FreeCAD SheetMetal workbench
**Input:** `05-Sheet-Metal-Bracket/drawings/SMB-001-bracket.png`
**Skills:** base flange, bend, unfold, K-factor settings

Model the bracket as sheet metal — a base flange 60 × 50 at 1.6 thick, one
90° bend at R3 — then use **Unfold** to get the flat pattern.

**This is the interesting one.** `sheet_metal.py` computes the blank as
**101.52 mm** using a K-factor of 0.40. FreeCAD's unfold has its own
K-factor setting.

- Set K = 0.40 and the two should agree closely. Do they?
- Then try FreeCAD's default and see how far the answer moves.

Either outcome is a genuine result. Agreement validates the Python against
an independent implementation, the same species of check as the XFoil
cross-check on the analysis side. Disagreement means one of you is wrong
and finding out which is the whole exercise. **Write down what you find.**

## 5 · Put a load on it

**Tool:** FreeCAD FEM (CalculiX is bundled)
**Skills:** material assignment, constraints, meshing, reading a result

Fix the bracket at its two base holes, load the upright's holes with a
plausible equipment mass — say 2 kg at 9g, so roughly 180 N — mesh, solve,
look at von Mises stress and displacement.

There is no target to check against here, which is the point: this is the
first project where you produce a number nobody has produced before. So be
sceptical of it. Refine the mesh and see whether the peak stress converges
or keeps climbing — a stress singularity at a sharp corner will climb
forever, and knowing that is most of what FEA literacy is.

Then **change something and re-run.** A design iteration justified by
analysis is the deliverable, not the pretty contour plot.

## 6 · One part in CATIA

**Tool:** CATIA V5 on the Cranfield VDI, if the catalogue has it
**Skills:** the ones your CV already claims

Your CV says *CATIA V5 (Proficient) — 80 hrs*. Rebuild the cylinder body
there and screenshot the spec tree and a drawing. That turns a certificate
into evidence, and it is the single item that most changes how the rest of
this portfolio reads.

---

## Updating the portfolio as you go

Each project produces the same three things:

1. **A screenshot** — the model with its tree visible. The tree is the
   evidence: it shows the part was modelled, feature by feature, not
   imported.
2. **A drawing or a result** — a TechDraw sheet, a flat pattern, a stress
   plot.
3. **A paragraph** — what you did, and what you checked it against.

Drop the image in `public/products/`, add an entry to `products` in
`app/data.js` (see `public/products/README.md` for the field format), and
add a line to the CAD project entry in `projects`.

**One rule, the same one this repository already follows:** say what you
checked it against. "Modelled in FreeCAD" is a claim. "Modelled in
FreeCAD, volume within 0.1% of the generated solid" is evidence.
