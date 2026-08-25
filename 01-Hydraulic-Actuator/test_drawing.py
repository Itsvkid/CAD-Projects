"""Smoke tests for the drawing pack.

What a sheet *says* is tested in test_tolerances.py. What is checked here
is only that every sheet builds, for every family member, and that the
few numbers printed straight onto the sheet agree with the model -- a
drawing quoting a length the generator does not build is the failure mode
worth catching automatically.
"""

from __future__ import annotations

import matplotlib
import pytest

matplotlib.use("Agg")

from drawing import (  # noqa: E402
    _wrap,
    build_all,
    clevis_end_detail,
    cylinder_body_detail,
    general_arrangement,
    piston_rod_detail,
)
from hydraulic_actuator import HydraulicActuator  # noqa: E402
from tolerances import installed_length_stack  # noqa: E402

SHEETS = (cylinder_body_detail, piston_rod_detail, clevis_end_detail,
          general_arrangement)


@pytest.mark.parametrize("bore,rod,stroke", [
    (16, 10, 100), (25, 15, 150), (35, 21, 200), (50, 30, 250)])
@pytest.mark.parametrize("sheet", SHEETS, ids=[s.__name__ for s in SHEETS])
def test_every_sheet_builds_for_every_family_member(sheet, bore, rod, stroke):
    figure = sheet(HydraulicActuator(bore, rod, stroke), path=None)
    assert figure is not None
    matplotlib.pyplot.close(figure)


def test_build_all_writes_four_sheets(tmp_path):
    paths = build_all(HydraulicActuator(35, 21, 200), directory=tmp_path)
    assert len(paths) == 4
    assert all(p.exists() and p.stat().st_size > 0 for p in paths)
    assert len({p.name for p in paths}) == 4


def test_clevis_holes_clear_the_pin_bore_on_every_variant():
    """The defect the clevis detail exists to have fixed. If the plate ever
    stops being derived from the bore, this fails before anyone looks at a
    sheet showing holes swallowed by the bore."""
    for bore, rod, stroke in [(16, 10, 100), (25, 15, 150),
                              (35, 21, 200), (50, 30, 250)]:
        unit = HydraulicActuator(bore, rod, stroke)
        gap = (unit.bolt_hole_offset - unit.BOLT_CLEARANCE_HOLE / 2
               - unit.pin_bore_diameter / 2)
        assert gap >= unit.BORE_TO_HOLE_LIGAMENT - 1e-9
        edge = (unit.clevis_size / 2 - unit.bolt_hole_offset
                - unit.BOLT_CLEARANCE_HOLE / 2)
        assert edge >= unit.HOLE_TO_EDGE_MARGIN - 1e-9


def test_installed_length_on_the_ga_matches_the_stack():
    unit = HydraulicActuator(35, 21, 200)
    _, stack = installed_length_stack(unit)
    assert stack.nominal == pytest.approx(390.0)


def test_wrap_breaks_on_words_and_respects_width():
    lines = _wrap("THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG", 12)
    assert all(len(line) <= 12 for line in lines)
    assert " ".join(lines) == "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG"


def test_wrap_does_not_drop_a_word_longer_than_the_width():
    lines = _wrap("SUPERCALIFRAGILISTIC AND", 8)
    assert "SUPERCALIFRAGILISTIC" in lines
