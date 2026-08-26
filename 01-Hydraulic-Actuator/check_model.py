#!/usr/bin/env python3
"""Check a hand-modelled part against the generated reference.

Model the part yourself in FreeCAD (or Onshape, or CATIA), export it as
STEP, and run this. It compares the solid you built against the one
`hydraulic_actuator.py` generates and tells you which measurements
disagree -- not just that something is wrong, but which dimension is
likely to have caused it.

    python check_model.py my_cylinder.step
    python check_model.py my_clevis.step --part clevis

STEP rather than .FCStd on purpose. It works with any CAD package rather
than only FreeCAD, and exporting to a neutral format is the habit you want
anyway -- it is how the part leaves your machine and reaches anyone else.

A note on what "correct" means here. Volume agreeing to a few mm3 says the
shape is right. It does not say the *model* is right: a part modelled as
one lumpy pad measures identically to one built from a clean revolve, and
only one of them can be edited afterwards. The face count is a partial
check on that -- extra faces mean features the original does not have --
but the real test is whether you can change the bore diameter and have
everything follow. Nothing automated can check that. Look at your tree.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cadquery as cq

sys.path.insert(0, str(Path(__file__).parent))
from hydraulic_actuator import HydraulicActuator  # noqa: E402

# Reference design point: the B737-class actuator the drawing pack details.
REFERENCE = HydraulicActuator(35, 21, 200)

PARTS = {
    "cylinder": ("CYLINDER BODY", REFERENCE.create_cylinder_body, "ACT-001",
                 2.70, "Aluminium 6061-T6"),
    "rod": ("PISTON ROD", REFERENCE.create_piston_rod, "ACT-002",
            7.85, "Steel 4340"),
    "clevis": ("CLEVIS END", REFERENCE.create_clevis_end, "ACT-003",
               7.85, "Steel 4340"),
}

# How close counts as a match. Volume is held tightest because it is the
# most sensitive to a mis-read dimension; area is looser because a fillet
# or chamfer nobody asked for moves it without moving volume much.
TOLERANCES = {"volume": 0.001, "area": 0.01, "bbox": 0.0005}


def measure(shape) -> dict:
    box = shape.BoundingBox()
    return {
        "volume": shape.Volume(),
        "area": shape.Area(),
        "bbox": (box.xlen, box.ylen, box.zlen),
        "faces": len(shape.Faces()),
        "edges": len(shape.Edges()),
        "solids": len(shape.Solids()),
    }


def diagnose(part_key: str, mine: dict, reference: dict) -> list[str]:
    """Turn a mismatch into something actionable."""
    hints = []
    volume_ratio = mine["volume"] / reference["volume"]

    if abs(volume_ratio - 1) > TOLERANCES["volume"]:
        if volume_ratio > 1:
            hints.append(
                "Your solid has MORE material than the reference. A pocket "
                "or bore is missing, too shallow, or too small.")
        else:
            hints.append(
                "Your solid has LESS material than the reference. A bore is "
                "too deep or too large, or an outside dimension is short.")

    for axis, (m, r) in zip("XYZ", zip(mine["bbox"], reference["bbox"])):
        if abs(m - r) > TOLERANCES["bbox"] * max(r, 1.0):
            hints.append(
                f"Overall {axis} is {m:.3f} against {r:.3f} -- an outside "
                f"dimension is wrong, so fix that before anything internal.")

    if mine["solids"] != reference["solids"]:
        hints.append(
            f"{mine['solids']} solids against {reference['solids']}. Features "
            "that do not touch produce separate lumps; in PartDesign every "
            "feature must build on the previous one.")

    if mine["faces"] != reference["faces"]:
        extra = mine["faces"] - reference["faces"]
        hints.append(
            f"{abs(extra)} {'extra' if extra > 0 else 'missing'} faces "
            f"({mine['faces']} against {reference['faces']}). "
            + ("Fillets, chamfers or split faces the drawing does not ask for."
               if extra > 0 else
               "A feature has not been cut, or two faces have merged."))

    if part_key == "cylinder" and abs(volume_ratio - 1) > TOLERANCES["volume"]:
        hints.append(
            "For this part specifically: the bore is 200 deep from the ROD "
            "end and the cap cavity is 25 deep from the BASE, leaving a 25 "
            "thick web between them. Boring straight through is the usual "
            "mistake and loses about 24,000 mm3.")
    return hints


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("step_file", type=Path, help="your exported STEP file")
    parser.add_argument("--part", default="cylinder", choices=sorted(PARTS),
                        help="which part you modelled (default: cylinder)")
    args = parser.parse_args()

    if not args.step_file.exists():
        print(f"No such file: {args.step_file}", file=sys.stderr)
        return 2

    name, build, drawing, density, material = PARTS[args.part]
    try:
        mine = measure(cq.importers.importStep(str(args.step_file)).val())
    except Exception as exc:                      # noqa: BLE001
        print(f"Could not read {args.step_file} as STEP: {exc}", file=sys.stderr)
        return 2
    reference = measure(build().val())

    print(f"\n  {name}  |  drawing {drawing}  |  {material}")
    print(f"  {args.step_file}")
    print("  " + "-" * 64)
    print(f"  {'':<20}{'YOURS':>15}{'REFERENCE':>15}{'ERROR':>10}")

    passed = True
    rows = [
        ("Volume, mm3", mine["volume"], reference["volume"], "volume"),
        ("Surface area, mm2", mine["area"], reference["area"], "area"),
        ("Mass, kg", mine["volume"] / 1e6 * density,
         reference["volume"] / 1e6 * density, "volume"),
    ]
    for label, m, r, key in rows:
        error = (m - r) / r
        ok = abs(error) <= TOLERANCES[key]
        passed &= ok
        print(f"  {label:<20}{m:>15.2f}{r:>15.2f}{error:>9.3%}  "
              f"{'ok' if ok else 'MISMATCH'}")

    for axis, m, r in zip("XYZ", mine["bbox"], reference["bbox"]):
        ok = abs(m - r) <= TOLERANCES["bbox"] * max(r, 1.0)
        passed &= ok
        print(f"  {'Overall ' + axis:<20}{m:>15.2f}{r:>15.2f}"
              f"{(m - r):>+9.3f}  {'ok' if ok else 'MISMATCH'}")

    for label, key in (("Faces", "faces"), ("Edges", "edges"),
                       ("Solids", "solids")):
        ok = mine[key] == reference[key]
        # Edge count differs harmlessly between kernels, so it is reported
        # but does not fail the check.
        if key != "edges":
            passed &= ok
        status = "ok" if ok else ("note" if key == "edges" else "MISMATCH")
        print(f"  {label:<20}{mine[key]:>15}{reference[key]:>15}{'':>10}  {status}")

    print("  " + "-" * 64)
    if passed:
        print("  MATCH - the geometry agrees with the reference.\n")
        print("  Now look at your own tree, which this cannot check: is it")
        print("  built so that changing the bore diameter updates everything")
        print("  downstream? A part that measures right but cannot be edited")
        print("  is a model of this actuator, not a parametric one.\n")
        return 0

    print("  MISMATCH\n")
    for hint in diagnose(args.part, mine, reference):
        print(f"    - {hint}")
    print()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
