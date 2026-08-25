"""Limits, fits and geometric tolerances for the actuator drawing pack.

A model with nominal dimensions is not a manufacturable part. What turns
one into the other is saying, for every functional feature, how far from
nominal it is allowed to be and still work -- and saying it in the language
a machine shop and an inspector both already read: ISO 286 limits and fits
for size, ISO 1101 geometric tolerances for form, orientation and location.

Everything here is derived rather than typed in. The fit deviations come
from the ISO 286 tables below, indexed by nominal size band, so changing
the actuator's bore changes its limits without anyone re-reading a
handbook. That is the same argument the geometry makes: a parametric model
whose tolerances are hand-entered constants stops being parametric at
exactly the point it starts to matter.

Scope, stated plainly: this covers the features the model actually has. A
production drawing of a real actuator would also carry a piston and gland
(this model has neither), a rod-end bearing, thread callouts for the port
bosses, and a full surface-treatment and NDT schedule. Those are not
tolerances left out -- they are features not modelled, and inventing
tolerances for them would be decoration.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ── ISO 286 ────────────────────────────────────────────────────────────────
#
# Nominal size bands, in mm, as upper bounds. ISO 286 quantises tolerance by
# band rather than computing it per size, which is why a 30 mm and a 50 mm
# bore in the same grade carry the same tolerance.
SIZE_BANDS = (3, 6, 10, 18, 30, 50, 80, 120, 180, 250, 315, 400, 500)

# Standard tolerance grades, in micrometres, one entry per band above.
IT_GRADES = {
    6:  (6, 8, 9, 11, 13, 16, 19, 22, 25, 29, 32, 36, 40),
    7:  (10, 12, 15, 18, 21, 25, 30, 35, 40, 46, 52, 57, 63),
    8:  (14, 18, 22, 27, 33, 39, 46, 54, 63, 72, 81, 89, 97),
    9:  (25, 30, 36, 43, 52, 62, 74, 87, 100, 115, 130, 140, 155),
    11: (60, 75, 90, 110, 130, 160, 190, 220, 250, 290, 320, 360, 400),
}

# Upper deviation (es) for the shaft fundamental deviations used here, in
# micrometres. Both are negative: the shaft sits below nominal, which is
# what makes a clearance fit clear.
SHAFT_UPPER_DEVIATION = {
    "f": (-6, -10, -13, -16, -20, -25, -30, -36, -43, -50, -56, -62, -68),
    "g": (-2, -4, -5, -6, -7, -9, -10, -12, -14, -15, -17, -18, -20),
    "h": (0,) * 13,
}


def _band_index(nominal_mm: float) -> int:
    """Which ISO 286 size band a nominal diameter falls in."""
    if nominal_mm <= 0:
        raise ValueError("nominal size must be positive")
    for index, upper in enumerate(SIZE_BANDS):
        if nominal_mm <= upper:
            return index
    raise ValueError(f"{nominal_mm} mm is outside the tabulated range "
                     f"(max {SIZE_BANDS[-1]} mm)")


def it_tolerance(nominal_mm: float, grade: int) -> float:
    """Standard tolerance IT<grade> at this nominal size, in millimetres."""
    if grade not in IT_GRADES:
        raise ValueError(f"IT{grade} is not tabulated here; have "
                         f"{sorted(IT_GRADES)}")
    return IT_GRADES[grade][_band_index(nominal_mm)] / 1000.0


@dataclass(frozen=True)
class Limits:
    """One toleranced size: nominal, and the two deviations from it."""

    nominal: float
    lower_deviation: float
    upper_deviation: float
    designation: str

    @property
    def minimum(self) -> float:
        return self.nominal + self.lower_deviation

    @property
    def maximum(self) -> float:
        return self.nominal + self.upper_deviation

    @property
    def tolerance(self) -> float:
        return self.upper_deviation - self.lower_deviation

    def callout(self) -> str:
        """As it appears on the drawing: size, class, and both deviations."""
        return (f"⌀{self.nominal:g} {self.designation} "
                f"({self.upper_deviation:+.3f}/{self.lower_deviation:+.3f})")


def hole_limits(nominal_mm: float, grade: int) -> Limits:
    """An H-class hole: lower deviation zero, so the hole is never smaller
    than nominal. This is the hole-basis system, and it is the default for
    good reason -- holes are cut by fixed-size tooling (drills, reamers)
    while shafts are turned to any size the operator likes, so it is
    cheaper to fix the hole and vary the shaft."""
    return Limits(nominal_mm, 0.0, it_tolerance(nominal_mm, grade),
                  f"H{grade}")


def shaft_limits(nominal_mm: float, deviation: str, grade: int) -> Limits:
    """A shaft in one of the clearance-fit letter classes."""
    if deviation not in SHAFT_UPPER_DEVIATION:
        raise ValueError(f"deviation {deviation!r} not tabulated; have "
                         f"{sorted(SHAFT_UPPER_DEVIATION)}")
    es = SHAFT_UPPER_DEVIATION[deviation][_band_index(nominal_mm)] / 1000.0
    return Limits(nominal_mm, es - it_tolerance(nominal_mm, grade), es,
                  f"{deviation}{grade}")


@dataclass(frozen=True)
class Fit:
    """A hole and a shaft at the same nominal size, and what results."""

    hole: Limits
    shaft: Limits

    def __post_init__(self):
        if self.hole.nominal != self.shaft.nominal:
            raise ValueError("a fit needs both members at the same nominal size")

    @property
    def minimum_clearance(self) -> float:
        """Tightest condition: smallest hole against largest shaft."""
        return self.hole.minimum - self.shaft.maximum

    @property
    def maximum_clearance(self) -> float:
        """Loosest condition: largest hole against smallest shaft."""
        return self.hole.maximum - self.shaft.minimum

    @property
    def is_clearance_fit(self) -> bool:
        """True when the parts always assemble -- no interference at any
        combination of sizes within the limits."""
        return self.minimum_clearance >= 0.0

    def designation(self) -> str:
        return (f"⌀{self.hole.nominal:g} "
                f"{self.hole.designation}/{self.shaft.designation}")


# ── ISO 1101 geometric tolerances ──────────────────────────────────────────

# Characteristic symbols. Spelled out as names as well, because a feature
# control frame rendered as a bare glyph in a matplotlib text box is not
# reliably legible at drawing scale, and an inspector reading a PDF should
# not have to guess.
CHARACTERISTICS = {
    "straightness": ("—", "STRAIGHTNESS"),
    "flatness": ("▱", "FLATNESS"),
    "roundness": ("○", "ROUNDNESS"),
    "cylindricity": ("⌓", "CYLINDRICITY"),
    "perpendicularity": ("⊥", "PERPENDICULARITY"),
    "parallelism": ("∥", "PARALLELISM"),
    "position": ("⊕", "POSITION"),
    "concentricity": ("◎", "CONCENTRICITY"),
    "total_runout": ("↗", "TOTAL RUNOUT"),
}


@dataclass(frozen=True)
class FeatureControlFrame:
    """One ISO 1101 geometric tolerance, as it sits on the drawing.

    `material_condition` is 'M' for maximum material condition, which
    matters more than it looks: a position tolerance at MMC earns bonus
    tolerance as the feature departs from its maximum material size, so a
    hole drilled larger than minimum may be further off position and still
    assemble. Applying it to clearance holes is close to free and is what
    keeps a drawing from rejecting parts that would have worked.
    """

    characteristic: str
    tolerance: float
    datums: tuple[str, ...] = ()
    material_condition: str | None = None
    note: str = ""

    def __post_init__(self):
        if self.characteristic not in CHARACTERISTICS:
            raise ValueError(f"unknown characteristic {self.characteristic!r}")
        if self.tolerance <= 0:
            raise ValueError("a geometric tolerance must be positive")
        if self.material_condition not in (None, "M", "L"):
            raise ValueError("material condition must be 'M', 'L' or None")
        # Form tolerances -- straightness, flatness, roundness, cylindricity --
        # are properties of a single feature measured against itself. They
        # have no datum because there is nothing to reference: a cylinder is
        # round or it is not, regardless of what else the part is doing.
        form_only = {"straightness", "flatness", "roundness", "cylindricity"}
        if self.characteristic in form_only and self.datums:
            raise ValueError(f"{self.characteristic} is a form tolerance and "
                             "cannot take a datum reference")
        if self.characteristic not in form_only and not self.datums:
            raise ValueError(f"{self.characteristic} needs at least one datum")

    @property
    def symbol(self) -> str:
        return CHARACTERISTICS[self.characteristic][0]

    @property
    def name(self) -> str:
        return CHARACTERISTICS[self.characteristic][1]

    def callout(self) -> str:
        """Rendered in the linear form a feature control frame reads in:
        characteristic | tolerance | datums."""
        parts = [self.name, f"{self.tolerance:.3g}"]
        if self.material_condition:
            parts[-1] += " (M)" if self.material_condition == "M" else " (L)"
        if self.datums:
            parts.append(" ".join(self.datums))
        return " | ".join(parts)


@dataclass(frozen=True)
class ToleranceScheme:
    """Everything one detail drawing has to say beyond nominal geometry."""

    part_name: str
    datums: dict[str, str]
    sizes: list[Limits] = field(default_factory=list)
    geometric: list[FeatureControlFrame] = field(default_factory=list)
    surface_finish: dict[str, float] = field(default_factory=dict)
    general_note: str = ""


# ── The actuator's own schemes ─────────────────────────────────────────────
#
# One per detail drawing. Kept here rather than inside drawing.py so the
# engineering is testable without rendering anything, and so the drawing
# module stays purely presentational.


def cylinder_body_scheme(actuator) -> ToleranceScheme:
    """Cylinder body.

    Datum A is the bore axis, not the outside diameter. The bore is what
    the part exists to do -- it contains pressure and guides the piston --
    so it is the feature everything else should be measured from. Taking
    the OD as datum instead would be easier to fixture and wrong: it would
    let the bore wander relative to the very axis the actuator works on.
    """
    bore = hole_limits(actuator.bore, 8)
    outside = shaft_limits(actuator.cylinder_od, "h", 11)
    return ToleranceScheme(
        part_name="CYLINDER BODY",
        datums={"A": "BORE AXIS", "B": "ROD-END FACE"},
        sizes=[bore, outside],
        geometric=[
            # Form of the bore, against itself. A bore that is round at
            # every station but tapered still leaks past a seal, which is
            # why this is cylindricity and not roundness.
            FeatureControlFrame("cylindricity", 0.02,
                                note="BORE, FULL DEPTH"),
            # Total runout, not concentricity: it controls the whole
            # surface rather than the derived centre of it, and it is what
            # an inspector can actually measure by rotating the part
            # against an indicator.
            FeatureControlFrame("total_runout", 0.05, ("A",),
                                note="OUTSIDE DIAMETER"),
            FeatureControlFrame("perpendicularity", 0.05, ("A",),
                                note="ROD-END FACE"),
        ],
        surface_finish={"BORE": 0.4, "OUTSIDE DIAMETER": 3.2, "END FACES": 1.6},
        general_note="MATERIAL: ALUMINIUM 6061-T6. DEBURR ALL EDGES.",
    )


def piston_rod_scheme(actuator) -> ToleranceScheme:
    """Piston rod.

    Straightness carries the interesting call here. The rod is slender --
    at the B737 size, 200 mm long on a 21 mm diameter, near 10:1 -- and a
    bent rod in a close-fitting gland binds and scrubs its seal even when
    every diameter it has measures perfectly.
    """
    rod = shaft_limits(actuator.rod, "f", 7)
    slenderness = actuator.stroke / actuator.rod
    return ToleranceScheme(
        part_name="PISTON ROD",
        datums={"A": "ROD AXIS"},
        sizes=[rod],
        geometric=[
            FeatureControlFrame("cylindricity", 0.015, note="ROD DIAMETER"),
            FeatureControlFrame("straightness", 0.05,
                                note=f"OVER FULL LENGTH (L/D {slenderness:.1f})"),
        ],
        # A dynamic sealing surface, so finer than anything else on the
        # assembly: too rough and it abrades the seal, too smooth and it
        # will not retain the oil film that lubricates it.
        surface_finish={"ROD DIAMETER": 0.2, "END FACES": 1.6},
        general_note="MATERIAL: STEEL 4340. HARD CHROME PLATE ROD DIAMETER.",
    )


def clevis_end_scheme(actuator) -> ToleranceScheme:
    """Clevis end.

    The bolt holes carry position at maximum material condition. They are
    clearance holes for M6 into a mating structure, so what matters is
    that the pattern assembles, not that any one hole is exactly placed --
    and at MMC a hole drilled larger than its minimum earns proportional
    bonus tolerance on position. Withholding that would reject parts that
    fit perfectly well.
    """
    pin_bore = hole_limits(actuator.pin_bore_diameter, 9)
    bolt_hole = hole_limits(actuator.BOLT_CLEARANCE_HOLE, 11)
    return ToleranceScheme(
        part_name="CLEVIS END",
        datums={"A": "BACK FACE", "B": "PIN BORE AXIS", "C": "SIDE FACE"},
        sizes=[pin_bore, bolt_hole],
        geometric=[
            FeatureControlFrame("perpendicularity", 0.05, ("A",),
                                note="PIN BORE AXIS"),
            FeatureControlFrame("position", 0.3, ("A", "B", "C"), "M",
                                note="2× BOLT HOLES"),
            FeatureControlFrame("parallelism", 0.1, ("A",),
                                note="FRONT FACE"),
        ],
        surface_finish={"PIN BORE": 1.6, "GENERAL": 3.2},
        general_note="MATERIAL: STEEL 4340. DEBURR ALL EDGES.",
    )


# ── Stack-up ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class StackContributor:
    """One dimension feeding an assembly stack, and its direction."""

    name: str
    nominal: float
    tolerance: float   # half-width, i.e. the +/- value
    sense: int = 1     # +1 adds to the gap, -1 closes it

    def __post_init__(self):
        if self.sense not in (1, -1):
            raise ValueError("sense must be +1 or -1")
        if self.tolerance < 0:
            raise ValueError("tolerance must not be negative")


@dataclass(frozen=True)
class StackResult:
    nominal: float
    worst_case: float
    rss: float

    @property
    def worst_case_range(self) -> tuple[float, float]:
        return (self.nominal - self.worst_case, self.nominal + self.worst_case)

    @property
    def rss_range(self) -> tuple[float, float]:
        return (self.nominal - self.rss, self.nominal + self.rss)


def stack_up(contributors: list[StackContributor]) -> StackResult:
    """One-dimensional tolerance stack, both ways.

    **Worst case** adds every tolerance arithmetically: the gap this
    guarantees will never be violated, and it is what a safety-critical or
    single-build assembly should be designed against. It is also usually
    pessimistic, because it assumes every part is simultaneously at its
    worst limit in the same direction.

    **RSS** (root sum square) adds them in quadrature, which is the right
    model when the contributors are independent and roughly normally
    distributed within their limits -- true of a production run, not of one
    prototype. It gives a much tighter answer, and it is a statistical
    statement rather than a guarantee: roughly 3-sigma, so a small fraction
    of assemblies fall outside it.

    Reporting both is the point. Quoting only RSS hides the parts that will
    not fit; quoting only worst case buys tolerance nobody needed.
    """
    if not contributors:
        raise ValueError("a stack needs at least one contributor")
    nominal = sum(c.sense * c.nominal for c in contributors)
    worst_case = sum(c.tolerance for c in contributors)
    rss = sum(c.tolerance ** 2 for c in contributors) ** 0.5
    return StackResult(nominal=nominal, worst_case=worst_case, rss=rss)


def installed_length_stack(actuator) -> tuple[list[StackContributor], StackResult]:
    """Extended eye-to-eye length: cylinder base face to clevis pin-bore
    axis, with the actuator posed at its modelled extension.

    This is the dimension an airframe installer cares about, because it
    decides whether the rod-end reaches its attachment lug. Four dimensions
    drive it and they do not all push the same way -- rod engagement
    *subtracts*, since rod buried in the bore is length the assembly does
    not gain -- which is exactly why the arithmetic is worth doing rather
    than eyeballing.

    Note what this is not: it is a stack on the *posed* assembly, so it
    describes the model, not a working stroke envelope. A real installation
    drawing would carry retracted and extended lengths and the pin-to-pin
    range between them.
    """
    contributors = [
        StackContributor("CYLINDER BODY LENGTH", actuator.stroke + 50, 0.20, +1),
        StackContributor("ROD ENGAGEMENT IN BORE",
                         actuator.ROD_ENGAGEMENT * actuator.stroke, 0.30, -1),
        StackContributor("ROD LENGTH", actuator.stroke, 0.20, +1),
        StackContributor("CLEVIS PIN-BORE OFFSET FROM ROD TIP", 10.0, 0.15, +1),
        # Nominal zero, tolerance only: the base face is a datum, and its
        # own squareness still feeds the stack even though it adds no
        # length.
        StackContributor("BASE FACE SQUARENESS", 0.0, 0.05, +1),
    ]
    return contributors, stack_up(contributors)
