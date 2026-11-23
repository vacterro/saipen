"""T-2056 live demonstration: a CURRENT_FAIL hands back permitted actions.

Against the user's own words: "The cc CURRENT_FAIL dead-end ... must project an
exact executable repair per blocking conformance finding". This prints the
decision payload that the cc stop route carries (diagnostic.actions,
remediation_command/primary_action, terminal) for three finding classes:
live owner, unowned finding, operator-gated class.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import conformance as C  # noqa: E402
from saipen_engine import findings  # noqa: E402
import test_conformance_repair_boundary as fixtures  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

BOARD_WITH_OWNER = """# BOARD

## DOING
- [/] T-9 [P1] existing owner of the blocked subject | verify: the subject is repaired | owner: agent | claim_time: 2026-11-14T00:00:00Z

## TODO

## BLOCKED

## DONE
"""


def diagnostics(*messages: str) -> dict:
    problems = [findings.classify("problem", message) for message in messages]
    return {
        "status": "complete",
        "ruleset_version": findings.RULESET_VERSION,
        "ruleset_fingerprint": findings.ruleset_fingerprint(),
        "problem_count": len(problems),
        "warning_count": 0,
        "problems": problems,
    }


def decide(name: str, *messages: str, board: str | None = None) -> dict:
    case = fixtures.RepairBoundaryTests(
        "test_current_fail_without_registered_repair_has_terminal_diagnosis"
    )
    case.setUp()
    case.addCleanup(case.doCleanups)
    kwargs = {"board": board} if board is not None else {}
    root = case.make_project(name, **kwargs)
    C.generate_conformance_receipt(
        root, gate="core", exit_code=1, blocking_findings=diagnostics(*messages)
    )
    return C.conformance_decision(root)


def main() -> int:
    isolate_host_session()
    scenarios = [
        (
            "live-owner",
            "ticket T-9 is ## DONE but carries no current-cycle verification evidence (classifier: none)",
            {"board": BOARD_WITH_OWNER},
        ),
        ("unowned", "ORPHAN_RECEIPT SRC-009 is not linked to any Work", {}),
        (
            "operator-gated",
            "SOURCE_CREDENTIALS_UNSAFE credential pattern in .saipen/evidence/x",
            {},
        ),
    ]
    out = {}
    for name, message, kwargs in scenarios:
        decision = decide(name, message, **kwargs)
        out[name] = {
            "status": decision["status"],
            "repair_status": decision["repair_status"],
            "remediation_command": decision["remediation_command"],
            "primary_action": decision["primary_action"],
            "terminal": decision["remediation_command"] is None,
            "operator_action_count": decision["diagnostic"].get("operator_action_count"),
            "repair_actions": decision["repair_actions"],
        }
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())