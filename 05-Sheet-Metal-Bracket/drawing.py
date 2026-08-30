"""Detail drawing for the formed bracket: views, flat pattern, bend table.

A sheet-metal drawing has to say two things a machined-part drawing never
does. First, what the blank looks like before forming -- the flat pattern,
with its bend lines marked, because that is the shape the shop cuts.
Second, a bend table: how far each fold goes, which way, around what
radius, and how much material it consumes. Between them they let a shop
produce the part without re-deriving anything.

Same visual language as the actuator pack in 01-Hydraulic-Actuator: A4
landscape, millimetres, third-angle projection, arrowhead dimensions, a
title block. Reimplemented rather than imported -- each project here stays
self-contained.

    python drawing.py     # drawings/SMB-001-bracket.png
"""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, Polygon, Rectangle  # noqa: E402

from bracket import AngleBracket  # noqa: E402

SHEET_W, SHEET_H = 297.0, 210.0
MARGIN = 10.0
TITLE_W, TITLE_H = 108.0, 40.0

INK = "#111111"
DIM_COLOR = "#333333"
PART_FILL = "#e8e4dc"
BEND_COLOR = "#b23d0e"
THIN, MEDIUM, THICK = 0.5, 0.9, 1.4
HEAD_L, HEAD_W = 2.2, 0.7

DRAWN_BY = "V. Venkateshkumar"


def _sheet():
    fig, ax = plt.subplots(figsize=(SHEET_W / 25.4, SHEET_H / 25.4), dpi=200)
    fig.subplots_adjust(0, 0, 1, 1)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.set_xlim(0, SHEET_W)
    ax.set_ylim(0, SHEET_H)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.add_patch(Rectangle((MARGIN, MARGIN), SHEET_W - 2 * MARGIN,
                           SHEET_H - 2 * MARGIN, fill=False, edgecolor=INK,
                           lw=THICK))
    ax.text(MARGIN + 4, SHEET_H - MARGIN - 5.5,
            "THIRD ANGLE PROJECTION   ·   ALL DIMENSIONS IN MILLIMETRES   ·   "
            "DIMENSIONS ARE TO THE OUTSIDE OF FORM",
            fontsize=5.6, color=DIM_COLOR)
    return fig, ax


def _head(ax, tip, ux, uy):
    bx, by = tip[0] - ux * HEAD_L, tip[1] - uy * HEAD_L
    px, py = -uy * HEAD_W / 2.0, ux * HEAD_W / 2.0
    ax.add_patch(Polygon([tip, (bx + px, by + py), (bx - px, by - py)],
                         closed=True, facecolor=DIM_COLOR, edgecolor="none",
                         zorder=6))


def _dim(ax, p1, p2, dim_pos, text, vertical=False, text_side=1):
    gap, over = 1.0, 1.8
    if vertical:
        x = dim_pos
        for p in (p1, p2):
            d = 1.0 if x > p[0] else -1.0
            ax.plot([p[0] + d * gap, x + d * over], [p[1], p[1]],
                    color=DIM_COLOR, lw=THIN, zorder=4)
        lo, hi = sorted((p1[1], p2[1]))
        ax.plot([x, x], [lo, hi], color=DIM_COLOR, lw=THIN, zorder=4)
        _head(ax, (x, lo), 0.0, -1.0)
        _head(ax, (x, hi), 0.0, 1.0)
        ax.text(x + text_side * 1.6, (lo + hi) / 2.0, text, rotation=90,
                ha="center", va="center", fontsize=6.0, color=INK, zorder=7)
    else:
        y = dim_pos
        for p in (p1, p2):
            d = 1.0 if y > p[1] else -1.0
            ax.plot([p[0], p[0]], [p[1] + d * gap, y + d * over],
                    color=DIM_COLOR, lw=THIN, zorder=4)
        lo, hi = sorted((p1[0], p2[0]))
        ax.plot([lo, hi], [y, y], color=DIM_COLOR, lw=THIN, zorder=4)
        _head(ax, (lo, y), -1.0, 0.0)
        _head(ax, (hi, y), 1.0, 0.0)
        ax.text((lo + hi) / 2.0, y + text_side * 1.4, text, ha="center",
                va="bottom" if text_side > 0 else "top", fontsize=6.0,
                color=INK, zorder=7)


def _centreline(ax, p1, p2, color=DIM_COLOR):
    ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=color, lw=THIN,
            linestyle=(0, (7, 2, 1.5, 2)), zorder=5)


def _leader(ax, target, text_xy, text, fontsize=5.8):
    ax.annotate(text, xy=target, xytext=text_xy, fontsize=fontsize, color=INK,
                zorder=9, va="center",
                arrowprops=dict(arrowstyle="-", color=DIM_COLOR, lw=THIN,
                                shrinkA=0, shrinkB=1))
    ax.plot([target[0]], [target[1]], marker="o", markersize=1.6,
            color=DIM_COLOR, zorder=9)


def _formed_outline(bracket, scale):
    """The folded section, as a closed polygon in sheet coordinates.

    Both fillets are real: the inside of the fold is the specified radius,
    the outside is that plus one thickness, because a fold makes the two
    surfaces concentric. Drawing the corner square would misrepresent the
    only part of the geometry this drawing exists to control.
    """
    a, b = bracket.base_length, bracket.upright_length
    t, r = bracket.thickness, bracket.inside_radius
    ro = r + t
    steps = 24

    points = [(a, 0.0), (ro, 0.0)]
    centre = (ro, ro)
    for i in range(steps + 1):                       # outer fillet
        angle = math.radians(270 - 90 * i / steps)
        points.append((centre[0] + ro * math.cos(angle),
                       centre[1] + ro * math.sin(angle)))
    points += [(0.0, b), (t, b), (t, t + r)]
    centre = (t + r, t + r)
    for i in range(steps + 1):                       # inner fillet
        angle = math.radians(180 + 90 * i / steps)
        points.append((centre[0] + r * math.cos(angle),
                       centre[1] + r * math.sin(angle)))
    points += [(a, t)]
    return [(x * scale, y * scale) for x, y in points]


def bracket_drawing(bracket, path=None, scale_denominator=1, date=None,
                    drawing_number="SMB-001"):
    """One sheet: formed elevation and plan, flat pattern, bend table.

    `drawing_number` is a parameter because changing gauge is a drawing
    re-issue, not a quiet edit: 2.0 mm sheet has a different bend
    deduction, so the blank changes length (101.52 -> 100.97 mm) and the
    developed hole positions move with it. A shop cutting to the old
    sheet would make the wrong blank.
    """
    s = 1.0 / scale_denominator
    a, b = bracket.base_length, bracket.upright_length
    t, w = bracket.thickness, bracket.width
    d = bracket.hole_diameter

    fig, ax = _sheet()

    # ── Formed part, side elevation ────────────────────────────────────
    ex, ey = 30.0, 134.0
    outline = [(ex + px, ey + py) for px, py in _formed_outline(bracket, s)]
    ax.add_patch(Polygon(outline, closed=True, facecolor=PART_FILL,
                         edgecolor=INK, lw=MEDIUM, zorder=4))
    ax.text(ex + a * s / 2, ey + b * s + 8, "FORMED — SIDE",
            fontsize=6.2, fontweight="bold", ha="center", color=INK)

    _dim(ax, (ex, ey), (ex + a * s, ey), ey - 10, f"{a:g}", text_side=-1)
    _dim(ax, (ex, ey), (ex, ey + b * s), ex - 12, f"{b:g}", vertical=True,
         text_side=-1)
    _leader(ax, (ex + (t + bracket.inside_radius) * s * 0.4,
                 ey + (t + bracket.inside_radius) * s * 0.4),
            (ex + 26, ey + 30),
            f"R{bracket.inside_radius:g} INSIDE\nR{bracket.inside_radius + t:g} OUTSIDE\n"
            f"90° BEND UP")
    _leader(ax, (ex + a * s, ey + t * s / 2), (ex + a * s + 14, ey - 4),
            f"t {t:g}")

    # ── Formed part, plan (third angle: below the elevation) ───────────
    px0, py0 = ex, 85.0
    ax.add_patch(Rectangle((px0, py0 - w * s / 2), a * s, w * s,
                           facecolor=PART_FILL, edgecolor=INK, lw=MEDIUM,
                           zorder=4))
    # Bend tangent lines, shown on the plan where the fold crosses it.
    for offset in (t, t + bracket.inside_radius):
        ax.plot([px0 + offset * s] * 2,
                [py0 - w * s / 2, py0 + w * s / 2], color=BEND_COLOR,
                lw=THIN, linestyle=(0, (4, 2)), zorder=6)
    for sign in (1, -1):
        centre = (px0 + (a - bracket.hole_setback) * s,
                  py0 + sign * bracket.hole_pitch / 2 * s)
        ax.add_patch(Circle(centre, d / 2 * s, facecolor="white",
                            edgecolor=INK, lw=MEDIUM, zorder=5))
        _centreline(ax, (centre[0] - 5, centre[1]), (centre[0] + 5, centre[1]))
        _centreline(ax, (centre[0], centre[1] - 5), (centre[0], centre[1] + 5))
    ax.text(px0 + a * s / 2, py0 + w * s / 2 + 8, "FORMED — PLAN",
            fontsize=6.2, fontweight="bold", ha="center", color=INK)

    _dim(ax, (px0, py0 - w * s / 2), (px0, py0 + w * s / 2), px0 - 12,
         f"{w:g}", vertical=True, text_side=-1)
    _dim(ax, (px0 + (a - bracket.hole_setback) * s, py0 - bracket.hole_pitch / 2 * s),
         (px0 + (a - bracket.hole_setback) * s, py0 + bracket.hole_pitch / 2 * s),
         px0 + a * s + 10, f"{bracket.hole_pitch:g}", vertical=True)
    _dim(ax, (px0 + (a - bracket.hole_setback) * s, py0 - w * s / 2),
         (px0 + a * s, py0 - w * s / 2), py0 - w * s / 2 - 9,
         f"{bracket.hole_setback:g}", text_side=-1)

    # ── Flat pattern ───────────────────────────────────────────────────
    fx, fy = 150.0, 160.0
    flat = bracket.flat_length
    ax.add_patch(Rectangle((fx, fy - w * s / 2), flat * s, w * s,
                           facecolor="white", edgecolor=INK, lw=MEDIUM,
                           zorder=4))
    start, end = bracket.bend_zone
    ax.add_patch(Rectangle((fx + start * s, fy - w * s / 2),
                           (end - start) * s, w * s, facecolor=BEND_COLOR,
                           alpha=0.13, edgecolor="none", zorder=5))
    for edge in (start, end):
        ax.plot([fx + edge * s] * 2, [fy - w * s / 2, fy + w * s / 2],
                color=BEND_COLOR, lw=THIN, linestyle=(0, (4, 2)), zorder=6)
    _centreline(ax, (fx + bracket.bend_line * s, fy - w * s / 2 - 4),
                (fx + bracket.bend_line * s, fy + w * s / 2 + 4), BEND_COLOR)

    for x_pos in (a - bracket.hole_setback, flat - bracket.hole_setback):
        for sign in (1, -1):
            centre = (fx + x_pos * s, fy + sign * bracket.hole_pitch / 2 * s)
            ax.add_patch(Circle(centre, d / 2 * s, facecolor="white",
                                edgecolor=INK, lw=MEDIUM, zorder=6))
    ax.text(fx + flat * s / 2, fy + w * s / 2 + 8, "FLAT PATTERN — AS CUT",
            fontsize=6.2, fontweight="bold", ha="center", color=INK)
    ax.text(fx + bracket.bend_line * s, fy + w * s / 2 + 2.5, "BL1",
            fontsize=5.6, ha="center", color=BEND_COLOR, fontweight="bold")

    _dim(ax, (fx, fy - w * s / 2), (fx + bracket.bend_line * s, fy - w * s / 2),
         fy - w * s / 2 - 10, f"{bracket.bend_line:.2f} TO BL1", text_side=-1)
    _dim(ax, (fx, fy - w * s / 2), (fx + flat * s, fy - w * s / 2),
         fy - w * s / 2 - 20, f"{flat:.2f}", text_side=-1)

    # ── Bend table ─────────────────────────────────────────────────────
    tx, ty = 150.0, 104.0
    ax.text(tx, ty, "BEND TABLE", fontsize=6.6, fontweight="bold", color=INK)
    header = f"{'ID':<5}{'ANGLE':>7}{'DIR':>6}{'R IN':>7}{'ALLOW':>8}{'DEDUCT':>8}"
    ax.text(tx, ty - 5.5, header, fontsize=5.4, family="monospace", color=INK)
    ax.text(tx, ty - 10.2,
            f"{'BL1':<5}{bracket.BEND_ANGLE_DEG:>6.0f}°{'UP':>6}"
            f"{bracket.inside_radius:>7.1f}{bracket.bend_allowance:>8.3f}"
            f"{bracket.bend_deduction:>8.3f}",
            fontsize=5.4, family="monospace", color=INK)
    k = (bracket.bend_allowance / math.radians(bracket.BEND_ANGLE_DEG)
         - bracket.inside_radius) / t
    ax.text(tx, ty - 16.5,
            f"FLAT = {a:g} + {b:g} − {bracket.bend_deduction:.3f} = {flat:.2f}",
            fontsize=5.4, family="monospace", color=INK)
    ax.text(tx, ty - 21.2,
            f"K = {k:.2f}  (R/T = {bracket.inside_radius / t:.2f}),  "
            f"BA = θ·(R + K·T)",
            fontsize=5.4, family="monospace", color=INK)

    # ── Notes ──────────────────────────────────────────────────────────
    nx, ny = MARGIN + 6, 50.0
    material = bracket.material
    notes = [
        f"1. MATERIAL: {material.name} SHEET, {t:g} THK.",
        f"2. MINIMUM BEND RADIUS {material.min_bend_radius_factor:g}T = "
        f"{material.minimum_bend_radius(t):.1f}; SPECIFIED R{bracket.inside_radius:g}.",
        "3. BEND LINE DIMENSIONED ON THE FLAT PATTERN, NOT THE FORMED PART.",
        "4. FORM AFTER CUTTING. HOLES MAY BE CUT IN THE FLAT.",
        f"5. 4× ⌀{d:g} THRU. EDGE DISTANCE {bracket.edge_distance:.1f} "
        f"(≥ 2×⌀ = {2 * d:.1f}).",
        f"6. NEAREST HOLE EDGE TO BEND TANGENT {bracket.hole_edge_to_bend:.1f} "
        f"(≥ R+2T = {bracket.inside_radius + 2 * t:.1f}).",
        "7. BEND WITH GRAIN WHERE POSSIBLE; ACROSS GRAIN IF NOT.",
        "8. DEBURR ALL EDGES AND HOLES. NO SHARP EDGES.",
        f"9. FINISHED MASS {bracket.mass_kg() * 1000:.1f} g, FROM SOLID VOLUME.",
    ]
    ax.text(nx, ny, "NOTES", fontsize=6.4, fontweight="bold", color=INK)
    for index, note in enumerate(notes):
        ax.text(nx, ny - 5.0 - index * 4.2, note, fontsize=5.4,
                family="monospace", color=INK)

    # ── Title block ────────────────────────────────────────────────────
    bx, by = SHEET_W - MARGIN - TITLE_W, MARGIN
    ax.add_patch(Rectangle((bx, by), TITLE_W, TITLE_H, facecolor="white",
                           edgecolor=INK, lw=MEDIUM, zorder=8))
    for frac in (0.28, 0.60):
        ax.plot([bx, bx + TITLE_W], [by + TITLE_H * frac, by + TITLE_H * frac],
                color=INK, lw=THIN, zorder=9)
    ax.plot([bx + TITLE_W * 0.52] * 2, [by + TITLE_H * 0.28, by + TITLE_H * 0.60],
            color=INK, lw=THIN, zorder=9)
    ax.text(bx + 3, by + TITLE_H - 6.0, "EQUIPMENT MOUNTING BRACKET",
            fontsize=8.2, fontweight="bold", color=INK, zorder=10)
    ax.text(bx + 3, by + TITLE_H - 11.0, "FORMED SHEET — DETAIL AND FLAT PATTERN",
            fontsize=6.0, color=INK, zorder=10)
    left = [f"MATL     {material.name}", f"THK      {t:g}",
            f"FORM     {a:g} × {b:g} × {w:g}"]
    right = [f"FLAT     {flat:.2f} × {w:g}", f"BENDS    1 × 90° UP",
             f"MASS     {bracket.mass_kg() * 1000:.1f} g"]
    for index, line in enumerate(left):
        ax.text(bx + 3, by + TITLE_H * 0.50 - index * 4.0, line, fontsize=5.4,
                color=INK, family="monospace", zorder=10)
    for index, line in enumerate(right):
        ax.text(bx + TITLE_W * 0.545, by + TITLE_H * 0.50 - index * 4.0, line,
                fontsize=5.4, color=INK, family="monospace", zorder=10)
    footer = (f"DRAWN {DRAWN_BY}   DWG {drawing_number}   SCALE 1:{scale_denominator}"
              f"   UNITS mm")
    if date:
        footer += f"   {date}"
    ax.text(bx + 3, by + 3.0, footer, fontsize=5.0, color=INK,
            family="monospace", zorder=10)

    if path is not None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, facecolor="white", dpi=200)
        print(f"  {path}")
    return fig


if __name__ == "__main__":
    print("Sheet-metal bracket drawing")
    bracket_drawing(AngleBracket(), "drawings/SMB-001-bracket.png")
    # The redesign trade_study.py selects: 2.0 mm gauge, +28% margin at 9g.
    # A separate sheet rather than an edit of the first, because the two
    # blanks differ and both parts exist in the repository.
    bracket_drawing(AngleBracket(thickness=2.0),
                    "drawings/SMB-002-bracket-2mm.png",
                    drawing_number="SMB-002")
