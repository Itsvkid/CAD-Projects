#!/usr/bin/env python3
"""Run every project's tests in the interpreter it needs.

    python run_tests.py

No single interpreter can run all of these: projects 01, 02 and 05 need
CadQuery and 03 and 04 need pythonocc, and the two do not share an
environment here. Rather than pretend otherwise, this dispatches each
project to the right Python and adds up what actually ran.

Exit code is non-zero if any project fails, so it works in CI.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Project, and the module its tests cannot run without.
PROJECTS = [
    ("01-Hydraulic-Actuator", "cadquery"),
    ("02-Gearbox-Family", "cadquery"),
    ("03-Thermal-Duct", "OCC"),
    ("04-DFM-Optimizer", "OCC"),
    ("05-Sheet-Metal-Bracket", "cadquery"),
]

# Interpreters to try for each backend, in order. The bare names come last
# so a machine that has everything in one place still works.
CANDIDATES = {
    "cadquery": ["/opt/anaconda3/bin/python3", sys.executable, "python3"],
    "OCC": ["/opt/anaconda3/envs/pyocc_env/bin/python", sys.executable, "python3"],
}


def interpreter_for(backend: str) -> str | None:
    """First interpreter on the list that can actually import the backend."""
    for candidate in CANDIDATES[backend]:
        path = candidate if Path(candidate).exists() else shutil.which(candidate)
        if not path:
            continue
        probe = subprocess.run(
            [path, "-c", f"import {backend}"],
            capture_output=True, text=True)
        if probe.returncode == 0:
            return path
    return None


def run(project: str, backend: str):
    directory = ROOT / project
    if not (directory.exists() and list(directory.glob("test_*.py"))):
        return project, "no tests", 0, True

    python = interpreter_for(backend)
    if python is None:
        return project, f"skipped — no interpreter with {backend}", 0, True

    result = subprocess.run(
        [python, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=directory, capture_output=True, text=True)
    tail = [l for l in result.stdout.strip().splitlines() if l.strip()]
    summary = tail[-1] if tail else "no output"
    match = re.search(r"(\d+) passed", summary)
    count = int(match.group(1)) if match else 0
    return project, summary, count, result.returncode == 0


def main() -> int:
    print(f"Running every project's tests in the interpreter it needs\n"
          f"{'=' * 68}")
    total, failures = 0, []
    for project, backend in PROJECTS:
        name, summary, count, ok = run(project, backend)
        total += count
        status = "ok  " if ok else "FAIL"
        print(f"  {status}  {name:24s} {summary}")
        if not ok:
            failures.append(name)
    print("=" * 68)
    print(f"  {total} tests passed across {len(PROJECTS)} projects")
    if failures:
        print(f"  FAILING: {', '.join(failures)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
