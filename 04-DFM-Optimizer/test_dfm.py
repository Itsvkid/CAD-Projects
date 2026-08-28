"""Tests for the DFM checker.

These need pyOCC, and most need STEP files that live outside git (the CAD
repositories ignore generated geometry). Anything reading a part is skipped
rather than failed when its STEP is absent, so a fresh clone runs green and
a populated one runs thoroughly.

    conda run -n pyocc_env python -m pytest -q
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from OCC.Core.BRepPrimAPI import (
    BRepPrimAPI_MakeBox,
    BRepPrimAPI_MakeCylinder,
)
from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
from OCC.Extend.DataExchange import read_step_file

from dfm import DFMRules, analyse, check_holes, check_wall_thickness
from geometry import describe_faces, ray_thickness_mm

ROOT = Path(__file__).resolve().parent.parent


def part(relative):
    path = ROOT / relative
    if not path.exists():
        pytest.skip(f"{relative} not on disk — generated geometry is gitignored")
    return read_step_file(str(path))


# ── Geometry interrogation ─────────────────────────────────────────────────

def test_ray_measures_a_known_wall():
    """A 10 mm cube: a ray fired inward from any face must travel exactly
    10 mm to the far side. If this drifts, every thickness result is
    wrong by the same amount and nothing else would show it."""
    box = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
    assert ray_thickness_mm(box, (5.0, 5.0, 0.0), (0, 0, 1)) == pytest.approx(10.0)


def test_bores_and_bosses_are_told_apart():
    """The check that caught the orientation bug. A tube has one convex
    outer surface and one concave bore; an early version reported both as
    bosses because it flipped normals that BRepGProp_Face had already
    flipped."""
    outer = BRepPrimAPI_MakeCylinder(20.0, 50.0).Shape()
    inner = BRepPrimAPI_MakeCylinder(15.0, 60.0).Shape()
    tube = BRepAlgoAPI_Cut(outer, inner).Shape()
    cylinders = [f for f in describe_faces(tube) if f.kind == "cylinder"]
    assert len(cylinders) == 2
    assert {f.concave for f in cylinders} == {True, False}
    bore = next(f for f in cylinders if f.concave)
    assert bore.radius_mm == pytest.approx(15.0)


def test_wall_thickness_of_a_known_tube():
    outer = BRepPrimAPI_MakeCylinder(20.0, 50.0).Shape()
    inner = BRepPrimAPI_MakeCylinder(15.0, 60.0).Shape()
    tube = BRepAlgoAPI_Cut(outer, inner).Shape()
    _, thinnest = check_wall_thickness(tube, DFMRules.for_process("machined"))
    assert thinnest == pytest.approx(5.0, abs=0.05)


# ── Holes versus fillets ───────────────────────────────────────────────────

def test_a_bend_fillet_is_not_reported_as_a_hole():
    """The false positive this checker shipped with for an hour. The
    sheet-metal bracket's R3 bend fillet is concave and 50 mm long across
    the part, and came back as '⌀6 × 50 deep, needs gun-drilling' -- a
    confident recommendation about a feature that does not exist. A hole
    sweeps a full turn; a fillet sweeps a quarter."""
    shape = part("05-Sheet-Metal-Bracket/exports/bracket-formed.step")
    findings = check_holes(shape, DFMRules.for_process("machined"))
    assert not [f for f in findings if f.check == "HOLE ASPECT"]


def test_a_real_deep_hole_is_still_reported():
    """The other half: suppressing fillets must not suppress holes. The
    actuator's ⌀35 bore is 200 deep, which is 5.7:1 and genuinely needs
    gun-drilling."""
    shape = part("01-Hydraulic-Actuator/parts/01_cylinder_body.step")
    findings = check_holes(shape, DFMRules.for_process("machined"))
    aspects = [f for f in findings if f.check == "HOLE ASPECT"]
    assert len(aspects) == 1
    assert aspects[0].measured == pytest.approx(200 / 35, rel=0.01)


# ── Process sensitivity ────────────────────────────────────────────────────

def test_the_same_part_passes_machined_and_fails_cast():
    """The reason process is a property of the rules rather than an option.
    The actuator cylinder is turned: its bores have no draft and need none.
    Judge it as a casting and every one of them fails."""
    shape = part("01-Hydraulic-Actuator/parts/01_cylinder_body.step")
    assert analyse(shape, DFMRules.for_process("machined")).passed
    assert not analyse(shape, DFMRules.for_process("sand-cast")).passed


def test_machining_rules_never_check_draft():
    assert DFMRules.for_process("machined").checks_draft is False
    assert DFMRules.for_process("sand-cast").checks_draft is True


def test_unknown_process_is_refused():
    with pytest.raises(ValueError):
        DFMRules.for_process("wishful-thinking")


def test_overrides_reach_the_rules():
    rules = DFMRules.for_process("machined", min_wall_mm=9.9)
    assert rules.min_wall_mm == 9.9
    assert rules.checks_draft is False


# ── Against the repository's own parts ─────────────────────────────────────

def test_thickness_recovers_the_actuator_design_constant():
    """The strongest validation available: the actuator sets
    wall_thickness = 3 mm in its generator, and ray-casting the exported
    solid returns 3.00 mm without ever reading that code."""
    shape = part("01-Hydraulic-Actuator/parts/01_cylinder_body.step")
    _, thinnest = check_wall_thickness(shape, DFMRules.for_process("machined"))
    assert thinnest == pytest.approx(3.0, abs=0.02)


def test_the_gearbox_housing_fails_as_a_casting():
    """Its own README says casting draft angles are 'explicitly NOT
    modelled'. This confirms that from the geometry, having never read the
    README -- which is what makes it a check rather than a restatement."""
    shape = part("02-Gearbox-Family/parts/03_housing.step")
    report = analyse(shape, DFMRules.for_process("sand-cast"))
    assert not report.passed
    assert any(f.check == "DRAFT ANGLE" for f in report.failures)


def test_parts_pass_under_the_process_they_are_actually_made_by():
    for relative, process in [
        ("01-Hydraulic-Actuator/parts/02_piston_rod.step", "machined"),
        ("01-Hydraulic-Actuator/parts/03_clevis_end.step", "machined"),
        ("03-Thermal-Duct/exports/bleed-duct.step", "formed-tube"),
        ("05-Sheet-Metal-Bracket/exports/bracket-formed.step", "machined"),
    ]:
        report = analyse(part(relative), DFMRules.for_process(process),
                         part=relative)
        assert report.passed, report.summary()


def test_a_duct_wall_is_unmachinable_but_fine_as_tube():
    """The survey's other finding, and it was about the process assigned
    rather than the part: 0.60 mm cannot be machined from solid, and is
    ordinary for rolled and welded tube."""
    shape = part("03-Thermal-Duct/exports/bleed-duct.step")
    assert not analyse(shape, DFMRules.for_process("machined")).passed
    assert analyse(shape, DFMRules.for_process("formed-tube")).passed


def test_findings_carry_a_number_and_a_limit():
    shape = part("02-Gearbox-Family/parts/03_housing.step")
    for finding in analyse(shape, DFMRules.for_process("sand-cast")).findings:
        assert finding.measured is not None and finding.limit > 0
        assert finding.severity in ("fail", "advisory")
        assert str(finding)
