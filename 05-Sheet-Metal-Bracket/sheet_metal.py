"""Sheet-metal forming arithmetic and design-for-manufacture rules.

A folded part is not the sum of its legs. Bending stretches the outside of
the material and compresses the inside, and somewhere between the two sits
a neutral axis whose length does not change -- so the flat blank a shop
cuts is shorter than the finished part's outside dimensions added together.
Getting that wrong is the classic sheet-metal error: the drawing is
dimensionally correct, the blank is cut to the wrong length, and every part
in the batch is out of tolerance in the same direction.

Everything here is that arithmetic, plus the manufacturability rules that
decide whether the fold is possible at all. No CAD dependency: this is the
engineering, and `bracket.py` is what turns it into geometry.

Values are representative rather than authoritative. Real minimum bend
radii come from the material specification or MIL-HDBK-5 for the exact
alloy, temper, thickness and bend direction (with respect to grain), and a
production drawing would cite that source. They are tabulated here to make
the design rules concrete, not to stand in for a materials data sheet.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class SheetMaterial:
    """A sheet alloy in a given temper.

    `min_bend_radius_factor` is the tightest inside bend radius the material
    will take without cracking, as a multiple of thickness. It is the single
    number that most constrains a sheet-metal design, and it varies enormously
    with temper: 5052-H32 will fold around its own thickness, while 2024-T3
    -- stronger, and the reason it is used -- needs four times that or it
    cracks on the outside of the bend.
    """

    name: str
    density_g_cm3: float
    min_bend_radius_factor: float
    tensile_mpa: float
    note: str = ""

    def minimum_bend_radius(self, thickness_mm: float) -> float:
        return self.min_bend_radius_factor * thickness_mm


MATERIALS = {
    "2024-T3": SheetMaterial(
        "2024-T3", 2.78, 4.0, 435,
        "High strength, poor formability. Common in airframe structure."),
    "7075-T6": SheetMaterial(
        "7075-T6", 2.81, 5.0, 545,
        "Highest strength, worst formability. Rarely folded tightly."),
    "6061-T6": SheetMaterial(
        "6061-T6", 2.70, 3.0, 310,
        "General purpose, weldable, moderate formability."),
    "5052-H32": SheetMaterial(
        "5052-H32", 2.68, 1.0, 228,
        "Excellent formability and corrosion resistance. The default "
        "choice when a part is bent more than it is loaded."),
    "CRES-321-ANN": SheetMaterial(
        "CRES 321 annealed", 7.90, 0.5, 620,
        "Stainless, annealed. Folds tightly; used where temperature or "
        "fire resistance rules out aluminium."),
}


def k_factor(inside_radius_mm: float, thickness_mm: float) -> float:
    """Position of the neutral axis, as a fraction of thickness from the
    inside surface of the bend.

    It is not a constant. A tight bend forces the neutral axis inward,
    towards a third of the thickness; as the radius opens out the material
    is deformed less severely and the axis relaxes back towards the middle.
    The banding here is standard shop practice. A shop with its own press
    and its own tooling will have measured its own values, and those beat
    any table -- which is exactly why a drawing dimensions the *formed*
    part and lets the shop compute the blank.
    """
    if thickness_mm <= 0:
        raise ValueError("thickness must be positive")
    if inside_radius_mm < 0:
        raise ValueError("bend radius must not be negative")
    ratio = inside_radius_mm / thickness_mm
    if ratio < 1.0:
        return 0.33
    if ratio < 3.0:
        return 0.40
    return 0.45


def bend_allowance(angle_deg: float, inside_radius_mm: float,
                   thickness_mm: float) -> float:
    """Arc length of the neutral axis through the bend, in millimetres.

    BA = θ · (R + K·T), with θ in radians. This is the material actually
    consumed by the fold -- the length that has to be present in the flat
    blank between the two straight legs.
    """
    if not 0 < angle_deg <= 180:
        raise ValueError("bend angle must be in (0, 180] degrees")
    k = k_factor(inside_radius_mm, thickness_mm)
    return math.radians(angle_deg) * (inside_radius_mm + k * thickness_mm)


def outside_setback(angle_deg: float, inside_radius_mm: float,
                    thickness_mm: float) -> float:
    """Distance from the bend tangent line to the apex where the two
    outside surfaces would meet if the bend were sharp.

    OSSB = tan(θ/2) · (R + T). It is what makes a folded part's outside
    dimensions add up to more than its blank.
    """
    if not 0 < angle_deg < 180:
        raise ValueError("setback is undefined at 0 and 180 degrees")
    return math.tan(math.radians(angle_deg) / 2.0) * (inside_radius_mm
                                                      + thickness_mm)


def bend_deduction(angle_deg: float, inside_radius_mm: float,
                   thickness_mm: float) -> float:
    """How much shorter the blank is than the sum of the outside legs.

    BD = 2·OSSB − BA. Subtract one of these per bend from the summed
    outside dimensions and the result is the flat length.
    """
    return (2 * outside_setback(angle_deg, inside_radius_mm, thickness_mm)
            - bend_allowance(angle_deg, inside_radius_mm, thickness_mm))


@dataclass(frozen=True)
class Bend:
    """One fold: how far round, how tight, and which way."""

    angle_deg: float
    inside_radius_mm: float
    up: bool = True

    def allowance(self, thickness_mm: float) -> float:
        return bend_allowance(self.angle_deg, self.inside_radius_mm, thickness_mm)

    def deduction(self, thickness_mm: float) -> float:
        return bend_deduction(self.angle_deg, self.inside_radius_mm, thickness_mm)


def flat_length(outside_legs_mm: list[float], bends: list[Bend],
                thickness_mm: float) -> float:
    """Blank length for a part folded from a strip.

    Takes the *outside* leg dimensions -- which is how a formed part is
    dimensioned on a drawing, and how it is measured with a rule -- and
    subtracts one bend deduction per fold.
    """
    if len(outside_legs_mm) != len(bends) + 1:
        raise ValueError(
            f"{len(bends)} bends need {len(bends) + 1} legs, "
            f"got {len(outside_legs_mm)}")
    if thickness_mm <= 0:
        raise ValueError("thickness must be positive")
    return (sum(outside_legs_mm)
            - sum(bend.deduction(thickness_mm) for bend in bends))


# ── Design for manufacture ─────────────────────────────────────────────────
#
# Rules that decide whether a fold is possible, not whether it is optimal.
# Each returns a violation string or None, so a design can be checked
# wholesale and report everything wrong at once rather than failing on the
# first problem.

# Minimum flange, as a multiple of thickness: below this there is nothing
# for the press brake's tooling to hold, and the leg folds unpredictably or
# not at all.
MIN_FLANGE_FACTOR = 4.0
# Fastener edge distance, centre to sheet edge, as a multiple of hole
# diameter. 2.0 is the usual aerospace minimum; 2.5 is preferred, because a
# hole nearer the edge tears out under bearing load before the fastener
# fails in shear.
MIN_EDGE_DISTANCE_FACTOR = 2.0
PREFERRED_EDGE_DISTANCE_FACTOR = 2.5


@dataclass(frozen=True)
class Violation:
    rule: str
    detail: str
    actual: float
    required: float

    def __str__(self) -> str:
        return (f"{self.rule}: {self.detail} "
                f"(is {self.actual:.2f}, needs {self.required:.2f})")


def check_bend_radius(material: SheetMaterial, thickness: float,
                      inside_radius: float) -> Violation | None:
    """Too tight a bend cracks the outside fibre. Non-negotiable, and the
    first thing to check, because it is set by the material rather than by
    anything the designer can adjust apart from choosing another alloy."""
    required = material.minimum_bend_radius(thickness)
    if inside_radius < required - 1e-9:
        return Violation(
            "MIN BEND RADIUS",
            f"{material.name} needs {material.min_bend_radius_factor:g}T",
            inside_radius, required)
    return None


def check_flange_length(thickness: float, inside_radius: float,
                        flange: float) -> Violation | None:
    """A flange shorter than the tooling can grip will not form."""
    required = max(MIN_FLANGE_FACTOR * thickness, inside_radius + 2 * thickness)
    if flange < required - 1e-9:
        return Violation("MIN FLANGE LENGTH",
                         "too short for press-brake tooling to hold",
                         flange, required)
    return None


def check_hole_to_bend(thickness: float, inside_radius: float,
                       hole_edge_to_bend: float) -> Violation | None:
    """A hole too close to a bend line is dragged oval by the fold.

    The material near a bend moves; a hole drilled there before forming
    distorts, and one drilled after is hard to reach. Keeping holes clear
    of the bend by R + 2T is the standard avoidance.
    """
    required = inside_radius + 2 * thickness
    if hole_edge_to_bend < required - 1e-9:
        return Violation("HOLE TO BEND", "hole will distort during forming",
                         hole_edge_to_bend, required)
    return None


def check_edge_distance(hole_diameter: float, edge_distance: float,
                        preferred: bool = False) -> Violation | None:
    """Centre-to-edge distance for a fastener hole."""
    factor = (PREFERRED_EDGE_DISTANCE_FACTOR if preferred
              else MIN_EDGE_DISTANCE_FACTOR)
    required = factor * hole_diameter
    if edge_distance < required - 1e-9:
        return Violation(
            "EDGE DISTANCE",
            "fastener will tear out before it fails in shear",
            edge_distance, required)
    return None


def check_hole_diameter(thickness: float, hole_diameter: float) -> Violation | None:
    """A hole smaller than the sheet is thick is a drilling problem, not a
    design feature -- the drill wanders and breaks through raggedly."""
    if hole_diameter < thickness - 1e-9:
        return Violation("MIN HOLE DIAMETER",
                         "hole smaller than sheet thickness",
                         hole_diameter, thickness)
    return None
