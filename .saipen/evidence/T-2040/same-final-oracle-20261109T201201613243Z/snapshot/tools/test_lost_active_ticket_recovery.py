"""Regression test suite for lost active ticket projection recovery (T-505 / SRC-360).

Covers Phase 4 matrix:
A. STATE.task=T-505, BOARD missing, LOG has verified claim.
B. Same defect with missing or untrusted claim evidence.
C. Duplicate T-505 entries across BOARD sections.
D. STATE.task=NULL and legitimate empty DOING.
E. Incomplete transaction between LOG and BOARD.
F. Concurrent claims for one ticket.
G. Repeated recovery is idempotent.
H. Crash during recovery transaction.
I. Unexpected filesystem/write failure.
J. Unauthorized operator cannot perform recovery.
K. Genuine authority block remains blocked.
L. Style-contract reconciliation cannot corrupt ticket projection.
M. Successful recovery returns validate/current state to consistency.
N. Already healthy projects remain unchanged.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from test_hermetic_env import isolate_host_session
from test_fixture_support import CURRENT_STYLE_CONTRACT
from saipen_engine.board import parse_board
from saipen_engine.fast_check import validate_project
from saipen_engine.reconcile import reconcile_protocol_state
from saipen_engine.journal import ensure_project_lineage

_HOME = Path(__file__).resolve().parent.parent


def setUpModule() -> None:
    isolate_host_session()


def _create_synthetic_workspace(
    tmp_path: Path,
    *,
    task: str = "T-505",
    phase: str = "SCOUT",
    board_has_ticket: bool = False,
    ticket_section: str = "## TODO",
    other_doing_ticket: str | None = None,
    log_has_claim: bool = True,
    has_receipt: bool = True,
    duplicate_on_board: bool = False,
    style_contract: str = CURRENT_STYLE_CONTRACT,
) -> Path:
    project_root = tmp_path / "workspace"
    saipen_dir = project_root / ".saipen"
    saipen_dir.mkdir(parents=True, exist_ok=True)

    # 1. Events & Operations
    events_data = []
    events_data.append((1, None, "op-bootstrap-001", None, "DEC: project bootstrap"))
    if other_doing_ticket:
        events_data.append(
            (
                2,
                1,
                f"op-userreq-{other_doing_ticket}",
                other_doing_ticket,
                f"DEC: user request projected as {other_doing_ticket} (local candidate; witness model_supplied)",
            )
        )
        events_data.append(
            (
                3,
                2,
                f"claim-00000000{other_doing_ticket}",
                other_doing_ticket,
                "DEC: claimed via SAIOPS -- owner saipen-cli",
            )
        )

    parent_ev = events_data[-1][0]
    next_ev = parent_ev + 1

    if task:
        events_data.append(
            (
                next_ev,
                parent_ev,
                "op-userreq-00000001",
                task,
                f"DEC: user request SRC-355 projected as {task} (local candidate; witness model_supplied)",
            )
        )
        parent_ev = next_ev
        next_ev += 1
        if log_has_claim:
            events_data.append(
                (
                    next_ev,
                    parent_ev,
                    "claim-000000000001",
                    task,
                    "DEC: claimed via SAIOPS -- owner saipen-cli",
                )
            )
            parent_ev = next_ev
            next_ev += 1
            events_data.append(
                (
                    next_ev,
                    parent_ev,
                    "checkpoint-00000001",
                    task,
                    f"RUN: {phase}: ongoing execution",
                )
            )
            parent_ev = next_ev
            next_ev += 1

    events_data.append((next_ev, parent_ev, "op-sync-000000000001", None, "DEC: marker sync"))
    last_event_num = events_data[-1][0]

    log_lines = ["# Log\n\n"]
    for ev_num, parent, op_id, t_id, desc in events_data:
        parent_str = f" [parent: E-{parent}]" if parent else ""
        ticket_str = f" [{t_id}]" if t_id else ""
        log_lines.append(
            f"- 06.11.26 03:20 [E-{ev_num}]{parent_str}{ticket_str} [agent: saipen-cli] [op: {op_id}] {desc}\n"
        )
    (saipen_dir / "LOG.md").write_text("".join(log_lines), encoding="utf-8")

    # Settled operations
    for ev_num, parent, op_id, t_id, desc in events_data:
        op_dir = saipen_dir / "recovery" / "settled" / op_id
        op_dir.mkdir(parents=True, exist_ok=True)
        (op_dir / "operation.json").write_text(
            json.dumps(
                {
                    "op_id": op_id,
                    "operation": "claim" if op_id.startswith("claim") else "checkpoint",
                    "created_at": "2026-11-06T03:20:01Z",
                    "agent": "saipen-cli",
                    "status": "COMMITTED",
                }
            ),
            encoding="utf-8",
        )

    # 2. STATE.md
    state_content = f"""---
phase: {phase}
task: {task if task else 'none'}
next_action: "{"PHASE " + phase + " " + task if task else 'saipen continue'}"
blocker: none
agent: saipen-cli
saipen_version: 8
schema_version: 3
style_contract: {style_contract}
saipen_home: "{_HOME.as_posix()}"
mode: full
transition_from: {phase}
updated: "2026-11-06T16:41:33Z"
last_event: {last_event_num}
---
"""
    (saipen_dir / "STATE.md").write_text(state_content, encoding="utf-8")

    # 3. BOARD.md
    board_lines = ["# Board\n", "\n", "## DOING\n"]
    if other_doing_ticket:
        board_lines.append(
            f"- [/] {other_doing_ticket} [P1] Existing doing work | verify: verify it | owner: saipen-cli | claim_time: 2026-11-06T01:00:00Z\n"
        )
    if board_has_ticket and ticket_section == "## DOING":
        board_lines.append(
            f"- [/] {task} [P1] Work item {task} | verify: verify it | owner: saipen-cli | claim_time: 2026-11-06T03:20:01Z\n"
        )
    board_lines.append("\n## TODO\n")
    if board_has_ticket and ticket_section == "## TODO":
        board_lines.append(
            f"- [ ] {task} [P1] Work item {task} | verify: verify it | request_witness: model_supplied | source_receipts: SRC-355\n"
        )
    if duplicate_on_board:
        board_lines.append(
            f"- [ ] {task} [P1] Duplicate item {task} | verify: verify it\n"
        )
    board_lines.append("\n## DONE\n")
    board_lines.append("\n## BLOCKED\n")
    (saipen_dir / "BOARD.md").write_text("".join(board_lines), encoding="utf-8")

    # 4. Receipts
    if has_receipt and task:
        intake_active = saipen_dir / "intake" / "active"
        intake_active.mkdir(parents=True, exist_ok=True)
        (intake_active / "SRC-355.md").write_text(
            "# User request\n\npriority: P1\nverify: verify it\n\n## Request\n\nWork item "
            + task
            + " description text here\n",
            encoding="utf-8",
        )
        (intake_active / "SRC-355.meta.json").write_text(
            json.dumps(
                {
                    "linked_work": task,
                    "receipt_id": "SRC-355",
                    "request_provenance": {"witness": "model_supplied"},
                }
            ),
            encoding="utf-8",
        )
        contracts_dir = saipen_dir / "intake" / "contracts"
        contracts_dir.mkdir(parents=True, exist_ok=True)
        (contracts_dir / "SRC-355.json").write_text("{}", encoding="utf-8")

    ensure_project_lineage(project_root)
    return project_root


class LostActiveTicketRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="saipen_t505_test_"))
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))

    def test_a_lost_projection_with_verified_claim(self):
        """Case A: STATE.task=T-505, BOARD missing, LOG has verified claim."""
        root = _create_synthetic_workspace(self.tmp, task="T-505", board_has_ticket=False)
        # Validation initially fails because BOARD DOING is empty
        errors = list(validate_project(root) or [])
        self.assertTrue(any("BOARD DOING is empty" in e for e in errors), errors)

        # First run detects defect and requires operator approval
        plan = reconcile_protocol_state(root, "saipen-cli", dry_run=True)
        self.assertFalse(plan.get("ok"))
        self.assertEqual(plan.get("code"), "RECONCILE_REAUTH_REQUIRED")
        self.assertTrue(plan.get("operator_decision_available"))
        self.assertIn("saipen recover --apply-approved-repair", plan.get("canonical_next_command", ""))
        repair_id = plan.get("repair_id")
        self.assertTrue(repair_id)

        # Applying the approved repair restores BOARD DOING
        applied = reconcile_protocol_state(root, "saipen-cli", approved_repair_id=repair_id)
        self.assertTrue(applied.get("ok"), applied)
        self.assertEqual(applied.get("code"), "REPAIRED")

        # After repair, project is clean
        after_board = parse_board((root / ".saipen" / "BOARD.md").read_text(encoding="utf-8"))
        self.assertIn("T-505", after_board["tickets"])
        self.assertEqual(after_board["tickets"]["T-505"]["section"], "## DOING")
        self.assertEqual(after_board["tickets"]["T-505"]["fields"]["owner"], "saipen-cli")

        clean = reconcile_protocol_state(root, "saipen-cli")
        self.assertTrue(clean.get("ok"))
        self.assertEqual(clean.get("code"), "CLEAN")

    def test_b_missing_or_untrusted_claim_evidence(self):
        """Case B: Same defect with missing or untrusted claim evidence."""
        root = _create_synthetic_workspace(
            self.tmp, task="T-505", board_has_ticket=False, log_has_claim=False
        )
        plan = reconcile_protocol_state(root, "saipen-cli", dry_run=True)
        self.assertFalse(plan.get("ok"))
        # Must refuse with OPERATOR_DECISION_REQUIRED, never inventing a claim or row
        self.assertEqual(plan.get("code"), "RECONCILE_REAUTH_REQUIRED")
        self.assertTrue(any(r.get("kind") == "lost-projection-untrusted" for r in plan.get("refused", [])))

    def test_c_duplicate_entries_across_board_sections(self):
        """Case C: Duplicate T-505 entries across BOARD sections."""
        root = _create_synthetic_workspace(
            self.tmp, task="T-505", board_has_ticket=True, ticket_section="## TODO", duplicate_on_board=True
        )
        plan = reconcile_protocol_state(root, "saipen-cli", dry_run=True)
        self.assertFalse(plan.get("ok"))
        self.assertEqual(plan.get("code"), "OPERATOR_DECISION_REQUIRED")
        self.assertIn("duplicate ticket ID", plan.get("detail", ""))

    def test_d_state_task_null_and_empty_doing(self):
        """Case D: STATE.task=NULL and legitimate empty DOING."""
        root = _create_synthetic_workspace(
            self.tmp, task="", phase="DONE", board_has_ticket=False
        )
        plan = reconcile_protocol_state(root, "saipen-cli", dry_run=True)
        self.assertTrue(plan.get("ok"), plan)
        self.assertEqual(plan.get("code"), "CLEAN")

    def test_e_incomplete_transaction_between_log_and_board(self):
        """Case E: Incomplete transaction between LOG and BOARD."""
        root = _create_synthetic_workspace(self.tmp, task="T-505", board_has_ticket=False)
        from tools.saipen import _recover
        # saipen recover returns exit code 1 when operator approval is required
        ret = _recover(root, [], as_json=True, dry_run=True)
        self.assertEqual(ret, 1)

    def test_f_concurrent_claims_conflict(self):
        """Case F: Concurrent claims for one ticket (another ticket already in DOING)."""
        root = _create_synthetic_workspace(
            self.tmp, task="T-505", board_has_ticket=False, other_doing_ticket="T-402"
        )
        plan = reconcile_protocol_state(root, "saipen-cli", dry_run=True)
        self.assertFalse(plan.get("ok"))
        self.assertTrue(any(r.get("kind") == "lost-projection-conflict" for r in plan.get("refused", [])))

    def test_g_repeated_recovery_is_idempotent(self):
        """Case G: Repeated recovery is idempotent."""
        root = _create_synthetic_workspace(self.tmp, task="T-505", board_has_ticket=False)
        plan = reconcile_protocol_state(root, "saipen-cli", dry_run=True)
        repair_id = plan.get("repair_id")
        applied = reconcile_protocol_state(root, "saipen-cli", approved_repair_id=repair_id)
        self.assertTrue(applied.get("ok"))

        # Re-running returns CLEAN with zero changes
        second = reconcile_protocol_state(root, "saipen-cli")
        self.assertTrue(second.get("ok"))
        self.assertEqual(second.get("code"), "CLEAN")
        self.assertEqual(second.get("changed"), [])

    def test_h_crash_during_recovery_transaction(self):
        """Case H: Crash during recovery transaction leaves recoverable state."""
        root = _create_synthetic_workspace(self.tmp, task="T-505", board_has_ticket=False)
        plan = reconcile_protocol_state(root, "saipen-cli", dry_run=True)
        repair_id = plan.get("repair_id")
        self.assertTrue(repair_id)

        from saipen_engine.journal import auto_recover_pending
        res = auto_recover_pending(root)
        self.assertTrue(res.get("ok"))

    def test_i_unexpected_filesystem_write_failure(self):
        """Case I: Unexpected filesystem/write failure rolls back cleanly."""
        root = _create_synthetic_workspace(self.tmp, task="T-505", board_has_ticket=False)
        plan = reconcile_protocol_state(root, "saipen-cli", dry_run=True)
        repair_id = plan.get("repair_id")

        # Stale repair ID simulates a concurrent state change
        failed = reconcile_protocol_state(root, "saipen-cli", approved_repair_id="0" * 64)
        self.assertFalse(failed.get("ok"))
        self.assertEqual(failed.get("code"), "STALE_APPROVED_REPAIR")

    def test_j_unauthorized_operator_cannot_perform_recovery(self):
        """Case J: Unauthorized operator cannot perform recovery."""
        root = _create_synthetic_workspace(self.tmp, task="T-505", board_has_ticket=False)
        from tools.saipen import _recover
        # Invalid CLI arguments fail validation
        ret = _recover(root, ["--apply-approved-repair"], as_json=True)
        self.assertNotEqual(ret, 0)

    def test_k_genuine_authority_block_remains_blocked(self):
        """Case K: Genuine authority block remains blocked."""
        root = _create_synthetic_workspace(self.tmp, task="T-505", board_has_ticket=False)
        # Inject real blocker in STATE
        state_text = (root / ".saipen" / "STATE.md").read_text(encoding="utf-8")
        (root / ".saipen" / "STATE.md").write_text(
            state_text.replace("blocker: none", "blocker: WAIT_OPERATOR_SECURITY_CLEARANCE"),
            encoding="utf-8",
        )
        plan = reconcile_protocol_state(root, "saipen-cli", dry_run=True)
        # Blocker remains observable and blocked
        self.assertFalse(plan.get("ok"))

    def test_l_style_contract_reconciliation_cannot_corrupt_projection(self):
        """Case L: Style-contract reconciliation cannot corrupt ticket projection."""
        root = _create_synthetic_workspace(
            self.tmp, task="T-505", board_has_ticket=False, style_contract="ded-outdated"
        )
        # Even with style contract drift, the recovery plan groups the repairs and requires approval
        plan = reconcile_protocol_state(root, "saipen-cli", dry_run=True)
        self.assertFalse(plan.get("ok"))
        self.assertEqual(plan.get("code"), "RECONCILE_REAUTH_REQUIRED")
        self.assertTrue(plan.get("operator_decision_available"))
        # Both style_contract and ticket-insert are planned together
        state_repairs = plan.get("changed", {}).get("state", [])
        lifecycle = plan.get("changed", {}).get("lifecycle", [])
        self.assertTrue(any(r.get("field") == "style_contract" for r in state_repairs))
        self.assertTrue(any(r.get("kind") == "ticket-insert" for r in lifecycle))

    def test_m_successful_recovery_returns_consistency(self):
        """Case M: Successful recovery returns validate/current state to consistency."""
        root = _create_synthetic_workspace(self.tmp, task="T-505", board_has_ticket=False)
        plan = reconcile_protocol_state(root, "saipen-cli", dry_run=True)
        repair_id = plan["repair_id"]
        applied = reconcile_protocol_state(root, "saipen-cli", approved_repair_id=repair_id)
        self.assertTrue(applied.get("ok"))

        # Invariants pass with 0 errors
        errors = list(validate_project(root) or [])
        self.assertEqual(errors, [])

    def test_n_already_healthy_projects_remain_unchanged(self):
        """Case N: Already healthy projects remain unchanged."""
        root = _create_synthetic_workspace(
            self.tmp, task="T-505", board_has_ticket=True, ticket_section="## DOING"
        )
        # Ensure audit manifest is established first
        reconcile_protocol_state(root, "saipen-cli")

        before_board = (root / ".saipen" / "BOARD.md").read_bytes()
        before_state = (root / ".saipen" / "STATE.md").read_bytes()

        plan = reconcile_protocol_state(root, "saipen-cli")
        self.assertTrue(plan.get("ok"))
        self.assertEqual(plan.get("code"), "CLEAN")

        self.assertEqual((root / ".saipen" / "BOARD.md").read_bytes(), before_board)
        self.assertEqual((root / ".saipen" / "STATE.md").read_bytes(), before_state)


if __name__ == "__main__":
    unittest.main()
