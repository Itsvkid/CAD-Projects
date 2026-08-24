"""Figures for the CAD projects — shaded renders and parametric-scaling plots.

Two kinds of output, both driven from the same generator scripts that build
the STEP files, so a figure cannot describe a different part from the one
exported:

  * **Shaded renders.** The assembly is tessellated on the OpenCASCADE
    kernel — the same mesh a STEP viewer builds — and rendered offscreen
    through VTK, which CadQuery already depends on. No browser, no CAD GUI,
    no screenshotting: this runs headless, which is the whole reason it can
    live in the repository next to the code it draws.
  * **Scaling plots.** What the parametric family actually does as its one
    driving input changes: force and mass against bore for the actuator,
    module and tooth bending stress against power for the gearbox.

Colours come from the portfolio site's own tokens (app/globals.css) so a
figure sits flush on the page it is dropped into rather than carrying its
own unrelated palette.

    python render.py            # everything, both themes
    python render.py actuator   # one project only
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import cadquery as cq
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import vtk
from PIL import Image

ROOT = Path(__file__).parent
ACTUATOR_DIR = ROOT / "01-Hydraulic-Actuator"
GEARBOX_DIR = ROOT / "02-Gearbox-Family"

# Kernel tessellation tolerances, in mm and radians. Fine enough that a
# 20 mm-radius cylinder comes out around 40 facets rather than 18 — VTK
# smooth-shades across them, but a silhouette is still polygonal, and the
# silhouette is what gives a coarse mesh away.
LINEAR_DEFLECTION = 0.06
ANGULAR_DEFLECTION = 0.12

# Site tokens — see the portfolio's app/globals.css :root / [data-theme]
# blocks. `parts` are the matte greys assembly components are shaded in,
# ordered to match the gray70/50/30 the generator scripts already assign in
# their own cq.Assembly colours.
THEMES = {
    "light": {
        "surface": "#f2eee6", "ink": "#221e18", "ink_muted": "#6e6558",
        "grid": "#d9d0c0", "accent": "#b23d0e",
        "parts": ("#9a9288", "#7d766c", "#b5ada1"),
    },
    "dark": {
        "surface": "#1b1815", "ink": "#f1ece4", "ink_muted": "#8c8377",
        "grid": "#39332b", "accent": "#ff6d3b",
        "parts": ("#8b8378", "#6e675e", "#a49c90"),
    },
}

# Camera direction, in model space, and the up axis. Both projects build
# along +Z, so Z is up and the camera sits off to one side and slightly
# above — a three-quarter view that shows a round part as round.
VIEW_DIRECTION = (1.0, -2.4, 0.72)
VIEW_UP = (0.0, 0.0, 1.0)


def _load(module_path: Path, name: str):
    """Import a generator script by path. The two projects are standalone
    scripts in sibling folders rather than an installed package, so there is
    nothing to `import` in the ordinary way."""
    spec = importlib.util.spec_from_file_location(name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _hex_to_rgb(value: str) -> tuple[float, float, float]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


# ── Rendering ───────────────────────────────────────────────────────────────

def assembly_parts(assembly, offset=(0.0, 0.0, 0.0)):
    """Flatten a cq.Assembly into world-space shapes, in child order.

    Each child's own location is applied, then the whole thing is shifted by
    `offset` — which is how several assemblies get laid out side by side in
    one scene without any of them knowing about the others."""
    shift = cq.Location(cq.Vector(*offset))
    parts = []
    for child in assembly.children:
        shape = child.obj.val() if hasattr(child.obj, "val") else child.obj
        parts.append(shape.moved(child.loc).moved(shift))
    return parts


def _actor(shape, rgb):
    """One tessellated shape as a VTK actor, smooth-shaded but keeping its
    hard edges hard.

    `SetFeatureAngle(30)` with splitting on is what separates the two: normals
    are averaged across neighbouring facets only where the real surface is
    genuinely curved, so a cylinder reads smooth while the flat that meets it
    keeps a crisp edge instead of being blurred into a fillet that isn't
    there."""
    verts, tris = shape.tessellate(LINEAR_DEFLECTION, ANGULAR_DEFLECTION)

    points = vtk.vtkPoints()
    points.SetNumberOfPoints(len(verts))
    for index, vertex in enumerate(verts):
        points.SetPoint(index, vertex.x, vertex.y, vertex.z)

    cells = vtk.vtkCellArray()
    for triangle in tris:
        cells.InsertNextCell(3)
        for vertex_index in triangle:
            cells.InsertCellPoint(int(vertex_index))

    polydata = vtk.vtkPolyData()
    polydata.SetPoints(points)
    polydata.SetPolys(cells)

    # OCC triangulates a planar face with a hole into slivers radiating from
    # that hole, and a zero-area sliver has no meaningful normal -- left in,
    # they shade as random dark scratches across an otherwise flat face.
    # Cleaning merges coincident points and drops the degenerate triangles
    # before any normal is computed from them.
    clean = vtk.vtkCleanPolyData()
    clean.SetInputData(polydata)
    clean.ConvertPolysToLinesOff()
    clean.ConvertLinesToPointsOff()
    clean.PointMergingOn()
    clean.Update()

    normals = vtk.vtkPolyDataNormals()
    normals.SetInputConnection(clean.GetOutputPort())
    normals.SetFeatureAngle(30.0)
    normals.SplittingOn()
    normals.ConsistencyOn()
    normals.AutoOrientNormalsOn()
    normals.Update()

    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(normals.GetOutputPort())

    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    prop = actor.GetProperty()
    prop.SetColor(*rgb)
    prop.SetAmbient(0.28)
    prop.SetDiffuse(0.72)
    # Just enough specular to tell a curved surface from a flat one. More
    # than this and matte engineering geometry starts reading as chrome.
    prop.SetSpecular(0.14)
    prop.SetSpecularPower(24.0)
    return actor


def _trim(path: Path, background_rgb, margin=0.03):
    """Crop a render to its content, then pad by a fixed fraction.

    VTK frames to the camera, not to the geometry, so a long thin assembly
    leaves most of the image empty. Cropping afterwards is both simpler and
    more reliable than trying to compute the exact parallel scale that would
    have filled the frame."""
    image = Image.open(path).convert("RGB")
    pixels = np.asarray(image, dtype=np.int16)
    reference = np.array([round(c * 255) for c in background_rgb], dtype=np.int16)
    content = np.abs(pixels - reference).max(axis=2) > 6
    if not content.any():
        return path

    rows, columns = np.where(content)
    pad = int(round(margin * max(image.width, image.height)))
    box = (max(int(columns.min()) - pad, 0), max(int(rows.min()) - pad, 0),
           min(int(columns.max()) + 1 + pad, image.width),
           min(int(rows.max()) + 1 + pad, image.height))
    image.crop(box).save(path)
    return path


def shaded_render(parts, path, theme="light", *, size=(1800, 1200), zoom=1.0,
                  direction=VIEW_DIRECTION):
    """Render world-space shapes to a PNG. `parts` is a list of shapes; each
    takes the theme grey at its own index, so component order decides tone.

    `direction` is where the camera sits in model space. The default suits a
    tall part seen from the side; a flat one wants more height, or it is read
    edge-on and its layout disappears."""
    t = THEMES[theme]
    background = _hex_to_rgb(t["surface"])
    greys = [_hex_to_rgb(c) for c in t["parts"]]

    renderer = vtk.vtkRenderer()
    renderer.SetBackground(*background)
    for index, shape in enumerate(parts):
        renderer.AddActor(_actor(shape, greys[index % len(greys)]))

    window = vtk.vtkRenderWindow()
    window.SetOffScreenRendering(1)
    window.AddRenderer(renderer)
    window.SetSize(*size)
    window.SetMultiSamples(8)

    camera = renderer.GetActiveCamera()
    camera.ParallelProjectionOn()
    camera.SetPosition(*direction)
    camera.SetFocalPoint(0.0, 0.0, 0.0)
    camera.SetViewUp(*VIEW_UP)
    renderer.ResetCamera()
    camera.Zoom(zoom)

    # A single light following the camera, plus the ambient term set on each
    # actor. A fixed world light would leave whichever end of a long family
    # line-up faces away from it in the dark.
    light = vtk.vtkLight()
    light.SetLightTypeToCameraLight()
    light.SetPosition(-0.35, 0.25, 1.0)
    light.SetFocalPoint(0.0, 0.0, 0.0)
    light.SetIntensity(1.0)
    renderer.RemoveAllLights()
    renderer.AddLight(light)

    window.Render()

    to_image = vtk.vtkWindowToImageFilter()
    to_image.SetInput(window)
    to_image.Update()

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = vtk.vtkPNGWriter()
    writer.SetFileName(str(path))
    writer.SetInputConnection(to_image.GetOutputPort())
    writer.Write()
    window.Finalize()

    _trim(path, background)
    print(f"  {path}")
    return path


def _style_axes(ax, t):
    ax.set_facecolor(t["surface"])
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(t["grid"])
    ax.tick_params(colors=t["ink_muted"], labelsize=8)
    ax.xaxis.label.set_color(t["ink"])
    ax.yaxis.label.set_color(t["ink"])
    ax.grid(True, color=t["grid"], linewidth=0.6, alpha=0.7)
    ax.set_axisbelow(True)


def _suffix(theme):
    return "-dark" if theme == "dark" else ""


# ── Project 01: hydraulic actuator ──────────────────────────────────────────

# The four aircraft classes generate_family_of_actuators() builds, in the same
# order and with the same dimensions — bore, rod, stroke in mm.
ACTUATOR_FAMILY = [
    ("Cessna-class", 16, 10, 100),
    ("Q400-class", 25, 15, 150),
    ("B737-class", 35, 21, 200),
    ("B777-class", 50, 30, 250),
]


def actuator_family_render(actuator_module, theme="light"):
    """All four aircraft classes in one scene at true relative scale.

    A single actuator render says "this is an actuator". Four of them, to
    scale, say what the script is for: one parameter set per aircraft class,
    one code path, geometry that follows."""
    actuators = [actuator_module.HydraulicActuator(bore, rod, stroke)
                 for _, bore, rod, stroke in ACTUATOR_FAMILY]
    # One constant pitch, set by the widest member, so the four sit on a
    # common baseline at an even spacing — a family line-up, not a huddle.
    # Wide enough that the whole group reads landscape: the site crops
    # product tiles to 4:3, and a portrait render would lose its ends.
    spacing = max(a.cylinder_od for a in actuators) * 2.6
    parts = []
    for index, actuator in enumerate(actuators):
        parts.extend(assembly_parts(actuator.assembly(),
                                    offset=(index * spacing, 0.0, 0.0)))
    return shaded_render(parts,
                         ACTUATOR_DIR / "figures" / f"actuator-family{_suffix(theme)}.png",
                         theme, size=(2000, 1100))


def actuator_assembly_render(actuator_module, theme="light"):
    """The B737-class design on its own, close enough to read the rod-end."""
    actuator = actuator_module.HydraulicActuator(35, 21, 200)
    return shaded_render(assembly_parts(actuator.assembly()),
                         ACTUATOR_DIR / "figures" / f"actuator-assembly{_suffix(theme)}.png",
                         theme, size=(1400, 1800))


def actuator_scaling_figure(actuator_module, theme="light"):
    """Output force and force per unit mass against bore across the family.

    Plotting force against mass would be a straight line and say nothing:
    both go as bore squared. The ratio is where the family earns its keep —
    specific force climbs from 9.8 to 15.1 kN/kg across the four classes,
    because `wall_thickness` is a fixed 3 mm however big the bore gets, so
    the wall falls from 27% of the cylinder diameter to 11%. Small actuators
    spend a much larger share of their mass on being a pressure vessel.

    That is a property of this model's own sizing rule, not a law: it is
    what a constant wall thickness implies. A real design would scale wall
    with hoop stress and flatten the curve considerably."""
    t = THEMES[theme]
    bores, forces, specific, labels = [], [], [], []
    for label, bore, rod, stroke in ACTUATOR_FAMILY:
        actuator = actuator_module.HydraulicActuator(bore, rod, stroke)
        bom = actuator.get_bom()
        force = actuator._calc_force_output()
        mass = sum(c.get("mass_kg", 0.0) for c in bom["components"])
        bores.append(bore)
        forces.append(force)
        specific.append(force / mass)
        labels.append(label)

    fig, ax1 = plt.subplots(figsize=(6.6, 4.3), dpi=200)
    fig.patch.set_facecolor(t["surface"])
    _style_axes(ax1, t)

    ax1.plot(bores, forces, "o-", color=t["accent"], linewidth=1.8, markersize=5)
    ax1.set_xlabel("Bore diameter, mm")
    ax1.set_ylabel("Force output at 210 bar, kN")
    ax1.tick_params(axis="y", colors=t["accent"])
    ax1.yaxis.label.set_color(t["accent"])
    ax1.set_ylim(0, max(forces) * 1.25)

    ax2 = ax1.twinx()
    ax2.plot(bores, specific, "s--", color=t["ink_muted"], linewidth=1.5, markersize=4)
    ax2.set_ylabel("Force per unit mass, kN/kg")
    ax2.tick_params(axis="y", colors=t["ink_muted"], labelsize=8)
    ax2.yaxis.label.set_color(t["ink_muted"])
    ax2.set_ylim(0, max(specific) * 1.25)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_color(t["grid"])
    ax2.grid(False)

    for bore, force, label in zip(bores, forces, labels):
        ax1.annotate(label, (bore, force), textcoords="offset points",
                     xytext=(-5, 7), fontsize=7.5, color=t["ink_muted"],
                     ha="right")

    ax1.set_title("Actuator family: output force and force per unit mass",
                  color=t["ink"], fontsize=10.5, pad=10)
    fig.tight_layout()

    path = ACTUATOR_DIR / "figures" / f"actuator-scaling{_suffix(theme)}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=t["surface"])
    plt.close(fig)
    print(f"  {path}")
    return path


# ── Project 02: gearbox family ──────────────────────────────────────────────

# The five power ratings generate_gearbox_family() builds, same order and same
# parameters — power kW, input rpm, target reduction ratio.
GEARBOX_FAMILY = [
    ("5 kW", 5, 6000, 3.5),
    ("10 kW", 10, 8000, 4.0),
    ("20 kW", 20, 10000, 4.5),
    ("30 kW", 30, 11000, 5.0),
    ("50 kW", 50, 12000, 5.5),
]


def gearbox_assembly_render(gearbox_module, theme="light"):
    """The 20 kW narrow-body design: housing, pinion and gear in mesh."""
    gearbox = gearbox_module.GearboxDesign(power_kw=20, input_speed_rpm=10000,
                                           speed_ratio=4.5)
    return shaded_render(assembly_parts(gearbox.assembly()),
                         GEARBOX_DIR / "figures" / f"gearbox-assembly{_suffix(theme)}.png",
                         theme, size=(1900, 1500), direction=(0.55, -1.15, 1.05))


def gearbox_sizing_figure(gearbox_module, theme="light"):
    """Module and tooth bending stress against power rating.

    The module line is a staircase, not a curve, because Lewis gives a
    *required* module and `round_up_to_standard_module` then snaps it up to a
    preferred size a cutter actually exists for. Every step up in module drops
    the stress well under the allowable, which is why the stress line
    sawtooths instead of tracking power — the safety factor is a consequence
    of the standard module list, not a number anyone chose."""
    t = THEMES[theme]
    powers, modules, stresses, allowable = [], [], [], None
    for _, power, rpm, ratio in GEARBOX_FAMILY:
        design = gearbox_module.GearboxDesign(power_kw=power,
                                              input_speed_rpm=rpm,
                                              speed_ratio=ratio)
        powers.append(power)
        modules.append(design.module_mm)
        stresses.append(design.actual_bending_stress_mpa)
        allowable = design.ALLOWABLE_BENDING_STRESS_MPA

    fig, ax1 = plt.subplots(figsize=(6.6, 4.3), dpi=200)
    fig.patch.set_facecolor(t["surface"])
    _style_axes(ax1, t)

    ax1.step(powers, modules, where="post", color=t["ink_muted"],
             linewidth=1.6, linestyle="--")
    ax1.plot(powers, modules, "s", color=t["ink_muted"], markersize=4)
    ax1.set_xlabel("Power rating, kW")
    ax1.set_ylabel("Standard module, mm")
    ax1.tick_params(axis="y", colors=t["ink_muted"])
    ax1.yaxis.label.set_color(t["ink_muted"])
    ax1.set_ylim(0, max(modules) * 1.6)

    ax2 = ax1.twinx()
    ax2.plot(powers, stresses, "o-", color=t["accent"], linewidth=1.8, markersize=5)
    ax2.axhline(allowable, color=t["accent"], linestyle=":", linewidth=1.2, alpha=0.75)
    ax2.annotate(f"allowable {allowable:.0f} MPa", (powers[-1], allowable),
                 textcoords="offset points", xytext=(-2, 5), fontsize=7.5,
                 color=t["accent"], ha="right")
    ax2.set_ylabel("Tooth bending stress, MPa")
    ax2.tick_params(axis="y", colors=t["accent"], labelsize=8)
    ax2.yaxis.label.set_color(t["accent"])
    ax2.set_ylim(0, allowable * 1.35)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_color(t["grid"])
    ax2.grid(False)

    ax1.set_title("Gearbox family: Lewis module sizing against power",
                  color=t["ink"], fontsize=10.5, pad=10)
    fig.tight_layout()

    path = GEARBOX_DIR / "figures" / f"gearbox-sizing{_suffix(theme)}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=t["surface"])
    plt.close(fig)
    print(f"  {path}")
    return path


# ── Entry point ─────────────────────────────────────────────────────────────

def main(argv):
    targets = set(argv[1:]) or {"actuator", "gearbox"}

    if "actuator" in targets:
        print("01-Hydraulic-Actuator")
        module = _load(ACTUATOR_DIR / "hydraulic_actuator.py", "hydraulic_actuator")
        for theme in ("light", "dark"):
            actuator_family_render(module, theme)
            actuator_assembly_render(module, theme)
            actuator_scaling_figure(module, theme)

    if "gearbox" in targets:
        print("02-Gearbox-Family")
        module = _load(GEARBOX_DIR / "gearbox_family.py", "gearbox_family")
        for theme in ("light", "dark"):
            gearbox_assembly_render(module, theme)
            gearbox_sizing_figure(module, theme)


if __name__ == "__main__":
    main(sys.argv)
