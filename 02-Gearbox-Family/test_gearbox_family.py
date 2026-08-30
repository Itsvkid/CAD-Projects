"""Tests for the parametric gearbox family.

This project was, for a while, the only one here with no tests -- and it is
the one where the most defects turned up, which is not a coincidence. Every
one of them was found by checking generated geometry against something that
knew the answer independently, and each has a test below that would now
catch it:

  * the involute half-angle carried the wrong sign, so teeth widened toward
    the tip instead of narrowing;
  * the housing footprint was driven by bearing-boss diameter, so the 50 kW
    gear hung 84 mm outside its own casing;
  * ribs that only tangentially touched the bosses left six disjoint solids
    where one was intended;
  * every bill-of-materials mass was a hand-rolled formula, one of them
    wrong by 3.4x.

The pure-arithmetic tests are cheap. The geometry tests build real solids,
so the designs are cached per-session rather than per-test.
"""

import math

import cadquery as cq
import pytest

from gearbox_family import (
    BEARING_60XX_SERIES,
    LEWIS_FORM_FACTOR_20DEG_FULL_DEPTH,
    STANDARD_MODULES_MM,
    GearboxDesign,
    contact_ratio,
    create_gear,
    involute_gear_profile_points,
    lewis_form_factor,
    round_up_to_standard_module,
    select_bearing,
)

# The shipped family, exactly as generate_gearbox_family() defines it.
FAMILY = {
    "5kw_small_turboprop": dict(power_kw=5, input_speed_rpm=6000, speed_ratio=3.5),
    "10kw_regional": dict(power_kw=10, input_speed_rpm=8000, speed_ratio=4.0),
    "20kw_narrow_body": dict(power_kw=20, input_speed_rpm=10000, speed_ratio=4.5),
    "30kw_wide_body": dict(power_kw=30, input_speed_rpm=11000, speed_ratio=5.0),
    "50kw_large_jet": dict(power_kw=50, input_speed_rpm=12000, speed_ratio=5.5),
}


@pytest.fixture(scope="session")
def designs():
    """Every family member, built once."""
    return {name: GearboxDesign(**params) for name, params in FAMILY.items()}


@pytest.fixture(scope="session")
def design(designs):
    """The 20 kW narrow-body case, this project's default."""
    return designs["20kw_narrow_body"]


# --- Involute tooth geometry -------------------------------------------
#
# The sign error lived here. It is worth being precise about why it
# survived: it produces the *correct* tooth thickness at the pitch circle,
# so every pitch-dimension check passes. Only the variation of thickness
# with radius distinguishes the two.


def _outline(*args, **kwargs):
    """Just the (x, y) points. involute_gear_profile_points returns a
    (points, geometry) pair despite a docstring that says otherwise."""
    return involute_gear_profile_points(*args, **kwargs)[0]


def _half_angles_by_radius(num_teeth=20, module=2.0, pressure_angle_deg=20.0):
    """Polar half-angle of one flank against radius, read off the emitted
    outline rather than recomputed from the formula under test.

    Only the first tooth is used, and only its involute flanks. The tooth
    is centred on +X, so a point's half-angle is just |atan2(y, x)| -- but
    that only holds inside one tooth's own sector. Folding the whole
    outline into a single sector with a modulo instead returns, for every
    radius, both psi and its complement, whose mean is constant by
    construction and hides exactly the trend being looked for.
    """
    pts = _outline(num_teeth, module, pressure_angle_deg, points_per_flank=24)
    r_p = module * num_teeth / 2.0
    r_b = r_p * math.cos(math.radians(pressure_angle_deg))
    r_a = r_p + module
    sector = math.pi / num_teeth
    out = []
    for x, y in pts:
        r, angle = math.hypot(x, y), math.atan2(y, x)
        # inside tooth zero, on the involute, and off the flat tip land
        if abs(angle) < sector and r_b * 1.0005 < r < r_a * 0.9999:
            out.append((r, abs(angle)))
    return sorted(out)


def test_tooth_is_exactly_half_a_pitch_wide_at_the_pitch_circle():
    """Standard, and true of the correct profile -- but ALSO true of the
    mirrored one. This is the check that passed while the teeth were
    hourglasses, kept here to document that it is not sufficient."""
    num_teeth, module = 20, 2.0
    r_p = module * num_teeth / 2.0
    samples = _half_angles_by_radius(num_teeth, module)
    at_pitch = min(samples, key=lambda s: abs(s[0] - r_p))
    assert at_pitch[1] == pytest.approx(math.pi / (2 * num_teeth), abs=0.02)


def test_tooth_narrows_from_root_to_tip():
    """The check that actually catches the sign error.

    psi(r) = pi/(2N) + inv(alpha) - inv(alpha_r), and inv(alpha_r) grows
    with radius, so the half-angle must *decrease* outward: the tooth is
    widest at the root and narrowest at the tip. The mirrored sign makes it
    widen outward instead.

    This is the only test here that catches that, which was verified by
    reintroducing the sign error and re-running the suite. Both the pitch-
    thickness check and the valid-solid check below pass with the sign
    mirrored, for reasons each of them documents.
    """
    samples = _half_angles_by_radius()
    assert len(samples) > 10
    inner = [a for r, a in samples[:len(samples) // 3]]
    outer = [a for r, a in samples[-len(samples) // 3:]]
    assert sum(outer) / len(outer) < sum(inner) / len(inner), (
        "tooth widens toward the tip -- the involute half-angle sign is "
        "mirrored, and the flanks will cross")


def test_the_profile_is_a_closed_counterclockwise_loop():
    pts = _outline(20, 2.0)
    area = 0.5 * sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1)
                     in zip(pts, pts[1:] + pts[:1]))
    assert area > 0, "outline is clockwise; extrusion orientation is wrong"


def test_every_profile_point_lies_between_the_root_and_tip_circles():
    num_teeth, module = 20, 2.0
    r_p = module * num_teeth / 2.0
    r_a, r_d = r_p + module, r_p - 1.25 * module
    for x, y in _outline(num_teeth, module):
        assert r_d - 1e-6 <= math.hypot(x, y) <= r_a + 1e-6


def test_the_outline_reaches_the_tip_circle():
    """A profile that never reaches the addendum radius has no tooth."""
    num_teeth, module = 20, 2.0
    r_a = module * num_teeth / 2.0 + module
    assert max(math.hypot(x, y) for x, y
               in _outline(num_teeth, module)) == pytest.approx(r_a, rel=1e-3)


def test_a_pointed_tooth_is_rejected_rather_than_drawn():
    """Too much addendum on too few teeth leaves zero land at the tip. The
    generator should refuse, not emit a degenerate outline."""
    with pytest.raises(ValueError, match="pointed tooth"):
        involute_gear_profile_points(18, 2.0, addendum_factor=3.0)


@pytest.mark.parametrize("num_teeth", [18, 20, 35, 90])
def test_the_extruded_gear_is_a_single_valid_solid(num_teeth):
    """Guards the outline extruding cleanly: a wire that crosses itself
    gives a solid that fails BRepCheck_Analyzer and will not triangulate,
    exporting an end face with holes in it.

    Worth being exact about what this does NOT cover. It does not catch the
    mirrored involute sign at any tooth count this project ships. Mirrored,
    psi_tip reaches 0.125 rad on the 20-tooth pinion against a half-sector
    of 0.157 -- the tooth is the wrong shape but its flanks still stay
    inside their own sector, so the solid is valid and this test passes.
    Checking that geometry is well-formed is not the same as checking it is
    correct, and only test_tooth_narrows_from_root_to_tip does the latter.
    """
    gear, _ = create_gear(num_teeth, 2.0, 12.0)
    assert gear.val().isValid()
    assert len(gear.solids().vals()) == 1


def test_the_gear_has_one_tip_land_per_tooth():
    """Counts teeth from the geometry rather than trusting the loop that
    drew them: a self-crossing profile loses tips."""
    num_teeth, module = 20, 2.0
    r_a = module * num_teeth / 2.0 + module
    pts = _outline(num_teeth, module)
    at_tip = [i for i, (x, y) in enumerate(pts)
              if math.hypot(x, y) > r_a - 1e-6]
    runs = sum(1 for i, j in zip(at_tip, at_tip[1:]) if j != i + 1) + 1
    assert runs == num_teeth


# --- Contact ratio ------------------------------------------------------


def test_contact_ratio_exceeds_one_or_the_gears_stop_driving(designs):
    """Below 1.0 a tooth pair disengages before the next one takes up, and
    the drive is not continuous. Standard spur practice wants >= 1.2."""
    for name, d in designs.items():
        assert d.contact_ratio > 1.2, f"{name} at {d.contact_ratio:.3f}"


def test_contact_ratio_matches_an_independent_recomputation(design):
    alpha = math.radians(design.PRESSURE_ANGLE_DEG)
    p, g = design.pinion_geom, design.gear_geom
    expected = ((math.sqrt(p["addendum_radius"] ** 2 - p["base_radius"] ** 2)
                 + math.sqrt(g["addendum_radius"] ** 2 - g["base_radius"] ** 2)
                 - design.center_distance_mm * math.sin(alpha))
                / (math.pi * design.module_mm * math.cos(alpha)))
    assert design.contact_ratio == pytest.approx(expected, rel=1e-9)


# --- Lewis form factor --------------------------------------------------


@pytest.mark.parametrize("teeth", sorted(LEWIS_FORM_FACTOR_20DEG_FULL_DEPTH))
def test_table_entries_are_returned_exactly(teeth):
    assert lewis_form_factor(teeth) == LEWIS_FORM_FACTOR_20DEG_FULL_DEPTH[teeth]


def test_interpolation_lands_between_its_neighbours():
    assert lewis_form_factor(23) == pytest.approx((0.331 + 0.337) / 2, abs=1e-9)


def test_the_factor_is_clamped_outside_the_table():
    assert lewis_form_factor(5) == LEWIS_FORM_FACTOR_20DEG_FULL_DEPTH[12]
    assert lewis_form_factor(5000) == LEWIS_FORM_FACTOR_20DEG_FULL_DEPTH[300]


def test_the_factor_rises_with_tooth_count():
    """More teeth is a stronger tooth form. A non-monotone table would be a
    transcription error."""
    values = [lewis_form_factor(n) for n in range(12, 301)]
    assert all(b >= a for a, b in zip(values, values[1:]))


# --- Module and bearing selection ---------------------------------------


def test_the_module_is_never_rounded_down():
    """The safety factor is a consequence of this: snapping up to a cutter
    size that exists is what turns a computed module into a buyable one."""
    for required in (0.4, 1.01, 1.26, 2.7, 4.9, 8.5):
        assert round_up_to_standard_module(required) >= required


def test_an_exact_standard_module_is_left_alone():
    for m in STANDARD_MODULES_MM:
        assert round_up_to_standard_module(m) == m


def test_the_chosen_module_is_the_smallest_that_fits():
    assert round_up_to_standard_module(2.01) == 2.5
    assert round_up_to_standard_module(1.0) == 1.0


def test_beyond_the_largest_cutter_it_returns_the_largest():
    assert round_up_to_standard_module(999.0) == STANDARD_MODULES_MM[-1]


def test_the_bearing_bore_always_takes_the_shaft():
    for shaft in (9.0, 10.0, 12.5, 23.7, 41.2):
        designation, bore, od, width = select_bearing(shaft)
        assert bore >= shaft
        assert od > bore and width > 0


def test_the_bearing_is_the_smallest_one_that_fits():
    bores = sorted(BEARING_60XX_SERIES)
    for shaft in (11.0, 26.0, 36.0):
        chosen = select_bearing(shaft)[1]
        smaller = [b for b in bores if b >= shaft and b < chosen]
        assert not smaller


# --- Sizing physics -----------------------------------------------------


def test_input_torque_follows_from_power_and_speed(designs):
    for name, d in designs.items():
        omega = d.input_speed_rpm * 2 * math.pi / 60.0
        assert d.input_torque_nm == pytest.approx(d.power_kw * 1000.0 / omega)


def test_output_torque_carries_the_ratio_and_loses_the_mesh_efficiency(design):
    assert design.output_torque_nm == pytest.approx(
        design.input_torque_nm * design.actual_speed_ratio * design.MESH_EFFICIENCY)
    assert design.output_torque_nm < design.input_torque_nm * design.actual_speed_ratio


def test_the_teeth_are_not_worked_past_their_allowable_stress(designs):
    """What the Lewis sizing is for. If this fails the gearbox is not
    merely inelegant, it is under-designed."""
    for name, d in designs.items():
        assert d.actual_bending_stress_mpa < d.ALLOWABLE_BENDING_STRESS_MPA, (
            f"{name}: {d.actual_bending_stress_mpa:.1f} MPa")


def test_rounding_the_module_up_is_what_buys_the_margin(designs):
    """The stress margin should be a consequence of the cutter list, not a
    number anyone chose -- so it should vary across the family rather than
    sit at some constant design factor."""
    margins = {n: d.actual_bending_stress_mpa / d.ALLOWABLE_BENDING_STRESS_MPA
               for n, d in designs.items()}
    assert max(margins.values()) - min(margins.values()) > 0.05


def test_shaft_diameter_solves_the_torsion_equation(designs):
    for name, d in designs.items():
        expected = (16 * d.input_torque_nm * 1000.0 * d.SHAFT_DESIGN_FACTOR
                    / (math.pi * d.SHAFT_ALLOWABLE_SHEAR_MPA)) ** (1 / 3)
        assert d.pinion_shaft_diameter_mm == pytest.approx(expected)


def test_the_output_shaft_is_the_thicker_of_the_two(design):
    """It carries the multiplied torque."""
    assert design.gear_shaft_diameter_mm > design.pinion_shaft_diameter_mm


def test_a_pinion_that_would_undercut_is_refused():
    with pytest.raises(ValueError, match="undercut"):
        GearboxDesign(20.0, 10000, 4.5, pinion_teeth=16)


def test_the_gear_always_has_more_teeth_than_the_pinion(designs):
    for name, d in designs.items():
        assert d.gear_teeth >= d.pinion_teeth + 1


def test_centre_distance_is_the_sum_of_the_pitch_radii(designs):
    for name, d in designs.items():
        assert d.center_distance_mm == pytest.approx(
            d.pinion_geom["pitch_radius"] + d.gear_geom["pitch_radius"])


def test_more_power_never_gives_a_smaller_module(designs):
    ordered = [designs[n] for n in
               ("5kw_small_turboprop", "10kw_regional", "20kw_narrow_body",
                "30kw_wide_body", "50kw_large_jet")]
    modules = [d.module_mm for d in ordered]
    assert all(b >= a for a, b in zip(modules, modules[1:])), modules


# --- Housing ------------------------------------------------------------


@pytest.mark.parametrize("name", list(FAMILY))
def test_the_gear_fits_inside_its_own_housing(designs, name):
    """The 50 kW defect, pinned.

    The footprint was driven by bearing-boss diameter, which scales with
    the shaft rather than with the gear, so the largest member's gear
    overhung the casing by 84 mm. Checking the real bounding box against
    the real tip circle is the only way to catch that -- the sizing
    arithmetic is all individually correct.
    """
    d = designs[name]
    bb = d.create_housing().val().BoundingBox()
    pinion_tip = d.pinion_geom["addendum_radius"]
    gear_tip = d.gear_geom["addendum_radius"]

    assert bb.xmin <= -pinion_tip, f"{name}: pinion overhangs by {-pinion_tip - bb.xmin:.1f} mm"
    assert bb.xmax >= d.center_distance_mm + gear_tip, (
        f"{name}: gear overhangs the casing by "
        f"{d.center_distance_mm + gear_tip - bb.xmax:.1f} mm")
    assert bb.ymin <= -gear_tip and bb.ymax >= gear_tip, f"{name}: gear overhangs across the width"


@pytest.mark.parametrize("name", list(FAMILY))
def test_the_housing_is_one_connected_solid(designs, name):
    """Ribs that only tangentially touched the bosses once left six
    disjoint solids. union() reports no error for that -- only counting
    does."""
    housing = designs[name].create_housing()
    assert len(housing.solids().vals()) == 1
    assert housing.val().isValid()


def test_the_gears_sit_clear_of_the_housing(design):
    """Both gears are placed on top of the bearing bosses. If the boss
    height were taken from face width instead -- which it once was -- a
    47 mm tower would run straight through a 25 mm bore."""
    housing = design.create_housing()
    z = design.boss_height_mm
    for part, offset in ((design.create_pinion(), (0, 0, z)),
                         (design.create_gear_wheel(),
                          (design.center_distance_mm, 0, z))):
        overlap = housing.val().intersect(part.translate(offset).val())
        assert overlap.Volume() < 1.0, "gear fouls the housing"


@pytest.mark.parametrize("name", list(FAMILY))
def test_the_meshing_teeth_do_not_occupy_the_same_space(designs, name):
    """Found by this suite, and it had reached the exported STEP files.

    Both profiles are drawn with a tooth centred on their own +X axis, so
    the pinion always presents a tooth toward the gear. With an even tooth
    count the gear presents one straight back, and the two solids overlapped
    by 424 mm3 -- 2.1% of the pinion. Every member of the shipped family has
    an even gear, so every exported assembly had it.

    assembly() now offsets the gear by half a tooth pitch. The parity
    matters: an odd gear already presents a space, and rotating it would
    cause exactly the clash it is meant to avoid.
    """
    d = designs[name]
    asm = d.assembly()
    parts = {c.name: c.obj.val().located(c.loc) for c in asm.children}
    overlap = parts["pinion"].intersect(parts["gear"]).Volume()
    assert overlap < 1.0, f"{name}: teeth interfere by {overlap:.1f} mm3"


@pytest.mark.parametrize("teeth,expected_phase", [(90, 2.0), (91, 0.0)])
def test_the_mesh_phase_follows_tooth_count_parity(teeth, expected_phase):
    """Pins the parity rule, since getting it backwards is silent: it
    produces a clash of the same size it was meant to remove."""
    ratio = teeth / 20.0
    d = GearboxDesign(20.0, 10000, ratio)
    d.assembly()
    assert d.gear_teeth == teeth
    assert d.mesh_phase_deg == pytest.approx(expected_phase)


# --- Bill of materials --------------------------------------------------


def test_bom_masses_come_from_the_real_solids(design):
    """Every BOM mass was once a hand-rolled formula, and the housing's was
    wrong by 3.4x because it predated the base flange. They are now read
    from the solids' own volumes, and this recomputes that independently."""
    bom = design.get_bom()
    volume_mm3 = design.create_housing().val().Volume()
    expected_kg = (volume_mm3 / 1000) * 2.70 / 1000

    housing = next(item for item in bom["components"]
                   if "housing" in item["part_name"].lower())
    assert housing["mass_kg"] == pytest.approx(expected_kg, rel=0.02)


def test_the_quoted_total_is_the_sum_of_the_parts(design):
    """Only the three modelled solids carry a mass. Bearings, seals and
    bolts are listed with quantities but no weight, so the total is the
    manufactured mass rather than the assembly's -- which the BOM now says
    out loud rather than leaving to be inferred."""
    bom = design.get_bom()
    weighed = [i for i in bom["components"] if "mass_kg" in i]
    assert len(weighed) == 3
    total = sum(i["mass_kg"] * i.get("quantity", 1) for i in weighed)
    assert bom["total_mass_kg"] == pytest.approx(total, rel=0.02)

    unweighed = [i["part_name"] for i in bom["components"] if "mass_kg" not in i]
    assert unweighed, "bought-in parts vanished from the BOM"
    assert any("bought-in" in s or "no mass" in s
               for s in bom["known_simplifications"]), (
        "the BOM quotes a total that excludes bought-in parts without "
        "saying so")


def test_masses_are_physically_possible(designs):
    """A steel gear cannot be lighter than the same volume of water, and an
    accessory gearbox does not weigh a tonne. Catches a units slip."""
    for name, d in designs.items():
        bom = d.get_bom()
        assert 0.05 < bom["total_mass_kg"] < 200.0, f"{name}: {bom['total_mass_kg']}"


def test_the_simplifications_are_still_declared(design):
    """The BOM states what it does not model. If that list disappears the
    document starts implying a certifiable design."""
    bom = design.get_bom()
    assert bom["known_simplifications"]
    assert len(bom["known_simplifications"]) >= 3
