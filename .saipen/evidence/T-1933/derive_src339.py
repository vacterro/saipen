"""Derive SRC-339's clauses from the ZAICODE handoff, then read back the result.

SRC-339 arrived with an uninterpreted contract (`clauses: {}`). This script
records the clauses the handoff actually states, through the canonical
`intake.add_requirements` batch writer: one contract revision, one
OperationPlan, zero writes if any clause is malformed.

Each clause is a distinct claim the handoff makes, not a restatement of its
prose. The two defects it reports are separable and are recorded separately.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine import intake  # noqa: E402

RECEIPT = "SRC-339"

CLAUSES = [
    {
        "rid": "R001",
        "class": "requirement",
        "text": (
            "extensions/adapters/zaicode/saipen-guard.py must seal the operator's declared "
            "intent instead of hardcoding action = \"continue\": a goal request seals "
            "action \"goal\" and an explicit grant seals action \"authorize-goal\". "
            "saipen_engine/operator_origin.py reserves goal authority only for those two "
            "actions, so a guard that seals only \"continue\" makes persistent grants "
            "unreachable for a ZAICODE operator."
        ),
    },
    {
        "rid": "R002",
        "class": "requirement",
        "text": (
            "The sealed action must be derived from the operator's own request text, not "
            "from model-supplied metadata: a prompt that is not a goal or an explicit grant "
            "still seals \"continue\", and an agent must not be able to manufacture a goal "
            "or authorize-goal seal by claiming one."
        ),
    },
    {
        "rid": "R003",
        "class": "invariant",
        "text": (
            "The safety valve must keep working: hitting goal_tickets must still trip "
            "continuation_authority to operator_required with safety_valve_mode hard_wait, "
            "and an agent CLI replay must still be refused with RECONCILE_REAUTH_REQUIRED. "
            "Renewal requires fresh operator carrier provenance, never an agent call."
        ),
    },
    {
        "rid": "R004",
        "class": "requirement",
        "text": (
            "Worker registration must make the sealed origin recognizable: the registered "
            "worker process must match the ancestry the broker requires, so a seal issued by "
            "the guard is recognized and spent exactly once rather than refused as unproven."
        ),
    },
    {
        "rid": "R005",
        "class": "invariant",
        "text": (
            "No budget may be renewed or extended without a native operator carrier. A "
            "direct CLI call by an agent, a replayed message, and a forged or copied seal "
            "all fail closed."
        ),
    },
    {
        "rid": "R006",
        "class": "non-goal",
        "text": (
            "Manually editing .saipen/STATE.md to clear a tripped goal_tickets counter is not "
            "a supported repair and must not be implemented as one. The protocol's own "
            "canonical reauthorization route is the only sanctioned path."
        ),
    },
    {
        "rid": "R007",
        "class": "acceptance-criterion",
        "text": (
            "A ZAICODE operator who sends a goal request through the native host hook is "
            "sealed with action \"goal\", and one who sends an explicit grant is sealed with "
            "action \"authorize-goal\", demonstrated by a control that would fail if the "
            "action were the hardcoded \"continue\"."
        ),
    },
    {
        "rid": "R008",
        "class": "context",
        "text": (
            "The upstream consumer is ZAICODE task T-435 (A3 Autopilot Mode 2 Hardening), "
            "which cannot complete its live end-to-end positive-finding acceptance run "
            "while every 20 tickets trip the valve into hard_wait. T-1933 repairs the "
            "protocol side only; it does not claim T-435 is complete."
        ),
    },
]


def main() -> int:
    result = intake.add_requirements(ROOT, RECEIPT, CLAUSES)
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result.get("ok"):
        return 1
    ledger = json.loads(
        (ROOT / f".saipen/intake/coverage/{RECEIPT}.json").read_text(encoding="utf-8")
    )
    print(f"\nrecorded {len(ledger['requirements'])} clauses")
    for rid in sorted(ledger["requirements"]):
        row = ledger["requirements"][rid]
        print(f"  {rid} {row['class']:22s} actionable={row['actionable']!s:5s} {row['disposition']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
