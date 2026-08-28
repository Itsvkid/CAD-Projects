"""Tests for the swept geometry. Needs pyOCC.

    conda run -n pyocc_env python -m pytest test_duct.py -q
"""

from __future__ import annotations

import math

import pytest

from build import BLEED, ROUTE_INITIAL, ROUTE_REVISED, obstructions
from duct import RoutedDuct, minimum_distance, volume_mm3
from sizing import required_clearance_mm, size_duct


@pytest.fixture(scope="module")
def design():
    return size_duct(BLEED)


@pytest.fixture(scope="module")
def duct(design):
    return RoutedDuct(design, ROUTE_REVISED)


def test_the_swept_solid_is_valid(duct):
    assert duct.is_valid()


def test_route_is_longer_than_the_straight_line(duct):
    """A routed duct that measured the same as point-to-point would mean
    the spline had collapsed."""
    start, end = ROUTE_REVISED[0], ROUTE_REVISED[-1]
    straight = math.dist(start, end)
    assert duct.route_length_mm() > straight


def test_swept_volume_matches_the_annulus_it_sweeps(design):
    """Independent check on the sweep: a straight run's volume must equal
    the wall's cross-sectional area times its length. If MakePipe ever
    silently produced something else, this catches it -- flanges excluded,
    since they are fused on afterwards."""
    straight = RoutedDuct(design, [(0, 0, 0), (600, 0, 0)])
    r_o = design.outer_diameter_mm / 2
    r_i = design.bore_mm / 2
    expected = math.pi * (r_o ** 2 - r_i ** 2) * 600.0
    swept = volume_mm3(straight._swept(r_o)) - volume_mm3(straight._swept(r_i))
    assert swept == pytest.approx(expected, rel=1e-6)


def test_mass_exceeds_bare_tube_because_of_the_flanges(duct, design):
    bare = design.mass_per_metre_kg() * duct.route_length_mm() / 1000.0
    assert duct.mass_kg() > bare


def test_a_two_point_route_is_the_minimum(design):
    with pytest.raises(ValueError):
        RoutedDuct(design, [(0, 0, 0)])


# ── Clearance ──────────────────────────────────────────────────────────────

def test_the_initial_route_is_rejected(design):
    """The route that looks right and is not. It fouls the casing outright,
    which is the whole reason the clearance query exists."""
    candidate = RoutedDuct(design, ROUTE_INITIAL)
    solid = candidate.solid()
    needed = required_clearance_mm(design, candidate.route_length_mm())
    gaps = [minimum_distance(solid, o) for o in obstructions().values()]
    assert min(gaps) < needed


def test_the_revised_route_clears_everything(duct, design):
    needed = required_clearance_mm(design, duct.route_length_mm())
    solid = duct.solid()
    for name, obstacle in obstructions().items():
        assert minimum_distance(solid, obstacle) >= needed, name


def test_clearance_allows_for_thermal_growth(duct, design):
    """The requirement is not arbitrary: it must exceed how much the duct
    actually grows, or it is measuring the cold build and nothing else."""
    from sizing import thermal_growth_mm
    length = duct.route_length_mm()
    assert (required_clearance_mm(design, length)
            > thermal_growth_mm(design, length))


def test_a_shape_has_zero_distance_to_itself(duct):
    solid = duct.solid()
    assert minimum_distance(solid, solid) == pytest.approx(0.0)
