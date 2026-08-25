"""Parametric formed sheet-metal angle bracket, with its flat pattern.

An equipment mounting bracket: a base that bolts to structure, an upright
that bolts to the equipment, one 90 degree fold between them. It is about
the simplest part that is genuinely a *sheet-metal* design rather than a
machined one, and every constraint that makes sheet metal its own
discipline is present -- a minimum bend radius set by the alloy, a minimum
flange the press brake can grip, holes that have to stay clear of the bend,
edge distances that decide whether a fastener tears out.

Two solids come out of this, and they are not the same shape:

  * the **formed part**, which is what the bracket looks like installed and
    what the assembly is dimensioned from, and
  * the **flat pattern**, which is what the shop actually cuts.

The second is shorter than the sum of the first's outside legs, by one bend
deduction. `sheet_metal.py` has that arithmetic and the reasoning.

    python bracket.py       # build, check, export STEP + DXF-ready flat
"""

from __future__ import annotations

from pathlib import Path

import cadquery as cq

from sheet_metal import (
    MATERIALS,
    Bend,
    bend_allowance,
    check_bend_radius,
    check_edge_distance,
    check_flange_length,
    check_hole_diameter,
    check_hole_to_bend,
    flat_length,
    outside_setback,
)


class AngleBracket:
    """A 90-degree formed angle bracket.

    Dimensions are to the **outside** of the fold, which is how a formed
    part is dimensioned on a drawing and how it is measured with a rule.
    The flat pattern is derived, never specified.
    """

    BEND_ANGLE_DEG = 90.0

    def __init__(self, base_length=60.0, upright_length=45.0, width=50.0,
                 thickness=1.6, inside_radius=3.0, hole_diameter=5.1,
                 hole_setback=12.0, hole_pitch=26.0, material="5052-H32"):
        if material not in MATERIALS:
            raise ValueError(f"unknown material {material!r}; have "
                             f"{sorted(MATERIALS)}")
        self.base_length = base_length
        self.upright_length = upright_length
        self.width = width
        self.thickness = thickness
        self.inside_radius = inside_radius
        self.hole_diameter = hole_diameter
        self.hole_setback = hole_setback
        self.hole_pitch = hole_pitch
        self.material = MATERIALS[material]

        self.bend = Bend(self.BEND_ANGLE_DEG, inside_radius)
        self.setback = outside_setback(self.BEND_ANGLE_DEG, inside_radius,
                                       thickness)
        self.bend_allowance = bend_allowance(self.BEND_ANGLE_DEG, inside_radius,
                                             thickness)
        self.bend_deduction = self.bend.deduction(thickness)
        self.flat_length = flat_length([base_length, upright_length],
                                       [self.bend], thickness)

    # ── Manufacturability ──────────────────────────────────────────────

    @property
    def edge_distance(self) -> float:
        """Hole centre to the nearest sheet edge across the width."""
        return self.width / 2.0 - self.hole_pitch / 2.0

    @property
    def hole_edge_to_bend(self) -> float:
        """Nearest hole edge to the bend tangent line, on the base leg.

        The tangent line sits `thickness + inside_radius` from the outside
        corner; beyond it the material is flat and a hole is safe.
        """
        tangent = self.thickness + self.inside_radius
        hole_edge = (self.base_length - self.hole_setback
                     - self.hole_diameter / 2.0)
        return hole_edge - tangent

    def violations(self) -> list:
        """Every manufacturability rule this design breaks.

        Returned as a list rather than raised one at a time, so a design
        that is wrong in three ways reports three problems instead of
        making the designer fix and re-run three times.
        """
        found = [
            check_bend_radius(self.material, self.thickness, self.inside_radius),
            check_flange_length(self.thickness, self.inside_radius,
                                self.base_length),
            check_flange_length(self.thickness, self.inside_radius,
                                self.upright_length),
            check_hole_to_bend(self.thickness, self.inside_radius,
                               self.hole_edge_to_bend),
            check_edge_distance(self.hole_diameter, self.edge_distance),
            check_hole_diameter(self.thickness, self.hole_diameter),
        ]
        return [v for v in found if v is not None]

    def assert_manufacturable(self) -> None:
        problems = self.violations()
        if problems:
            raise ValueError("bracket is not manufacturable as drawn:\n  "
                             + "\n  ".join(str(p) for p in problems))

    # ── Geometry ───────────────────────────────────────────────────────

    def formed(self) -> cq.Workplane:
        """The bracket as folded.

        Built as two overlapping boxes unioned into an L, then filleted at
        the corner -- inside radius R, outside R + T, which is what a fold
        physically produces. Drawing the profile as a polyline and filleting
        it afterwards gives the same result; this way round the two radii
        cannot drift apart, since the outer one is derived.
        """
        t, w = self.thickness, self.width
        base = (cq.Workplane("XY")
                .box(self.base_length, w, t, centered=(False, True, False)))
        upright = (cq.Workplane("XY")
                   .box(t, w, self.upright_length,
                        centered=(False, True, False)))
        bracket = base.union(upright)

        # The two corner edges run across the width. Selecting by direction
        # and then by position keeps this robust to the union's edge
        # ordering, which is not guaranteed.
        bracket = (bracket.edges("|Y")
                   .edges(cq.selectors.BoxSelector(
                       (t - 0.01, -w, t - 0.01), (t + 0.01, w, t + 0.01)))
                   .fillet(self.inside_radius))
        bracket = (bracket.edges("|Y")
                   .edges(cq.selectors.BoxSelector(
                       (-0.01, -w, -0.01), (0.01, w, 0.01)))
                   .fillet(self.inside_radius + t))

        # Base holes, drilled down through the flat leg.
        bracket = (bracket.faces(">Z").workplane(centerOption="ProjectedOrigin")
                   .pushPoints([(self.base_length - self.hole_setback,
                                 sign * self.hole_pitch / 2.0)
                                for sign in (1, -1)])
                   .hole(self.hole_diameter))
        # Upright holes, drilled through the standing leg.
        bracket = (bracket.faces(">X").workplane(centerOption="ProjectedOrigin")
                   .pushPoints([(sign * self.hole_pitch / 2.0,
                                 self.upright_length - self.hole_setback)
                                for sign in (1, -1)])
                   .hole(self.hole_diameter))
        return bracket

    def flat_pattern(self) -> cq.Workplane:
        """The blank, as cut, with the holes at their developed positions.

        Hole positions are *not* the formed part's dimensions transferred
        across. A hole 12 mm from the free end of the upright is 12 mm from
        the end of the blank too -- but the blank's end is at `flat_length`,
        not at `base_length + upright_length`, so its coordinate moves by
        the bend deduction.
        """
        blank = (cq.Workplane("XY")
                 .box(self.flat_length, self.width, self.thickness,
                      centered=(False, True, False)))
        positions = [
            (self.base_length - self.hole_setback, sign * self.hole_pitch / 2.0)
            for sign in (1, -1)
        ] + [
            (self.flat_length - self.hole_setback, sign * self.hole_pitch / 2.0)
            for sign in (1, -1)
        ]
        return (blank.faces(">Z").workplane(centerOption="ProjectedOrigin")
                .pushPoints(positions).hole(self.hole_diameter))

    @property
    def bend_zone(self) -> tuple[float, float]:
        """Where the bend starts and stops along the flat blank."""
        start = self.base_length - self.setback
        return start, start + self.bend_allowance

    @property
    def bend_line(self) -> float:
        """Centre of the bend zone -- what a press-brake operator lines up."""
        start, end = self.bend_zone
        return (start + end) / 2.0

    # ── Reporting ──────────────────────────────────────────────────────

    def mass_kg(self) -> float:
        """From the formed solid's real volume, not a plate-area estimate."""
        volume_mm3 = self.formed().val().Volume()
        return (volume_mm3 / 1000.0) * self.material.density_g_cm3 / 1000.0

    def specs(self) -> dict:
        start, end = self.bend_zone
        return {
            "material": self.material.name,
            "thickness_mm": self.thickness,
            "outside_base_mm": self.base_length,
            "outside_upright_mm": self.upright_length,
            "width_mm": self.width,
            "inside_bend_radius_mm": self.inside_radius,
            "min_bend_radius_mm": self.material.minimum_bend_radius(self.thickness),
            "bend_angle_deg": self.BEND_ANGLE_DEG,
            "bend_allowance_mm": round(self.bend_allowance, 4),
            "outside_setback_mm": round(self.setback, 4),
            "bend_deduction_mm": round(self.bend_deduction, 4),
            "flat_length_mm": round(self.flat_length, 3),
            "summed_outside_legs_mm": self.base_length + self.upright_length,
            "bend_zone_mm": (round(start, 3), round(end, 3)),
            "hole_diameter_mm": self.hole_diameter,
            "edge_distance_mm": round(self.edge_distance, 3),
            "hole_edge_to_bend_mm": round(self.hole_edge_to_bend, 3),
            "mass_kg": round(self.mass_kg(), 5),
            "violations": [str(v) for v in self.violations()],
        }


def main():
    bracket = AngleBracket()
    specs = bracket.specs()

    print("EQUIPMENT MOUNTING BRACKET")
    print("=" * 58)
    for key, value in specs.items():
        if key != "violations":
            print(f"  {key:26s} {value}")
    problems = specs["violations"]
    print(f"\n  DFM: {'PASS — no violations' if not problems else 'FAIL'}")
    for problem in problems:
        print(f"    {problem}")

    Path("exports").mkdir(exist_ok=True)
    cq.exporters.export(bracket.formed(), "exports/bracket-formed.step")
    cq.exporters.export(bracket.flat_pattern(), "exports/bracket-flat.step")
    cq.exporters.export(bracket.flat_pattern().faces(">Z").wires().toPending(),
                        "exports/bracket-flat.dxf")
    print("\n  exports/bracket-formed.step")
    print("  exports/bracket-flat.step")
    print("  exports/bracket-flat.dxf   (profile for laser/waterjet)")


if __name__ == "__main__":
    main()
