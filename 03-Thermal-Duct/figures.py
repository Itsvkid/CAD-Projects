"""Figures for the duct project.

Two outputs, and they run in different places for a reason:

  * **The constraint chart** is matplotlib and runs here, in `pyocc_env`.
  * **The 3D scene** is exported as STL here and rendered by
    `../render.py` in the base environment, which is where VTK lives.
    Tessellation belongs with the kernel that built the solid; rendering
    belongs with the renderer. Splitting them avoids installing VTK twice.

    conda run -n pyocc_env python figures.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from OCC.Extend.DataExchange import write_stl_file  # noqa: E402

from build import BLEED, ROUTE_INITIAL, ROUTE_REVISED, obstructions  # noqa: E402
from duct import RoutedDuct  # noqa: E402
from sizing import required_clearance_mm, size_duct  # noqa: E402

# Site tokens, so a figure sits flush on the page it is published to.
THEMES = {
    "light": {"surface": "#f2eee6", "ink": "#221e18", "ink_muted": "#6e6558",
              "grid": "#d9d0c0", "accent": "#b23d0e", "bar": "#8a8378"},
    "dark": {"surface": "#1b1815", "ink": "#f1ece4", "ink_muted": "#8c8377",
             "grid": "#39332b", "accent": "#ff6d3b", "bar": "#6b655c"},
}


def constraint_figure(design, path, theme="light"):
    """What each constraint demanded of the wall, and which one won.

    A bar chart rather than a table because the point is comparative: the
    reader should see at a glance that the bend bar is the tall one, and
    that pressure — the constraint everyone assumes governs a pressure
    vessel — is the short one.
    """
    t = THEMES[theme]
    labels = ["Hoop stress\nat 12.5 bar", "Minimum\nhandling gauge",
              "Surviving\na 2D bend"]
    values = [design.hoop_required_mm, design.min_gauge_mm,
              design.bend_required_mm]
    governing = values.index(max(values))
    colours = [t["bar"]] * 3
    colours[governing] = t["accent"]

    fig, ax = plt.subplots(figsize=(6.8, 4.3), dpi=110)
    fig.patch.set_facecolor(t["surface"])
    ax.set_facecolor(t["surface"])

    bars = ax.bar(labels, values, color=colours, width=0.55, zorder=3)
    ax.axhline(design.wall_mm, color=t["ink_muted"], linestyle="--",
               linewidth=1.2, zorder=2)
    ax.annotate(f"{design.wall_mm:.2f} mm — next standard gauge",
                xy=(2.42, design.wall_mm), xytext=(2.42, design.wall_mm + 0.03),
                fontsize=7.5, color=t["ink_muted"], ha="right")

    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.012,
                f"{value:.3f}", ha="center", fontsize=8, color=t["ink"])

    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(t["grid"])
    ax.tick_params(colors=t["ink_muted"], labelsize=8)
    ax.set_ylabel("Wall thickness demanded, mm", color=t["ink"])
    ax.set_ylim(0, max(values) * 1.3)
    ax.grid(axis="y", color=t["grid"], linewidth=0.6, alpha=0.7, zorder=0)
    ax.set_axisbelow(True)
    ax.set_title("What actually sets the wall thickness",
                 color=t["ink"], fontsize=11, pad=12)

    fig.tight_layout()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=t["surface"])
    plt.close(fig)
    print(f"  {path}")
    return path


def export_scene(design, directory="exports/scene"):
    """STL for every body in the clearance study, for ../render.py.

    Linear deflection is fine at 0.4 mm here: these are 68 mm tubes and a
    260 mm casing, and the render is a communication tool, not a
    measurement. The clearance numbers come from the B-rep, never from
    this mesh.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    written = {}
    for name, route in (("duct-revised", ROUTE_REVISED),
                        ("duct-initial", ROUTE_INITIAL)):
        path = directory / f"{name}.stl"
        write_stl_file(RoutedDuct(design, route).solid(), str(path),
                       mode="binary", linear_deflection=0.4,
                       angular_deflection=0.3)
        written[name] = path
    for name, shape in obstructions().items():
        path = directory / f"{name.replace(' ', '-')}.stl"
        write_stl_file(shape, str(path), mode="binary",
                       linear_deflection=0.8, angular_deflection=0.4)
        written[name] = path
    for name, path in written.items():
        print(f"  {path}  ({path.stat().st_size / 1024:.0f} KB)")
    return written


def main():
    design = size_duct(BLEED)
    for theme in ("light", "dark"):
        suffix = "-dark" if theme == "dark" else ""
        constraint_figure(design, f"figures/duct-constraints{suffix}.png", theme)
    export_scene(design)

    revised = RoutedDuct(design, ROUTE_REVISED)
    print(f"\n  required clearance "
          f"{required_clearance_mm(design, revised.route_length_mm()):.2f} mm")


if __name__ == "__main__":
    main()
