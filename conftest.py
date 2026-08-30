"""Let `pytest` at the repository root do something sensible.

These five projects are independent and do not share a dependency set.
Projects 01, 02 and 05 build on CadQuery; 03 and 04 build on pythonocc,
which lives in a separate conda environment because the two do not
coexist comfortably. No single interpreter can import both.

Without this file, running `pytest` here **stops before running
anything**: pytest treats an unimportable test module as a collection
error, and collection errors abort the session. The result was that
`pytest` at the root reported errors and zero tests while all 134 passed
perfectly well when run per project.

So: skip the projects whose backend is absent, and say so in the header
rather than silently. A test run that quietly covers half of what you
think it covers is worse than one that fails.

For the whole suite in one command, use `python run_tests.py`, which
dispatches each project to the interpreter it needs.
"""

from __future__ import annotations

import importlib.util

CADQUERY_PROJECTS = ("01-Hydraulic-Actuator", "02-Gearbox-Family",
                     "05-Sheet-Metal-Bracket")
PYTHONOCC_PROJECTS = ("03-Thermal-Duct", "04-DFM-Optimizer")


def _available(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


HAS_CADQUERY = _available("cadquery")
HAS_PYTHONOCC = _available("OCC")

collect_ignore_glob = []
if not HAS_CADQUERY:
    collect_ignore_glob += [f"{p}/test_*.py" for p in CADQUERY_PROJECTS]
if not HAS_PYTHONOCC:
    collect_ignore_glob += [f"{p}/test_*.py" for p in PYTHONOCC_PROJECTS]


def pytest_report_header(config):
    """Say what is not being run, and how to run it."""
    lines = [
        f"backends: cadquery={'yes' if HAS_CADQUERY else 'NO'}  "
        f"pythonocc={'yes' if HAS_PYTHONOCC else 'NO'}"
    ]
    skipped = []
    if not HAS_CADQUERY:
        skipped += list(CADQUERY_PROJECTS)
    if not HAS_PYTHONOCC:
        skipped += list(PYTHONOCC_PROJECTS)
    if skipped:
        lines.append("SKIPPED (backend not in this interpreter): "
                     + ", ".join(skipped))
        lines.append("run `python run_tests.py` for the whole suite")
    return lines
