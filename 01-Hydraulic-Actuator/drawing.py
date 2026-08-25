"""Dimensioned detail drawings with GD&T, plus an assembly GA.

A4 landscape, millimetres, third-angle projection, in the visual language
projects 04 and 06 of the sibling portfolio use -- arrowhead dimension
lines, a title block, THIN/MEDIUM/THICK line weights. Reimplemented rather
than imported: each project here stays self-contained.

What separates these from the general-arrangement drawings those projects
produce is that a GA describes a shape and these describe a *part*. Every
functional feature carries limits from `tolerances.py`, a geometric
tolerance where form or location matters, a surface finish where it rubs or
seals, and a datum scheme saying what is measured from what. That is the
difference between a picture of a component and something a shop can quote
and an inspector can accept or reject.

    python drawing.py            # all four sheets, B737-class

Sheets:
    ACT-001  cylinder body, detail
    ACT-002  piston rod, detail
    ACT-003  clevis end, detail
    ACT-100  assembly, general arrangement
"""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, Polygon, Rectangle  # noqa: E402

from hydraulic_actuator import HydraulicActuator  # noqa: E402
from tolerances import (  # noqa: E402
    clevis_end_scheme,
    cylinder_body_scheme,
    installed_length_stack,
    piston_rod_scheme,
)

SHEET_W, SHEET_H = 297.0, 210.0
MARGIN = 10.0
TITLE_W, TITLE_H = 108.0, 40.0

INK = "#111111"
DIM_COLOR = "#333333"
SECTION_FILL = "#e8e4dc"
THIN, MEDIUM, THICK = 0.5, 0.9, 1.4
HEAD_L, HEAD_W = 2.2, 0.7

DRAWN_BY = "V. Venkateshkumar"


# ── Sheet furniture ────────────────────────────────────────────────────────

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
            "THIRD ANGLE PROJECTION   ·   ALL DIMENSIONS IN MILLIMETRES",
            fontsize=5.6, color=DIM_COLOR)
    return fig, ax


def _head(ax, tip, ux, uy):
    bx, by = tip[0] - ux * HEAD_L, tip[1] - uy * HEAD_L
    px, py = -uy * HEAD_W / 2.0, ux * HEAD_W / 2.0
    ax.add_patch(Polygon([tip, (bx + px, by + py), (bx - px, by - py)],
                         closed=True, facecolor=DIM_COLOR, edgecolor="none",
                         zorder=6))


def _dim_linear(ax, p1, p2, dim_pos, text, vertical=False, text_side=1):
    """A dimension between two points, offset to `dim_pos`, with witness
    lines back to the feature."""
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


def _centreline(ax, p1, p2):
    ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=DIM_COLOR, lw=THIN,
            linestyle=(0, (7, 2, 1.5, 2)), zorder=3)


def _leader(ax, target, text_xy, text, fontsize=5.8):
    """A leader line from a feature to a note, with a dot at the feature."""
    ax.annotate(text, xy=target, xytext=text_xy, fontsize=fontsize, color=INK,
                zorder=8, va="center",
                arrowprops=dict(arrowstyle="-", color=DIM_COLOR, lw=THIN,
                                shrinkA=0, shrinkB=1))
    ax.plot([target[0]], [target[1]], marker="o", markersize=1.6,
            color=DIM_COLOR, zorder=8)


def _feature_control_frame(ax, xy, frame, height=5.0, fontsize=5.4):
    """An ISO 1101 feature control frame: characteristic, tolerance, datums,
    each in its own compartment.

    Drawn with the characteristic spelled out rather than as its glyph. The
    symbols are not reliably present in the fonts matplotlib will fall back
    to, and a control frame that renders as a missing-glyph box on someone
    else's machine is worse than one that reads as a word.
    """
    x, y = xy
    cells = [frame.name, f"{frame.tolerance:.3g}"
             + (" (M)" if frame.material_condition == "M" else "")]
    cells += list(frame.datums)
    widths = [max(len(c) * 1.35 + 2.6, 7.0) for c in cells]

    cursor = x
    for width, cell in zip(widths, cells):
        ax.add_patch(Rectangle((cursor, y), width, height, facecolor="white",
                               edgecolor=INK, lw=THIN, zorder=8))
        ax.text(cursor + width / 2.0, y + height / 2.0, cell, ha="center",
                va="center", fontsize=fontsize, color=INK, zorder=9)
        cursor += width
    return cursor - x  # total width, so a caller can stack frames


def _datum_symbol(ax, target, text_xy, letter):
    """A datum feature symbol: filled triangle on the feature, boxed letter.

    The triangle sits on the surface or its extension line, which is what
    makes a datum a physical thing an inspector can set the part down on --
    not an idea about its centre.
    """
    tx, ty = text_xy
    ax.plot([target[0], tx], [target[1], ty], color=DIM_COLOR, lw=THIN, zorder=7)
    size = 2.2
    ax.add_patch(Polygon([(target[0], target[1]),
                          (target[0] - size / 2, target[1] - size),
                          (target[0] + size / 2, target[1] - size)],
                         closed=True, facecolor=INK, edgecolor=INK, zorder=8))
    box = 5.0
    ax.add_patch(Rectangle((tx - box / 2, ty - box / 2), box, box,
                           facecolor="white", edgecolor=INK, lw=THIN, zorder=8))
    ax.text(tx, ty, letter, ha="center", va="center", fontsize=6.0,
            fontweight="bold", color=INK, zorder=9)


def _surface_finish(ax, target, text_xy, ra):
    """A surface texture symbol -- the open tick with the Ra value."""
    tx, ty = text_xy
    ax.plot([target[0], tx], [target[1], ty], color=DIM_COLOR, lw=THIN, zorder=7)
    ax.plot([tx - 1.6, tx, tx + 2.6], [ty, ty - 2.2, ty + 2.6],
            color=INK, lw=THIN, zorder=8)
    ax.text(tx + 3.0, ty + 1.6, f"Ra {ra:g}", fontsize=5.4, color=INK,
            ha="left", va="center", zorder=8)


def _wrap(text, width):
    """Break a note into lines no wider than `width` characters, on word
    boundaries. The sheet uses a monospace face for notes, so a character
    count is a reliable proxy for width."""
    words, lines, current = text.split(), [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _notes_block(ax, xy, scheme, extra=()):
    """Limits, geometric tolerances, finishes and general notes, as a list.

    A drawing needs these somewhere legible even when every callout is also
    placed on the view -- an inspector writing a report works from the note
    block, not by hunting leaders around the sheet.
    """
    x, y = xy
    ax.text(x, y, "NOTES", fontsize=6.4, fontweight="bold", color=INK)
    lines = []
    for index, (letter, feature) in enumerate(scheme.datums.items(), start=1):
        lines.append(f"{index}. DATUM {letter}: {feature}")
    start = len(lines) + 1
    for offset, limits in enumerate(scheme.sizes):
        lines.append(f"{start + offset}. {limits.callout()}")
    start = len(lines) + 1
    for offset, frame in enumerate(scheme.geometric):
        note = f" — {frame.note}" if frame.note else ""
        lines.append(f"{start + offset}. {frame.callout()}{note}")
    start = len(lines) + 1
    for offset, (feature, ra) in enumerate(scheme.surface_finish.items()):
        lines.append(f"{start + offset}. SURFACE FINISH {feature}: Ra {ra:g} μm")
    lines.append(f"{len(lines) + 1}. {scheme.general_note}")

    # `extra` entries are whole notes, each possibly needing more than one
    # line on the sheet. Only the first line of a note is numbered -- and
    # the number is taken before the loop, not from len(lines) inside it,
    # which quietly counted the continuation lines and produced 12, 14, 16.
    number = len(lines) + 1
    for note in extra:
        for offset, segment in enumerate(_wrap(note, 62)):
            lines.append(f"{number}. {segment}" if offset == 0
                         else f"    {segment}")
        number += 1

    for index, line in enumerate(lines):
        ax.text(x, y - 5.0 - index * 4.0, line, fontsize=5.4,
                family="monospace", color=INK)
    return y - 5.0 - len(lines) * 4.0


def _title_block(ax, title, subtitle, left, right, drawing_no, scale_text,
                 date=None):
    tx, ty = SHEET_W - MARGIN - TITLE_W, MARGIN
    ax.add_patch(Rectangle((tx, ty), TITLE_W, TITLE_H, facecolor="white",
                           edgecolor=INK, lw=MEDIUM, zorder=8))
    for frac in (0.28, 0.60):
        ax.plot([tx, tx + TITLE_W], [ty + TITLE_H * frac, ty + TITLE_H * frac],
                color=INK, lw=THIN, zorder=9)
    ax.plot([tx + TITLE_W * 0.52] * 2, [ty + TITLE_H * 0.28, ty + TITLE_H * 0.60],
            color=INK, lw=THIN, zorder=9)

    ax.text(tx + 3, ty + TITLE_H - 6.0, title, fontsize=8.2,
            fontweight="bold", color=INK, zorder=10)
    ax.text(tx + 3, ty + TITLE_H - 11.0, subtitle, fontsize=6.0, color=INK,
            zorder=10)
    for index, line in enumerate(left):
        ax.text(tx + 3, ty + TITLE_H * 0.50 - index * 4.0, line, fontsize=5.4,
                color=INK, family="monospace", zorder=10)
    for index, line in enumerate(right):
        ax.text(tx + TITLE_W * 0.545, ty + TITLE_H * 0.50 - index * 4.0, line,
                fontsize=5.4, color=INK, family="monospace", zorder=10)
    footer = f"DRAWN {DRAWN_BY}   DWG {drawing_no}   {scale_text}   UNITS mm"
    if date:
        footer += f"   {date}"
    ax.text(tx + 3, ty + 3.0, footer, fontsize=5.0, color=INK,
            family="monospace", zorder=10)


def _save(fig, path):
    if path is not None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, facecolor="white", dpi=200)
        print(f"  {path}")
    return fig


def _fcf_stack(ax, xy, frames, pitch=7.0, title="GEOMETRIC TOLERANCES"):
    """Feature control frames stacked downward from a fixed sheet position.

    Placed as a block rather than floated beside each feature. On a sheet
    this size a frame parked above the view collides with the sheet header,
    and leaders crossing dimension lines to reach them cost more legibility
    than the association buys -- the note block carries the same
    information indexed to the feature by name.
    """
    x, y = xy
    if title:
        ax.text(x, y + 5.0, title, fontsize=6.4, fontweight="bold", color=INK)
    for index, frame in enumerate(frames):
        _feature_control_frame(ax, (x, y - index * pitch), frame)
    return y - len(frames) * pitch


# ── ACT-001  Cylinder body ─────────────────────────────────────────────────

def cylinder_body_detail(actuator, path=None, scale_denominator=2, date=None):
    """Longitudinal half-section plus an end view.

    Sectioned because the part is defined by what has been removed from it:
    a bore that stops short of the far end, and a separate cap cavity at
    the base with a solid web between them. An outside view of a cylinder
    is a rectangle, and says none of that.
    """
    s = 1.0 / scale_denominator
    scheme = cylinder_body_scheme(actuator)

    length = actuator.stroke + 50.0
    outer_d, bore_d = actuator.cylinder_od, actuator.bore
    bore_depth, cap_depth = actuator.stroke, 25.0

    fig, ax = _sheet()
    x0, cy = 34.0, 148.0
    x1 = x0 + length * s
    ro, rb = outer_d / 2 * s, bore_d / 2 * s

    # Outline, then the two cavities knocked out of it. Material is filled
    # and hatched; the cavities are left white.
    ax.add_patch(Rectangle((x0, cy - ro), length * s, 2 * ro,
                           facecolor=SECTION_FILL, edgecolor=INK, lw=MEDIUM,
                           hatch="///", zorder=4))
    bore_x0 = x1 - bore_depth * s
    ax.add_patch(Rectangle((bore_x0, cy - rb), bore_depth * s, 2 * rb,
                           facecolor="white", edgecolor=INK, lw=MEDIUM,
                           zorder=5))
    ax.add_patch(Rectangle((x0, cy - rb), cap_depth * s, 2 * rb,
                           facecolor="white", edgecolor=INK, lw=MEDIUM,
                           zorder=5))
    _centreline(ax, (x0 - 6, cy), (x1 + 6, cy))

    # End view, looking on the rod end.
    ev_x = x1 + 44.0
    ax.add_patch(Circle((ev_x, cy), ro, facecolor=SECTION_FILL, edgecolor=INK,
                        lw=MEDIUM, zorder=4))
    ax.add_patch(Circle((ev_x, cy), rb, facecolor="white", edgecolor=INK,
                        lw=MEDIUM, zorder=5))
    _centreline(ax, (ev_x - ro - 5, cy), (ev_x + ro + 5, cy))
    _centreline(ax, (ev_x, cy - ro - 5), (ev_x, cy + ro + 5))
    ax.text(ev_x, cy + ro + 9, "VIEW ON ROD END", fontsize=6.0,
            fontweight="bold", ha="center", color=INK)

    # Dimensions.
    _dim_linear(ax, (x0, cy - ro), (x1, cy - ro), cy - ro - 20,
                f"{length:.0f}", text_side=-1)
    _dim_linear(ax, (bore_x0, cy + rb), (x1, cy + rb), cy + ro + 8,
                f"{bore_depth:.0f}")
    _dim_linear(ax, (x0, cy - rb), (x0 + cap_depth * s, cy - rb), cy - ro - 11,
                f"{cap_depth:.0f}", text_side=-1)
    _dim_linear(ax, (ev_x + ro, cy - ro), (ev_x + ro, cy + ro), ev_x + ro + 12,
                f"⌀{outer_d:.0f} h11", vertical=True)
    _dim_linear(ax, (ev_x - rb, cy - rb), (ev_x - rb, cy + rb), ev_x - ro - 12,
                f"⌀{bore_d:.0f} H8", vertical=True, text_side=-1)

    # Datums: A on the bore axis, B on the rod-end face.
    _datum_symbol(ax, (ev_x - rb, cy - rb - 2), (ev_x - ro - 12, cy - ro - 16), "A")
    _datum_symbol(ax, (x1, cy - ro * 0.5), (x1 + 12, cy - ro - 14), "B")

    _fcf_stack(ax, (172.0, 112.0), scheme.geometric)
    _surface_finish(ax, (bore_x0 + 30, cy + rb), (bore_x0 + 30, cy + ro + 14), 0.4)

    _notes_block(ax, (MARGIN + 6, 112.0), scheme)
    _title_block(
        ax, "HYDRAULIC ACTUATOR", "CYLINDER BODY — DETAIL",
        [f"BORE     ⌀{bore_d:.0f} H8", f"OD       ⌀{outer_d:.0f} h11",
         f"LENGTH   {length:.0f}"],
        [f"WALL     {actuator.wall_thickness:.0f}", "MATL     AL 6061-T6",
         f"CLASS    {actuator.stroke:.0f} STROKE"],
        "ACT-001", f"SCALE 1:{scale_denominator}", date)
    return _save(fig, path)


# ── ACT-002  Piston rod ────────────────────────────────────────────────────

def piston_rod_detail(actuator, path=None, scale_denominator=2, date=None):
    """Side view with a local section through the seal-groove pocket."""
    s = 1.0 / scale_denominator
    scheme = piston_rod_scheme(actuator)

    length, rod_d = actuator.stroke, actuator.rod
    pocket_r = max(rod_d / 2 - actuator.rod_seal_groove_width, 1.0)
    pocket_depth = actuator.rod_seal_groove_depth

    fig, ax = _sheet()
    x0, cy = 40.0, 152.0
    x1 = x0 + length * s
    rr, pr = rod_d / 2 * s, pocket_r * s

    ax.add_patch(Rectangle((x0, cy - rr), length * s, 2 * rr,
                           facecolor=SECTION_FILL, edgecolor=INK, lw=MEDIUM,
                           hatch="///", zorder=4))
    ax.add_patch(Rectangle((x1 - pocket_depth * s, cy - pr), pocket_depth * s,
                           2 * pr, facecolor="white", edgecolor=INK, lw=MEDIUM,
                           zorder=5))
    _centreline(ax, (x0 - 6, cy), (x1 + 6, cy))

    ev_x = x1 + 40.0
    ax.add_patch(Circle((ev_x, cy), rr, facecolor=SECTION_FILL, edgecolor=INK,
                        lw=MEDIUM, zorder=4))
    ax.add_patch(Circle((ev_x, cy), pr, facecolor="white", edgecolor=INK,
                        lw=MEDIUM, zorder=5))
    _centreline(ax, (ev_x - rr - 5, cy), (ev_x + rr + 5, cy))
    _centreline(ax, (ev_x, cy - rr - 5), (ev_x, cy + rr + 5))
    ax.text(ev_x, cy + rr + 9, "VIEW ON POCKET END", fontsize=6.0,
            fontweight="bold", ha="center", color=INK)

    _dim_linear(ax, (x0, cy - rr), (x1, cy - rr), cy - rr - 16,
                f"{length:.0f}", text_side=-1)
    _dim_linear(ax, (ev_x + rr, cy - rr), (ev_x + rr, cy + rr), ev_x + rr + 12,
                f"⌀{rod_d:.0f} f7", vertical=True)
    _leader(ax, (x1 - pocket_depth * s / 2, cy + pr),
            (x1 - 30, cy + rr + 16),
            f"⌀{2 * pocket_r:.0f} × {pocket_depth:.1f} DEEP")

    _datum_symbol(ax, (x0 + 24, cy), (x0 + 24, cy - 18), "A")

    _fcf_stack(ax, (172.0, 112.0), scheme.geometric)
    _surface_finish(ax, (x0 + 60, cy + rr), (x0 + 60, cy + rr + 16), 0.2)

    _notes_block(ax, (MARGIN + 6, 112.0), scheme, extra=(
        "SEAL POCKET IS A SIMPLIFIED STAND-IN, NOT A TRUE O-RING GROOVE. "
        "A REAL ROD CARRIES A CIRCUMFERENTIAL GROOVE ON ITS DIAMETER.",
    ))
    _title_block(
        ax, "HYDRAULIC ACTUATOR", "PISTON ROD — DETAIL",
        [f"ROD      ⌀{rod_d:.0f} f7", f"LENGTH   {length:.0f}",
         f"L/D      {length / rod_d:.1f}"],
        ["MATL     STEEL 4340", "FINISH   HARD CHROME", "SEAL     PTFE"],
        "ACT-002", f"SCALE 1:{scale_denominator}", date)
    return _save(fig, path)


# ── ACT-003  Clevis end ────────────────────────────────────────────────────

def clevis_end_detail(actuator, path=None, scale_denominator=1, date=None):
    """Front view showing the hole pattern, plus a side view for thickness."""
    s = 1.0 / scale_denominator
    scheme = clevis_end_scheme(actuator)

    size = actuator.clevis_size
    thickness = actuator.clevis_thickness
    bore_d = actuator.pin_bore_diameter
    hole_d = actuator.BOLT_CLEARANCE_HOLE
    offset = actuator.bolt_hole_offset

    fig, ax = _sheet()
    cx, cy = 78.0, 140.0
    half = size / 2 * s

    ax.add_patch(Rectangle((cx - half, cy - half), size * s, size * s,
                           facecolor=SECTION_FILL, edgecolor=INK, lw=MEDIUM,
                           zorder=4))
    ax.add_patch(Circle((cx, cy), bore_d / 2 * s, facecolor="white",
                        edgecolor=INK, lw=MEDIUM, zorder=5))
    for sign in (+1, -1):
        ax.add_patch(Circle((cx, cy + sign * offset * s), hole_d / 2 * s,
                            facecolor="white", edgecolor=INK, lw=MEDIUM,
                            zorder=5))
        _centreline(ax, (cx - 6, cy + sign * offset * s),
                    (cx + 6, cy + sign * offset * s))
    _centreline(ax, (cx - half - 5, cy), (cx + half + 5, cy))
    _centreline(ax, (cx, cy - half - 5), (cx, cy + half + 5))

    # Side view, third angle: placed to the right of the front view.
    sv_x = cx + half + 32.0
    ax.add_patch(Rectangle((sv_x, cy - half), thickness * s, size * s,
                           facecolor=SECTION_FILL, edgecolor=INK, lw=MEDIUM,
                           hatch="///", zorder=4))
    for sign in (+1, -1):
        ax.plot([sv_x, sv_x + thickness * s],
                [cy + sign * offset * s] * 2, color=INK, lw=THIN,
                linestyle=(0, (3, 2)), zorder=5)
    ax.text(sv_x + thickness * s / 2, cy + half + 8, "SIDE", fontsize=6.0,
            fontweight="bold", ha="center", color=INK)

    _dim_linear(ax, (cx - half, cy - half), (cx + half, cy - half),
                cy - half - 12, f"{size:.0f}", text_side=-1)
    _dim_linear(ax, (cx - half, cy - half), (cx - half, cy + half),
                cx - half - 14, f"{size:.0f}", vertical=True, text_side=-1)
    _dim_linear(ax, (cx, cy), (cx, cy + offset * s), cx + half + 10,
                f"{offset:.2f}", vertical=True)
    _dim_linear(ax, (sv_x, cy - half), (sv_x + thickness * s, cy - half),
                cy - half - 12, f"{thickness:.0f}", text_side=-1)

    _leader(ax, (cx - bore_d / 2 * s * 0.71, cy - bore_d / 2 * s * 0.71),
            (cx - half - 30, cy - 14), f"⌀{bore_d:.0f} H9")
    _leader(ax, (cx + hole_d / 2 * s * 0.71, cy + offset * s + hole_d / 2 * s * 0.71),
            (cx + 26, cy + half + 6), f"2× ⌀{hole_d:g} H11 THRU")

    _datum_symbol(ax, (sv_x, cy - half * 0.4), (sv_x - 12, cy - half - 22), "A")
    _datum_symbol(ax, (cx, cy - bore_d / 2 * s), (cx - 20, cy - half - 22), "B")
    _datum_symbol(ax, (cx + half, cy - half * 0.5), (cx + half + 12, cy - half - 8), "C")

    _fcf_stack(ax, (MARGIN + 6, 96.0), scheme.geometric)

    _notes_block(ax, (150.0, 122.0), scheme, extra=(
        "PLATE SIZE IS DERIVED FROM THE PIN BORE SO THE BOLT HOLES ALWAYS "
        "CLEAR IT. AN EARLIER FIXED SIZE PUT THEM INSIDE THE BORE ON THE "
        "TWO LARGEST VARIANTS — SEE README.",
    ))
    _title_block(
        ax, "HYDRAULIC ACTUATOR", "CLEVIS END — DETAIL",
        [f"PLATE    {size:.0f} × {size:.0f} × {thickness:.0f}",
         f"PIN BORE ⌀{bore_d:.0f} H9", f"BOLTS    2× M{hole_d - 0.5:.0f}"],
        ["MATL     STEEL 4340", f"PCD      {2 * offset:.1f}",
         "FINISH   AS MACHINED"],
        "ACT-003", f"SCALE 1:{scale_denominator}", date)
    return _save(fig, path)


# ── ACT-100  Assembly general arrangement ──────────────────────────────────

def general_arrangement(actuator, path=None, scale_denominator=3, date=None):
    """The assembled actuator in section, ballooned, with a parts list and
    the installed-length stack.

    Sectioned for the same reason the cylinder detail is: it is the only
    view that shows the rod engaged in the bore, which is the whole point
    of the pose. The overall length carries its stack-up result rather than
    a bare nominal, because on an assembly the useful number is not where
    the pin bore is meant to be but how far from there it might actually
    land.
    """
    s = 1.0 / scale_denominator
    contributors, stack = installed_length_stack(actuator)

    length = actuator.stroke + 50.0
    rod_base = length - actuator.ROD_ENGAGEMENT * actuator.stroke
    rod_tip = rod_base + actuator.stroke
    clevis_centre = rod_tip + 10.0

    fig, ax = _sheet()
    x0, cy = 30.0, 152.0
    ro = actuator.cylinder_od / 2 * s
    rb = actuator.bore / 2 * s
    rr = actuator.rod / 2 * s
    ch = actuator.clevis_size / 2 * s

    # Cylinder body, sectioned.
    ax.add_patch(Rectangle((x0, cy - ro), length * s, 2 * ro,
                           facecolor=SECTION_FILL, edgecolor=INK, lw=MEDIUM,
                           hatch="///", zorder=4))
    ax.add_patch(Rectangle((x0 + (length - actuator.stroke) * s, cy - rb),
                           actuator.stroke * s, 2 * rb, facecolor="white",
                           edgecolor=INK, lw=MEDIUM, zorder=5))
    ax.add_patch(Rectangle((x0, cy - rb), 25.0 * s, 2 * rb, facecolor="white",
                           edgecolor=INK, lw=MEDIUM, zorder=5))

    # Rod, drawn over the bore it sits in.
    ax.add_patch(Rectangle((x0 + rod_base * s, cy - rr), actuator.stroke * s,
                           2 * rr, facecolor=SECTION_FILL, edgecolor=INK,
                           lw=MEDIUM, hatch="\\\\\\", zorder=6))

    # Clevis, on the rod tip.
    ax.add_patch(Rectangle((x0 + (clevis_centre - actuator.clevis_size / 2) * s,
                            cy - ch), actuator.clevis_size * s,
                           actuator.clevis_size * s, facecolor=SECTION_FILL,
                           edgecolor=INK, lw=MEDIUM, zorder=7))
    ax.add_patch(Circle((x0 + clevis_centre * s, cy),
                        actuator.pin_bore_diameter / 2 * s, facecolor="white",
                        edgecolor=INK, lw=MEDIUM, zorder=8))
    for sign in (+1, -1):
        ax.add_patch(Circle((x0 + clevis_centre * s,
                             cy + sign * actuator.bolt_hole_offset * s),
                            actuator.BOLT_CLEARANCE_HOLE / 2 * s,
                            facecolor="white", edgecolor=INK, lw=MEDIUM,
                            zorder=8))
    _centreline(ax, (x0 - 6, cy), (x0 + (clevis_centre + 20) * s, cy))

    # Balloons, keyed to the parts list.
    for number, (bx, by) in enumerate([
        (x0 + length * s * 0.35, cy + ro),
        (x0 + (rod_base + actuator.stroke * 0.75) * s, cy + rr),
        (x0 + clevis_centre * s, cy + ch),
    ], start=1):
        ax.plot([bx, bx + 6], [by, by + 13], color=DIM_COLOR, lw=THIN, zorder=9)
        ax.add_patch(Circle((bx + 6, by + 16), 3.4, facecolor="white",
                            edgecolor=INK, lw=THIN, zorder=10))
        ax.text(bx + 6, by + 16, str(number), ha="center", va="center",
                fontsize=6.0, color=INK, zorder=11)

    # Installed length, quoted with its stack.
    _dim_linear(ax, (x0, cy - ch), (x0 + clevis_centre * s, cy - ch),
                cy - ch - 13, f"{stack.nominal:.0f}", text_side=-1)
    ax.text(x0 + clevis_centre * s / 2, cy - ch - 20,
            f"INSTALLED LENGTH — WORST CASE ±{stack.worst_case:.2f}, "
            f"RSS ±{stack.rss:.2f}", fontsize=5.6, ha="center", color=INK)

    # Parts list.
    bom = actuator.get_bom()
    px, py = MARGIN + 6, 108.0
    ax.text(px, py, "PARTS LIST", fontsize=6.4, fontweight="bold", color=INK)
    ax.text(px, py - 5.5, f"{'ITEM':<6}{'DESCRIPTION':<22}{'MATERIAL':<24}{'MASS kg':>8}",
            fontsize=5.4, family="monospace", color=INK)
    listed = [c for c in bom["components"] if c.get("mass_kg")]
    for index, component in enumerate(listed):
        ax.text(px, py - 10.5 - index * 4.2,
                f"{index + 1:<6}{component['part_name'][:21]:<22}"
                f"{component.get('material', '')[:23]:<24}"
                f"{component['mass_kg']:>8.3f}",
                fontsize=5.4, family="monospace", color=INK)
    total = sum(c["mass_kg"] for c in listed)
    ax.text(px, py - 10.5 - len(listed) * 4.2 - 2.0,
            f"{'':<6}{'TOTAL':<22}{'':<24}{total:>8.3f}",
            fontsize=5.4, family="monospace", fontweight="bold", color=INK)

    # Stack-up table -- the contributors, not just the answer.
    sx, sy = 150.0, 108.0
    ax.text(sx, sy, "INSTALLED LENGTH STACK", fontsize=6.4,
            fontweight="bold", color=INK)
    ax.text(sx, sy - 5.5, f"{'':<3}{'CONTRIBUTOR':<38}{'NOM':>8}{'±TOL':>7}",
            fontsize=5.4, family="monospace", color=INK)
    for index, contributor in enumerate(contributors):
        ax.text(sx, sy - 10.5 - index * 4.2,
                f"{'+' if contributor.sense > 0 else '−':<3}"
                f"{contributor.name[:37]:<38}{contributor.nominal:>8.1f}"
                f"{contributor.tolerance:>7.2f}",
                fontsize=5.4, family="monospace", color=INK)
    base = sy - 10.5 - len(contributors) * 4.2
    ax.text(sx, base - 2.0,
            f"{'':<3}{'NOMINAL':<38}{stack.nominal:>8.1f}",
            fontsize=5.4, family="monospace", fontweight="bold", color=INK)
    ax.text(sx, base - 6.2,
            f"{'':<3}{'WORST CASE':<38}{'':>8}{stack.worst_case:>7.2f}",
            fontsize=5.4, family="monospace", color=INK)
    ax.text(sx, base - 10.4,
            f"{'':<3}{'RSS (3σ, PRODUCTION)':<38}{'':>8}{stack.rss:>7.2f}",
            fontsize=5.4, family="monospace", color=INK)

    _title_block(
        ax, "HYDRAULIC ACTUATOR", "ASSEMBLY — GENERAL ARRANGEMENT",
        [f"BORE     ⌀{actuator.bore:.0f}", f"ROD      ⌀{actuator.rod:.0f}",
         f"STROKE   {actuator.stroke:.0f}"],
        [f"FORCE    {actuator._calc_force_output():.1f} kN @ 210 bar",
         f"MASS     {total:.2f} kg", f"LENGTH   {stack.nominal:.0f} EXTENDED"],
        "ACT-100", f"SCALE 1:{scale_denominator}", date)
    return _save(fig, path)


def build_all(actuator=None, directory="drawings", date=None):
    """Every sheet in the pack. Returns the paths written, not the figures --
    the individual sheet functions hand back a figure so they can be built
    and inspected without touching the disk, but the whole-pack entry point
    is only ever used for its output."""
    actuator = actuator or HydraulicActuator(35, 21, 200)
    directory = Path(directory)
    sheets = [
        (cylinder_body_detail, "ACT-001-cylinder-body.png"),
        (piston_rod_detail, "ACT-002-piston-rod.png"),
        (clevis_end_detail, "ACT-003-clevis-end.png"),
        (general_arrangement, "ACT-100-assembly-ga.png"),
    ]
    written = []
    for build, filename in sheets:
        path = directory / filename
        figure = build(actuator, path, date=date)
        plt.close(figure)
        written.append(path)
    return written


if __name__ == "__main__":
    print("Drawing pack — B737-class actuator (⌀35 bore, ⌀21 rod, 200 stroke)")
    build_all()
