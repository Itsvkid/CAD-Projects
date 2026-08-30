"""Tests for the section properties and the redesign trade study."""

import json
from pathlib import Path

import pytest

from beam_check import (
    BASE_ARM_MM,
    FORCE_N,
    UPRIGHT_ARM_MM,
    WIDTH_MM,
    YIELD_MPA,
    channel_section,
    estimate,
    plate_section,
)
from trade_study import ARMS, Arm, converged_fea, evaluate


@pytest.fixture(scope="session")
def results():
    baseline = evaluate(ARMS[0])
    return [baseline] + [evaluate(a, baseline.mass_g) for a in ARMS[1:]]


# --- Section properties -------------------------------------------------


def test_plate_section_matches_the_rectangle_formulas():
    second_moment, modulus = plate_section(50.0, 1.6)
    assert second_moment == pytest.approx(50.0 * 1.6 ** 3 / 12.0)
    assert modulus == pytest.approx(50.0 * 1.6 ** 2 / 6.0)


def test_a_channel_with_no_flange_is_a_plate():
    """The degenerate case has to agree, or the two are not comparable and
    the whole trade table is built on a discontinuity."""
    assert channel_section(50.0, 1.6, 0.0) == plate_section(50.0, 1.6)


def test_flanges_dominate_through_their_offset_not_their_own_stiffness():
    """A 12 mm flange's own I about its centroid is small; nearly all of
    the gain is A*d^2. If that stops being true the neutral-axis term has
    been dropped."""
    _, plain = plate_section(50.0, 1.6)
    _, flanged = channel_section(50.0, 1.6, 12.0)
    assert flanged > 7 * plain

    own_stiffness_only = 2 * (1.6 * 12.0 ** 3 / 12.0) + 50.0 * 1.6 ** 3 / 12.0
    full, _ = channel_section(50.0, 1.6, 12.0)
    assert full > 2 * own_stiffness_only


def test_deeper_flanges_are_stiffer():
    moduli = [channel_section(50.0, 1.6, h)[1] for h in (0, 4, 8, 12, 16)]
    assert all(b > a for a, b in zip(moduli, moduli[1:]))


# --- The trade study ----------------------------------------------------


def test_the_baseline_fails(results):
    assert not results[0].passes
    assert results[0].margin < 0


def test_the_bracket_is_as_weak_as_its_worse_leg(results):
    for r in results:
        assert r.governing_stress_mpa == max(r.stress_upright_mpa,
                                             r.stress_base_mpa)


def test_stiffening_only_the_upright_buys_nothing(results):
    """The finding, pinned.

    Folding flanges up the upright's free edges makes that leg over seven
    times stronger and leaves the part's margin unchanged, because the base
    reacts the same moment through the same unflanged section. If this ever
    starts passing, either the base has been flanged too or the load path
    has changed, and the trade study needs rewriting rather than quietly
    recommending a part that does not work.
    """
    baseline, flanged = results[0], results[1]
    assert flanged.arm.flange_height_mm > 0

    assert flanged.stress_upright_mpa < baseline.stress_upright_mpa / 5
    assert flanged.governing_leg == "base"
    assert flanged.governing_stress_mpa == pytest.approx(
        baseline.governing_stress_mpa, rel=1e-9)
    assert not flanged.passes
    assert flanged.mass_g > baseline.mass_g, "and it costs mass to achieve"


def test_the_gauge_arms_pass(results):
    for r in results[2:]:
        assert r.passes, f"{r.arm.label} margin {r.margin:+.0%}"


def test_the_chosen_arm_is_the_lightest_that_passes(results):
    passing = [r for r in results if r.passes]
    assert passing
    best = min(passing, key=lambda r: r.mass_g)
    assert best.arm.label == "2.0 mm gauge"
    assert best.margin > 0.25


def test_going_thicker_always_costs_mass_and_buys_margin(results):
    gauge = sorted((r for r in results if not r.arm.flange_height_mm),
                   key=lambda r: r.arm.thickness_mm)
    assert all(b.mass_g > a.mass_g for a, b in zip(gauge, gauge[1:]))
    assert all(b.margin > a.margin for a, b in zip(gauge, gauge[1:]))


def test_stress_falls_as_the_square_of_gauge(results):
    """Z goes as t^2, so 1.6 -> 2.0 should cut stress by (1.6/2.0)^2."""
    thin = next(r for r in results if r.arm.thickness_mm == 1.6
                and not r.arm.flange_height_mm)
    thick = next(r for r in results if r.arm.thickness_mm == 2.0)
    assert thick.governing_stress_mpa == pytest.approx(
        thin.governing_stress_mpa * (1.6 / 2.0) ** 2, rel=1e-6)


def test_every_buildable_arm_is_manufacturable(results):
    """A redesign that cannot be folded is not a redesign. 5052-H32 takes a
    1T inside radius, so a 3 mm radius stays legal as gauge rises -- but
    that is a fact about this alloy, not a general one, and it is worth a
    test rather than an assumption."""
    for r in results:
        if r.arm.buildable:
            assert not r.violations, f"{r.arm.label}: {r.violations}"


def test_a_thick_gauge_would_eventually_break_the_bend():
    """The counter-case, so the test above is known to be capable of
    failing: at 4 mm the 3 mm inside radius drops below 1T and 5052-H32
    cracks on the outside of the fold."""
    assert evaluate(Arm("4.0 mm gauge", 4.0)).violations


# --- The screen checked against the solves ------------------------------

needs_both_solves = pytest.mark.skipif(
    not (Path("fea_results.json").is_file()
         and Path("fea_results_2mm.json").is_file()),
    reason="run fea.py on both gauges first")


@needs_both_solves
def test_the_fea_confirms_the_chosen_arm_passes(results):
    """The screen said +28%. The solver is the one that has to agree."""
    chosen = next(r for r in results if r.arm.thickness_mm == 2.0)
    fea = converged_fea(2.0)
    assert fea is not None
    assert YIELD_MPA / fea["p99_von_mises_mpa"] - 1.0 > 0.25
    assert chosen.passes


@needs_both_solves
def test_the_fea_confirms_the_baseline_fails(results):
    fea = converged_fea(1.6)
    assert fea["p99_von_mises_mpa"] > YIELD_MPA


@needs_both_solves
def test_the_hand_calculation_is_conservative_by_a_constant_factor():
    """The assumption the whole trade study rests on.

    Every arm is ranked by beam theory and only the winner is solved. That
    is only legitimate if the beam model's error does not vary with the
    thing being changed. It reads about 16% high at both gauges, and the
    two ratios agree to a fraction of a point -- so a gauge change does not
    move the calibration, and the ranking holds.

    If this ever fails, the screen has stopped being trustworthy and every
    arm needs its own solve before anything is recommended.
    """
    ratios = []
    for thickness in (1.6, 2.0):
        fea = converged_fea(thickness)
        hand = estimate(FORCE_N, UPRIGHT_ARM_MM, BASE_ARM_MM,
                        WIDTH_MM, thickness)
        ratios.append(fea["p99_von_mises_mpa"] / hand.bending_stress_mpa)

    assert all(0.7 < r < 1.0 for r in ratios), ratios
    assert abs(ratios[0] - ratios[1]) < 0.03, (
        f"beam model calibration moved with gauge: {ratios}")


@needs_both_solves
def test_the_thicker_gauge_actually_deflects_less_in_the_solver():
    """Stiffness is the other half of the reason for going thicker, and it
    is the half beam theory is worst at -- so it is worth confirming."""
    thin, thick = converged_fea(1.6), converged_fea(2.0)
    assert thick["max_displacement_mm"] < thin["max_displacement_mm"] / 1.8


@needs_both_solves
def test_the_peak_still_diverges_on_the_redesign():
    """The redesign does not fix the singularity, and should not appear to.
    It is a property of the constraint, not of the part's thickness."""
    runs = [r for r in json.loads(Path("fea_results_2mm.json").read_text())["runs"]
            if "p99_von_mises_mpa" in r and r["through_wall"] >= 2.0]
    peaks = [r["max_von_mises_mpa"] for r in runs]
    p99s = [r["p99_von_mises_mpa"] for r in runs]

    def spread(values):
        return (max(values) - min(values)) / (sum(values) / len(values))

    assert spread(peaks) > 5 * spread(p99s)
    for run in runs:
        z = run["peak_location_mm"][2]
        assert min(abs(z), abs(z - 2.0)) < 0.05, "peak left the constraint face"
