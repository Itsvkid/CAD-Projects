"""Sizing a bleed-air duct from the conditions the engine actually delivers.

A duct is not a tube with a diameter. It is the answer to four questions
asked in order, and each answer constrains the next:

  1. How big must the bore be to pass the flow without choking it or
     throwing away pressure?
  2. How thick must the wall be to contain the pressure at temperature?
  3. What material survives that temperature at all?
  4. How tightly can it be bent before the outside wall thins below what
     question 2 demanded?

The interesting result falls out of asking them in that order, and it is
not the one people expect: a bleed duct is almost never pressure-limited.
Hoop stress at these sizes asks for a wall measured in tenths of a
millimetre, and what actually sets the gauge is that nobody can handle,
weld or fit a tube that thin. Then bending thins it further. `governing()`
reports which constraint won rather than quietly taking the maximum.

Inputs come from the twin-spool cycle model in the analysis portfolio --
station 3, HPC exit, which is where a real engine takes customer bleed for
cabin air and wing anti-ice. Nothing here is invented: give it a different
design point and it sizes a different duct.

No CAD dependency. `duct.py` turns these numbers into geometry.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

R_AIR = 287.05          # J/(kg K), specific gas constant for dry air
GAMMA_AIR = 1.4


@dataclass(frozen=True)
class DuctMaterial:
    """A candidate duct material.

    `allowable_mpa` is already derated to the service temperature -- these
    are representative values in the right region, not a substitute for
    MMPDS or a mill certificate, and a production design would cite the
    latter. `max_service_k` is where the material stops being a candidate
    at all rather than merely getting weaker.
    """

    name: str
    density_kg_m3: float
    allowable_mpa: float
    max_service_k: float
    min_gauge_mm: float
    note: str = ""


MATERIALS = {
    "AL-6061-T6": DuctMaterial(
        "Aluminium 6061-T6", 2700, 240, 450, 0.9,
        "Light and cheap. Loses most of its strength by 500 K, so it is a "
        "fan-air material, not a compressor-bleed one."),
    "TI-6AL-4V": DuctMaterial(
        "Titanium 6Al-4V", 4430, 620, 700, 0.6,
        "Excellent strength for its weight, and the usual choice where "
        "temperature allows it."),
    "CRES-321": DuctMaterial(
        "Stainless 321", 7900, 140, 1100, 0.5,
        "Stabilised against sensitisation, so it welds and stays welded. "
        "Heavy, and the fallback when titanium runs out of temperature."),
    "INCONEL-625": DuctMaterial(
        "Inconel 625", 8440, 250, 1250, 0.5,
        "Nickel superalloy. Expensive and heavy, and the reason to use it "
        "is that it is still strong where everything else has given up."),
}


@dataclass(frozen=True)
class BleedCondition:
    """Total conditions at the offtake, and how much is being taken."""

    total_temperature_k: float
    total_pressure_pa: float
    mass_flow_kg_s: float
    source: str = "HPC exit (station 3)"

    def __post_init__(self):
        if self.total_temperature_k <= 0 or self.total_pressure_pa <= 0:
            raise ValueError("temperature and pressure must be positive")
        if self.mass_flow_kg_s <= 0:
            raise ValueError("mass flow must be positive")

    @property
    def density_kg_m3(self) -> float:
        """Ideal-gas density at total conditions.

        Using total rather than static is a deliberate simplification and a
        conservative one for sizing: at the low duct Mach numbers this
        targets the two differ by under 2%, and erring toward higher density
        gives a slightly smaller bore, not a larger one.
        """
        return self.total_pressure_pa / (R_AIR * self.total_temperature_k)

    def speed_of_sound_m_s(self) -> float:
        return math.sqrt(GAMMA_AIR * R_AIR * self.total_temperature_k)


def bore_diameter_m(condition: BleedCondition, velocity_m_s: float) -> float:
    """Internal diameter to pass the flow at a chosen velocity.

    Velocity is the design lever. Too low and the duct is heavy and eats
    space nobody has; too high and pressure loss climbs with the square of
    it, and the bleed becomes expensive in the cycle it was taken from.
    Somewhere around 40-60 m/s is the usual compromise -- see
    `duct_mach_number` for the check that keeps it honest.
    """
    if velocity_m_s <= 0:
        raise ValueError("velocity must be positive")
    area = condition.mass_flow_kg_s / (condition.density_kg_m3 * velocity_m_s)
    return math.sqrt(4.0 * area / math.pi)


def duct_mach_number(condition: BleedCondition, velocity_m_s: float) -> float:
    """Flow Mach in the duct. Above roughly 0.3 compressibility starts to
    matter and the incompressible sizing above stops being defensible."""
    return velocity_m_s / condition.speed_of_sound_m_s()


def hoop_wall_thickness_m(pressure_pa: float, bore_m: float,
                          allowable_pa: float, safety_factor: float = 1.5) -> float:
    """Thin-wall hoop stress, solved for thickness.

    sigma = p*d / (2*t)  =>  t = p*d*SF / (2*sigma_allow)

    Thin-wall is valid while t/d stays under about 0.05, which it does by an
    enormous margin here -- the answer usually lands near a tenth of a
    millimetre, which is the whole point this module is making.
    """
    if allowable_pa <= 0:
        raise ValueError("allowable stress must be positive")
    return pressure_pa * bore_m * safety_factor / (2.0 * allowable_pa)


def bend_thinning_factor(centreline_radius_m: float, outer_diameter_m: float) -> float:
    """Fraction of wall thickness surviving on the outside of a bend.

    The outside fibre of a bend sits at radius R + D/2 while the centreline
    sits at R, so it is stretched by (R + D/2)/R. Wall volume is conserved,
    so thickness falls by the inverse of that ratio. A 2D bend keeps about
    80% of the wall; a 1D bend keeps two thirds and is why tight bends are
    quoted as a wall-thickness problem rather than a shape one.
    """
    if centreline_radius_m <= 0 or outer_diameter_m <= 0:
        raise ValueError("radius and diameter must be positive")
    return centreline_radius_m / (centreline_radius_m + outer_diameter_m / 2.0)


def select_material(condition: BleedCondition, margin_k: float = 50.0):
    """Lightest material that survives the temperature with margin.

    Sorted by density, so the first survivor is the lightest. That ordering
    is the whole selection: on an aircraft the question is never "what is
    strong enough" but "what is the lightest thing that is strong enough".
    """
    required = condition.total_temperature_k + margin_k
    candidates = [m for m in MATERIALS.values() if m.max_service_k >= required]
    if not candidates:
        raise ValueError(
            f"no tabulated material survives {required:.0f} K "
            f"({condition.total_temperature_k:.0f} K plus {margin_k:.0f} K margin)")
    return min(candidates, key=lambda m: m.density_kg_m3)


# Standard thin-wall tube gauges, mm. A duct is bought as tube, and tube
# comes in the sizes a mill rolls -- asking for 0.5583 gets you 0.6 and an
# invoice for the conversation.
STANDARD_GAUGES_MM = (0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2, 1.5, 1.6, 2.0, 2.5, 3.0)


@dataclass(frozen=True)
class DuctDesign:
    """A sized duct, and a record of what forced each number.

    Built by `size_duct`, which asks the four questions in order and keeps
    the reasoning rather than only the answers.
    """

    condition: BleedCondition
    material: DuctMaterial
    velocity_m_s: float
    bore_mm: float
    wall_mm: float
    bend_radius_mm: float

    hoop_required_mm: float          # what pressure alone asks for
    min_gauge_mm: float              # what handling and welding ask for
    bend_required_mm: float          # what surviving the bend asks for
    governing_constraint: str

    @property
    def outer_diameter_mm(self) -> float:
        return self.bore_mm + 2 * self.wall_mm

    @property
    def wall_after_bending_mm(self) -> float:
        """Thinnest the wall gets: outside of the tightest bend. A straight
        run keeps its full wall."""
        if math.isinf(self.bend_radius_mm):
            return self.wall_mm
        return self.wall_mm * bend_thinning_factor(
            self.bend_radius_mm, self.outer_diameter_mm)

    @property
    def bend_ratio(self) -> float:
        """Centreline bend radius in diameters -- how tube benders talk."""
        return self.bend_radius_mm / self.outer_diameter_mm

    @property
    def duct_mach(self) -> float:
        return duct_mach_number(self.condition, self.velocity_m_s)

    def mass_per_metre_kg(self) -> float:
        """Bare tube, no insulation, no flanges, no brackets."""
        r_o = self.outer_diameter_mm / 2000.0
        r_i = self.bore_mm / 2000.0
        return math.pi * (r_o ** 2 - r_i ** 2) * self.material.density_kg_m3

    def is_pressure_safe(self) -> bool:
        """Does the *thinned* wall still contain the pressure?

        Checked after bending, not before. A wall that passes at nominal
        and fails at the outside of a bend is the failure this whole module
        exists to catch.
        """
        return self.wall_after_bending_mm >= self.hoop_required_mm - 1e-9


def size_duct(condition: BleedCondition, velocity_m_s: float = 50.0,
              bend_diameters: float | None = 2.0, safety_factor: float = 1.5,
              material: DuctMaterial | None = None) -> DuctDesign:
    """Size a duct, and record which constraint set the wall thickness.

    `bend_diameters` is the centreline bend radius in duct diameters, which
    is how a tube bender specifies tooling. 2D is a normal aerospace bend;
    1D is tight and 3D is generous. **Pass None for a straight run.**

    That option is not decoration. The bend requirement is the hoop
    requirement divided by a thinning factor that is always below one, so
    wherever a bend exists it necessarily exceeds plain hoop stress and
    hoop can never be what governs. Hoop only governs a duct with no bends
    in it — which is worth being able to express, and worth noticing,
    because it means "sized for pressure" is not a thing a bent duct ever
    is.
    """
    material = material or select_material(condition)
    bore_m = bore_diameter_m(condition, velocity_m_s)

    hoop_m = hoop_wall_thickness_m(condition.total_pressure_pa, bore_m,
                                   material.allowable_mpa * 1e6, safety_factor)
    hoop_mm = hoop_m * 1000.0

    # The bend thins the outside wall, so the nominal wall has to be thicker
    # than the hoop requirement by exactly that factor. Solved iteratively
    # only because the thinning factor depends on the outer diameter, which
    # depends on the wall being solved for -- two passes converge to well
    # inside a micron at these proportions.
    if bend_diameters is None:
        bend_required_mm = 0.0
    else:
        wall_guess = max(hoop_mm, material.min_gauge_mm)
        for _ in range(3):
            outer = bore_m * 1000.0 + 2 * wall_guess
            radius = bend_diameters * outer
            wall_guess = hoop_mm / bend_thinning_factor(radius, outer)
        bend_required_mm = wall_guess

    required = max(hoop_mm, material.min_gauge_mm, bend_required_mm)
    wall_mm = next((g for g in STANDARD_GAUGES_MM if g >= required - 1e-9),
                   STANDARD_GAUGES_MM[-1])

    if required == bend_required_mm:
        governing = "BEND THINNING"
    elif required == material.min_gauge_mm:
        governing = "MINIMUM GAUGE"
    else:
        governing = "HOOP STRESS"

    outer_mm = bore_m * 1000.0 + 2 * wall_mm
    return DuctDesign(
        condition=condition, material=material, velocity_m_s=velocity_m_s,
        bore_mm=bore_m * 1000.0, wall_mm=wall_mm,
        bend_radius_mm=(math.inf if bend_diameters is None
                        else bend_diameters * outer_mm),
        hoop_required_mm=hoop_mm, min_gauge_mm=material.min_gauge_mm,
        bend_required_mm=bend_required_mm, governing_constraint=governing)


# Mean coefficient of thermal expansion, 1/K, over the range these ducts
# see. Representative values -- a production design would take them from
# the material spec at the actual temperature.
THERMAL_EXPANSION = {
    "Aluminium 6061-T6": 23.6e-6,
    "Titanium 6Al-4V": 8.6e-6,
    "Stainless 321": 16.5e-6,
    "Inconel 625": 12.8e-6,
}


def thermal_growth_mm(design: DuctDesign, length_mm: float,
                      ambient_k: float = 288.15) -> float:
    """How much longer the duct gets when the engine is running.

    dL = alpha * L * dT. It sounds like a rounding error and it is not: a
    metre of stainless going from a cold soak to compressor-bleed
    temperature grows the better part of a centimetre. That growth has to
    go somewhere -- into a bellows, a sliding joint, or a deliberate bend
    that can flex -- and the clearance to everything nearby has to allow
    for it. A duct routed with 5 mm of clearance is touching its neighbour
    the first time the engine reaches temperature.
    """
    alpha = THERMAL_EXPANSION.get(design.material.name)
    if alpha is None:
        raise ValueError(f"no expansion coefficient for {design.material.name}")
    return alpha * length_mm * (design.condition.total_temperature_k - ambient_k)


def required_clearance_mm(design: DuctDesign, length_mm: float,
                          vibration_allowance_mm: float = 3.0,
                          ambient_k: float = 288.15) -> float:
    """Cold clearance a hot duct needs to everything around it.

    Thermal growth plus an allowance for vibration and build tolerance.
    Stated as a single number so a routing study has something to check
    against rather than a feeling about what looks tight.
    """
    return (thermal_growth_mm(design, length_mm, ambient_k)
            + vibration_allowance_mm)
