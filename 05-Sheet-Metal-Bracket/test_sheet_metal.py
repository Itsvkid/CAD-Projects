"""Tests for the forming arithmetic, the DFM rules, and the bracket.

The arithmetic tests need nothing but Python. The geometry tests need
CadQuery, and are what check that the flat pattern and the formed part
actually describe the same piece of metal.
"""

from __future__ import annotations

import math

import pytest

from bracket import AngleBracket
from sheet_metal import (
    MATERIALS,
    Bend,
    bend_allowance,
    bend_deduction,
    check_bend_radius,
    check_edge_distance,
    check_flange_length,
    check_hole_to_bend,
    flat_length,
    k_factor,
    outside_setback,
)


# ── Forming arithmetic ─────────────────────────────────────────────────────

def test_bend_allowance_matches_the_closed_form():
    ba = bend_allowance(90, 3.0, 1.6)
    expected = math.radians(90) * (3.0 + k_factor(3.0, 1.6) * 1.6)
    assert ba == pytest.approx(expected)


def test_setback_at_ninety_degrees_is_radius_plus_thickness():
    """tan(45°) = 1, so the general formula collapses to R + T -- the one
    case worth pinning by hand, since 90° is most of sheet metal."""
    assert outside_setback(90, 3.0, 1.6) == pytest.approx(4.6)


def test_k_factor_moves_outward_as_the_bend_opens_up():
    """A tighter bend forces the neutral axis inward. If this ever
    inverts, every flat length computed from it is wrong in a way that
    still looks plausible."""
    tight = k_factor(0.5, 1.6)
    medium = k_factor(3.0, 1.6)
    loose = k_factor(10.0, 1.6)
    assert tight < medium < loose
    assert 0.3 <= tight and loose <= 0.5


def test_neutral_axis_stays_inside_the_material():
    for radius in (0.1, 1.0, 3.0, 20.0):
        assert 0.0 < k_factor(radius, 1.6) < 1.0


def test_blank_is_shorter_than_the_summed_outside_legs():
    """The entire point. A blank cut to the summed legs is too long by one
    bend deduction per fold, and every part in the batch is wrong the same
    way."""
    legs = [60.0, 45.0]
    length = flat_length(legs, [Bend(90, 3.0)], 1.6)
    assert length < sum(legs)
    assert sum(legs) - length == pytest.approx(bend_deduction(90, 3.0, 1.6))


def test_more_bends_remove_more_material():
    one = flat_length([40, 40], [Bend(90, 3.0)], 1.6)
    two = flat_length([40, 20, 40], [Bend(90, 3.0), Bend(90, 3.0)], 1.6)
    assert (40 + 20 + 40) - two > (40 + 40) - one


def test_leg_and_bend_counts_must_agree():
    with pytest.raises(ValueError):
        flat_length([60.0, 45.0], [Bend(90, 3.0), Bend(90, 3.0)], 1.6)


@pytest.mark.parametrize("angle", [0, -10, 181])
def test_impossible_bend_angles_are_refused(angle):
    with pytest.raises(ValueError):
        bend_allowance(angle, 3.0, 1.6)


# ── Material and DFM rules ─────────────────────────────────────────────────

def test_harder_alloys_need_larger_bend_radii():
    """The trade that decides the material choice: 2024-T3 is far stronger
    than 5052-H32 and will not fold anywhere near as tightly."""
    hard = MATERIALS["2024-T3"]
    soft = MATERIALS["5052-H32"]
    assert hard.tensile_mpa > soft.tensile_mpa
    assert hard.min_bend_radius_factor > soft.min_bend_radius_factor


def test_bend_radius_rule_fires_on_the_hard_alloy_and_not_the_soft_one():
    thickness, radius = 1.6, 3.0
    assert check_bend_radius(MATERIALS["2024-T3"], thickness, radius) is not None
    assert check_bend_radius(MATERIALS["5052-H32"], thickness, radius) is None


def test_bend_radius_rule_passes_exactly_at_the_limit():
    material = MATERIALS["2024-T3"]
    assert check_bend_radius(material, 1.6, material.minimum_bend_radius(1.6)) is None


def test_short_flange_is_rejected():
    assert check_flange_length(1.6, 3.0, 5.0) is not None
    assert check_flange_length(1.6, 3.0, 20.0) is None


def test_hole_too_near_a_bend_is_rejected():
    assert check_hole_to_bend(1.6, 3.0, 2.0) is not None
    assert check_hole_to_bend(1.6, 3.0, 10.0) is None


def test_edge_distance_rule_has_a_stricter_preferred_form():
    assert check_edge_distance(5.1, 11.0) is None
    assert check_edge_distance(5.1, 11.0, preferred=True) is not None


def test_a_violation_reports_both_actual_and_required():
    violation = check_edge_distance(5.1, 8.0)
    assert violation.actual == pytest.approx(8.0)
    assert violation.required == pytest.approx(10.2)
    assert "8.00" in str(violation) and "10.20" in str(violation)


# ── The bracket ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def bracket():
    return AngleBracket()


def test_reference_design_is_manufacturable(bracket):
    assert bracket.violations() == []
    bracket.assert_manufacturable()


def test_a_bad_design_reports_every_problem_at_once():
    """Three things wrong should give three violations, not the first one
    and a re-run."""
    bad = AngleBracket(material="2024-T3", inside_radius=1.0,
                       upright_length=4.0, hole_pitch=46.0)
    problems = {v.rule for v in bad.violations()}
    assert {"MIN BEND RADIUS", "MIN FLANGE LENGTH", "EDGE DISTANCE"} <= problems
    with pytest.raises(ValueError):
        bad.assert_manufacturable()


def test_unknown_material_is_refused():
    with pytest.raises(ValueError):
        AngleBracket(material="unobtainium")


def test_formed_and_flat_are_valid_single_solids(bracket):
    from OCP.BRepCheck import BRepCheck_Analyzer
    for build in (bracket.formed, bracket.flat_pattern):
        shape = build()
        assert len(shape.solids().vals()) == 1
        assert BRepCheck_Analyzer(shape.val().wrapped).IsValid()


def test_formed_and_flat_have_the_same_holes(bracket):
    """Same part, same holes. This is the test that was missing.

    The formed solid shipped for a while with two of its four holes
    absent: the upright pair was cut on a face-relative workplane whose
    frame put them outside the material, and CadQuery treats a hole that
    misses the solid as a no-op rather than an error. Nothing complained,
    and the volume check below passed anyway -- see its docstring.
    """
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder

    def hole_centres(shape):
        found = []
        for face in shape.Faces():
            surface = BRepAdaptor_Surface(face.wrapped)
            if surface.GetType() != GeomAbs_Cylinder:
                continue
            if abs(surface.Cylinder().Radius()
                   - bracket.hole_diameter / 2) < 1e-6:
                found.append(face.Center())
        return found

    formed = hole_centres(bracket.formed().val())
    flat = hole_centres(bracket.flat_pattern().val())
    assert len(formed) == 4, f"formed part has {len(formed)} holes, expected 4"
    assert len(flat) == 4, f"flat pattern has {len(flat)} holes, expected 4"


def test_forming_conserves_volume(bracket):
    """The independent check on the whole flat-pattern calculation.

    Bending moves metal, it does not create or destroy it, so the blank and
    the formed part must have the same volume. They agree to 0.25%, which
    is the residual of modelling the neutral axis as a single K-factor
    against the exact toroidal geometry of the fillet.

    **This test used to pass at 1.07% with two holes missing from the
    formed part.** The absent holes added material, the K-factor
    approximation removed some, the two partly cancelled, and a 2%
    tolerance swallowed what was left. A check is only as sharp as its
    bound: this one was measuring the right quantity and was set too loose
    to notice a defect twice its own residual. The bound is now 0.5%, and
    `test_formed_and_flat_have_the_same_holes` covers what volume alone
    cannot.
    """
    formed = bracket.formed().val().Volume()
    flat = bracket.flat_pattern().val().Volume()
    assert formed == pytest.approx(flat, rel=0.005)

    naive = ((bracket.base_length + bracket.upright_length)
             * bracket.width * bracket.thickness)
    assert abs(naive - flat) > abs(formed - flat) * 3


def test_bend_zone_length_is_the_bend_allowance(bracket):
    start, end = bracket.bend_zone
    assert end - start == pytest.approx(bracket.bend_allowance)
    assert 0 < start < end < bracket.flat_length


def test_bend_line_sits_at_the_centre_of_the_bend_zone(bracket):
    start, end = bracket.bend_zone
    assert bracket.bend_line == pytest.approx((start + end) / 2)


def test_flat_pattern_is_a_constant_thickness_blank(bracket):
    box = bracket.flat_pattern().val().BoundingBox()
    assert box.zlen == pytest.approx(bracket.thickness)
    assert box.xlen == pytest.approx(bracket.flat_length)
    assert box.ylen == pytest.approx(bracket.width)


def test_formed_part_fits_its_outside_dimensions(bracket):
    box = bracket.formed().val().BoundingBox()
    assert box.xlen == pytest.approx(bracket.base_length)
    assert box.zlen == pytest.approx(bracket.upright_length)
    assert box.ylen == pytest.approx(bracket.width)


@pytest.mark.parametrize("thickness,radius,base,upright", [
    (1.0, 2.0, 50.0, 40.0), (1.6, 3.0, 60.0, 45.0), (2.5, 4.0, 80.0, 60.0)])
def test_the_generator_scales(thickness, radius, base, upright):
    unit = AngleBracket(thickness=thickness, inside_radius=radius,
                        base_length=base, upright_length=upright)
    assert unit.violations() == []
    assert unit.flat_length < base + upright
    assert unit.formed().val().Volume() == pytest.approx(
        unit.flat_pattern().val().Volume(), rel=0.01)
