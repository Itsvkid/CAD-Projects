"""Size, route, check and export a bleed-air duct.

    conda run -n pyocc_env python build.py

Takes station-3 conditions from the twin-spool cycle model in the analysis
portfolio, sizes a duct against them, routes it around the engine core, and
checks it clears everything it has to clear -- with the duct hot, not cold.
"""

from __future__ import annotations

from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt

from duct import RoutedDuct, minimum_distance
from sizing import (
    BleedCondition,
    required_clearance_mm,
    size_duct,
    thermal_growth_mm,
)

# Station 3, HPC exit, from the reference design point of the twin-spool
# cycle model (projects/08-cycle-model): 40 kg/s core flow, OPR 35.8,
# TET 1650 K at FL350 / M0.78. Customer bleed is taken here on a real
# engine. 1 kg/s is a representative ECS and anti-ice offtake -- 2.5% of
# core flow, which is in the usual range.
BLEED = BleedCondition(
    total_temperature_k=759.5,
    total_pressure_pa=1_251_651.0,
    mass_flow_kg_s=1.0,
    source="HPC exit (station 3), reference cycle design point",
)

# Waypoints: off the HPC bleed port, aft along the core, then up and
# outboard to the pylon interface.
#
# Both routes are kept deliberately. The first is the obvious one, drawn to
# hug the core and keep the run short, and the clearance check below rejects
# it -- it fouls the casing outright and leaves the bracket inside the
# thermal-growth allowance. Keeping the rejected route in the file is the
# point: a routing study that only ever shows the answer that worked looks
# like luck rather than method.
ROUTE_INITIAL = [(0, 0, 0), (250, 0, 60), (500, 80, 120),
                 (700, 220, 140), (820, 380, 140)]
ROUTE_REVISED = [(0, 0, 70), (250, 20, 125), (500, 110, 180),
                 (700, 250, 195), (820, 390, 195)]


def obstructions():
    """What the duct has to avoid. A simplified core casing it must stay
    outside of, and an accessory bracket in the bay."""
    casing = BRepPrimAPI_MakeCylinder(
        gp_Ax2(gp_Pnt(0, 0, -260), gp_Dir(1, 0, 0)), 260.0, 900.0).Shape()
    bracket = BRepPrimAPI_MakeBox(gp_Pnt(430, 130, 60), 90.0, 70.0, 40.0).Shape()
    return {"core casing": casing, "accessory bracket": bracket}


def main() -> None:
    design = size_duct(BLEED)
    duct = RoutedDuct(design, ROUTE_INITIAL)
    length = duct.route_length_mm()

    print("BLEED AIR DUCT")
    print("=" * 62)
    print(f"  source                {BLEED.source}")
    print(f"  offtake               {BLEED.total_temperature_k:.1f} K, "
          f"{BLEED.total_pressure_pa / 1e5:.2f} bar, "
          f"{BLEED.mass_flow_kg_s:.2f} kg/s")
    print()
    print(f"  material              {design.material.name}")
    print(f"  bore                  {design.bore_mm:.1f} mm "
          f"(duct Mach {design.duct_mach:.3f})")
    print(f"  wall                  {design.wall_mm:.2f} mm")
    print(f"  outer diameter        {design.outer_diameter_mm:.1f} mm")
    print(f"  bend radius           {design.bend_radius_mm:.0f} mm "
          f"({design.bend_ratio:.1f}D)")
    print()
    print("  WALL THICKNESS — what each constraint demanded")
    print(f"    hoop stress         {design.hoop_required_mm:.3f} mm")
    print(f"    minimum gauge       {design.min_gauge_mm:.3f} mm")
    print(f"    surviving the bend  {design.bend_required_mm:.3f} mm")
    print(f"    governing           {design.governing_constraint}")
    print(f"    wall after bending  {design.wall_after_bending_mm:.3f} mm "
          f"(needs ≥ {design.hoop_required_mm:.3f})")
    print(f"    pressure safe       {design.is_pressure_safe()}")
    print()

    growth = thermal_growth_mm(design, length)
    required = required_clearance_mm(design, length)
    print("  INSTALLATION")
    print(f"    route length        {length:.1f} mm")
    print(f"    mass (with flanges) {duct.mass_kg():.3f} kg")
    print(f"    thermal growth      {growth:.2f} mm at temperature")
    print(f"    clearance required  {required:.2f} mm (growth + 3 mm vibration)")
    print()

    print("  CLEARANCE — routes tried")
    obstacles = obstructions()
    passing = None
    for label, route in (("initial", ROUTE_INITIAL), ("revised", ROUTE_REVISED)):
        candidate = RoutedDuct(design, route)
        solid = candidate.solid()
        needed = required_clearance_mm(design, candidate.route_length_mm())
        gaps = {n: minimum_distance(solid, o) for n, o in obstacles.items()}
        worst = min(gaps.values())
        verdict = "PASS" if worst >= needed else "REJECTED"
        print(f"    {label:8s} " + "   ".join(
            f"{n} {g:6.2f}" for n, g in gaps.items())
            + f"   tightest {worst:6.2f} vs {needed:5.2f}   {verdict}")
        if verdict == "PASS" and passing is None:
            passing = candidate
    print()

    if passing is None:
        print("  No route clears. Widen the bay or accept a bellows.")
        return

    print(f"  valid solid           {passing.is_valid()}")
    print(f"  {passing.export_step('exports/bleed-duct.step')}")


if __name__ == "__main__":
    main()
