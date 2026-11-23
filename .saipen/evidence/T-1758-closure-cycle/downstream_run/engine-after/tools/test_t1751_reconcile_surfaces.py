"""T-1751: every operator-facing surface agrees with the reconcile verdict.

`continue` reconciles before it routes and stops when recovery needs an
operator decision. `status`, its automation block and the response digest
routed past that verdict: on SMART_VAC_CLEANER (E-241) they advertised `cc`
with no operator action due while `continue` and `recover` answered
RECONCILE_REAUTH_REQUIRED, and the operator-question gate, which admits a
handback only when the automation block says a decision is due, then refused
the one handback the refusal needs (audit/SAIPEN_20261013_1451_SMARTVAC_
RECONCILE_HANDOFF.md, SRC-242). The verdict has one owner,
`reconcile_protocol_state`; `router.reconcile_gate` projects its dry run.

The fixture's only defect is a phantom `## DONE` row -- no closure_mode,
owner, claim_time or verification evidence -- beside a legal DOING ticket, so
the reopen plan needs exactly one operator approval.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen import main as saipen_main  # noqa: E402
from saipen_engine import automation, response_surface, router  # noqa: E402
from saipen_engine.paths import identity_file_content, new_project_lineage  # noqa: E402
from saipen_engine.reconcile import (  # noqa: E402
    SAFETY_VALVE_TRIPPED,
    reconcile_protocol_state,
)
from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_legacy_lifecycle_compat import audapack_project  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


_TEMPS: list[tempfile.TemporaryDirectory] = []

STATE = (
    "---\n"
    "phase: BUILD\n"
    "task: T-9000\n"
    'next_action: "PHASE BUILD T-9000"\n'
    'blocker: ""\n'
    "transition_from: SCOUT\n"
    "saipen_version: 8\n"
    "schema_version: 3\n"
    "last_event: 102\n"
    "style_contract: " + CURRENT_STYLE_CONTRACT + "\n"
    "mode: full\n"
    "updated: 2026-09-15T00:00:00Z\n"
    "agent: test-agent\n"
    "---\n"
)
PHANTOM = "- [x] T-9003 phantom done | verify: reopened without evidence\n"
BOARD = (
    "## DOING\n"
    "- [/] T-9000 legal active work | verify: resume | owner: test-agent"
    " | claim_time: 2026-09-15T00:00:00Z\n"
    "## TODO\n"
    "## DONE\n" + PHANTOM + "## BLOCKED\n"
)
LOG = (
    "- 15.09.26 00:00 [E-098] [T-9000] [agent: test-agent] "
    "[op: ticket-00000000000000000000000000000000] DEC: ticket added via SAIOPS\n"
    "- 15.09.26 00:00 [E-099] [T-9003] [agent: test-agent] "
    "[op: ticket-00000000000000000000000000000003] DEC: ticket added via SAIOPS\n"
    "- 15.09.26 00:00 [E-100] [parent: E-099] [T-9000] [agent: test-agent] "
    "[op: claim-00000000000000000000000000000004] DEC: claimed via SAIOPS -- owner test-agent\n"
    "- 15.09.26 00:00 [E-101] [parent: E-100] [T-9000] [agent: test-agent] "
    "[op: transition-00000000000000000000000000000005] RUN: transition to SCOUT\n"
    "- 15.09.26 00:00 [E-102] [parent: E-101] [T-9000] [agent: test-agent] "
    "[op: transition-00000000000000000000000000000006] RUN: transition to BUILD\n"
)
CANONICAL = ("STATE.md", "BOARD.md", "LOG.md")


def project(*, phantom: bool = True) -> Path:
    tmp = tempfile.TemporaryDirectory(prefix="saipen-t1751-")
    _TEMPS.append(tmp)
    root = Path(tmp.name)
    memory = root / ".saipen"
    memory.mkdir()
    (memory / "IDENTITY.md").write_text(
        identity_file_content(new_project_lineage()), encoding="utf-8"
    )
    (memory / "STATE.md").write_text(STATE, encoding="utf-8")
    (memory / "BOARD.md").write_text(
        BOARD if phantom else BOARD.replace(PHANTOM, ""), encoding="utf-8"
    )
    (memory / "LOG.md").write_text(LOG, encoding="utf-8")
    return root


def run(root: Path, *args: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = saipen_main([*args, "--project-root", str(root), "--agent", "test-agent"])
    return code, out.getvalue()


def status(root: Path) -> dict:
    code, text = run(root, "status", "--json")
    payload = json.loads(text)
    assert code == 0, payload
    return payload


def canonical(root: Path) -> dict:
    return {name: (root / ".saipen" / name).read_bytes() for name in CANONICAL}


class SurfacesAgreeTests(unittest.TestCase):
    def test_status_names_the_decision_continue_refuses_on(self):
        root = project()
        payload = status(root)
        auto = payload["automation"]
        self.assertEqual(auto["disposition"], automation.WAIT_USER, auto)
        self.assertIs(auto["operator_action_due"], True)
        self.assertEqual(auto["reason_code"], "reconcile-decision")
        self.assertEqual(auto["reconcile_code"], "RECONCILE_REAUTH_REQUIRED")
        self.assertIsNone(auto["next_command"])
        # The approval-gated command is never handed out as the next step.
        self.assertIsNone(payload["computed_next_action"])
        self.assertIn("T-9003", auto["operator_action"])
        self.assertTrue(
            any(
                line.startswith("RECONCILE_REAUTH_REQUIRED: ")
                for line in payload.get("waiting_on_you") or []
            ),
            payload.get("waiting_on_you"),
        )

    def test_continue_and_recover_refuse_with_the_plan_status_names(self):
        root = project()
        auto = status(root)["automation"]
        code, text = run(root, "continue", "--json")
        refused = json.loads(text)
        self.assertEqual(code, 1)
        self.assertEqual(refused["code"], "RECONCILE_REAUTH_REQUIRED")
        code, text = run(root, "recover", "--json")
        recover = json.loads(text)
        self.assertEqual(recover["code"], "RECONCILE_REAUTH_REQUIRED")
        self.assertEqual(auto["remediation_command"], recover["canonical_next_command"])
        self.assertIn(str(recover["repair_id"])[:12], auto["operator_action"])

    def test_the_digest_names_the_decision_instead_of_the_refused_route(self):
        root = project()
        facts = response_surface.canonical_facts(root, status=status(root))
        text = response_surface.digest_from_facts(facts, reason="status", language="en")
        self.assertIn("BLOCKER: RECONCILE_REAUTH_REQUIRED -- ", text)
        self.assertIn("OPERATOR ACTION: Approve recovery plan ", text)
        self.assertIn("NEXT EXACT ACTION: NONE", text)
        self.assertNotIn("PHASE BUILD T-9000", text)
        self.assertEqual(response_surface.response_errors(text, operator_due=True), [])

    def test_the_question_gate_admits_that_decision_and_nothing_else(self):
        root = project()
        current = status(root)
        facts = response_surface.canonical_facts(root, status=current)
        context = {
            "status": current,
            "operator_action": facts.get("operator_action"),
            "canonical_surface": response_surface.digest_from_facts(facts),
        }
        exact = {"questions": [{"question": facts["operator_action"], "options": []}]}
        invented = {"questions": [{"question": "Which ticket next?", "options": []}]}
        self.assertTrue(response_surface.gate_operator_question(exact, context=context)["admitted"])
        self.assertFalse(
            response_surface.gate_operator_question(invented, context=context)["admitted"]
        )

    def test_the_projection_writes_nothing(self):
        root = project()
        before = canonical(root)
        status(root)
        run(root, "next", "--json")
        self.assertEqual(canonical(root), before)


class BoundaryTests(unittest.TestCase):
    def test_a_clean_project_still_continues(self):
        auto = status(project(phantom=False))["automation"]
        self.assertEqual(auto["disposition"], automation.CONTINUE, auto)
        self.assertIs(auto["operator_action_due"], False)
        self.assertNotIn("reconcile_code", auto)

    def test_a_tripped_valve_alone_stays_a_continuation(self):
        """`cc` is itself the valve's reauthorization (CORE-001)."""
        route = {"ok": True, "action": "PHASE BUILD T-9000", "reason": "finish"}
        valve = {
            "ok": False,
            "code": "RECONCILE_REAUTH_REQUIRED",
            "remediation": SAFETY_VALVE_TRIPPED,
            "operator_decision_available": True,
            "canonical_next_command": "saipen continue",
        }
        self.assertIsNone(router.gate_route(project(), route, reconciled=valve))

    def test_a_refusal_without_a_command_is_a_stop(self):
        route = {"ok": True, "action": "PHASE BUILD T-9000", "reason": "finish"}
        terminal = {
            "ok": False,
            "code": "RESIDUAL_DEFECTS",
            "operator_decision_available": False,
            "canonical_next_command": None,
            "detail": "a defect no local mutation can repair",
        }
        gated = router.gate_route(project(phantom=False), route, reconciled=terminal)
        self.assertEqual(gated["reason"], "reconcile-refused")
        self.assertIsNone(gated["operator_action"])
        # T-1324: a terminal refusal advertises no command, not even bare recover.
        self.assertIsNone(gated["canonical_next_command"])
        self.assertIsNone(gated["action"])
        disposition, reason = automation._routing_disposition(
            gated, gated["action"] or "", gated["reason"]
        )
        self.assertEqual((disposition, reason), (automation.BLOCKED, "reconcile-refused"))

    def test_a_route_that_already_refuses_keeps_its_refusal(self):
        refused = {"ok": False, "action": "saipen recover", "reason": "recovery-pending"}
        self.assertIsNone(router.reconcile_gate(project(), refused))

    def test_the_continuation_hands_its_verdict_over_instead_of_reconciling_twice(self):
        route = {"ok": True, "action": "PHASE BUILD T-9000", "reason": "finish"}
        with mock.patch(
            "saipen_engine.reconcile.reconcile_protocol_state",
            side_effect=AssertionError("reconciled a second time"),
        ):
            self.assertIsNone(router.reconcile_gate(project(), route, reconciled={"ok": True}))


class LegacyCarrierTests(unittest.TestCase):
    """SRC-242 R002/R004/R005 on the production shape: an operator-attested
    legacy completion stays DONE, and repeated clean diagnostics write nothing."""

    def test_attested_legacy_stays_done_on_repeated_recovery(self):
        root = audapack_project(modern_phantom=False)
        applied = reconcile_protocol_state(root, "test-agent", attest_legacy_done=["T-118"])
        self.assertTrue(applied["ok"], applied)
        before = canonical(root)
        for _ in range(2):
            again = reconcile_protocol_state(root, "test-agent")
            self.assertTrue(again["ok"], again)
            self.assertNotEqual(again.get("code"), "RECONCILE_REAUTH_REQUIRED")
        self.assertEqual(canonical(root), before)
        self.assertIn("- [x] T-118", (root / ".saipen" / "BOARD.md").read_text(encoding="utf-8"))
        auto = status(root)["automation"]
        self.assertNotEqual(auto.get("reason_code"), "reconcile-decision", auto)

    def test_a_modern_unverified_done_still_needs_its_approval(self):
        root = project()
        plan = reconcile_protocol_state(root, "test-agent", dry_run=True)
        self.assertEqual(plan["code"], "RECONCILE_REAUTH_REQUIRED")
        self.assertTrue(plan["operator_decision_available"])
        self.assertIn("T-9003", json.dumps(plan.get("operator_decisions")))


if __name__ == "__main__":
    unittest.main()
