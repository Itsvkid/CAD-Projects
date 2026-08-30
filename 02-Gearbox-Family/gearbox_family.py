"""
Parametric Gearbox Family Generator
====================================

Generates 3D CAD models for aircraft engine accessory gearboxes (hydraulic
pump / fuel pump / oil pump / generator drives) that scale with engine
power rating.

Input: Power rating, input shaft speed, reduction ratio
Output: STEP file (pinion + gear + housing assembly) + Bill of Materials

Author: Vinaykumar (Aerospace Engineering)
Date: 2026-08-23

Gear tooth geometry is a real involute profile (the standard construction
from the involute function inv(alpha) = tan(alpha) - alpha, e.g. Shigley's
"Mechanical Engineering Design"), sampled and joined with straight
segments -- a polygon approximation of the true curve, not exact to the
micron, but geometrically the right shape and verified to extrude cleanly
(see the module docstring on create_gear). Module sizing uses the Lewis
bending-stress equation with a standard Y-factor table; bearing/shaft
sizing uses standard torsion and deep-groove-ball-bearing dimensions.
Where a real manufacturer spec (L10 life, dynamic load rating, casting
draft) would be needed for a certifiable design, this is flagged
explicitly rather than faked -- see get_bom()'s "known_simplifications".
"""

import cadquery as cq
import json
import math
from pathlib import Path


# ---------------------------------------------------------------------------
# Involute gear tooth geometry
# ---------------------------------------------------------------------------

def involute_gear_profile_points(num_teeth, module, pressure_angle_deg=20.0,
                                  points_per_flank=8, addendum_factor=1.0,
                                  dedendum_factor=1.25, root_arc_points=4,
                                  tip_arc_points=2):
    """Full closed outline of an external spur gear (list of (x, y) tuples
    in mm), built from the standard involute-function construction: each
    tooth flank is the true involute of the base circle, sampled and joined
    with straight segments (a polygon approximation of the curve, not exact
    to the micron). Root fillets are a plain circular arc at the dedendum
    radius, not the true trochoidal fillet a hobbing cutter leaves.

    The half tooth angle at radius r is

        psi(r) = pi/(2N) + inv(alpha) - inv(alpha_r)

    where inv(x) = tan(x) - x and alpha_r is the pressure angle at r, so
    cos(alpha_r) = r_b/r. The two involute terms have *opposite* signs: the
    tooth is exactly pi/(2N) wide at the pitch circle, wider below it, and
    narrower above it, coming to its narrowest at the tip. Getting that
    sign wrong -- writing pi/(2N) - inv(alpha) + inv(alpha_r) -- still gives
    the right thickness at the pitch circle, which is why it survives a
    check of pitch dimensions, but it flares every tooth outward into an
    hourglass whose flanks cross. The resulting wire self-intersects, and
    the solid extruded from it fails BRepCheck_Analyzer and will not
    triangulate: its end face renders and exports with holes in it.

    Points come out in counter-clockwise order, tooth by tooth: up the
    trailing flank, across the tip land, down the leading flank, then round
    the root arc to the next tooth.
    """
    N = num_teeth
    m = module
    alpha = math.radians(pressure_angle_deg)

    r_p = m * N / 2.0
    r_b = r_p * math.cos(alpha)
    r_a = r_p + addendum_factor * m
    r_d = r_p - dedendum_factor * m

    inv_alpha = math.tan(alpha) - alpha
    # Half tooth angle extrapolated back to the base circle, where the
    # involute has zero polar angle. Every psi below is this minus inv(alpha_r).
    half_angle_at_base = math.pi / (2 * N) + inv_alpha

    # The involute exists only outside the base circle. Where the dedendum
    # falls below it, the flank starts at r_b and a radial segment drops to
    # the root; where the dedendum is above it, the flank starts at r_d.
    r_start = max(r_b, r_d)
    t_start = math.sqrt(max((r_start / r_b) ** 2 - 1.0, 0.0))
    t_max = math.sqrt((r_a / r_b) ** 2 - 1.0)

    def involute_point(t):
        r = r_b * math.sqrt(1 + t * t)
        phi = t - math.atan(t)
        return r, phi

    def half_angle(t):
        return half_angle_at_base - (t - math.atan(t))

    ts = [t_start + (t_max - t_start) * i / (points_per_flank - 1)
          for i in range(points_per_flank)]

    psi_start = half_angle(t_start)
    psi_tip = half_angle(t_max)
    if psi_tip <= 0.0:
        raise ValueError(
            f"{N} teeth at {pressure_angle_deg} deg pressure angle and "
            f"addendum factor {addendum_factor} gives a pointed tooth "
            "(zero land at the tip)")
    if 2 * psi_start >= 2 * math.pi / N:
        raise ValueError(
            f"{N} teeth leaves no root gap between adjacent teeth")

    def polar(r, ang):
        return (r * math.cos(ang), r * math.sin(ang))

    all_points = []
    for i in range(N):
        c = 2 * math.pi * i / N
        next_c = 2 * math.pi * (i + 1) / N

        # Radial drop to the root, trailing side, when the involute cannot
        # reach the dedendum circle on its own.
        if r_d < r_start:
            all_points.append(polar(r_d, c - psi_start))

        # Trailing flank, root to tip. Angle increases as psi shrinks.
        for t in ts:
            r, _ = involute_point(t)
            all_points.append(polar(r, c - half_angle(t)))

        # Tip land, an arc at the addendum radius across the top of the tooth.
        for k in range(1, tip_arc_points + 1):
            frac = k / (tip_arc_points + 1)
            all_points.append(polar(r_a, c - psi_tip + 2 * psi_tip * frac))

        # Leading flank, tip back down to root.
        for t in reversed(ts):
            r, _ = involute_point(t)
            all_points.append(polar(r, c + half_angle(t)))

        if r_d < r_start:
            all_points.append(polar(r_d, c + psi_start))

        # Root arc through to where the next tooth begins.
        start_ang = c + psi_start
        end_ang = next_c - psi_start
        for k in range(1, root_arc_points + 1):
            frac = k / (root_arc_points + 1)
            all_points.append(polar(r_d, start_ang + (end_ang - start_ang) * frac))

    geom = dict(pitch_radius=r_p, base_radius=r_b, addendum_radius=r_a,
                dedendum_radius=r_d, center_module=m, num_teeth=N)
    return all_points, geom


def create_gear(num_teeth, module, face_width_mm, pressure_angle_deg=20.0,
                 bore_diameter_mm=None):
    """Build a CadQuery spur gear solid. Verified standalone (isolated
    test, not just assumed from the point-generation math): the closed
    polyline extrudes into exactly 1 solid, and min/max radius across all
    profile points matches the computed dedendum/addendum radii exactly
    -- see this project's development notes / README for that check."""
    pts, geom = involute_gear_profile_points(num_teeth, module, pressure_angle_deg)
    gear = cq.Workplane("XY").polyline(pts).close().extrude(face_width_mm)
    if bore_diameter_mm:
        gear = gear.faces(">Z").workplane().circle(bore_diameter_mm / 2).cutThruAll()
    return gear, geom


def contact_ratio(pinion_geom, gear_geom, center_distance_mm, pressure_angle_deg=20.0):
    """Standard transverse contact ratio (Shigley's eq. for spur gears):
    mp = [sqrt(Ra1^2-Rb1^2) + sqrt(Ra2^2-Rb2^2) - C*sin(alpha)] / (pi*m*cos(alpha))
    """
    alpha = math.radians(pressure_angle_deg)
    ra1, rb1 = pinion_geom["addendum_radius"], pinion_geom["base_radius"]
    ra2, rb2 = gear_geom["addendum_radius"], gear_geom["base_radius"]
    m = pinion_geom["center_module"]
    numerator = (math.sqrt(ra1 ** 2 - rb1 ** 2) + math.sqrt(ra2 ** 2 - rb2 ** 2)
                 - center_distance_mm * math.sin(alpha))
    return numerator / (math.pi * m * math.cos(alpha))


# ---------------------------------------------------------------------------
# Lewis bending-stress sizing
# ---------------------------------------------------------------------------

# Standard Lewis form factor Y, 20-degree full-depth involute teeth
# (Shigley's "Mechanical Engineering Design" table) -- textbook-standard
# values, not fitted/derived here. Linearly interpolated between entries.
LEWIS_FORM_FACTOR_20DEG_FULL_DEPTH = {
    12: 0.245, 13: 0.261, 14: 0.277, 15: 0.290, 16: 0.296, 17: 0.303,
    18: 0.309, 19: 0.314, 20: 0.322, 21: 0.328, 22: 0.331, 24: 0.337,
    26: 0.346, 28: 0.353, 30: 0.359, 34: 0.371, 38: 0.384, 45: 0.397,
    50: 0.408, 60: 0.421, 75: 0.434, 100: 0.447, 150: 0.460, 300: 0.472,
}


def lewis_form_factor(num_teeth):
    teeth_sorted = sorted(LEWIS_FORM_FACTOR_20DEG_FULL_DEPTH)
    if num_teeth <= teeth_sorted[0]:
        return LEWIS_FORM_FACTOR_20DEG_FULL_DEPTH[teeth_sorted[0]]
    if num_teeth >= teeth_sorted[-1]:
        return LEWIS_FORM_FACTOR_20DEG_FULL_DEPTH[teeth_sorted[-1]]
    for lo, hi in zip(teeth_sorted, teeth_sorted[1:]):
        if lo <= num_teeth <= hi:
            y_lo = LEWIS_FORM_FACTOR_20DEG_FULL_DEPTH[lo]
            y_hi = LEWIS_FORM_FACTOR_20DEG_FULL_DEPTH[hi]
            t = (num_teeth - lo) / (hi - lo)
            return y_lo + t * (y_hi - y_lo)
    raise AssertionError("unreachable")  # teeth_sorted is exhaustive between its own bounds


STANDARD_MODULES_MM = [1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0]


def round_up_to_standard_module(module_mm):
    for m in STANDARD_MODULES_MM:
        if m >= module_mm:
            return m
    return STANDARD_MODULES_MM[-1]


# ---------------------------------------------------------------------------
# Standard deep-groove ball bearing dimensions (60xx light series)
# ---------------------------------------------------------------------------

# (bore_mm, od_mm, width_mm) -- standard published 60xx-series dimensions,
# not manufacturer-certified load ratings (no dynamic load rating /
# L10-life data is claimed here -- see get_bom()'s known_simplifications).
BEARING_60XX_SERIES = {
    10: ("6000", 10, 26, 8), 12: ("6001", 12, 28, 8), 15: ("6002", 15, 32, 9),
    17: ("6003", 17, 35, 10), 20: ("6004", 20, 42, 12), 25: ("6005", 25, 47, 12),
    30: ("6006", 30, 55, 13), 35: ("6007", 35, 62, 14), 40: ("6008", 40, 68, 15),
    45: ("6009", 45, 75, 16), 50: ("6010", 50, 80, 16),
}


def select_bearing(min_bore_mm):
    """Smallest standard 60xx-series bearing whose bore is >= the required
    shaft diameter. Returns (designation, bore, od, width)."""
    for bore in sorted(BEARING_60XX_SERIES):
        if bore >= min_bore_mm:
            return BEARING_60XX_SERIES[bore]
    largest = max(BEARING_60XX_SERIES)
    return BEARING_60XX_SERIES[largest]


# ---------------------------------------------------------------------------
# Gearbox design: sizing math
# ---------------------------------------------------------------------------

class GearboxDesign:
    """Sizes a single-stage spur gear reduction for a given power rating,
    then builds pinion + gear + housing CAD geometry.

    Simplifications, stated up front (see get_bom()'s known_simplifications
    for the full list): single spur stage only (no helical/planetary), a
    single representative allowable bending stress / overload factor /
    dynamic factor rather than an AGMA-rated material+duty selection, no
    bearing L10 life calculation, no gear efficiency map (one assumed
    value), housing without casting draft or stepped bearing pockets.
    """

    PRESSURE_ANGLE_DEG = 20.0
    FACE_WIDTH_TO_MODULE = 10.0     # F = k*m, typical starting proportion
    OVERLOAD_FACTOR_KO = 1.25       # typical light shock, moderate duty
    DYNAMIC_FACTOR_KV = 1.4         # typical, commercial-quality gearing
    ALLOWABLE_BENDING_STRESS_MPA = 150.0  # representative through-hardened steel gear
    MESH_EFFICIENCY = 0.94          # single spur mesh, within this project's 92-96% spec
    SHAFT_ALLOWABLE_SHEAR_MPA = 40.0  # representative steel shaft, moderate SF
    SHAFT_DESIGN_FACTOR = 1.5

    def __init__(self, power_kw, input_speed_rpm, speed_ratio, pinion_teeth=20):
        if pinion_teeth < 17:
            raise ValueError(
                "pinion_teeth < 17 undercuts at 20 deg pressure angle, full depth")

        self.power_kw = power_kw
        self.input_speed_rpm = input_speed_rpm
        self.target_speed_ratio = speed_ratio
        self.pinion_teeth = pinion_teeth
        self.gear_teeth = max(pinion_teeth + 1, round(pinion_teeth * speed_ratio))
        self.actual_speed_ratio = self.gear_teeth / self.pinion_teeth
        self.output_speed_rpm = input_speed_rpm / self.actual_speed_ratio

        omega_in = input_speed_rpm * 2 * math.pi / 60.0
        self.input_torque_nm = power_kw * 1000.0 / omega_in
        self.output_torque_nm = (self.input_torque_nm * self.actual_speed_ratio
                                  * self.MESH_EFFICIENCY)

        self.module_mm = self._size_module()
        self.face_width_mm = self.FACE_WIDTH_TO_MODULE * self.module_mm

        _, self.pinion_geom = create_gear(self.pinion_teeth, self.module_mm, 1.0)
        _, self.gear_geom = create_gear(self.gear_teeth, self.module_mm, 1.0)
        self.center_distance_mm = (self.pinion_geom["pitch_radius"]
                                    + self.gear_geom["pitch_radius"])
        self.contact_ratio = contact_ratio(
            self.pinion_geom, self.gear_geom, self.center_distance_mm,
            self.PRESSURE_ANGLE_DEG)

        self.tangential_force_n = self._tangential_force()
        self.separating_force_n = self.tangential_force_n * math.tan(
            math.radians(self.PRESSURE_ANGLE_DEG))
        self.mesh_force_n = math.hypot(self.tangential_force_n, self.separating_force_n)
        self.actual_bending_stress_mpa = self._actual_bending_stress()

        self.pitch_line_velocity_m_s = self._pitch_line_velocity()

        self.pinion_shaft_diameter_mm = self._shaft_diameter(self.input_torque_nm)
        self.gear_shaft_diameter_mm = self._shaft_diameter(self.output_torque_nm)
        self.pinion_bearing = select_bearing(self.pinion_shaft_diameter_mm)
        self.gear_bearing = select_bearing(self.gear_shaft_diameter_mm)

    def _size_module(self):
        """Lewis bending equation, solved for module, sized off the
        pinion (fewer teeth -> lower Y -> usually the limiting member),
        with F = k*m substituted so the only unknown is m:

        sigma = Ft*Ko*Kv / (F*m*Y),  Ft = 2*T/(m*N)
              = 2*T*Ko*Kv / (k*N*Y*m^3)
        =>  m^3 = 2*T*Ko*Kv / (k*N*Y*sigma_allow)
        """
        Y = lewis_form_factor(self.pinion_teeth)
        T_n_mm = self.input_torque_nm * 1000.0
        m_cubed = (2 * T_n_mm * self.OVERLOAD_FACTOR_KO * self.DYNAMIC_FACTOR_KV
                   / (self.FACE_WIDTH_TO_MODULE * self.pinion_teeth * Y
                      * self.ALLOWABLE_BENDING_STRESS_MPA))
        return round_up_to_standard_module(m_cubed ** (1.0 / 3.0))

    def _tangential_force(self):
        r_p_m = self.pinion_geom["pitch_radius"] / 1000.0
        return self.input_torque_nm / r_p_m

    def _actual_bending_stress(self):
        Y = lewis_form_factor(self.pinion_teeth)
        return (self.tangential_force_n * self.OVERLOAD_FACTOR_KO * self.DYNAMIC_FACTOR_KV
                / (self.face_width_mm * self.module_mm * Y))

    def _pitch_line_velocity(self):
        d_p_mm = 2 * self.pinion_geom["pitch_radius"]
        return math.pi * d_p_mm * self.input_speed_rpm / 60000.0

    def _shaft_diameter(self, torque_nm):
        """Solid shaft, pure torsion: tau = 16*T / (pi*d^3)."""
        T_n_mm = torque_nm * 1000.0
        d_cubed = (16 * T_n_mm * self.SHAFT_DESIGN_FACTOR
                   / (math.pi * self.SHAFT_ALLOWABLE_SHEAR_MPA))
        return d_cubed ** (1.0 / 3.0)

    # -- CAD ---------------------------------------------------------------

    def create_pinion(self):
        bore = self.pinion_bearing[1]
        gear, _ = create_gear(self.pinion_teeth, self.module_mm, self.face_width_mm,
                               self.PRESSURE_ANGLE_DEG, bore_diameter_mm=bore)
        return gear

    def create_gear_wheel(self):
        bore = self.gear_bearing[1]
        gear, _ = create_gear(self.gear_teeth, self.module_mm, self.face_width_mm,
                               self.PRESSURE_ANGLE_DEG, bore_diameter_mm=bore)
        return gear

    def create_housing(self):
        """Simplified ribbed housing: a single 2D profile -- the two
        bearing-pocket bosses (pinion + gear bores), a connecting "waist"
        section sized generously inside both circles (not just tangent to
        them), corner mounting pads, and a drain plug boss -- all unioned
        as 2D shapes and extruded ONCE. Two separately-extruded 3D solids
        whose ribs only tangentially touched the bosses (rather than
        robustly overlapping) produced 6 disjoint solids in an earlier
        version of this method, caught by checking solids() count in
        isolation rather than assuming union() succeeded. A "base flange
        + boss towers" pattern -- one flat plate spanning the whole
        footprint, with the bearing bosses, corner pads and drain boss
        all sitting on/within it -- replaces that attempt: every feature
        overlaps the same common flange by construction, so connectivity
        never depends on getting two features' extents to line up.

        Explicitly NOT modelled: casting draft angles, stepped bearing
        pockets (a single through-bore stands in for a bearing seat +
        shaft clearance bore), fillets for stress concentration --
        documented here rather than silently assumed away, matching this
        family of projects' convention (see e.g. 01-Hydraulic-Actuator's
        seal-groove simplification)."""
        wall = 6.0
        c = self.center_distance_mm
        flange_thickness = 8.0
        # Boss height is a bearing seat's worth of tower, not an arbitrary
        # one: flange plus the widest of the two bearings, so both bosses
        # finish at the same height and the two gears that sit on them stay
        # coplanar (they have to, to mesh). Extruding these to
        # face_width + 20 instead -- which is what this did originally --
        # runs a 47 mm boss straight through a gear whose bore is 25 mm.
        depth = flange_thickness + max(self.pinion_bearing[3],
                                       self.gear_bearing[3])
        self.boss_height_mm = depth

        pinion_boss_od = self.pinion_bearing[2] + 2 * wall
        gear_boss_od = self.gear_bearing[2] + 2 * wall

        # Footprint has to clear two different things, and the larger one
        # wins on each edge: the bearing bosses (plus room for a mounting
        # pad), and the gears themselves (plus a running clearance to the
        # inside of the wall). Sizing on the bosses alone -- which is what
        # this did originally -- gives a housing the gear does not fit
        # inside: 8 mm of overhang at 5 kW, but 84 mm at 50 kW, because
        # bearing OD grows with shaft torque while the gear grows with the
        # module the Lewis equation asks for, and those are not the same
        # curve. A gearbox whose gear hangs outside its own casing is not a
        # simplification, it is a mistake.
        pad_margin = 15.0
        tip_clearance = 8.0
        pinion_tip = self.pinion_geom["addendum_radius"]
        gear_tip = self.gear_geom["addendum_radius"]

        min_x = min(-pinion_boss_od / 2 - pad_margin,
                    -pinion_tip - tip_clearance)
        max_x = max(c + gear_boss_od / 2 + pad_margin,
                    c + gear_tip + tip_clearance)
        max_y = max(max(pinion_boss_od, gear_boss_od) / 2 + pad_margin,
                    gear_tip + tip_clearance)
        pad_centres = [(px, py) for px in (min_x + 5, max_x - 5)
                       for py in (max_y - 5, -(max_y - 5))]
        drain_centre = (c / 2, -(max(pinion_boss_od, gear_boss_od) / 2 + 6))

        flange_width = max_x - min_x
        flange_centre_x = (min_x + max_x) / 2
        housing = (cq.Workplane("XY").center(flange_centre_x, 0)
                   .rect(flange_width, 2 * max_y).extrude(flange_thickness))

        housing = housing.union(
            cq.Workplane("XY").circle(pinion_boss_od / 2).extrude(depth))
        housing = housing.union(
            cq.Workplane("XY").center(c, 0).circle(gear_boss_od / 2).extrude(depth))

        pad_height = flange_thickness + 12.0
        for px, py in pad_centres:
            housing = housing.union(
                cq.Workplane("XY").center(px, py).circle(9.0).extrude(pad_height))

        housing = housing.union(
            cq.Workplane("XY").center(*drain_centre).circle(8.0).extrude(pad_height))

        housing = (housing.faces(">Z").workplane()
                   .circle(self.pinion_bearing[2] / 2)
                   .cutThruAll())
        housing = (housing.faces(">Z").workplane()
                   .center(c, 0)
                   .circle(self.gear_bearing[2] / 2)
                   .cutThruAll())
        for px, py in pad_centres:
            housing = (housing.faces(">Z").workplane()
                       .center(px, py)
                       .hole(6.5))  # M6 mounting bolt clearance
        housing = (housing.faces(">Z").workplane()
                   .center(*drain_centre)
                   .hole(6.0))

        return housing

    def assembly(self):
        housing = self.create_housing()
        pinion = self.create_pinion()
        gear = self.create_gear_wheel()

        # Gears sit on top of the bearing bosses rather than inside them.
        # create_housing() sets boss_height_mm; call it first so that value
        # exists before it is used.
        z = self.boss_height_mm

        # Phase the gear so its teeth interleave with the pinion's rather
        # than collide with them. Both profiles are drawn with a tooth
        # centred on their own +X axis, so the pinion always presents a
        # tooth toward the gear. Whether the gear presents a tooth or a
        # space back depends on parity: with an even tooth count it also
        # has one at 180 deg, pointing straight at the pinion's, and the
        # two solids overlap by 424 mm3 -- 2.1% of the pinion -- in the
        # exported assembly. Half a tooth pitch puts a space there instead.
        # An odd count already presents a space and must NOT be rotated;
        # doing so causes the same clash it would otherwise avoid.
        self.mesh_phase_deg = (360.0 / (2 * self.gear_teeth)
                               if self.gear_teeth % 2 == 0 else 0.0)

        asm = cq.Assembly()
        asm.add(housing, name="housing", color=cq.Color("gray50"))
        pinion_positioned = pinion.translate((0, 0, z))
        gear_positioned = gear.translate((self.center_distance_mm, 0, z))
        if self.mesh_phase_deg:
            gear_positioned = gear_positioned.rotate(
                (self.center_distance_mm, 0, 0),
                (self.center_distance_mm, 0, 1),
                self.mesh_phase_deg)
        asm.add(pinion_positioned, name="pinion", color=cq.Color("gray30"))
        asm.add(gear_positioned, name="gear", color=cq.Color("gray70"))
        return asm

    def export_step(self, filename):
        asm = self.assembly()
        asm.save(filename)
        print(f"✓ STEP file saved: {filename}")
        return filename

    def export_parts_separately(self, output_dir="./parts", prefix=""):
        Path(output_dir).mkdir(exist_ok=True)
        housing = self.create_housing()
        pinion = self.create_pinion()
        gear = self.create_gear_wheel()

        cq.exporters.export(pinion, f"{output_dir}/{prefix}01_pinion.step")
        cq.exporters.export(gear, f"{output_dir}/{prefix}02_gear.step")
        cq.exporters.export(housing, f"{output_dir}/{prefix}03_housing.step")

        print(f"✓ Individual parts saved to {output_dir}/")
        return output_dir

    def get_bom(self):
        pinion_mass = self._solid_mass_kg(self.create_pinion(), density_g_cm3=7.85)
        gear_mass = self._solid_mass_kg(self.create_gear_wheel(), density_g_cm3=7.85)
        housing_mass = self._solid_mass_kg(self.create_housing(), density_g_cm3=2.7)

        return {
            "design_point": {
                "power_kw": self.power_kw,
                "input_speed_rpm": self.input_speed_rpm,
                "target_speed_ratio": self.target_speed_ratio,
                "actual_speed_ratio": round(self.actual_speed_ratio, 4),
                "output_speed_rpm": round(self.output_speed_rpm, 1),
                "input_torque_nm": round(self.input_torque_nm, 2),
                "output_torque_nm": round(self.output_torque_nm, 2),
            },
            "gear_mesh": {
                "module_mm": self.module_mm,
                "pressure_angle_deg": self.PRESSURE_ANGLE_DEG,
                "pinion_teeth": self.pinion_teeth,
                "gear_teeth": self.gear_teeth,
                "center_distance_mm": round(self.center_distance_mm, 2),
                "face_width_mm": round(self.face_width_mm, 1),
                "contact_ratio": round(self.contact_ratio, 3),
                "pitch_line_velocity_m_s": round(self.pitch_line_velocity_m_s, 2),
                "tangential_force_n": round(self.tangential_force_n, 1),
                "actual_bending_stress_mpa": round(self.actual_bending_stress_mpa, 1),
                "allowable_bending_stress_mpa": self.ALLOWABLE_BENDING_STRESS_MPA,
                "bending_safety_factor": round(
                    self.ALLOWABLE_BENDING_STRESS_MPA / self.actual_bending_stress_mpa, 2),
            },
            "components": [
                {"part_name": "Pinion", "material": "Steel 4340 (carburized)",
                 "teeth": self.pinion_teeth, "mass_kg": round(pinion_mass, 3)},
                {"part_name": "Gear", "material": "Steel 4340 (carburized)",
                 "teeth": self.gear_teeth, "mass_kg": round(gear_mass, 3)},
                {"part_name": "Housing", "material": "Aluminum A356 casting",
                 "mass_kg": round(housing_mass, 3)},
                {"part_name": "Pinion shaft bearing",
                 "designation": self.pinion_bearing[0], "quantity": 2,
                 "bore_od_width_mm": self.pinion_bearing[1:]},
                {"part_name": "Gear shaft bearing",
                 "designation": self.gear_bearing[0], "quantity": 2,
                 "bore_od_width_mm": self.gear_bearing[1:]},
                {"part_name": "Shaft seal", "material": "PTFE/steel", "quantity": 2},
                {"part_name": "Mounting bolts", "spec": "M6", "quantity": 4},
                {"part_name": "Drain plug", "spec": "M8", "quantity": 1},
            ],
            "total_mass_kg": round(pinion_mass + gear_mass + housing_mass, 3),
            "known_simplifications": [
                "Single spur stage only -- no helical/planetary option.",
                "Ko, Kv, allowable bending stress are representative typical "
                "values, not an AGMA material+duty-class selection.",
                "Bearing selection matches shaft diameter to a standard 60xx "
                "bore; no dynamic load rating / L10 life calculation "
                "(would need real manufacturer catalog data).",
                "Housing has no casting draft angles or stepped bearing "
                "pockets -- a plain through-bore stands in for a bearing seat.",
                "No cost estimate -- no real supplier/cost data source "
                "available; fabricating one would misrepresent it as real.",
                "total_mass_kg covers only the three modelled solids "
                "(pinion, gear, housing). Bearings, seals and bolts are "
                "listed with quantities but carry no mass, so the figure "
                "is the manufactured mass, not the assembly's.",
            ],
        }

    @staticmethod
    def _solid_mass_kg(workplane, density_g_cm3):
        """Mass from the REAL solid's OCC volume, not a hand-rolled
        approximation. An earlier version approximated gear mass as a
        plain disc at the pitch radius and housing mass from a simplified
        two-boss formula written before the housing's base-flange design
        existed; checking against the actual generated solid's
        .val().Volume() found the housing estimate was off by 3.4x (the
        formula never accounted for the flange at all). Since the real
        solids already exist by the time get_bom() runs, there is no
        reason to approximate at all."""
        volume_mm3 = workplane.val().Volume()
        return (volume_mm3 / 1000) * density_g_cm3 / 1000

    def get_specs(self):
        return f"""
GEARBOX SPECIFICATIONS
=======================

Power Rating:       {self.power_kw} kW
Input Speed:        {self.input_speed_rpm} RPM
Target Ratio:       1:{self.target_speed_ratio}
Actual Ratio:       1:{self.actual_speed_ratio:.3f} ({self.pinion_teeth}T pinion / {self.gear_teeth}T gear)
Output Speed:       {self.output_speed_rpm:.1f} RPM

Module:             {self.module_mm} mm
Pressure Angle:     {self.PRESSURE_ANGLE_DEG} deg
Face Width:         {self.face_width_mm:.1f} mm
Center Distance:    {self.center_distance_mm:.2f} mm
Contact Ratio:      {self.contact_ratio:.3f}
Pitch Line Velocity: {self.pitch_line_velocity_m_s:.2f} m/s

Input Torque:       {self.input_torque_nm:.2f} Nm
Output Torque:      {self.output_torque_nm:.2f} Nm
Tangential Force:   {self.tangential_force_n:.1f} N
Bending Stress:     {self.actual_bending_stress_mpa:.1f} MPa (allow {self.ALLOWABLE_BENDING_STRESS_MPA} MPa)

Pinion Shaft:       {self.pinion_shaft_diameter_mm:.1f} mm min -> bearing {self.pinion_bearing[0]}
Gear Shaft:         {self.gear_shaft_diameter_mm:.1f} mm min -> bearing {self.gear_bearing[0]}

Application:        Engine accessory drive (hydraulic pump, fuel pump,
                    oil pump, generator)
"""

    def save_bom(self, filename="BOM.json"):
        bom = self.get_bom()
        with open(filename, "w") as f:
            json.dump(bom, f, indent=2)
        print(f"✓ BOM saved: {filename}")
        return filename


def generate_gearbox_family():
    """Generate a family of gearboxes for different engine accessory
    drive power ratings, per this project's spec (5-50 kW)."""

    print("\n" + "=" * 60)
    print("GENERATING GEARBOX FAMILY FOR DIFFERENT ENGINE SIZES")
    print("=" * 60)

    sizes = {
        "5kw_small_turboprop": dict(power_kw=5, input_speed_rpm=6000, speed_ratio=3.5),
        "10kw_regional": dict(power_kw=10, input_speed_rpm=8000, speed_ratio=4.0),
        "20kw_narrow_body": dict(power_kw=20, input_speed_rpm=10000, speed_ratio=4.5),
        "30kw_wide_body": dict(power_kw=30, input_speed_rpm=11000, speed_ratio=5.0),
        "50kw_large_jet": dict(power_kw=50, input_speed_rpm=12000, speed_ratio=5.5),
    }

    family_bom = {}
    for name, params in sizes.items():
        print(f"\n{name}")
        print("-" * 60)
        gearbox = GearboxDesign(**params)
        print(gearbox.get_specs())
        gearbox.export_step(f"gearbox_{name}.step")
        family_bom[name] = gearbox.get_bom()

    with open("BOM_family.json", "w") as f:
        json.dump(family_bom, f, indent=2)
    print("✓ Family BOM saved: BOM_family.json")

    return family_bom


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("GEARBOX CAD GENERATOR")
    print("=" * 60)

    print("\nCreating 20kW narrow-body-class gearbox...")
    gearbox = GearboxDesign(power_kw=20, input_speed_rpm=10000, speed_ratio=4.5)

    print(gearbox.get_specs())

    gearbox.export_step("gearbox_20kw.step")
    gearbox.export_parts_separately()
    gearbox.save_bom()

    generate_gearbox_family()

    print("\n" + "=" * 60)
    print("✓ Gearbox generation complete!")
    print("=" * 60)
