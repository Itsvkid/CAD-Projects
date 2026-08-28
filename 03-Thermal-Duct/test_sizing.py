"""Tests for the duct sizing arithmetic and material selection.

No pyOCC here -- this is the engineering, and it runs on any Python with
pytest. Geometry is tested separately in test_duct.py, which does need the
kernel.
"""

from __future__ import annotations

import math

import pytest

from sizing import (
    GAMMA_AIR,
    MATERIALS,
    R_AIR,
    STANDARD_GAUGES_MM,
    BleedCondition,
    bend_thinning_factor,
    bore_diameter_m,
    duct_mach_number,
    hoop_wall_thickness_m,
    required_clearance_mm,
    select_material,
    size_duct,
    thermal_growth_mm,
)

# Station 3 of the reference cycle design point.
HPC_EXIT = BleedCondition(759.5, 1_251_651.0, 1.0)


def test_density_matches_the_ideal_gas_law():
    assert HPC_EXIT.density_kg_m3 == pytest.approx(
        HPC_EXIT.total_pressure_pa / (R_AIR * HPC_EXIT.total_temperature_k))


def test_speed_of_sound_matches_closed_form():
    assert HPC_EXIT.speed_of_sound_m_s() == pytest.approx(
        math.sqrt(GAMMA_AIR * R_AIR * HPC_EXIT.total_temperature_k))


def test_bore_passes_the_requested_flow():
    """Continuity, checked backwards: the bore this returns must carry the
    mass flow it was given at the velocity it was given."""
    velocity = 50.0
    d = bore_diameter_m(HPC_EXIT, velocity)
    area = math.pi * d ** 2 / 4
    assert area * velocity * HPC_EXIT.density_kg_m3 == pytest.approx(
        HPC_EXIT.mass_flow_kg_s)


def test_faster_flow_needs_a_smaller_bore():
    assert bore_diameter_m(HPC_EXIT, 80.0) < bore_diameter_m(HPC_EXIT, 30.0)


def test_design_velocity_stays_incompressible():
    """The sizing uses incompressible continuity, which is only defensible
    below roughly Mach 0.3. If a change ever pushes past it, this fails
    before the numbers quietly stop meaning anything."""
    assert duct_mach_number(HPC_EXIT, 50.0) < 0.3


def test_hoop_thickness_matches_the_closed_form():
    t = hoop_wall_thickness_m(1e6, 0.05, 200e6, safety_factor=1.5)
    assert t == pytest.approx(1e6 * 0.05 * 1.5 / (2 * 200e6))


def test_thin_wall_assumption_holds_for_this_duct():
    """Thin-wall hoop stress needs t/d well under about 0.05."""
    design = size_duct(HPC_EXIT)
    assert design.wall_mm / design.bore_mm < 0.05


@pytest.mark.parametrize("bend_d,expected", [(1.0, 2 / 3), (2.0, 0.8), (3.0, 6 / 7)])
def test_bend_thinning_matches_the_geometry(bend_d, expected):
    """t_out/t = R/(R + D/2). At 2D that is 0.8 -- the 20% thinning a tube
    bender quotes for a standard bend."""
    diameter = 50.0
    assert bend_thinning_factor(bend_d * diameter, diameter) == pytest.approx(expected)


def test_tighter_bends_thin_more():
    assert (bend_thinning_factor(50.0, 50.0)
            < bend_thinning_factor(150.0, 50.0))


# ── Material selection ─────────────────────────────────────────────────────

def test_aluminium_is_excluded_by_compressor_bleed_temperature():
    """759 K is far past what 6061 survives. If selection ever returns it,
    something is very wrong."""
    assert select_material(HPC_EXIT).name != "Aluminium 6061-T6"


def test_titanium_is_excluded_at_this_temperature_but_chosen_when_cooler():
    """The trade that makes the selection interesting: titanium is lighter
    than steel and would win on weight, and it is ruled out purely on
    temperature."""
    assert select_material(HPC_EXIT).name != "Titanium 6Al-4V"
    # Cold fan air: aluminium survives and is lighter, so it wins.
    assert select_material(BleedCondition(330.0, 200_000.0, 1.0)).name \
        == "Aluminium 6061-T6"
    # Warm enough to rule aluminium out, cool enough for titanium: the one
    # band where titanium is the answer.
    assert select_material(BleedCondition(560.0, 400_000.0, 1.0)).name \
        == "Titanium 6Al-4V"


def test_selection_returns_the_lightest_survivor():
    chosen = select_material(HPC_EXIT)
    survivors = [m for m in MATERIALS.values()
                 if m.max_service_k >= HPC_EXIT.total_temperature_k + 50]
    assert chosen.density_kg_m3 == min(m.density_kg_m3 for m in survivors)


def test_impossible_temperature_is_refused():
    with pytest.raises(ValueError):
        select_material(BleedCondition(2000.0, 1e6, 1.0))


# ── The constraint chain ───────────────────────────────────────────────────

def test_wall_is_a_standard_gauge():
    assert size_duct(HPC_EXIT).wall_mm in STANDARD_GAUGES_MM


def test_bend_thinning_governs_this_design():
    """The finding this project exists to make. Pressure asks for 0.45 mm,
    handling asks for 0.50, and surviving a 2D bend asks for 0.56 -- so the
    bend sets the gauge, not the pressure everyone assumes sets it."""
    design = size_duct(HPC_EXIT)
    assert design.governing_constraint == "BEND THINNING"
    assert design.bend_required_mm > design.hoop_required_mm
    assert design.bend_required_mm > design.min_gauge_mm


def test_generous_bends_hand_control_back_to_minimum_gauge():
    """Open the bend radius and the thinning penalty shrinks until it stops
    being what governs -- which is the argument for routing with gentle
    bends where there is room."""
    design = size_duct(HPC_EXIT, bend_diameters=6.0)
    assert design.governing_constraint != "BEND THINNING"


def test_the_wall_still_contains_pressure_after_thinning():
    for bend_d in (1.5, 2.0, 3.0, 5.0):
        assert size_duct(HPC_EXIT, bend_diameters=bend_d).is_pressure_safe()


def test_higher_pressure_drives_a_thicker_wall():
    low = size_duct(BleedCondition(759.5, 500_000.0, 1.0))
    high = size_duct(BleedCondition(759.5, 4_000_000.0, 1.0))
    assert high.wall_mm > low.wall_mm


def test_hoop_can_only_govern_a_straight_duct():
    """Writing this test is what found it. The bend requirement is the hoop
    requirement divided by a factor below one, so it always exceeds hoop --
    meaning no *bent* duct is ever sized by pressure alone, however high
    the pressure. Only a straight run can be."""
    bent = size_duct(BleedCondition(759.5, 4_000_000.0, 1.0))
    assert bent.governing_constraint == "BEND THINNING"

    straight = size_duct(BleedCondition(759.5, 4_000_000.0, 1.0),
                         bend_diameters=None)
    assert straight.governing_constraint == "HOOP STRESS"
    assert straight.wall_after_bending_mm == straight.wall_mm


# ── Thermal growth ─────────────────────────────────────────────────────────

def test_thermal_growth_matches_the_closed_form():
    design = size_duct(HPC_EXIT)
    from sizing import THERMAL_EXPANSION
    alpha = THERMAL_EXPANSION[design.material.name]
    assert thermal_growth_mm(design, 1000.0) == pytest.approx(
        alpha * 1000.0 * (759.5 - 288.15))


def test_growth_is_large_enough_to_matter():
    """The point of computing it. A metre of hot stainless grows several
    millimetres -- far more than the clearance anyone eyeballs."""
    assert thermal_growth_mm(size_duct(HPC_EXIT), 1000.0) > 5.0


def test_required_clearance_exceeds_growth():
    design = size_duct(HPC_EXIT)
    assert (required_clearance_mm(design, 1000.0)
            > thermal_growth_mm(design, 1000.0))


# ── Guards ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("t,p,m", [(0, 1e6, 1), (759, 0, 1), (759, 1e6, 0)])
def test_impossible_conditions_are_refused(t, p, m):
    with pytest.raises(ValueError):
        BleedCondition(t, p, m)


def test_zero_velocity_is_refused():
    with pytest.raises(ValueError):
        bore_diameter_m(HPC_EXIT, 0.0)
