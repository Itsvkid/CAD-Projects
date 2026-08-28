"""Run the DFM checks across every part in this repository.

    conda run -n pyocc_env python build.py

Parts are read from STEP, not from the scripts that generated them. That is
the point: the checker gets the same thing a supplier would get.
"""

from __future__ import annotations

from pathlib import Path

from OCC.Extend.DataExchange import read_step_file

from dfm import DFMRules, analyse

ROOT = Path(__file__).resolve().parent.parent

# Each part with the process it is actually made by. Getting this right
# matters more than any individual limit -- casting rules on a turned part
# flag every bore for having no draft, which is true of a mould and
# meaningless on a lathe.
PARTS = [
    ("actuator cylinder body", "01-Hydraulic-Actuator/parts/01_cylinder_body.step",
     "machined"),
    ("actuator piston rod", "01-Hydraulic-Actuator/parts/02_piston_rod.step",
     "machined"),
    ("actuator clevis end", "01-Hydraulic-Actuator/parts/03_clevis_end.step",
     "machined"),
    ("gearbox housing", "02-Gearbox-Family/parts/03_housing.step", "sand-cast"),
    ("bleed duct", "03-Thermal-Duct/exports/bleed-duct.step", "formed-tube"),
    ("sheet-metal bracket", "05-Sheet-Metal-Bracket/exports/bracket-formed.step",
     "machined"),
]


def main() -> None:
    print("DFM SURVEY — every part in this repository")
    print("=" * 72)
    reports = []
    for name, relative, process in PARTS:
        path = ROOT / relative
        if not path.exists():
            print(f"  {name:24s} no STEP on disk — regenerate to check")
            continue
        report = analyse(read_step_file(str(path)),
                         DFMRules.for_process(process), part=name)
        reports.append(report)
        wall = (f"{report.thinnest_wall_mm:5.2f}"
                if report.thinnest_wall_mm else "  -  ")
        print(f"\n  {name}  [{process}]")
        print(f"    {'PASS' if report.passed else 'FAIL'}   "
              f"thinnest wall {wall} mm   {report.face_count} faces")
        for finding in report.findings:
            print(f"      {finding}")
        if report.passed and not report.findings:
            print("      nothing to raise")

    print("\n" + "=" * 72)
    failed = [r for r in reports if not r.passed]
    print(f"  {len(reports)} parts checked, {len(failed)} with failures")
    for report in failed:
        print(f"    {report.part}: {len(report.failures)} failure(s)")


if __name__ == "__main__":
    main()
