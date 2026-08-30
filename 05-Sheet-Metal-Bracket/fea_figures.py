"""Convergence figure for the bracket FEA.

Runs in the base environment against `fea_results.json`:

    python fea_figures.py

Plotted against nodes rather than element size, because the honest question
is what the answer does as the discretisation is refined, and nodes is the
axis on which "refined" is monotone.

Peak stress and tip deflection are drawn on separate panels deliberately.
They converge at very different rates -- displacement is an integral of the
solution and settles quickly, peak stress is a point value taken at the
worst node and settles slowly if at all. Putting them on one axis would
hide exactly the distinction the study exists to make.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from beam_check import (  # noqa: E402
    HOLE_DIAMETER_MM,
    WIDTH_MM,
    bracket_estimate,
    kt_hole_in_plate,
)

# Site tokens, so a figure sits flush on the page it is published to.
THEMES = {
    "light": {"surface": "#f2eee6", "ink": "#221e18", "ink_muted": "#6e6558",
              "grid": "#d9d0c0", "accent": "#b23d0e", "bar": "#8a8378"},
    "dark": {"surface": "#1b1815", "ink": "#f1ece4", "ink_muted": "#8c8377",
             "grid": "#39332b", "accent": "#ff6d3b", "bar": "#6b655c"},
}

# Two quadratic elements through a 1.6 mm wall. Below this a run is drawn
# hollow: it solved, but it cannot represent bending.
TRUSTED_THROUGH_WALL = 2.0


def convergence_figure(data, path, theme="light"):
    """Peak stress and deflection against mesh refinement."""
    t = THEMES[theme]
    runs = sorted((r for r in data["runs"] if "max_von_mises_mpa" in r),
                  key=lambda r: r["nodes"])
    if not runs:
        raise ValueError("no solved runs to plot")

    trusted = [r for r in runs if r["through_wall"] >= TRUSTED_THROUGH_WALL]
    coarse = [r for r in runs if r["through_wall"] < TRUSTED_THROUGH_WALL]
    hand = bracket_estimate()

    fig, (ax_s, ax_d) = plt.subplots(1, 2, figsize=(11, 4.2))
    fig.patch.set_facecolor(t["surface"])

    panels = [
        (ax_s, "max_von_mises_mpa", "Peak von Mises (MPa)",
         "Peak stress", hand.bending_stress_mpa, "nominal beam stress"),
        (ax_d, "max_displacement_mm", "Tip deflection (mm)",
         "Deflection", hand.total_deflection_mm, "hand calculation"),
    ]

    for ax, key, ylabel, title, reference, reference_label in panels:
        ax.set_facecolor(t["surface"])
        ax.plot([r["nodes"] for r in runs], [r[key] for r in runs],
                color=t["accent"], linewidth=1.6, zorder=2,
                label="peak node" if key == "max_von_mises_mpa" else None)

        # The 99th percentile on the same axes is the whole argument: if the
        # peak climbs while this stays flat, the climb is one node's
        # artefact and not the structure getting more highly stressed.
        if key == "max_von_mises_mpa" and all("p99_von_mises_mpa" in r
                                              for r in runs):
            ax.plot([r["nodes"] for r in runs],
                    [r["p99_von_mises_mpa"] for r in runs],
                    color=t["bar"], linewidth=1.6, marker="s", markersize=5,
                    zorder=2, label="99th percentile")
        if trusted:
            ax.scatter([r["nodes"] for r in trusted], [r[key] for r in trusted],
                       color=t["accent"], s=42, zorder=3,
                       label="2+ elements through wall")
        if coarse:
            ax.scatter([r["nodes"] for r in coarse], [r[key] for r in coarse],
                       facecolors="none", edgecolors=t["bar"], s=42, zorder=3,
                       linewidths=1.4, label="under-resolved wall")
        ax.axhline(reference, color=t["ink_muted"], linestyle="--",
                   linewidth=1.2, zorder=1, label=reference_label)

        if key == "max_von_mises_mpa":
            ax.axhline(data["yield_mpa"], color=t["ink"], linestyle=":",
                       linewidth=1.4, zorder=1,
                       label=f"5052-H32 yield ({data['yield_mpa']:.0f} MPa)")
            kt = kt_hole_in_plate(HOLE_DIAMETER_MM, WIDTH_MM)
            ax.axhline(reference * kt, color=t["ink_muted"], linestyle="-.",
                       linewidth=1.0, zorder=1,
                       label=f"nominal x Kt ({kt:.2f})")

        ax.set_xscale("log")
        ax.set_xlabel("Nodes", color=t["ink"])
        ax.set_ylabel(ylabel, color=t["ink"])
        ax.set_title(title, color=t["ink"], loc="left")
        ax.grid(True, color=t["grid"], linewidth=0.7, zorder=0)
        ax.tick_params(colors=t["ink_muted"])
        for spine in ax.spines.values():
            spine.set_color(t["grid"])
        # State the convergence rate rather than making the reader
        # eyeball a line that is nearly flat on an axis set by a reference.
        if len(trusted) >= 2:
            a, b = sorted(trusted, key=lambda r: r["nodes"])[-2:]

            def change(field):
                return (b[field] - a[field]) / a[field] * 100.0

            note = f"last refinement: {change(key):+.2f}%"
            if key == "max_von_mises_mpa" and "p99_von_mises_mpa" in b:
                note = (f"last refinement:  peak {change(key):+.2f}%   "
                        f"p99 {change('p99_von_mises_mpa'):+.2f}%")
            ax.annotate(note, xy=(0.03, 0.06), xycoords="axes fraction",
                        fontsize=8, color=t["ink_muted"])

        ax.legend(fontsize=7.5, facecolor=t["surface"], loc="best",
                  edgecolor=t["grid"], labelcolor=t["ink"])

    fig.suptitle(
        f"Mesh convergence -- {data['equipment_kg']} kg at "
        f"{data['load_factor_g']}g ({data['force_n']:.0f} N)",
        color=t["ink"], x=0.01, ha="left")
    fig.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160, facecolor=t["surface"])
    plt.close(fig)
    return path



def trade_figure(results, path, theme="light"):
    """Margin against mass for each redesign arm.

    Plotted this way because the trade is mass for margin, and the arm that
    matters is the one that moves right without moving up: folding flanges
    up the upright buys seven times the section in the leg that was never
    governing, and the bracket stays exactly as weak as it was.
    """
    t = THEMES[theme]
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    fig.patch.set_facecolor(t["surface"])
    ax.set_facecolor(t["surface"])

    ax.axhspan(-100, 0, color=t["bar"], alpha=0.13, zorder=0)
    ax.axhline(0, color=t["ink"], linestyle=":", linewidth=1.4, zorder=1,
               label="yield")

    # The two failing arms sit at the same margin by construction, which is
    # the point of the figure -- so their labels have to be pulled apart by
    # hand or they land on top of each other.
    offsets = [(11, 8), (11, -18), (11, -4), (11, -4)]
    for r, offset in zip(results, offsets):
        passes = r.margin > 0
        ax.scatter(r.mass_g, r.margin * 100,
                   s=110, zorder=3,
                   color=t["accent"] if passes else "none",
                   edgecolors=t["accent"] if passes else t["ink_muted"],
                   linewidths=1.6)
        ax.annotate(r.arm.label, (r.mass_g, r.margin * 100),
                    textcoords="offset points", xytext=offset,
                    fontsize=8.5, color=t["ink"])

    baseline, flanged = results[0], results[1]
    ax.annotate("", xy=(flanged.mass_g, flanged.margin * 100),
                xytext=(baseline.mass_g, baseline.margin * 100),
                arrowprops=dict(arrowstyle="->", color=t["ink_muted"],
                                linewidth=1.3, linestyle="--"))
    ax.annotate(f"+{(flanged.mass_g/baseline.mass_g-1)*100:.0f}% mass, "
                "identical margin",
                xy=((baseline.mass_g + flanged.mass_g) / 2,
                    baseline.margin * 100),
                textcoords="offset points", xytext=(-52, 16),
                fontsize=8.5, color=t["ink_muted"])

    ax.set_xlabel("Mass (g)", color=t["ink"])
    ax.set_ylabel("Margin of safety (%)", color=t["ink"])
    ax.set_title("Redesign options at 9g", color=t["ink"], loc="left")
    ax.grid(True, color=t["grid"], linewidth=0.7, zorder=0)
    ax.tick_params(colors=t["ink_muted"])
    for spine in ax.spines.values():
        spine.set_color(t["grid"])
    ax.set_xlim(19, 39)
    ax.set_ylim(-42, 118)
    ax.legend(fontsize=8, facecolor=t["surface"], edgecolor=t["grid"],
              labelcolor=t["ink"], loc="upper left")

    fig.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160, facecolor=t["surface"])
    plt.close(fig)
    return path

def main() -> None:
    data = json.loads(Path("fea_results.json").read_text())
    from trade_study import ARMS, evaluate
    baseline = evaluate(ARMS[0])
    results = [baseline] + [evaluate(a, baseline.mass_g) for a in ARMS[1:]]

    for theme in ("light", "dark"):
        suffix = "-dark" if theme == "dark" else ""
        print("wrote", convergence_figure(
            data, f"figures/fea-convergence{suffix}.png", theme))
        print("wrote", trade_figure(
            results, f"figures/redesign-trade{suffix}.png", theme))


if __name__ == "__main__":
    main()
