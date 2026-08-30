"""Figures for the DFM checker.

Same split as project 03: pythonocc tessellates and writes STL beside the
kernel that built the solid, `../render.py` draws it where VTK lives. The
findings are written alongside as plain coordinates, so the renderer can
mark exactly where each one was measured without ever recomputing one.

    conda run -n pyocc_env python figures.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from OCC.Extend.DataExchange import read_step_file, write_stl_file  # noqa: E402

from build import PARTS, ROOT  # noqa: E402
from dfm import DFMRules, analyse  # noqa: E402

THEMES = {
    "light": {"surface": "#f2eee6", "ink": "#221e18", "ink_muted": "#6e6558",
              "grid": "#d9d0c0", "accent": "#b23d0e", "pass": "#4f7a4f"},
    "dark": {"surface": "#1b1815", "ink": "#f1ece4", "ink_muted": "#8c8377",
             "grid": "#39332b", "accent": "#ff6d3b", "pass": "#7aa87a"},
}

PROCESSES = ["machined", "formed-tube", "investment-cast", "sand-cast"]


def process_matrix_figure(path, theme="light"):
    """Every part judged under every process.

    What the grid shows is that a part is not "manufacturable" in the
    abstract. It is manufacturable *by a process*, and the same geometry
    moves from clean to unbuildable depending only on which one you name.
    """
    t = THEMES[theme]
    names, grid = [], []
    for label, relative, _ in PARTS:
        step = ROOT / relative
        if not step.exists():
            continue
        shape = read_step_file(str(step))
        names.append(label)
        grid.append([len(analyse(shape, DFMRules.for_process(p)).failures)
                     for p in PROCESSES])

    fig, ax = plt.subplots(figsize=(8.4, 0.62 * len(names) + 2.2), dpi=110)
    fig.patch.set_facecolor(t["surface"])
    ax.set_facecolor(t["surface"])

    for row, counts in enumerate(grid):
        for col, count in enumerate(counts):
            ok = count == 0
            ax.add_patch(plt.Rectangle(
                (col - 0.46, row - 0.42), 0.92, 0.84,
                facecolor=t["pass"] if ok else t["accent"],
                alpha=0.9 if ok else min(0.35 + 0.06 * count, 0.95),
                edgecolor="none"))
            ax.text(col, row, "clean" if ok else f"{count}",
                    ha="center", va="center", fontsize=8.5,
                    color=t["surface"], fontweight="bold")

    ax.set_xticks(range(len(PROCESSES)))
    ax.set_xticklabels([p.replace("-", "\n") for p in PROCESSES], fontsize=8.5)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=8.5)
    ax.set_xlim(-0.6, len(PROCESSES) - 0.4)
    ax.set_ylim(len(names) - 0.5, -0.5)
    ax.tick_params(colors=t["ink_muted"], length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title("Failures per part, judged as each process\n"
                 "the same geometry, four sets of rules",
                 color=t["ink"], fontsize=11, pad=14, linespacing=1.7)

    fig.tight_layout()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=t["surface"])
    plt.close(fig)
    print(f"  {path}")
    return path


def export_housing_scene(directory="exports/scene"):
    """The gearbox housing plus the coordinate of every finding on it."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    step = ROOT / "02-Gearbox-Family/parts/03_housing.step"
    if not step.exists():
        print("  gearbox housing STEP not on disk — regenerate project 02")
        return None

    shape = read_step_file(str(step))
    stl = directory / "gearbox-housing.stl"
    write_stl_file(shape, str(stl), mode="binary",
                   linear_deflection=0.35, angular_deflection=0.3)

    report = analyse(shape, DFMRules.for_process("sand-cast"),
                     part="gearbox housing")
    findings = [{"check": f.check, "severity": f.severity,
                 "measured": f.measured, "limit": f.limit,
                 "location": list(f.location)}
                for f in report.findings if f.location]
    (directory / "gearbox-findings.json").write_text(json.dumps(findings, indent=2))
    print(f"  {stl}  ({stl.stat().st_size / 1024:.0f} KB)")
    print(f"  {directory / 'gearbox-findings.json'}  ({len(findings)} located)")
    return report


def main():
    for theme in ("light", "dark"):
        suffix = "-dark" if theme == "dark" else ""
        process_matrix_figure(f"figures/dfm-matrix{suffix}.png", theme)
    report = export_housing_scene()
    if report:
        print(f"\n  {report.summary()}")


if __name__ == "__main__":
    main()
