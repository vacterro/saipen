"""Before/after pair for the T-1829 publication boundary (R003).

One discriminating variable: whether `release._run_gate` consults
`focused_unit.publication_gate` before it spends the external validator.

Both arms are measured against the SAME live tree, with the SAME oracle
(a recording stand-in for `subprocess.run`), so the only difference is the
gate. No validator is actually executed and nothing is written.

Run: python .saipen/evidence/T-1829-cost-collapse/publication_pair.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine import focused_unit, release  # noqa: E402


class Recorder:
    """A stand-in for subprocess.run that records instead of executing."""

    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def __call__(self, command, **kwargs):  # noqa: ANN001, ANN003
        self.commands.append([str(part) for part in command])

        class Completed:
            returncode = 0
            stdout = ""
            stderr = ""

        return Completed()


def measure(gate_attached: bool) -> dict:
    recorder = Recorder()
    patches = [mock.patch.object(release.subprocess, "run", recorder)]
    if not gate_attached:
        # The pre-fix implementation: the publication boundary is never asked.
        patches.append(mock.patch.object(focused_unit, "publication_gate", return_value=None))
    for patcher in patches:
        patcher.start()
    try:
        verdict = release._run_gate(ROOT, "ship")
    finally:
        for patcher in reversed(patches):
            patcher.stop()
    return {
        "gate_attached": gate_attached,
        "external_validator_invoked": bool(recorder.commands),
        "gate_ok": bool(verdict.get("ok")),
        "detail": str(verdict.get("detail") or ""),
    }


def discriminating_fact() -> str | None:
    """The live reason the boundary must refuse, or None when it may pass."""
    return focused_unit.publication_gate(ROOT)


def main() -> int:
    live_reason = discriminating_fact()
    before = measure(gate_attached=False)
    after = measure(gate_attached=True)
    payload = {
        "schema": 1,
        "ticket": "T-1829",
        "requirement": "SRC-285:R003",
        "discriminating_variable": "focused_unit.publication_gate consulted by release._run_gate",
        "live_tree_publication_problem": live_reason,
        "before": before,
        "after": after,
        "writes_canonical_state": False,
        "validator_actually_executed": False,
        "oracle": "recording stand-in for subprocess.run; identical in both arms",
    }
    # The pair is meaningful only if the arms differ on the one variable and
    # the external validator is spared exactly when the boundary refuses.
    checks = {
        "before_reached_the_validator": before["external_validator_invoked"] is True,
        "after_refused_before_the_validator": after["external_validator_invoked"] is False,
        "after_reports_the_publication_problem": (
            after["detail"].startswith("FAIL: core-unit publication --")
            if live_reason
            else after["gate_ok"] is True
        ),
        "arms_differ_only_by_the_gate": (
            before["gate_attached"] is False and after["gate_attached"] is True
        ),
    }
    payload["checks"] = checks
    payload["pair_holds"] = all(checks.values())
    out = Path(__file__).with_name("publication-pair.json")
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"pair_holds": payload["pair_holds"], "checks": checks,
                      "live_problem": live_reason}, indent=2))
    return 0 if payload["pair_holds"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
