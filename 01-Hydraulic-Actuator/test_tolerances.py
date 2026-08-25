"""Tests for the limits, fits, geometric tolerances and stack-up.

Pure engineering content -- none of this needs matplotlib or a rendered
sheet. The drawing module is checked separately, and only that it produces
sheets; what the sheets *say* is tested here.
"""

from __future__ import annotations

import pytest

from hydraulic_actuator import HydraulicActuator
from tolerances import (
    FeatureControlFrame,
    Fit,
    StackContributor,
    clevis_end_scheme,
    cylinder_body_scheme,
    hole_limits,
    installed_length_stack,
    it_tolerance,
    piston_rod_scheme,
    shaft_limits,
    stack_up,
)


@pytest.fixture
def actuator():
    return HydraulicActuator(35, 21, 200)


# ── ISO 286 ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("nominal,grade,expected_um", [
    # Spot values read off the published ISO 286-1 table, in micrometres.
    (10, 7, 15), (30, 7, 21), (50, 7, 25),
    (10, 8, 22), (35, 8, 39), (21, 9, 52),
])
def test_it_grades_match_the_published_table(nominal, grade, expected_um):
    assert it_tolerance(nominal, grade) == pytest.approx(expected_um / 1000.0)


def test_tolerance_is_constant_within_a_size_band():
    """ISO 286 quantises by band, so 31 mm and 49 mm share a tolerance and
    50 mm does not -- a property worth pinning, because it is the thing
    people expect to be a smooth function of size and isn't."""
    assert it_tolerance(31, 8) == it_tolerance(49, 8)
    assert it_tolerance(50, 8) != it_tolerance(51, 8)


def test_h_hole_never_falls_below_nominal():
    limits = hole_limits(35, 8)
    assert limits.lower_deviation == 0.0
    assert limits.minimum == 35.0
    assert limits.maximum == pytest.approx(35.039)


def test_f_shaft_sits_entirely_below_nominal():
    limits = shaft_limits(21, "f", 7)
    assert limits.maximum < 21.0
    assert limits.minimum == pytest.approx(21 - 0.041)
    assert limits.maximum == pytest.approx(21 - 0.020)


def test_size_outside_the_table_is_refused():
    with pytest.raises(ValueError):
        it_tolerance(900, 7)
    with pytest.raises(ValueError):
        it_tolerance(-5, 7)


# ── Fits ───────────────────────────────────────────────────────────────────

def test_h8_f7_is_always_a_clearance_fit():
    """The whole point of an f-class shaft in an H-class hole: the parts go
    together at every combination of sizes inside the limits."""
    fit = Fit(hole_limits(21, 8), shaft_limits(21, "f", 7))
    assert fit.is_clearance_fit
    assert fit.minimum_clearance > 0
    assert fit.maximum_clearance > fit.minimum_clearance


def test_clearance_bounds_are_the_extreme_combinations():
    fit = Fit(hole_limits(21, 8), shaft_limits(21, "f", 7))
    assert fit.minimum_clearance == pytest.approx(
        fit.hole.minimum - fit.shaft.maximum)
    assert fit.maximum_clearance == pytest.approx(
        fit.hole.maximum - fit.shaft.minimum)


def test_a_fit_needs_both_members_at_one_nominal_size():
    with pytest.raises(ValueError):
        Fit(hole_limits(20, 8), shaft_limits(21, "f", 7))


# ── Feature control frames ─────────────────────────────────────────────────

def test_form_tolerance_rejects_a_datum():
    """Cylindricity is a property of a feature against itself. Referencing
    a datum from one is a real drafting error, not a stylistic choice."""
    with pytest.raises(ValueError):
        FeatureControlFrame("cylindricity", 0.02, ("A",))


def test_orientation_tolerance_requires_a_datum():
    """Perpendicular to what? Without a datum the callout means nothing."""
    with pytest.raises(ValueError):
        FeatureControlFrame("perpendicularity", 0.05)


def test_tolerance_must_be_positive():
    with pytest.raises(ValueError):
        FeatureControlFrame("flatness", 0.0)


def test_unknown_characteristic_is_refused():
    with pytest.raises(ValueError):
        FeatureControlFrame("wishfulness", 0.1, ("A",))


def test_material_condition_appears_in_the_callout():
    frame = FeatureControlFrame("position", 0.3, ("A", "B", "C"), "M")
    assert "(M)" in frame.callout()
    assert "A B C" in frame.callout()


# ── The actuator's schemes ─────────────────────────────────────────────────

def test_every_scheme_names_its_datums_and_tolerates_its_features(actuator):
    for build in (cylinder_body_scheme, piston_rod_scheme, clevis_end_scheme):
        scheme = build(actuator)
        assert scheme.datums, f"{scheme.part_name} has no datum scheme"
        assert scheme.sizes, f"{scheme.part_name} has no toleranced sizes"
        assert scheme.geometric, f"{scheme.part_name} has no geometric tolerances"
        assert scheme.surface_finish, f"{scheme.part_name} has no finish called out"
        assert scheme.general_note


def test_geometric_tolerances_only_reference_declared_datums(actuator):
    """A control frame pointing at a datum the drawing never defines is
    unbuildable, and is exactly the kind of thing that survives a visual
    check of a sheet."""
    for build in (cylinder_body_scheme, piston_rod_scheme, clevis_end_scheme):
        scheme = build(actuator)
        for frame in scheme.geometric:
            for datum in frame.datums:
                assert datum in scheme.datums, (
                    f"{scheme.part_name}: {frame.name} references datum "
                    f"{datum}, which the drawing does not define")


def test_bore_and_rod_tolerances_track_the_model(actuator):
    assert cylinder_body_scheme(actuator).sizes[0].nominal == actuator.bore
    assert piston_rod_scheme(actuator).sizes[0].nominal == actuator.rod


def test_sealing_surfaces_are_the_finest_finishes(actuator):
    """The rod runs through a dynamic seal, so it must be finer than the
    bore, which is finer than anything merely machined."""
    rod = piston_rod_scheme(actuator).surface_finish["ROD DIAMETER"]
    bore = cylinder_body_scheme(actuator).surface_finish["BORE"]
    outside = cylinder_body_scheme(actuator).surface_finish["OUTSIDE DIAMETER"]
    assert rod < bore < outside


def test_clevis_bolt_holes_carry_position_at_mmc(actuator):
    frames = {f.characteristic: f for f in clevis_end_scheme(actuator).geometric}
    assert frames["position"].material_condition == "M"


@pytest.mark.parametrize("bore,rod,stroke", [
    (16, 10, 100), (25, 15, 150), (35, 21, 200), (50, 30, 250)])
def test_schemes_build_for_every_family_member(bore, rod, stroke):
    unit = HydraulicActuator(bore, rod, stroke)
    for build in (cylinder_body_scheme, piston_rod_scheme, clevis_end_scheme):
        assert build(unit).sizes


# ── Stack-up ───────────────────────────────────────────────────────────────

def test_worst_case_is_never_tighter_than_rss():
    """Arithmetic addition cannot come out below addition in quadrature.
    If it ever does, the stack has been built wrong."""
    result = stack_up([StackContributor("a", 10, 0.1),
                       StackContributor("b", 10, 0.2),
                       StackContributor("c", 10, 0.3)])
    assert result.worst_case >= result.rss


def test_rss_matches_the_closed_form():
    result = stack_up([StackContributor("a", 0, 0.3),
                       StackContributor("b", 0, 0.4)])
    assert result.rss == pytest.approx(0.5)      # 3-4-5
    assert result.worst_case == pytest.approx(0.7)


def test_sense_controls_whether_a_dimension_adds_or_subtracts():
    adds = stack_up([StackContributor("a", 10, 0.1, +1)])
    subtracts = stack_up([StackContributor("a", 10, 0.1, -1)])
    assert adds.nominal == 10
    assert subtracts.nominal == -10
    # Direction never reduces the spread -- a subtracted dimension's
    # variation still widens the gap it feeds.
    assert adds.worst_case == subtracts.worst_case


def test_an_empty_stack_is_refused():
    with pytest.raises(ValueError):
        stack_up([])


def test_installed_length_matches_the_assembled_model(actuator):
    """The stack's nominal has to agree with where assembly() actually puts
    the clevis, or the drawing is dimensioning a different part from the
    one the generator builds."""
    _, result = installed_length_stack(actuator)
    clevis = next(child for child in actuator.assembly().children
                  if child.name == "clevis_end")
    box = clevis.obj.val().BoundingBox()
    pin_bore_axis_z = (box.zmin + box.zmax) / 2.0
    assert result.nominal == pytest.approx(pin_bore_axis_z)


def test_rod_engagement_subtracts_from_installed_length(actuator):
    contributors, _ = installed_length_stack(actuator)
    engagement = next(c for c in contributors if "ENGAGEMENT" in c.name)
    assert engagement.sense == -1
