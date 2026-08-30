"""Closed-form beam theory for the bracket, as a check on the FEA.

Runs in the base environment -- pure `math`, no CAD kernel, no solver.

An FEA result with nothing to compare it against is a picture, and the
failure mode is specific: a wrong constraint or a mis-set unit produces a
contour plot that looks entirely plausible and is wrong by an order of
magnitude. Hand calculation is the cheapest defence. It will not match the
FEA closely -- it cannot, since it has no stress concentrations and no
Poisson effects -- but it fixes the order of magnitude and the *shape* of
the answer, and that is what catches a blunder.

The bracket is two cantilevers in series, which is the part worth getting
right and the part a first pass usually misses:

  1. the upright bends about the bend line, and
  2. the base *also* bends, between the bend and the bolt line, because it
     is reacting the moment the upright hands it through the same 1.6 mm
     of material.

Ignore (2) and the predicted deflection comes out several times too small.
Both segments have the same section, so both see the same peak bending
stress -- the bracket has no single obvious weak end.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

YOUNGS_MPA = 70300.0
YIELD_MPA = 193.0


@dataclass(frozen=True)
class BeamEstimate:
    """Closed-form prediction for one load case."""

    moment_n_mm: float
    section_modulus_mm3: float
    second_moment_mm4: float
    bending_stress_mpa: float
    upright_deflection_mm: float
    base_rotation_rad: float
    total_deflection_mm: float

    @property
    def margin_of_safety(self) -> float:
        """Negative means the nominal stress is already past yield."""
        return YIELD_MPA / self.bending_stress_mpa - 1.0


def estimate(force_n: float, upright_arm_mm: float, base_arm_mm: float,
             width_mm: float, thickness_mm: float,
             youngs_mpa: float = YOUNGS_MPA) -> BeamEstimate:
    """Bending stress and tip deflection for the two-cantilever idealisation.

    `upright_arm_mm` is the load height above the bend line, `base_arm_mm`
    the distance from the bend line back to the bolt line.
    """
    second_moment = width_mm * thickness_mm ** 3 / 12.0
    section_modulus = width_mm * thickness_mm ** 2 / 6.0
    moment = force_n * upright_arm_mm

    # (1) upright bending as a cantilever built in at the bend
    upright = force_n * upright_arm_mm ** 3 / (3.0 * youngs_mpa * second_moment)
    # (2) the base carries that moment back to the bolts and rotates doing
    #     it; the upright rides that rotation rigidly, hence the second term
    rotation = moment * base_arm_mm / (youngs_mpa * second_moment)

    return BeamEstimate(
        moment_n_mm=moment,
        section_modulus_mm3=section_modulus,
        second_moment_mm4=second_moment,
        bending_stress_mpa=moment / section_modulus,
        upright_deflection_mm=upright,
        base_rotation_rad=rotation,
        total_deflection_mm=upright + rotation * upright_arm_mm,
    )


def kt_hole_in_plate(hole_diameter_mm: float, width_mm: float) -> float:
    """Peterson's stress concentration factor, hole in a finite-width plate.

    Heywood's approximation to the finite-width case: 3.0 for a small hole
    in a wide plate, rising as the hole eats the section. This is what the
    FEA should be expected to find *above* the nominal beam stress, and the
    reason a converged FEA peak of roughly 2-3x nominal is a believable
    answer rather than a suspicious one.
    """
    ratio = hole_diameter_mm / width_mm
    if not 0.0 < ratio < 1.0:
        raise ValueError(f"d/w must be in (0, 1), got {ratio}")
    return 3.0 - 3.14 * ratio + 3.667 * ratio ** 2 - 1.527 * ratio ** 3


# The load case fea.py solves, so the two can be compared directly.
EQUIPMENT_KG = 2.0
LOAD_FACTOR_G = 9.0
FORCE_N = EQUIPMENT_KG * 9.81 * LOAD_FACTOR_G

# Geometry, from bracket.py. The bend line sits one thickness plus one inner
# radius up from the base, so the effective arm is shorter than the 33 mm
# hole height by that much.
THICKNESS_MM = 1.6
WIDTH_MM = 50.0
HOLE_HEIGHT_MM = 33.0
BEND_INNER_RADIUS_MM = 3.0
UPRIGHT_ARM_MM = HOLE_HEIGHT_MM - THICKNESS_MM - BEND_INNER_RADIUS_MM
BASE_ARM_MM = 48.0          # bend line to the base bolt centres
HOLE_DIAMETER_MM = 5.1        # M5 clearance, per bracket.py


def bracket_estimate() -> BeamEstimate:
    """The hand calculation for the bracket's 9g load case."""
    return estimate(FORCE_N, UPRIGHT_ARM_MM, BASE_ARM_MM,
                    WIDTH_MM, THICKNESS_MM)


def main() -> None:
    e = bracket_estimate()
    kt = kt_hole_in_plate(HOLE_DIAMETER_MM, WIDTH_MM)
    print(f"Hand calculation -- {EQUIPMENT_KG} kg at {LOAD_FACTOR_G}g "
          f"= {FORCE_N:.1f} N\n")
    print(f"  upright arm            {UPRIGHT_ARM_MM:8.1f} mm")
    print(f"  root moment            {e.moment_n_mm:8.0f} N.mm")
    print(f"  section modulus        {e.section_modulus_mm3:8.2f} mm^3")
    print(f"  nominal bending stress {e.bending_stress_mpa:8.1f} MPa"
          f"   (yield {YIELD_MPA:.0f})")
    print(f"  margin of safety       {e.margin_of_safety:8.2f}")
    print()
    print(f"  upright bending        {e.upright_deflection_mm:8.2f} mm")
    print(f"  base rotation          {math.degrees(e.base_rotation_rad):8.2f} deg")
    print(f"  total tip deflection   {e.total_deflection_mm:8.2f} mm")
    print()
    print(f"  Kt at a {HOLE_DIAMETER_MM} mm hole   {kt:8.2f}")
    print(f"  so expect an FEA peak around "
          f"{e.bending_stress_mpa * 1.5:.0f}-"
          f"{e.bending_stress_mpa * kt:.0f} MPa near a feature")


if __name__ == "__main__":
    main()
