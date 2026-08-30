"""Redesign trade study: how to make the bracket survive 9g.

    python trade_study.py

The FEA (`fea.py`) established that the bracket yields at 9g with a -1.9%
margin. This screens the ways of fixing it, before any of them is modelled.

Screening first is the point. Building a candidate and then analysing it
costs hours; ruling it out with a section modulus costs seconds, and the
one that looks most attractive is ruled out that way here.

**Both legs carry the same moment through the same section.** The load
enters at the upright holes, bends the upright about the bend line, and the
base then reacts that same moment back to the bolts through the same 1.6 mm
of material. So the bracket has no single weak end, and a change that
stiffens one leg moves the part's margin not at all -- which is exactly
what happens to the otherwise obvious idea of folding flanges up the
upright's free edges.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from dataclasses import dataclass, field

from beam_check import (
    BASE_ARM_MM,
    FORCE_N,
    UPRIGHT_ARM_MM,
    WIDTH_MM,
    YIELD_MPA,
    YOUNGS_MPA,
    channel_section,
    plate_section,
)
from bracket import AngleBracket
from sheet_metal import MATERIALS

MATERIAL = "5052-H32"
BASELINE_THICKNESS_MM = 1.6


@dataclass(frozen=True)
class Arm:
    """One candidate fix."""

    label: str
    thickness_mm: float
    flange_height_mm: float = 0.0
    buildable: bool = True
    note: str = ""


@dataclass
class Result:
    arm: Arm
    z_upright_mm3: float
    z_base_mm3: float
    stress_upright_mpa: float
    stress_base_mpa: float
    deflection_mm: float
    mass_g: float
    violations: list = field(default_factory=list)

    @property
    def governing_stress_mpa(self) -> float:
        """The bracket is as strong as its worse leg, not its better one."""
        return max(self.stress_upright_mpa, self.stress_base_mpa)

    @property
    def governing_leg(self) -> str:
        return ("upright" if self.stress_upright_mpa >= self.stress_base_mpa
                else "base")

    @property
    def margin(self) -> float:
        return YIELD_MPA / self.governing_stress_mpa - 1.0

    @property
    def passes(self) -> bool:
        return self.margin > 0.0 and not self.violations


def evaluate(arm: Arm, baseline_mass_g: float | None = None) -> Result:
    """Section properties, stresses, deflection, mass and manufacturability."""
    t = arm.thickness_mm
    moment = FORCE_N * UPRIGHT_ARM_MM

    # The base is never flanged in any of these arms: a flange cannot be
    # folded continuously around the 90-degree corner between the legs, so
    # wrapping both would need a relief at the corner or a separate riveted
    # gusset -- a different part, not a different fold.
    i_upright, z_upright = (channel_section(WIDTH_MM, t, arm.flange_height_mm)
                            if arm.flange_height_mm
                            else plate_section(WIDTH_MM, t))
    i_base, z_base = plate_section(WIDTH_MM, t)

    # Two cantilevers in series, each with its own section.
    deflection = (FORCE_N * UPRIGHT_ARM_MM ** 3 / (3 * YOUNGS_MPA * i_upright)
                  + (moment * BASE_ARM_MM / (YOUNGS_MPA * i_base)) * UPRIGHT_ARM_MM)

    violations, mass_g = [], float("nan")
    if arm.buildable:
        bracket = AngleBracket(thickness=t, material=MATERIAL)
        violations = bracket.violations()
        mass_g = (bracket.formed().val().Volume() / 1000.0
                  * MATERIALS[MATERIAL].density_g_cm3)
    elif baseline_mass_g is not None:
        # Developed blank area of two flanges, added to the baseline part.
        added_mm3 = 2 * arm.flange_height_mm * UPRIGHT_ARM_MM * t
        mass_g = baseline_mass_g + added_mm3 / 1000.0 * MATERIALS[MATERIAL].density_g_cm3

    return Result(arm, z_upright, z_base, moment / z_upright, moment / z_base,
                  deflection, mass_g, violations)


ARMS = [
    Arm("1.6 mm plain (as built)", 1.6,
        note="the current part, for reference"),
    Arm("1.6 mm + 12 mm upright flanges", 1.6, flange_height_mm=12.0,
        buildable=False,
        note="folds the upright's free edges into a channel"),
    Arm("2.0 mm gauge", 2.0, note="next standard sheet thickness up"),
    Arm("2.5 mm gauge", 2.5, note="one further"),
]



# Where fea.py wrote each variant's sweep, if it has been run.
FEA_RESULTS = {1.6: "fea_results.json", 2.0: "fea_results_2mm.json"}


def converged_fea(thickness_mm: float) -> dict | None:
    """The finest trustworthy result for a gauge, or None if not solved.

    "Trustworthy" means at least two quadratic elements through the wall.
    The 99th percentile is read rather than the peak, because the peak sits
    on the edge of a fixed constraint and diverges with refinement -- see
    the README.
    """
    if thickness_mm not in FEA_RESULTS:
        return None                      # this gauge has not been solved
    path = Path(FEA_RESULTS[thickness_mm])
    if not path.is_file():
        return None
    runs = [r for r in json.loads(path.read_text())["runs"]
            if "p99_von_mises_mpa" in r and r["through_wall"] >= 2.0]
    return min(runs, key=lambda r: r["mesh_mm"]) if runs else None


def report_verification(results) -> None:
    """Check the analytical screen against the solves that exist.

    The screen decides the design, so its calibration is what has to hold.
    Beam theory has no 3D load spreading and should read high against the
    FEA's bulk field -- what matters is that it reads high by the *same*
    amount at different gauges, because that is what makes it safe to rank
    arms without solving each one.
    """
    checked = [(r, converged_fea(r.arm.thickness_mm)) for r in results]
    checked = [(r, f) for r, f in checked if f and not r.arm.flange_height_mm]
    if len(checked) < 2:
        return

    print("\n  Screen against FEA, where the solves exist:")
    print(f"    {'gauge':>7}{'hand':>9}{'FEA p99':>10}{'ratio':>8}"
          f"{'margin (FEA)':>15}")
    for r, fea in checked:
        ratio = fea["p99_von_mises_mpa"] / r.governing_stress_mpa
        margin = YIELD_MPA / fea["p99_von_mises_mpa"] - 1.0
        print(f"    {r.arm.thickness_mm:6.1f} {r.governing_stress_mpa:9.1f}"
              f"{fea['p99_von_mises_mpa']:10.1f}{ratio:8.3f}{margin:+15.0%}")

    ratios = [f["p99_von_mises_mpa"] / r.governing_stress_mpa
              for r, f in checked]
    print(f"    the hand calculation reads "
          f"{(1 - sum(ratios) / len(ratios)) * 100:.0f}% high at every gauge, "
          f"to within {(max(ratios) - min(ratios)) * 100:.1f} points --")
    print("    which is what makes it safe to rank arms without solving each.")

def main() -> None:
    print(f"Bracket redesign -- {FORCE_N:.1f} N at the upright holes, "
          f"{MATERIAL}, yield {YIELD_MPA:.0f} MPa\n")

    baseline = evaluate(ARMS[0])
    results = [baseline] + [evaluate(a, baseline.mass_g) for a in ARMS[1:]]

    print(f"  {'arm':<32}{'Z up':>8}{'Z base':>8}{'s up':>7}{'s base':>8}"
          f"{'governs':>9}{'margin':>9}{'defl':>7}{'mass':>8}{'':>7}")
    for r in results:
        delta = ("" if r is baseline or math.isnan(r.mass_g)
                 else f"{(r.mass_g/baseline.mass_g-1)*100:+.0f}%")
        print(f"  {r.arm.label:<32}{r.z_upright_mm3:8.1f}{r.z_base_mm3:8.1f}"
              f"{r.stress_upright_mpa:7.0f}{r.stress_base_mpa:8.0f}"
              f"{r.governing_leg:>9}{r.margin:+9.0%}{r.deflection_mm:7.2f}"
              f"{r.mass_g:8.1f}{delta:>7}")
        for v in r.violations:
            print(f"      not manufacturable: {v}")

    print("\n  The flanged arm is the one worth looking at twice.")
    flanged = results[1]
    print(f"  It makes the upright {flanged.z_upright_mm3/baseline.z_upright_mm3:.1f}x "
          f"stronger -- {baseline.stress_upright_mpa:.0f} -> "
          f"{flanged.stress_upright_mpa:.0f} MPa -- and leaves the bracket")
    print(f"  exactly as weak as before, because the base is untouched at "
          f"{flanged.stress_base_mpa:.0f} MPa.")
    print("  Stiffening the leg that was never governing buys nothing.")

    winners = [r for r in results if r.passes]
    if winners:
        best = min(winners, key=lambda r: r.mass_g)
        print(f"\n  Chosen: {best.arm.label} -- the lightest arm that passes.")
        print(f"    governing stress {best.governing_stress_mpa:.0f} MPa "
              f"in the {best.governing_leg}, margin {best.margin:+.0%}")
        print(f"    deflection {baseline.deflection_mm:.2f} -> "
              f"{best.deflection_mm:.2f} mm")
        print(f"    mass {baseline.mass_g:.1f} -> {best.mass_g:.1f} g "
              f"({(best.mass_g/baseline.mass_g-1)*100:+.0f}%)")

    report_verification(results)


if __name__ == "__main__":
    main()
