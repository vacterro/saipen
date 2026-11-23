"""Red-before-green control for CORE-003 (SRC-343 R003).

The repair for CORE-003 changes saipen/REGISTRY.json: the closed
`goal_authority.until` vocabulary gains `continuous_maintenance`, which is what
lets `shape_errors` accept the tuple `grant_fields` already produced. The test
module reads that registry from disk, so the honest control is the PRE-FIX
registry CONTENT with the test unchanged -- not a re-write of the test.

`goal_authority.shape_errors` imports `load_registry` from `.registry` at call
time, so substituting that one function is enough to put the pre-fix vocabulary
in front of the unchanged production code path.

Run from the repository root:
    python .saipen/evidence/T-1944-audit-wave3/control_core003.py
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools"))

from saipen_engine import registry  # noqa: E402


def _run(label: str) -> tuple[bool, str]:
    from test_t1944_core_wave1 import Core003MaintenanceScopeAgreesAcrossWriterAndReader

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        Core003MaintenanceScopeAgreesAcrossWriterAndReader
    )
    result = unittest.TextTestRunner(stream=open(__import__("os").devnull, "w")).run(suite)
    detail = (
        f"ran={result.testsRun} failures={len(result.failures)} errors={len(result.errors)}"
    )
    if result.failures:
        first = result.failures[0][1].strip().splitlines()[-1]
        detail += f" first={first[:120]}"
    print(f"{label:10s} {detail}", flush=True)
    return result.wasSuccessful(), detail


def main() -> int:
    current_ok, _ = _run("current")

    real_load = registry.load_registry
    pre_fix = json.loads(
        (REPO / "saipen" / "REGISTRY.json").read_text(encoding="utf-8-sig")
    )
    scopes = [
        scope
        for scope in pre_fix["goal_authority"]["until"]
        if scope != "continuous_maintenance"
    ]
    pre_fix["goal_authority"]["until"] = scopes
    print(f"pre-fix vocabulary: {scopes}", flush=True)

    def load_pre_fix(*args, **kwargs):
        return pre_fix

    registry.load_registry = load_pre_fix
    try:
        reverted_ok, _ = _run("reverted")
    finally:
        registry.load_registry = real_load

    proven = current_ok and not reverted_ok
    print()
    print(
        f"CORE-003 pair: current={'PASS' if current_ok else 'FAIL'} "
        f"reverted={'PASS' if reverted_ok else 'FAIL'} "
        f"-> {'PROVEN' if proven else 'NOT PROVEN'}",
        flush=True,
    )
    return 0 if proven else 1


if __name__ == "__main__":
    raise SystemExit(main())
