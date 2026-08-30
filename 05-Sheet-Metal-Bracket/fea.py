"""Static FEA of the formed bracket, run headless through CalculiX.

    /Applications/FreeCAD.app/Contents/MacOS/FreeCAD -c fea.py < /dev/null

FreeCAD bundles gmsh and CalculiX, so this needs no GUI and no separate
solver install. It meshes the exported STEP, applies a load case, solves,
and writes `fea_results.json`.

**The deliverable is the convergence sweep, not the peak stress.** A single
FEA number is worth very little: refine the mesh and it moves, and whether
it moves *toward something* or just keeps climbing is the only way to tell
a real stress from a meshing artefact. So this runs the same problem at
several element sizes and reports the trend.

One sizing rule matters more than the rest here. The bracket is 1.6 mm
sheet, and a first attempt at 2.0 mm elements put **less than one element
through the wall** — gmsh returned nonpositive Jacobians and the answer
would have been meaningless if it had solved at all. Bending needs at
least two quadratic elements through thickness, which caps the element
size at 0.8 mm before any convergence argument begins.

Load case: an avionics box on the upright, at 9g. That is a standard
crash-load factor for equipment attachment, and it is the case that sizes
brackets like this one — not the 1g weight, which is trivial.
"""

from __future__ import annotations

import json
import os
import sys

# FreeCAD's launcher re-execs and drops the locale, so the embedded
# interpreter comes up with an ASCII stdout and any non-ASCII character
# in a print kills the run. Fix it before the first print, not by
# rationing the punctuation.
sys.stdout.reconfigure(encoding="utf-8")

import FreeCAD
import ObjectsFem
import Part
from femmesh.gmshtools import GmshTools
from femtools.ccxtools import FemToolsCcx

HERE = os.path.dirname(os.path.abspath(__file__))
# Which variant to solve, so the same analysis runs on the redesign without
# being edited. See trade_study.py for where the 2 mm arm comes from.
STEP = os.environ.get("BRACKET_STEP",
                      os.path.join(HERE, "exports", "bracket-formed.step"))
OUT_JSON = os.environ.get("FEA_OUT", os.path.join(HERE, "fea_results.json"))
HOLE_RADIUS_MM = 2.55
# Wall thickness of the variant being solved. Only used to report how
# many elements sit through the wall, but that number decides which
# runs are trustworthy, so it must track the geometry rather than
# stay pinned to the baseline part.
WALL_MM = float(os.environ.get("BRACKET_WALL_MM", "1.6"))

# 5052-H32. Yield is the number that matters for a bracket -- permanent set
# in a mount is a failure even though nothing has parted.
YOUNGS_MPA = 70300.0
POISSON = 0.33
DENSITY_KG_M3 = 2680.0
YIELD_MPA = 193.0

EQUIPMENT_KG = 2.0
LOAD_FACTOR_G = 9.0
FORCE_N = EQUIPMENT_KG * 9.81 * LOAD_FACTOR_G

# Coarsest first. 0.8 mm is the largest that still puts two quadratic
# elements through a 1.6 mm wall; anything above it is reported for the
# trend but is not a believable answer.
MESH_SIZES_MM = [1.6, 1.2, 0.9, 0.8, 0.7, 0.6]

def find_bolt_faces(shape):
    """Locate the four bolt-hole bores by geometry, not by face index.

    Face numbering happens to survive a thickness change on this part, but
    relying on that is how this project lost two of its four holes once
    already: a selector that silently picks the wrong face produces a model
    that builds, exports and passes, and is wrong. Bores are found instead
    by what they are -- cylinders of the bolt radius -- and sorted by their
    axis: the upright holes face along X, the base holes along Z.

    Returns (loaded_face_names, fixed_face_names).
    """
    along_x, along_z = [], []
    for index, face in enumerate(shape.Faces, start=1):
        surface = face.Surface
        if type(surface).__name__ != "Cylinder":
            continue
        if abs(surface.Radius - HOLE_RADIUS_MM) > 0.05:
            continue                      # a bend fillet, not a bolt hole
        axis = surface.Axis
        name = f"Face{index}"
        if abs(axis.x) > 0.9:
            along_x.append(name)
        elif abs(axis.z) > 0.9:
            along_z.append(name)

    if len(along_x) != 2 or len(along_z) != 2:
        raise RuntimeError(
            f"expected two upright and two base bores, found "
            f"{len(along_x)} and {len(along_z)} -- the geometry is not the "
            "bracket this analysis is set up for")
    return along_x, along_z


def solve(mesh_mm: float) -> dict:
    """One complete analysis at one element size."""
    doc = FreeCAD.newDocument(f"fea_{mesh_mm}")
    part = doc.addObject("Part::Feature", "Bracket")
    part.Shape = Part.read(STEP)

    analysis = ObjectsFem.makeAnalysis(doc, "Analysis")
    solver = ObjectsFem.makeSolverCalculiXCcxTools(doc, "Solver")
    solver.AnalysisType = "static"
    solver.GeometricalNonlinearity = "linear"
    analysis.addObject(solver)

    material = ObjectsFem.makeMaterialSolid(doc, "Al5052H32")
    properties = material.Material
    properties["Name"] = "Aluminium 5052-H32"
    properties["YoungsModulus"] = f"{YOUNGS_MPA} MPa"
    properties["PoissonRatio"] = str(POISSON)
    properties["Density"] = f"{DENSITY_KG_M3} kg/m^3"
    material.Material = properties
    analysis.addObject(material)

    loaded_faces, fixed_faces = find_bolt_faces(part.Shape)

    fixed = ObjectsFem.makeConstraintFixed(doc, "FixedBaseHoles")
    fixed.References = [(part, f) for f in fixed_faces]
    analysis.addObject(fixed)

    force = ObjectsFem.makeConstraintForce(doc, "EquipmentLoad")
    force.References = [(part, f) for f in loaded_faces]
    force.Force = f"{FORCE_N} N"
    force.DirectionVector = FreeCAD.Vector(-1, 0, 0)
    force.Reversed = False
    analysis.addObject(force)

    mesh = ObjectsFem.makeMeshGmsh(doc, "Mesh")
    mesh.Shape = part
    mesh.CharacteristicLengthMax = f"{mesh_mm} mm"
    mesh.ElementOrder = "2nd"
    analysis.addObject(mesh)
    doc.recompute()

    if GmshTools(mesh).create_mesh():
        FreeCAD.closeDocument(doc.Name)
        return {"mesh_mm": mesh_mm, "failed": "meshing"}

    fea = FemToolsCcx(analysis, solver)
    fea.setup_working_dir()
    fea.update_objects()
    fea.purge_results()
    fea.write_inp_file()
    fea.ccx_run()
    fea.load_results()

    result = {"mesh_mm": mesh_mm, "nodes": mesh.FemMesh.NodeCount,
              "elements": mesh.FemMesh.VolumeCount,
              "through_wall": round(WALL_MM / mesh_mm, 2)}
    for obj in doc.Objects:
        if not (hasattr(obj, "vonMises") and obj.vonMises):
            continue
        stresses = list(obj.vonMises)
        result["max_von_mises_mpa"] = round(max(stresses), 2)
        result["max_displacement_mm"] = round(max(obj.DisplacementLengths), 4)

        # Percentiles, because the maximum is a single node and a single
        # node is exactly what a singularity corrupts. If the peak diverges
        # while the 99th percentile settles, the divergence is local to a
        # modelling artefact and the bulk field is still trustworthy --
        # which is a completely different conclusion from "the part is
        # more highly stressed than we thought".
        ordered = sorted(stresses)
        for pct in (95, 99, 99.9):
            index = int(pct / 100.0 * (len(ordered) - 1))
            result[f"p{pct}_von_mises_mpa"] = round(ordered[index], 2)

        # Where the peak actually sits. A peak on the constrained hole is
        # the constraint's own singularity; a peak at the bend is structure.
        nodes = obj.NodeNumbers
        peak = max(range(len(stresses)), key=lambda i: stresses[i])
        position = mesh.FemMesh.Nodes[nodes[peak]]
        result["peak_location_mm"] = [round(position.x, 2),
                                      round(position.y, 2),
                                      round(position.z, 2)]
    FreeCAD.closeDocument(doc.Name)
    return result


def main():
    print(f"Bracket FEA — {EQUIPMENT_KG} kg equipment at {LOAD_FACTOR_G}g "
          f"= {FORCE_N:.1f} N")
    print(f"  geometry: {os.path.basename(STEP)}, {WALL_MM} mm wall")
    print(f"5052-H32, yield {YIELD_MPA} MPa\n")
    print(f"  {'mesh':>6}{'thru wall':>11}{'nodes':>9}{'peak vM':>12}"
          f"{'p99':>10}{'disp':>10}   peak location")

    results = []
    for size in MESH_SIZES_MM:
        r = solve(size)
        results.append(r)
        if "failed" in r:
            print(f"  {size:6.2f}  meshing failed")
            continue
        print(f"  {size:6.2f}{r['through_wall']:>11.2f}{r['nodes']:>9}"
              f"{r.get('max_von_mises_mpa', float('nan')):>12.1f}"
              f"{r.get('p99_von_mises_mpa', float('nan')):>10.1f}"
              f"{r.get('max_displacement_mm', float('nan')):>10.3f}"
              f"   at {r.get('peak_location_mm')}")
        sys.stdout.flush()

    with open(OUT_JSON, "w") as handle:
        json.dump({"force_n": FORCE_N, "yield_mpa": YIELD_MPA,
                   "equipment_kg": EQUIPMENT_KG, "load_factor_g": LOAD_FACTOR_G,
                   "runs": results}, handle, indent=2)
    print(f"\n  wrote {OUT_JSON}")


main()
