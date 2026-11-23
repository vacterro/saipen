"""SRC-237: a work inventory never overrides the session's authority brake."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import unittest

from test_automation_block import (
    AutomationFixture, BOARD_EMPTY, CONVERGENCE_OK, ROOT, _state,
)
from saipen_engine import automation
from saipen_engine.board import parse_board
from saipen_engine.router import route_next
from saipen_engine.state import parse_state_or_error

WAIT = (
    "WAIT: blocked -- T-260 residual W2-002 complete per E-3002 evidence; "
    "operator must accept-or-extend the Flush(true) power-loss durability "
    "ceiling before any further work"
)
ACTIVE = "- [/] T-260 [P1] Captured active audit | verify: all source clauses"


def captured_state() -> str:
    text = _state("SCOUT", "T-260", WAIT).replace(
        "transition_from: SHIP", "transition_from: SCOUT"
    )
    return text.replace(
        "blocker: none\n",
        "blocker: none\nexecution_intent: goal\ngoal_waves: 0\ngoal_tickets: 13\n"
        "continuation_authority: operator_required\nauthority_source: E-1\n"
        "authority_until: budget\nsafety_valve_mode: hard_wait\n",
    )


def captured_board() -> str:
    blocked = "".join(
        f"- [ ] T-{i} [P2] Held work | verify: evidence | blocker: upstream\n"
        for i in range(261, 269)
    )
    return (
        f"# Board\n## DOING\n{ACTIVE} | owner: probe | "
        "claim_time: 2026-09-06T00:00:00Z\n## TODO\n"
        "- [ ] T-283 [P2] Independent candidate | verify: evidence\n"
        "- [ ] T-284 [P2] Another candidate | verify: evidence\n"
        f"## DONE\n## BLOCKED\n{blocked}"
    )


class WaitBoundary(AutomationFixture):
    def evaluate(self, text=None, board_text=None, *, convergence=None, capability=None):
        text = captured_state() if text is None else text
        board_text = captured_board() if board_text is None else board_text
        state, error = parse_state_or_error(text)
        board = parse_board(board_text)
        self.assertFalse(board["errors"])
        route = route_next(text, board_text, pending_ops=[], conflict_ops=[],
                           audit_inbox=None, current_capability=capability)
        block = self.block(
            routed=route, state=state or {}, board=board, audit_status=self.audit(),
            convergence={"ok": False} if convergence is None else convergence,
        )
        return state, error, route, block

    def test_operator_required_wait_dominates_two_candidates_and_eight_blocked(self):
        state, error, route, block = self.evaluate()
        self.assertIsNone(error)
        self.assertEqual(state["blocker"], "none")
        self.assertEqual(state["continuation_authority"], "operator_required")
        self.assertEqual(route["action"], WAIT)
        self.assertEqual(route["executable_behavior"], "RESTATE_AND_STOP")
        self.assertEqual(block["disposition"], automation.BLOCKED)
        self.assertIsNone(block["next_command"])
        self.assertFalse(block["closure_complete"])

    def test_blocked_claimed_ticket_cannot_grant_execution(self):
        text = captured_state().replace("blocker: none", "blocker: operator decision")
        _, _, route, block = self.evaluate(text)
        self.assertEqual(route["executable_behavior"], "RESTATE_AND_STOP")
        self.assertEqual(block["disposition"], automation.BLOCKED)
        self.assertIsNone(block["next_command"])

    def test_independent_candidate_is_eligible_only_after_session_brake_absent(self):
        board = captured_board().replace(
            ACTIVE + " | owner: probe | claim_time: 2026-09-06T00:00:00Z\n", ""
        ).replace(
            "## BLOCKED\n",
            "## BLOCKED\n- [ ] T-260 [P1] Held audit | verify: evidence | blocker: operator\n",
        )
        _, _, route, block = self.evaluate(_state(), board)
        self.assertEqual(route["ticket"], "T-283")
        self.assertEqual(block["disposition"], automation.CONTINUE)
        self.assertEqual(block["next_command"], "cc")
        # Two TODO records alone grant nothing when their prerequisite is held.
        dependent = board.replace("| verify: evidence\n", "| verify: evidence | needs: T-260\n")
        _, _, route, _ = self.evaluate(_state(), dependent)
        self.assertNotEqual(route.get("ticket"), "T-283")

    def test_no_executable_work_is_not_completion(self):
        board = BOARD_EMPTY + "- [ ] T-260 [P1] Held audit | verify: evidence | blocker: upstream\n"
        _, _, _, block = self.evaluate(_state(), board)
        self.assertFalse(block["closure_complete"])
        self.assertNotEqual(block["disposition"], automation.COMPLETE)

    def test_genuine_complete_requires_all_current_closure_conditions(self):
        _, _, _, block = self.evaluate(_state(), BOARD_EMPTY, convergence=CONVERGENCE_OK)
        self.assertEqual(block["disposition"], automation.COMPLETE)
        self.assertTrue(block["closure_complete"])
        self.assertIsNone(block["next_command"])

    def test_stale_projection_cannot_certify_current_completion(self):
        stale = {**CONVERGENCE_OK, "ok": False, "reasons": ["source changed"]}
        _, _, _, block = self.evaluate(_state(), BOARD_EMPTY, convergence=stale)
        self.assertFalse(block["closure_complete"])
        self.assertNotEqual(block["disposition"], automation.COMPLETE)

    def test_contradictory_authority_tuple_fails_closed(self):
        text = captured_state().replace(
            "safety_valve_mode: hard_wait", "safety_valve_mode: checkpoint"
        )
        _, error, _, block = self.evaluate(text)
        self.assertIsNotNone(error)
        self.assertEqual(block["disposition"], automation.INVALID)
        self.assertIsNone(block["next_command"])

    def test_safety_gates_and_existing_schema_remain_intact(self):
        for category in ("manual-verify", "destructive-op", "user brake", "safety valve"):
            with self.subTest(category=category):
                text = captured_state().replace(WAIT, f"WAIT: {category} -- operator action")
                _, _, _, block = self.evaluate(text)
                self.assertEqual(block["schema_version"], 1)
                self.assertEqual(block["disposition"], automation.WAIT_USER)
                self.assertTrue(block["operator_action_due"])
                self.assertIsNone(block["next_command"])
        _, _, _, block = self.evaluate(capability="read-only")
        self.assertEqual(block["disposition"], automation.BLOCKED)
        self.assertIsNone(block["next_command"])

    def test_native_status_and_continue_use_same_snapshot_without_writes(self):
        def native(*args):
            env = {k: v for k, v in os.environ.items() if k not in {
                "SAIPEN_PROJECT_ROOT", "SAIPEN_PROJECT_LINEAGE", "SAIPEN_AGENT",
                "SAIPEN_TASK_SHA256", "SAIPEN_TASK_FILE",
            }}
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            result = subprocess.run(
                [sys.executable, "-B", str(ROOT / "tools/saipen.py"), *args],
                cwd=self.root, env=env, capture_output=True, text=True,
                encoding="utf-8", timeout=45, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return json.loads(result.stdout)

        # Canonical setup proves a real fixture claim; only this disposable
        # fixture is then assigned the incident's WAIT/authority input tuple.
        pending = captured_board().replace(
            ACTIVE + " | owner: probe | claim_time: 2026-09-06T00:00:00Z\n", ""
        ).replace("## TODO\n", "## TODO\n" + ACTIVE.replace("[/]", "[ ]") + "\n")
        (self.root / ".saipen/STATE.md").write_text(
            _state().replace("last_event: 1", "last_event: 11"), encoding="utf-8"
        )
        (self.root / ".saipen/BOARD.md").write_text(pending, encoding="utf-8")
        history = "- 08.08.26 00:00 [E-001] [T-none] DEC: fixture bootstrap\n"
        for event, ticket in enumerate([283, 284, *range(261, 269)], 2):
            history += (f"- 08.08.26 00:{event:02d} [E-{event}] "
                        f"[parent: E-{event - 1}] [T-{ticket}] DEC: fixture ticket allocation\n")
        (self.root / ".saipen/LOG.md").write_text(history, encoding="utf-8")
        native("claim", "T-260", "--agent", "probe", "--json")
        path = self.root / ".saipen/STATE.md"
        text = re.sub(r"^next_action:.*$", f'next_action: "{WAIT}"',
                      path.read_text(encoding="utf-8"), flags=re.MULTILINE)
        authority = captured_state().split("blocker: none\n", 1)[1].split("transition_from:", 1)[0]
        authority = authority.replace("goal_tickets: 13", "goal_tickets: 0")
        text = text.replace("blocker: none\n", "blocker: none\n" + authority)
        path.write_text(text, encoding="utf-8")

        def hashes():
            return {p.relative_to(self.root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in self.root.rglob("*") if p.is_file()}

        before = hashes()
        status = native("status", "--json")
        continuation = native("continue", "--dry-run", "--json")
        self.assertEqual(status["claimed_ticket"], "T-260")
        self.assertEqual(status["top_workable_ticket"], "T-283")
        self.assertEqual(status["automation"]["disposition"], automation.BLOCKED)
        self.assertIsNone(status["automation"]["next_command"])
        self.assertEqual(continuation["action"], WAIT)
        self.assertEqual(continuation["reason"], "wait")
        self.assertEqual(hashes(), before)


if __name__ == "__main__":
    unittest.main()
