"""Tests for the closed-form beam check.

These are cheap and they guard the thing most likely to go quietly wrong:
the hand calculation is the FEA's only independent reference, so if it
drifts, the FEA loses the check that makes it trustworthy.
"""

import json
import math
from pathlib import Path

import pytest

from beam_check import (
    HOLE_DIAMETER_MM,
    BASE_ARM_MM,
    FORCE_N,
    THICKNESS_MM,
    UPRIGHT_ARM_MM,
    WIDTH_MM,
    YIELD_MPA,
    bracket_estimate,
    estimate,
    kt_hole_in_plate,
)


def test_section_properties_match_the_rectangle_formulas():
    e = estimate(100.0, 30.0, 40.0, 50.0, 2.0)
    assert e.second_moment_mm4 == pytest.approx(50.0 * 2.0 ** 3 / 12.0)
    assert e.section_modulus_mm3 == pytest.approx(50.0 * 2.0 ** 2 / 6.0)


def test_stress_is_moment_over_section_modulus():
    e = estimate(100.0, 30.0, 40.0, 50.0, 2.0)
    assert e.moment_n_mm == pytest.approx(100.0 * 30.0)
    assert e.bending_stress_mpa == pytest.approx(
        e.moment_n_mm / e.section_modulus_mm3)


def test_bending_stress_scales_with_thickness_squared():
    """Doubling the gauge should quarter the stress -- Z goes as t^2."""
    thin = estimate(100.0, 30.0, 40.0, 50.0, 1.6)
    thick = estimate(100.0, 30.0, 40.0, 50.0, 3.2)
    assert thick.bending_stress_mpa == pytest.approx(
        thin.bending_stress_mpa / 4.0)


def test_deflection_scales_with_thickness_cubed():
    """And should divide deflection by eight -- I goes as t^3."""
    thin = estimate(100.0, 30.0, 40.0, 50.0, 1.6)
    thick = estimate(100.0, 30.0, 40.0, 50.0, 3.2)
    assert thick.total_deflection_mm == pytest.approx(
        thin.total_deflection_mm / 8.0)


def test_base_flexibility_dominates_the_deflection():
    """The finding that a one-cantilever idealisation would have missed.

    Most of the tip movement is the base rotating, not the upright bending.
    If this ever flips, the second term in `estimate` has stopped mattering
    and the model has quietly changed.
    """
    e = bracket_estimate()
    from_base = e.base_rotation_rad * UPRIGHT_ARM_MM
    assert from_base > e.upright_deflection_mm * 3.0


def test_the_bracket_is_over_yield_at_9g():
    """Pins the actual engineering result, not just the arithmetic."""
    e = bracket_estimate()
    assert e.bending_stress_mpa > YIELD_MPA
    assert e.margin_of_safety < 0.0


def test_kt_approaches_three_for_a_small_hole():
    """The classic wide-plate result an approximation must reproduce."""
    assert kt_hole_in_plate(0.001, 1000.0) == pytest.approx(3.0, abs=1e-3)


def test_kt_falls_as_the_hole_grows():
    wide = kt_hole_in_plate(2.0, 50.0)
    narrow = kt_hole_in_plate(20.0, 50.0)
    assert narrow < wide < 3.0


def test_kt_rejects_impossible_geometry():
    with pytest.raises(ValueError):
        kt_hole_in_plate(60.0, 50.0)
    with pytest.raises(ValueError):
        kt_hole_in_plate(-1.0, 50.0)


def test_upright_arm_is_shorter_than_the_hole_height():
    """The bend line is a thickness plus a radius up from the base, so the
    lever arm is not the 33 mm hole height. Getting this wrong inflates the
    moment by about 16%."""
    assert UPRIGHT_ARM_MM == pytest.approx(28.4)


# --- Cross-checks against the FEA -------------------------------------
#
# These only run once fea.py has been executed under FreeCAD. They are the
# point of having a hand calculation at all: on their own, neither the
# closed form nor the solver can tell you it is wrong.

needs_fea = pytest.mark.skipif(
    not Path("fea_results.json").exists(),
    reason="run fea.py under FreeCAD first")

BORE_RADIUS_MM = HOLE_DIAMETER_MM / 2.0


def _results():
    return json.loads(Path("fea_results.json").read_text())


def _trusted():
    """Runs with at least two quadratic elements through the wall."""
    runs = [r for r in _results()["runs"] if "max_von_mises_mpa" in r]
    trusted = sorted((r for r in runs if r["through_wall"] >= 2.0),
                     key=lambda r: r["nodes"])
    assert len(trusted) >= 2, "need two usable mesh densities to judge trends"
    return trusted


def _change(field, runs):
    a, b = runs[-2:]
    return abs(b[field] - a[field]) / a[field]


@needs_fea
def test_at_least_one_mesh_resolved_the_wall_in_bending():
    """A mesh coarser than the wall cannot represent bending, whatever
    number it comes back with -- a single element through the thickness has
    no way to carry a linear stress gradient across it."""
    solved = [r for r in _results()["runs"] if "max_von_mises_mpa" in r]
    assert any(r["through_wall"] >= 2.0 for r in solved)


@needs_fea
def test_deflection_converges():
    """Displacement is an integral of the solution, so it settles fast and
    is the quantity worth quoting from this model."""
    assert _change("max_displacement_mm", _trusted()) < 0.005


@needs_fea
def test_bulk_stress_converges():
    """The 99th percentile is stable to well under a percent."""
    assert _change("p99_von_mises_mpa", _trusted()) < 0.01


@needs_fea
def test_peak_stress_does_not_converge():
    """The finding, pinned so it cannot quietly stop being true.

    If someone later rounds the constrained edge or swaps the fixed
    constraint for something compliant, the peak will start converging and
    this test will fail -- which is the correct outcome, because the
    README's whole argument would then need rewriting.
    """
    trusted = _trusted()

    def spread(field):
        values = [r[field] for r in trusted]
        return (max(values) - min(values)) / (sum(values) / len(values))

    assert spread("max_von_mises_mpa") > 5.0 * spread("p99_von_mises_mpa")


@needs_fea
def test_the_peak_sits_on_the_constraint_boundary():
    """Why the peak diverges: it is on the edge of the fixed constraint.

    A fixed boundary condition on a face is singular at that face's
    boundary -- the elastic solution has no finite stress there, so the
    discrete answer just tracks element size. Every peak node landing on
    the bore edge of a constrained hole, on a flat face of the base, is
    what distinguishes this from a real stress concentration.
    """
    for run in _trusted():
        x, y, z = run["peak_location_mm"]
        centre_y = 13.0 if y > 0 else -13.0
        radius = math.hypot(x - 48.0, y - centre_y)
        assert abs(radius - BORE_RADIUS_MM) < 1.0, (
            f"peak at r={radius:.2f} is not on the bore edge "
            f"(r={BORE_RADIUS_MM})")
        assert min(abs(z), abs(z - THICKNESS_MM)) < 0.05, (
            f"peak at z={z} is not on a flat face of the base")


@needs_fea
def test_the_peak_wanders_between_the_two_holes():
    """A real stress concentration stays put. This one does not: which hole
    wins is decided by whichever node the mesher happened to place worst,
    and that is a second, independent signature of a singularity."""
    sides = {1 if r["peak_location_mm"][1] > 0 else -1 for r in _trusted()}
    assert len(sides) == 2, (
        "peak stayed on one hole across all meshes -- it may be a genuine "
        "concentration rather than the constraint artefact assumed here")


@needs_fea
def test_converged_bulk_stress_agrees_with_the_hand_calculation():
    """The order-of-magnitude check that catches a wrong unit or constraint.

    Beam theory ignores 3D load spreading, so it should read somewhat high
    against the FEA's bulk field -- but within a factor, not an order.
    """
    bulk = _trusted()[-1]["p99_von_mises_mpa"]
    nominal = bracket_estimate().bending_stress_mpa
    assert 0.5 < bulk / nominal < 1.5


@needs_fea
def test_the_bracket_does_not_survive_9g():
    """Both methods independently put the bracket past yield. That verdict,
    not the 545 MPa peak, is the engineering result."""
    bulk = _trusted()[-1]["p99_von_mises_mpa"]
    assert bulk > _results()["yield_mpa"]
    assert bracket_estimate().bending_stress_mpa > YIELD_MPA
