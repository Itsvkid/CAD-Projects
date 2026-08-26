# Project 1 — Rebuild the cylinder body

**Drawing:** `drawings/ACT-001-cylinder-body.png`
**Tool:** FreeCAD 1.1.3, PartDesign workbench
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

## Setting up

1. **Edit → Preferences → General → Units** — Standard (mm/kg/s), decimals 2.
2. **File → New**, then switch to the **PartDesign** workbench.
3. **Create body** (the first toolbar button). Everything goes inside it.

## The approach worth taking: one revolve

A lathe makes this part by spinning it and cutting a profile. Model it the
same way and the whole thing is one sketch and one feature.

4. **Create sketch** → pick the **XZ plane**. You are now drawing a
   half-section: horizontal is radius from the axis, vertical is length.
5. Draw a **closed polyline** tracing the material of that half-section —
   up the outside, in across the top face, down the bore, across the web
   to the axis, and back. Eight segments. Rough is fine; constrain after.
6. **Constrain it.** Horizontal/vertical on every segment first, then a
   coincident constraint tying the profile to the origin, then dimensions
   off the drawing.
   - The sketch is done when the status bar says **"Fully constrained"**
     and the geometry turns green. Not before. A sketch with free
     geometry will move on its own the first time you edit anything near
     it, and you will not notice until the volume is wrong.
7. Close the sketch, then **Revolution**. Axis: the sketch's **vertical
   axis**. Angle 360°.

Note the profile only ever uses radii, while the drawing gives diameters.
Halve them as you go — mixing the two up is the second most common way to
get this wrong, and it produces a part exactly twice the size.

### If you would rather: pad and pockets

Pad a circle to full length, then pocket the bore from the top face to a
depth, then pocket the cavity from the bottom face. Three features instead
of one. It works and it is easier to follow the first time — but it models
the part as a milled block rather than a turned one, and each pocket
depends on a face that moves if you change anything.

## Checking your work

**File → Export**, choose **STEP with colors (*.step)**, then:

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

So test it: **edit your sketch and change the bore from 35 to 50.**

- Does the model rebuild without errors?
- Does the wall thickness stay 3 mm, or did it become whatever was left?
- Do the bore depth and the cap cavity still measure what they should?

If it rebuilds cleanly and everything that should follow does follow, you
have modelled it parametrically. If it breaks, look at *why* — usually a
dimension that should have been driven by another one was typed in
instead. Fix it and change the bore again.

Set it back to 35 before exporting.

## When it works

Screenshot the model **with the tree panel visible** — the tree is the
evidence that it was modelled rather than imported — and save the
`.FCStd` alongside. Both go into the portfolio; see the last section of
`../LEARNING-PATH.md` for where.
