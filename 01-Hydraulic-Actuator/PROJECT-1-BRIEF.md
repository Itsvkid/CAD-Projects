# Project 1 — Rebuild the cylinder body

**Drawing:** `drawings/ACT-001-cylinder-body.png`
**Tool:** Autodesk Fusion (education licence) — or FreeCAD, both below
**Time:** an hour the first time, ten minutes the third

Work from the drawing. Do not read `hydraulic_actuator.py` — reading
dimensions off a sheet is half the skill, and the script gives the answer
away.

## What you are building

A turned aluminium cylinder body. From the section on ACT-001: a plain
outside diameter, a bore that goes **part way** in from the rod end, and a
smaller cavity from the base end, with solid material left between them.
That web is the whole reason this part is more interesting than a tube —
and it is where the mistake usually happens.

## Which tool

**Use Fusion.** The education licence unlocks the things the free
personal licence does not — full drawings, simulation, and crucially
**STEP export**, which personal use disables and which the checker below
needs. It is also the name a design office recognises.

Keep FreeCAD for working offline, and for project 4, where having two
independent unfold implementations to compare against your own arithmetic
is worth more than having one.

*One thing to know: Autodesk education licences mark their output as
educational. Check an exported drawing for a stamp before publishing it.
For a student portfolio that is honest and fine — just know it is there.*

## The approach worth taking: one revolve

A lathe makes this part by spinning it and cutting a profile. Model it the
same way and the whole thing is one sketch and one feature.

Note throughout: the profile uses **radii**, the drawing gives
**diameters**. Halve as you go. Mixing them up is the second most common
way to get this wrong and produces a part exactly twice the size.

### In Fusion

1. **New Design**. Check units are mm — browser → *Document Settings* →
   *Units*.
2. **Create → Create Sketch** (`S`), pick the **Front** plane. You are now
   drawing a half-section: horizontal is radius from the axis, vertical is
   length.
3. **Line** (`L`). Trace the material of that half-section as a closed
   loop — up the outside, in across the top face, down the bore, across
   the web to the axis, back down and out. Eight segments. Rough is fine;
   dimension after.
4. **Sketch Dimension** (`D`) for each dimension off the drawing, plus
   coincident constraints tying the profile to the origin.
   - The sketch is done when the palette says **"Fully Constrained"** and
     the geometry goes black. Not before. Under-constrained geometry moves
     on its own the first time you edit near it, and you will not notice
     until the volume is wrong.
5. **Finish Sketch**, then **Create → Revolve** (`R`). Profile: the closed
   region. Axis: expand *Origin* in the browser and pick the **Z axis**.
   Angle 360°.

### In FreeCAD

1. **Edit → Preferences → General → Units** — Standard (mm/kg/s).
2. **File → New**, **PartDesign** workbench, **Create body**.
3. **Create sketch** → **XZ plane**, same profile as above.
4. Constrain horizontal/vertical first, then coincident to origin, then
   dimensions. Fully constrained shows in the status bar and turns the
   geometry green.
5. Close the sketch → **Revolution**, axis = the sketch's vertical axis,
   360°.

### If you would rather: pad and pockets

Extrude a circle to full length, then cut the bore from the top face to a
depth and the cavity from the bottom face. Three features instead of one.
Easier to follow the first time — but it models the part as a milled block
rather than a turned one, and each cut depends on a face that moves if you
change anything.

## Checking your work

**Fusion:** *File → Export*, type **STEP**, save to a local folder (not
just the cloud hub).
**FreeCAD:** *File → Export*, **STEP with colors (\*.step)**.

Then:

```bash
cd CAD-Projects/01-Hydraulic-Actuator
python check_model.py ~/Desktop/my_cylinder.step
```

It compares volume, area, mass, bounding box and face count against the
generated solid, and if something disagrees it tells you what kind of
mistake produces that signature. Targets, so you know what you are aiming
at:

| | |
|---|---|
| Volume | 113 588.21 mm³ |
| Mass (Al 6061-T6) | 0.30669 kg |
| Bounding box | 41.00 × 41.00 × 250.00 |
| Faces / solids | 7 / 1 |

**A volume 21% low means you bored straight through.** That is the web,
and it is worth about 24 000 mm³.

## Then the part the checker cannot do

Geometry agreeing does not mean the model is good. A part built as one
lumpy pad measures identically to a clean revolve, and only one of them
survives contact with a change request.

So test it: **edit your sketch and change the bore from 35 to 50.** In
Fusion, double-click the sketch in the timeline at the bottom; in FreeCAD,
double-click it in the tree.

- Does the model rebuild without errors?
- Does the wall thickness stay 3 mm, or did it become whatever was left?
- Do the bore depth and the cap cavity still measure what they should?

If it rebuilds cleanly and everything that should follow does follow, you
have modelled it parametrically. If it breaks, look at *why* — usually a
dimension that should have been driven by another one was typed in
instead. Fix it and change the bore again.

Set it back to 35 before exporting.

## When it works

Screenshot the model **with the browser and timeline visible** (in
FreeCAD, the tree panel) — that is the evidence it was modelled rather
than imported — and save the native file alongside. Both go into the portfolio; see the last section of
`../LEARNING-PATH.md` for where.
