"""Design-for-manufacture checks that read a solid rather than a spec.

Project 05 checks sheet-metal *parameters* -- numbers handed over by the
designer. That only works when the design and the check share an author.
This reads a STEP file it did not create, which is the situation a real
DFM review is in: a supplier's model, another team's part, or your own from
six months ago.

Four checks, each answering a question a shop would ask before quoting:

  MINIMUM WALL       Is there anywhere too thin to machine or cast without
                     distortion? Measured by firing rays through the solid,
                     not by trusting a dimension.
  DRAFT ANGLE        For a casting or moulding, can it leave the tool? Any
                     face closer to parallel with the pull direction than
                     the draft minimum locks the part in.
  HOLE ASPECT RATIO  Depth over diameter. Past about 5:1 a hole stops being
                     drilling and starts being gun-drilling, with the tool
                     cost and lead time that implies.
  INTERNAL RADIUS    A milled internal corner cannot be sharper than the
                     cutter that made it. Corners below the smallest
                     sensible tool radius are undercuts nobody can reach.

**No cost or lead-time estimate.** The scaffold for this project proposed
both, quoting $500 against $5,000 per part. Those numbers had no source --
no quote, no cost model, nothing but plausibility -- and projects 01 and 02
already removed exactly that kind of invented figure for exactly that
reason. A check that says "this hole is 8:1, which needs gun-drilling" is
useful. One that says "this costs $5,000" is a guess wearing a number.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.BRepTools import breptools
from OCC.Core.GeomAbs import GeomAbs_Cylinder

from geometry import (
    describe_faces,
    face_midpoint_uv,
    faces,
    outward_normal,
    point_at,
    ray_thickness_mm,
)


@dataclass(frozen=True)
class Finding:
    """One thing a shop would raise, with the number that raised it."""

    check: str
    severity: str          # "fail" or "advisory"
    detail: str
    measured: float
    limit: float
    location: tuple[float, float, float] | None = None

    def __str__(self) -> str:
        where = ""
        if self.location:
            where = ("  at (%.0f, %.0f, %.0f)" % self.location)
        return (f"[{self.severity.upper():8s}] {self.check}: {self.detail} "
                f"(measured {self.measured:.2f}, limit {self.limit:.2f}){where}")


@dataclass
class DFMRules:
    """Limits a shop would work to, for one process.

    The process matters more than the numbers, and getting it wrong is how
    a DFM checker earns a reputation for crying wolf. Run casting rules
    over a turned part and every cylindrical face fails on draft -- which
    is true of a mould and meaningless on a lathe, where a bore has no
    draft by definition and needs none. The first version of this module
    did exactly that and reported three failures on a part with nothing
    wrong with it.

    So `checks_draft` is a property of the process, not an option. Build
    rules with `DFMRules.for_process(...)` rather than by hand.
    """

    process: str = "machined"
    min_wall_mm: float = 2.0
    min_draft_deg: float = 2.0
    max_hole_aspect: float = 5.0
    min_internal_radius_mm: float = 1.5
    min_hole_diameter_mm: float = 2.0
    pull_direction: tuple[float, float, float] = (0.0, 0.0, 1.0)
    checks_draft: bool = False

    @classmethod
    def for_process(cls, process: str, **overrides):
        """Rules for a named process.

        Representative values for aluminium. A real shop works to its own,
        and every one of these is a parameter for that reason.
        """
        presets = {
            # Milled or turned from solid. Draft is meaningless -- nothing
            # has to leave a tool -- but internal corners are limited by
            # cutter radius and deep holes get expensive fast.
            "machined": dict(min_wall_mm=1.5, min_internal_radius_mm=1.5,
                             max_hole_aspect=5.0, min_hole_diameter_mm=2.0,
                             checks_draft=False),
            # Sand casting. Draft is the whole game, walls must be thick
            # enough to fill and not tear on cooling, and internal radii are
            # generous to avoid hot spots.
            "sand-cast": dict(min_wall_mm=4.0, min_draft_deg=2.0,
                              min_internal_radius_mm=3.0, max_hole_aspect=3.0,
                              min_hole_diameter_mm=6.0, checks_draft=True),
            # Investment casting holds finer detail and less draft.
            "investment-cast": dict(min_wall_mm=2.0, min_draft_deg=1.0,
                                    min_internal_radius_mm=1.5,
                                    max_hole_aspect=4.0,
                                    min_hole_diameter_mm=3.0, checks_draft=True),
            # Rolled and welded tube. Added after the survey flagged the
            # bleed duct's 0.60 mm wall as unmachinable -- which is true,
            # and irrelevant, because nobody machines a duct from solid.
            # The check was right and the process assigned to it was wrong,
            # which is the failure mode this whole class exists to make
            # visible: a DFM answer is only as good as the process behind
            # it, and "machined" is not a safe default.
            "formed-tube": dict(min_wall_mm=0.4, min_internal_radius_mm=0.5,
                                max_hole_aspect=99.0, min_hole_diameter_mm=1.0,
                                checks_draft=False),
        }
        if process not in presets:
            raise ValueError(f"unknown process {process!r}; "
                             f"have {sorted(presets)}")
        return cls(process=process, **{**presets[process], **overrides})


def check_wall_thickness(shape, rules: DFMRules, samples_per_face: int = 9):
    """Fire rays inward from sample points and report the thinnest result.

    Sampling on a UV grid rather than only at face midpoints, because a
    wall that thins toward one edge is exactly the case a midpoint probe
    walks straight past. Rays that escape are skipped rather than counted
    as zero -- an outward-facing convex surface legitimately hits nothing.
    """
    findings, thinnest = [], None
    side = max(2, int(math.sqrt(samples_per_face)))
    for face in faces(shape):
        u_min, u_max, v_min, v_max = breptools.UVBounds(face)
        for i in range(side):
            for j in range(side):
                # Inset from the boundary: a sample exactly on an edge sits
                # where two faces meet and the ray immediately re-hits its
                # own neighbour.
                u = u_min + (u_max - u_min) * (i + 1) / (side + 1)
                v = v_min + (v_max - v_min) * (j + 1) / (side + 1)
                try:
                    normal = outward_normal(face, u, v)
                except ValueError:
                    continue
                origin = point_at(face, u, v)
                inward = tuple(-c for c in normal)
                thickness = ray_thickness_mm(shape, origin, inward)
                if thickness is None:
                    continue
                if thinnest is None or thickness < thinnest[0]:
                    thinnest = (thickness, origin)
    if thinnest and thinnest[0] < rules.min_wall_mm:
        findings.append(Finding(
            "MINIMUM WALL", "fail",
            "material thinner than the process can hold flat",
            thinnest[0], rules.min_wall_mm, thinnest[1]))
    return findings, (thinnest[0] if thinnest else None)


def check_draft(shape, rules: DFMRules):
    """Faces too near parallel with the pull direction to release.

    Draft is measured from the pull direction: a face whose normal is
    exactly perpendicular to pull has zero draft and is a vertical wall in
    the tool. Faces facing along pull -- the top and bottom of the part --
    are not walls at all and are skipped.
    """
    if not rules.checks_draft:
        return []
    findings = []
    pull = rules.pull_direction
    magnitude = math.sqrt(sum(c * c for c in pull))
    pull = tuple(c / magnitude for c in pull)

    for info in describe_faces(shape):
        alignment = abs(sum(info.outward_normal[i] * pull[i] for i in range(3)))
        # 1.0 means the face looks straight along the pull; 0.0 means it is
        # a wall parallel to it. Draft is the angle away from that wall.
        if alignment > 0.98:
            continue
        draft_deg = math.degrees(math.asin(min(1.0, alignment)))
        if draft_deg < rules.min_draft_deg and info.area_mm2 > 1.0:
            findings.append(Finding(
                "DRAFT ANGLE", "fail",
                f"{info.kind} face cannot release from the tool",
                draft_deg, rules.min_draft_deg, info.centroid))
    return findings


def check_holes(shape, rules: DFMRules):
    """Bores that are too deep for their diameter, or too small to drill."""
    findings = []
    for face in faces(shape):
        adaptor = BRepAdaptor_Surface(face)
        if adaptor.GetType() != GeomAbs_Cylinder:
            continue
        from geometry import _is_concave_cylinder
        if not _is_concave_cylinder(face, adaptor):
            continue

        radius = adaptor.Cylinder().Radius()
        u_min, u_max, v_min, v_max = breptools.UVBounds(face)
        depth = abs(v_max - v_min)          # v runs along the cylinder axis
        sweep = abs(u_max - u_min)          # u runs around it, in radians

        # A concave cylinder is not necessarily a hole. The inside of a
        # bend fillet is concave too, and it sweeps a quarter turn rather
        # than a full one. Reading one as the other is not a rounding
        # error: on the sheet-metal bracket the R3 bend fillet, 50 mm wide
        # across the part, came back as "⌀6 × 50 deep, needs gun-drilling"
        # -- a confident recommendation about a feature that does not
        # exist. Anything sweeping less than half a turn is a fillet.
        if sweep < math.pi:
            continue

        u, v = face_midpoint_uv(face)
        where = point_at(face, u, v)

        if 2 * radius < rules.min_hole_diameter_mm:
            findings.append(Finding(
                "HOLE SIZE", "fail", "bore below the smallest sensible drill",
                2 * radius, rules.min_hole_diameter_mm, where))
        aspect = depth / (2 * radius) if radius else 0.0
        if aspect > rules.max_hole_aspect:
            findings.append(Finding(
                "HOLE ASPECT", "advisory",
                f"⌀{2 * radius:.1f} × {depth:.0f} deep needs gun-drilling",
                aspect, rules.max_hole_aspect, where))
    return findings


def check_internal_radii(shape, rules: DFMRules):
    """Internal corners sharper than any cutter that could reach them."""
    findings = []
    for face in faces(shape):
        adaptor = BRepAdaptor_Surface(face)
        if adaptor.GetType() != GeomAbs_Cylinder:
            continue
        from geometry import _is_concave_cylinder
        if not _is_concave_cylinder(face, adaptor):
            continue
        u_min, u_max, _, _ = breptools.UVBounds(face)
        # The mirror of the check above: a partial sweep is a corner, and
        # corners are what this check is about. Full bores are holes and
        # are judged on aspect ratio instead.
        if abs(u_max - u_min) >= math.pi:
            continue
        radius = adaptor.Cylinder().Radius()
        u, v = face_midpoint_uv(face)
        centroid = point_at(face, u, v)
        if radius < rules.min_internal_radius_mm:
            findings.append(Finding(
                "INTERNAL RADIUS", "advisory",
                "corner sharper than the smallest practical cutter",
                radius, rules.min_internal_radius_mm, centroid))
    return findings


@dataclass
class DFMReport:
    part: str
    findings: list = field(default_factory=list)
    thinnest_wall_mm: float | None = None
    face_count: int = 0

    @property
    def failures(self) -> list:
        return [f for f in self.findings if f.severity == "fail"]

    @property
    def advisories(self) -> list:
        return [f for f in self.findings if f.severity == "advisory"]

    @property
    def passed(self) -> bool:
        return not self.failures

    process: str = "machined"

    def summary(self) -> str:
        state = "PASS" if self.passed else "FAIL"
        return (f"{self.part} [{self.process}]: {state} — "
                f"{len(self.failures)} failure(s), "
                f"{len(self.advisories)} advisory, {self.face_count} faces")


def analyse(shape, rules: DFMRules | None = None, part: str = "part") -> DFMReport:
    """Run every check and collect what they found."""
    rules = rules or DFMRules.for_process("machined")
    wall_findings, thinnest = check_wall_thickness(shape, rules)
    findings = (wall_findings + check_draft(shape, rules)
                + check_holes(shape, rules) + check_internal_radii(shape, rules))
    return DFMReport(part=part, findings=findings, thinnest_wall_mm=thinnest,
                     face_count=len(describe_faces(shape)),
                     process=rules.process)
