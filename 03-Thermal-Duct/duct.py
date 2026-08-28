"""Routed bleed duct geometry, swept along a 3D centreline in pyOCC.

`sizing.py` decides how big the duct is and how thick its wall must be.
This turns those numbers into a solid: a spline through the waypoints the
duct has to hit, a circular profile swept along it, and a flange at each
end.

Why pyOCC rather than CadQuery, which the other projects here use: this
needs a **sweep along a general 3D curve**, and it needs to interrogate the
result afterwards -- minimum distance to surrounding structure, real swept
volume, wall thickness measured on the built solid rather than assumed.
`BRepOffsetAPI_MakePipe` and `BRepExtrema_DistShapeShape` are the tools for
that, and they sit at a level CadQuery does not expose directly.

    conda run -n pyocc_env python duct.py
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from OCC.Core.BRep import BRep_Tool
from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCC.Core.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakeWire,
)
from OCC.Core.BRepCheck import BRepCheck_Analyzer
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Core.BRepGProp import brepgprop
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCylinder
from OCC.Core.BRepOffsetAPI import BRepOffsetAPI_MakePipe
from OCC.Core.GeomAPI import GeomAPI_Interpolate
from OCC.Core.GProp import GProp_GProps
from OCC.Core.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt, gp_Vec
from OCC.Core.TColgp import TColgp_HArray1OfPnt
from OCC.Extend.DataExchange import write_step_file

from sizing import BleedCondition, DuctDesign, size_duct


def _spline_wire(points: list[tuple[float, float, float]]):
    """A C2-continuous spline through the given waypoints, as a wire.

    Interpolated rather than approximated: a routed duct must *pass through*
    the points where it clears a bracket or meets a bulkhead, not near them.
    GeomAPI_Interpolate honours them exactly; GeomAPI_PointsToBSpline would
    fit a smoother curve that misses.
    """
    if len(points) < 2:
        raise ValueError("a route needs at least two waypoints")
    array = TColgp_HArray1OfPnt(1, len(points))
    for i, (x, y, z) in enumerate(points, start=1):
        array.SetValue(i, gp_Pnt(x, y, z))
    interp = GeomAPI_Interpolate(array, False, 1.0e-6)
    interp.Perform()
    if not interp.IsDone():
        raise RuntimeError("could not interpolate a spline through the route")
    edge = BRepBuilderAPI_MakeEdge(interp.Curve()).Edge()
    return BRepBuilderAPI_MakeWire(edge).Wire(), interp.Curve()


def _circle_face(centre, direction, radius: float):
    """A planar disc, normal to the route, to be swept."""
    axis = gp_Ax2(gp_Pnt(*centre), gp_Dir(*direction))
    circle = gp_Circ(axis, radius)
    edge = BRepBuilderAPI_MakeEdge(circle).Edge()
    wire = BRepBuilderAPI_MakeWire(edge).Wire()
    return BRepBuilderAPI_MakeFace(wire).Face(), wire


def _start_tangent(curve):
    """Direction the route leaves its first point, so the swept profile
    starts square to the duct rather than square to the world."""
    point, vec = gp_Pnt(), gp_Vec()
    curve.D1(curve.FirstParameter(), point, vec)
    return (point.X(), point.Y(), point.Z()), (vec.X(), vec.Y(), vec.Z())


def volume_mm3(shape) -> float:
    props = GProp_GProps()
    brepgprop.VolumeProperties(shape, props)
    return props.Mass()


def minimum_distance(shape_a, shape_b) -> float:
    """Closest approach between two solids, in millimetres.

    Zero means they touch or interfere. This is the query a routing study
    exists to answer -- a duct that fits on paper and fouls a bracket in
    the bay is the failure mode, and it is not visible in any single view.
    """
    calc = BRepExtrema_DistShapeShape(shape_a, shape_b)
    calc.Perform()
    if not calc.IsDone():
        raise RuntimeError("distance calculation failed")
    return calc.Value()


@dataclass
class RoutedDuct:
    """A sized duct swept along a route, with flanges at both ends."""

    design: DuctDesign
    route: list[tuple[float, float, float]]
    flange_thickness_mm: float = 6.0
    flange_outer_extra_mm: float = 22.0

    def __post_init__(self):
        self._wire, self._curve = _spline_wire(self.route)

    @property
    def flange_outer_diameter_mm(self) -> float:
        return self.design.outer_diameter_mm + 2 * self.flange_outer_extra_mm

    def _swept(self, radius_mm: float):
        origin, tangent = _start_tangent(self._curve)
        face, _ = _circle_face(origin, tangent, radius_mm)
        pipe = BRepOffsetAPI_MakePipe(self._wire, face)
        pipe.Build()
        if not pipe.IsDone():
            raise RuntimeError("pipe sweep failed — the route may bend "
                               "tighter than the duct radius allows")
        return pipe.Shape()

    def solid(self):
        """The duct wall: outer sweep with the bore cut out of it."""
        outer = self._swept(self.design.outer_diameter_mm / 2.0)
        inner = self._swept(self.design.bore_mm / 2.0)
        wall = BRepAlgoAPI_Cut(outer, inner).Shape()
        for flange in self._flanges():
            wall = BRepAlgoAPI_Fuse(wall, flange).Shape()
        return wall

    def _flanges(self):
        """A raised face flange at each end, bored to the duct bore.

        Placed on the route's own end tangents, so a flange stays square to
        the duct however the route is edited -- fixing them to a world axis
        is the kind of thing that survives every review until the first
        route change.
        """
        out = []
        for parameter in (self._curve.FirstParameter(), self._curve.LastParameter()):
            point, vec = gp_Pnt(), gp_Vec()
            self._curve.D1(parameter, point, vec)
            direction = gp_Dir(vec)
            if parameter == self._curve.LastParameter():
                direction.Reverse()
            axis = gp_Ax2(point, direction)
            disc = BRepPrimAPI_MakeCylinder(
                axis, self.flange_outer_diameter_mm / 2.0,
                self.flange_thickness_mm).Shape()
            bore = BRepPrimAPI_MakeCylinder(
                axis, self.design.bore_mm / 2.0,
                self.flange_thickness_mm * 3).Shape()
            out.append(BRepAlgoAPI_Cut(disc, bore).Shape())
        return out

    def route_length_mm(self) -> float:
        from OCC.Core.GCPnts import GCPnts_AbscissaPoint
        from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
        return GCPnts_AbscissaPoint.Length(BRepAdaptor_Curve(
            BRepBuilderAPI_MakeEdge(self._curve).Edge()))

    def mass_kg(self) -> float:
        """From the real swept volume, not length times mass-per-metre."""
        return volume_mm3(self.solid()) / 1e9 * self.design.material.density_kg_m3

    def is_valid(self) -> bool:
        return BRepCheck_Analyzer(self.solid()).IsValid()

    def export_step(self, path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        write_step_file(self.solid(), str(path))
        return path
