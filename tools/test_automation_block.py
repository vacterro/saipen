"""Run-to-Closure automation projection regressions (SRC-021 R2-R8).

`audit/8.md` contracts a read-only machine surface SAIPATCH consumes: an
`automation` block on `saipen status --json` carrying a closed disposition
vocabulary, a next_command that is `cc` exactly for CONTINUE, and an
eight-condition COMPLETE gate. The acceptance bar here: the closed
vocabulary is emitted unchanged (R2), next_command obeys the R3 law for
every disposition, the R1 ownership invariant holds (SAIPEN decides from the
same evidence `status` reads, never from prose), WAIT categories map to the
right dispositions (R7), and the R5/R6 gate fails closed on every unmet
condition including the audit race rule.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine import automation  # noqa: E402
from saipen_engine.board import parse_board  # noqa: E402
from saipen_engine.router import route_next  # noqa: E402
from saipen_engine.state import parse_state_or_error  # noqa: E402

SCENARIO = ROOT / "tests" / "scenarios" / "userperson-valid" / ".saipen"

BOARD_EMPTY = "# Board\n## DOING\n## TODO\n## DONE\n## BLOCKED\n"

ALL_DISPOSITIONS = automation.DISPOSITIONS
CONTINUE = automation.CONTINUE

_I_AT = "2026-09-06T12:00:00Z"
CONVERGENCE_OK = {
    "ok": True,
    "reasons": [],
    "stages": [
        {"stage": "E", "verdict": "PASS", "op_id": "op-e", "created_at": "2026-09-06T10:00:00Z"},
        {"stage": "F", "verdict": "CLEAN", "op_id": "op-f", "created_at": "2026-09-06T10:05:00Z"},
        {
            "stage": "G",
            "verdict": "COMPLETED",
            "op_id": "op-g",
            "created_at": "2026-09-06T10:10:00Z",
        },
        {"stage": "H", "verdict": "PASS", "op_id": "op-h", "created_at": "2026-09-06T10:15:00Z"},
        {"stage": "I", "verdict": "CLEAN", "op_id": "op-i", "created_at": _I_AT},
    ],
    "source": {},
    "attribution_problems": [],
}


def _state(
    phase: str = "DONE",
    task: str = "none",
    next_action: str = "saipen continue",
) -> str:
    return (
        "---\n"
        f"phase: {phase}\n"
        f"task: {task}\n"
        f'next_action: "{next_action}"\n'
        "blocker: none\n"
        "transition_from: SHIP\n"
        "saipen_version: 7\n"
        "schema_version: 3\n"
        "last_event: 1\n"
        "style_contract: ded-4ae736e4\n"
        "agent: probe\n"
        "mode: full\n"
        "updated: 2026-09-06T00:00:00Z\n"
        "---\n"
    )


def _parsed(source: str) -> tuple[dict, dict]:
    state, err = parse_state_or_error(source)
    assert err is None, err
    return state, parse_board(BOARD_EMPTY)


class AutomationFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-automation-")
        self.root = Path(self.tmp.name) / "project"
        self.root.mkdir()
        shutil.copytree(SCENARIO, self.root / ".saipen")
        (self.root / ".saipen" / "USERPERSON.md").unlink(missing_ok=True)
        self.config = Path(self.tmp.name) / "user-config"
        self.env = patch.dict(os.environ, {"SAIPEN_USER_CONFIG_HOME": str(self.config)})
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()
        self.tmp.cleanup()

    # helpers -------------------------------------------------------------

    def block(
        self,
        *,
        routed: dict | None = None,
        state: dict | None = None,
        board: dict | None = None,
        history_events=(),
        audit_status: dict | None = None,
        convergence: dict | None = CONVERGENCE_OK,
        source_identity=None,
        agent: str | None = "probe",
    ) -> dict:
        if state is None:
            state, _ = _parsed(_state())
        if board is None:
            board = parse_board(BOARD_EMPTY)
        if source_identity is None:
            source_identity = type(
                "SID",
                (),
                {
                    "source_head": "0" * 40,
                    "source_tree_fingerprint": "git-delta-v1:" + "a" * 64,
                },
            )()
        return automation.automation_block(
            self.root,
            state=state,
            board=board,
            routed=routed,
            history_events=history_events,
            audit_status=audit_status,
            convergence=convergence,
            source_identity=source_identity,
            agent=agent,
        )

    def audit(self, *, layer_counts: int = 0, residue: bool = False) -> dict:
        from saipen_engine.audit_inbox import status

        (self.root / "audit").mkdir(exist_ok=True)
        (self.root / "audit" / ".gitkeep").write_text("", encoding="utf-8")
        if layer_counts:
            for i in range(1, layer_counts + 1):
                (self.root / "audit" / f"{i}.md").write_text("# layer\n", encoding="utf-8")
        if residue:
            (self.root / "audit" / "notes.md").write_text("x\n", encoding="utf-8")
        return status(self.root)


# ---------------------------------------------------------------------------
# R3: next_command law
# ---------------------------------------------------------------------------


class NextCommandLaw(unittest.TestCase):
    def test_only_continue_gets_cc(self) -> None:
        for disposition in ALL_DISPOSITIONS:
            if disposition == CONTINUE:
                self.assertEqual(automation._NEXT_COMMAND.get(disposition), "cc")
            else:
                self.assertIsNone(
                    automation._NEXT_COMMAND.get(disposition),
                    f"{disposition} must not carry a next_command",
                )

    def test_block_never_emits_cc_for_non_continue(self) -> None:
        for disposition in ALL_DISPOSITIONS:
            if disposition == CONTINUE:
                continue
            block = automation.failed_automation_block("x", "y")
            block = {**block, "disposition": disposition}
            self.assertIsNone(block["next_command"])


# ---------------------------------------------------------------------------
# R2: closed vocabulary
# ---------------------------------------------------------------------------


class ClosedVocabulary(AutomationFixture):
    def test_live_project_continues_with_cc(self) -> None:
        routed = route_next(
            _state(),
            BOARD_EMPTY,
            pending_ops=[],
            conflict_ops=[],
            audit_inbox=None,
        )
        block = self.block(routed=routed, audit_status=self.audit(), convergence=None)
        self.assertEqual(block["disposition"], CONTINUE)
        self.assertEqual(block["next_command"], "cc")
        self.assertEqual(block["schema_version"], 1)

    def test_diverted_unknown_disposition_cannot_be_emitted(self) -> None:
        block = self.block(routed=None)
        self.assertEqual(block["disposition"], automation.INVALID)
        self.assertIsNone(block["next_command"])
        self.assertIn(
            block["reason_code"],
            (automation.RC_AUTOMATION_FAILURE, "automation-invalid-route"),
        )

    def test_route_refusal_fails_closed(self) -> None:
        block = self.block(
            routed={"ok": False, "action": "saipen status", "reason": "state-malformed"}
        )
        self.assertEqual(block["disposition"], automation.INVALID)
        self.assertIsNone(block["next_command"])

    def test_recovery_pending_is_agent_work_not_a_stop(self) -> None:
        routed = route_next(_state(), BOARD_EMPTY, pending_ops=["op-x"], audit_inbox=None)
        self.assertEqual(routed["ok"], False)
        block = self.block(routed=routed, audit_status=self.audit(), convergence=None)
        self.assertEqual(block["disposition"], CONTINUE)
        self.assertEqual(block["next_command"], "cc")


# ---------------------------------------------------------------------------
# R1 / R7: WAIT category ownership
# ---------------------------------------------------------------------------


class WaitOwnership(AutomationFixture):
    def _wait_route(self, text: str) -> dict:
        state, _ = _parsed(_state(phase="SHIP", next_action=text))
        routed = route_next(_state(phase="SHIP", next_action=text), BOARD_EMPTY, audit_inbox=None)
        return self.block(
            routed=routed,
            state=state,
            board=parse_board(BOARD_EMPTY),
            audit_status=self.audit(),
        )

    def test_user_brake_is_a_human_stop(self) -> None:
        block = self._wait_route("WAIT: user brake -- the operator must decide")
        self.assertEqual(block["disposition"], automation.WAIT_USER)
        self.assertIsNone(block["next_command"])

    def test_manual_verify_is_a_human_stop(self) -> None:
        block = self._wait_route("WAIT: manual-verify -- double check the matrix")
        self.assertEqual(block["disposition"], automation.WAIT_USER)

    def test_safety_valve_keeps_ordinary_cc_legal(self) -> None:
        block = self._wait_route("WAIT: safety valve -- 3-waves exhausted; resume with cc")
        self.assertEqual(block["disposition"], CONTINUE)
        self.assertEqual(block["next_command"], "cc")

    def test_blocked_wait_is_a_stop(self) -> None:
        block = self._wait_route("WAIT: blocked -- upstream job is red")
        self.assertEqual(block["disposition"], automation.BLOCKED)
        self.assertIsNone(block["next_command"])

    def test_foreign_live_is_external(self) -> None:
        import datetime as _dt

        now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z"
        board = (
            "# Board\n## DOING\n- [/] T-400 [P1] live | owner: other | claim_time: "
            f"{now}\n## TODO\n## DONE\n## BLOCKED\n"
        )
        state, _ = _parsed(_state(phase="BUILD", task="none"))
        routed = route_next(
            _state(phase="BUILD", task="none"),
            board,
            audit_inbox=None,
            current_agent="probe",
        )
        self.assertEqual(routed["reason"], "foreign-live")
        block = self.block(
            routed=routed, state=state, board=parse_board(board), audit_status=self.audit()
        )
        self.assertEqual(block["disposition"], automation.WAIT_EXTERNAL)
        self.assertIsNone(block["next_command"])

    def test_read_only_session_blocks(self) -> None:
        routed = route_next(
            _state(), BOARD_EMPTY, audit_inbox=None, current_capability="read-only"
        )
        self.assertEqual(routed["reason"], "read-only-mode")
        block = self.block(routed=routed, audit_status=self.audit())
        self.assertEqual(block["disposition"], automation.BLOCKED)

    def test_audit_residue_waits_for_the_operator(self) -> None:
        routed = {
            "ok": True,
            "action": "saipen audit status",
            "reason": "audit-inbox-residue",
            "executable_behavior": "RESTATE_AND_STOP",
        }
        block = self.block(routed=routed, audit_status=self.audit(residue=True))
        self.assertEqual(block["disposition"], automation.WAIT_USER)


# ---------------------------------------------------------------------------
# R5/R6: the closure gate
# ---------------------------------------------------------------------------


class ClosureGate(AutomationFixture):
    def _idle_route(self) -> dict:
        return route_next(_state(), BOARD_EMPTY, audit_inbox=None)

    def test_full_closure_gate_yields_complete(self) -> None:
        block = self.block(
            routed=self._idle_route(),
            audit_status=self.audit(),
            history_events=[],
        )
        self.assertEqual(block["disposition"], automation.COMPLETE)
        self.assertIsNone(block["next_command"])
        self.assertTrue(block["closure_complete"])
        self.assertEqual(block["completed_at"], _I_AT)

    def test_audit_quiescence_is_required(self) -> None:
        block = self.block(
            routed=self._idle_route(),
            audit_status=self.audit(layer_counts=1),
        )
        self.assertEqual(block["disposition"], CONTINUE)
        self.assertFalse(block["closure_complete"])
        self.assertFalse(block["audit_quiescent"])

    def test_residue_vetoes_closure_although_dir_is_empty_of_layers(self) -> None:
        block = self.block(
            routed=self._idle_route(),
            audit_status=self.audit(residue=True),
        )
        self.assertEqual(block["disposition"], CONTINUE)
        self.assertFalse(block["closure_complete"])

    def test_no_convergence_evidence_vetoes_closure(self) -> None:
        block = self.block(
            routed=self._idle_route(),
            audit_status=self.audit(),
            convergence=None,
        )
        self.assertEqual(block["disposition"], CONTINUE)
        self.assertFalse(block["closure_complete"])

    def test_workable_board_work_vetoes_closure(self) -> None:
        board = (
            "# Board\n## DOING\n## TODO\n- [ ] T-500 [P1] stale | verify: proof\n"
            "## DONE\n## BLOCKED\n"
        )
        block = self.block(
            routed=self._idle_route(),
            board=parse_board(board),
            audit_status=self.audit(),
        )
        self.assertEqual(block["disposition"], CONTINUE)
        self.assertFalse(block["closure_complete"])

    def test_binding_wait_vetoes_closure(self) -> None:
        state, _ = _parsed(_state(next_action="WAIT: user brake -- wait for the human"))
        block = self.block(
            routed=self._idle_route(),
            state=state,
            audit_status=self.audit(),
        )
        self.assertEqual(block["disposition"], CONTINUE)
        self.assertFalse(block["closure_complete"])

    def test_race_rule_consume_after_convergence_vetoes_closure(self) -> None:
        block = self.block(
            routed=self._idle_route(),
            audit_status=self.audit(),
            history_events=[
                {
                    "event": 9,
                    "date": "06.09.26 12:05",
                    "taxonomy": "RUN",
                    "text": "AUDIT_INBOX_CLOSED audit/5.md sha256=x SRC-018 T-1280 coverage=10/10",
                }
            ],
        )
        self.assertEqual(block["disposition"], CONTINUE)
        self.assertFalse(block["closure_complete"])
        conds = automation.closure_gate(
            status_out=self.audit(),
            convergence=CONVERGENCE_OK,
            history_events=[
                {
                    "event": 9,
                    "date": "06.09.26 12:05",
                    "taxonomy": "RUN",
                    "text": "AUDIT_INBOX_CLOSED audit/5.md sha256=x SRC-018 T-1280 coverage=10/10",
                }
            ],
            board=None,
            state=None,
            agent="probe",
        )["conditions"]
        self.assertFalse(conds["C3"])
        self.assertFalse(conds["C5"])

    def test_race_rule_consume_before_convergence_allows_closure(self) -> None:
        block = self.block(
            routed=self._idle_route(),
            audit_status=self.audit(),
            history_events=[
                {
                    "event": 9,
                    "date": "06.09.26 10:30",
                    "taxonomy": "RUN",
                    "text": "AUDIT_INBOX_CLOSED audit/5.md sha256=x SRC-018 T-1280 coverage=10/10",
                }
            ],
        )
        self.assertEqual(block["disposition"], automation.COMPLETE)


# ---------------------------------------------------------------------------
# audit epoch determinism
# ---------------------------------------------------------------------------


class AuditEpoch(AutomationFixture):
    def test_epoch_deterministic_and_drifts_with_transport(self) -> None:
        from saipen_engine.audit_inbox import status

        e0 = automation.audit_epoch(status(self.root))
        e1 = automation.audit_epoch(status(self.root))
        self.assertEqual(e0, e1)
        self.assertTrue(e0.startswith("audit-epoch-v1:"))
        layer = self.root / "audit" / "7.md"
        layer.parent.mkdir(parents=True, exist_ok=True)
        layer.write_text("x\n", encoding="utf-8")
        self.assertNotEqual(automation.audit_epoch(status(self.root)), e0)
        layer.unlink()
        self.assertEqual(automation.audit_epoch(status(self.root)), e0)


if __name__ == "__main__":
    unittest.main()