"""Local closure keeps its own source obligations without publication scope debt."""

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from unittest.mock import patch
import unittest

import test_source_receipts as fixtures
from saipen_engine import intake, release
from saipen_engine.operations import checkpoint, transition_phase


class LocalSourceClosure(unittest.TestCase):
    setUp = fixtures.SourceReceiptTests.setUp
    tearDown = fixtures.SourceReceiptTests.tearDown
    resolve = fixtures.SourceReceiptTests.resolve
    _scope_file = fixtures.SourceReceiptTests._scope_file
    _record_scope = fixtures.SourceReceiptTests._record_scope
    _complete_work = fixtures.SourceReceiptTests._complete_work
    _incomplete_work = fixtures.SourceReceiptTests._incomplete_work

    def _project(self, *, complete=True):
        board_path = self.root / ".saipen/BOARD.md"
        board_path.write_text(
            "# Board\n## DOING\n"
            "- [/] T-001 current task | verify: current\n"
            "## TODO\n## DONE\n## BLOCKED\n"
            "- [ ] T-003 historical task | verify: parked | "
            "blocker: external owner | blocker_scope: ticket\n",
            encoding="utf-8",
        )
        (self.root / "VERSION").write_text("8.0.1\n", encoding="utf-8")
        make_current = self._complete_work if complete else self._incomplete_work
        make_current("current source obligation", "T-001")
        parked = self._incomplete_work("historical source obligation", "T-003")
        claimed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        board_path.write_text(
            board_path.read_text(encoding="utf-8").replace(
                "- [/] T-001 current task | verify: current",
                "- [/] T-001 current task | verify: current"
                f" | owner: old-agent | claim_time: {claimed_at}",
            ),
            encoding="utf-8",
        )
        self._scope_file("current.py")
        self._record_scope("T-001", ["current.py"])
        state = self.root / ".saipen/STATE.md"
        state.write_text(
            state.read_text(encoding="utf-8").replace("phase: PLAN", "phase: SCOUT")
            .replace("task: none", "task: T-001")
            .replace("transition_from: INIT", "transition_from: PLAN")
            .replace('next_action: "saipen plan"', 'next_action: "PHASE SCOUT T-001"'),
            encoding="utf-8",
        )
        for phase, reason in (
            ("BUILD", "fixture implementation present"),
            ("VERIFY", "fixture verification entered"),
        ):
            moved = transition_phase(self.root, phase, "old-agent", "T-001", reason)
            self.assertTrue(moved.ok, moved.to_dict())
        verified = checkpoint(
            self.root, "old-agent", "RUN", "T-001", "verify -> PASS conf: high fixture contract"
        )
        self.assertTrue(verified.ok, verified.to_dict())
        for phase, reason in (
            ("REVIEW", "fixture review PASS"),
            ("SHIP", "fixture ship entered"),
        ):
            moved = transition_phase(self.root, phase, "old-agent", "T-001", reason)
            self.assertTrue(moved.ok, moved.to_dict())
        return parked

    def _plan(self):
        # This minimal source-receipt fixture has no versioned protocol install.
        # Every source, scope, identity, STATE and BOARD gate remains real.
        with patch.object(release, "_check_parity", return_value=None):
            return release.plan_release(self.root, "ship", current_capability="no-publish")

    def _snapshot(self):
        return {
            path.relative_to(self.root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in self.root.rglob("*") if path.is_file()
        }

    def test_local_preflight_accepts_current_work_without_historical_scope(self):
        self._project()
        plan = self._plan()
        before = self._snapshot()
        result = release._preflight_plan(self.root, plan)
        self.assertTrue(result["ok"], result)
        self.assertEqual(self._snapshot(), before)

    def test_publication_still_refuses_unknown_historical_scope(self):
        self._project()
        result = release._preflight_plan(self.root, replace(self._plan(), mode="full"))
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["stage"], "SOURCE_COVERAGE", result)
        self.assertEqual(result["source_gate"]["code"], "SOURCE_SCOPE_MISSING", result)
        self.assertEqual(result["source_gate"]["work"], "T-003", result)

    def test_batch_terminal_closure_keeps_its_publication_gate(self):
        self._project()
        result = release._preflight_plan(self.root, replace(self._plan(), crew_closure=True))
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["stage"], "SOURCE_COVERAGE", result)
        self.assertEqual(result["source_gate"]["code"], "SOURCE_SCOPE_MISSING", result)
        self.assertEqual(result["source_gate"]["work"], "T-003", result)

    def test_local_closure_still_refuses_unresolved_current_source(self):
        self._project(complete=False)
        result = release._preflight_plan(self.root, self._plan())
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["stage"], "SOURCE_COVERAGE", result)
        self.assertEqual(result["source_gate"]["code"], "SOURCE_UNRESOLVED", result)
        self.assertEqual(result["source_gate"]["work"], "T-001", result)

    def test_local_closure_still_refuses_current_scope_loss(self):
        self._project()
        plan = self._plan()
        (self.root / ".saipen/kitchen/release_scope/T-001.json").unlink()
        before = self._snapshot()
        result = release._preflight_plan(self.root, plan)
        self.assertFalse(result["ok"], result)
        self.assertEqual(self._snapshot(), before)

    def test_unrelated_receipt_integrity_still_blocks_local_closure(self):
        parked = self._project()
        body = self.root / f".saipen/intake/active/{parked}.md"
        body.write_bytes(body.read_bytes() + b"\ncorrupted")
        gate = intake.release_gate(self.root, "T-001", publish=False)
        self.assertFalse(gate["ok"], gate)
        self.assertEqual(gate["code"], "SOURCE_CORRUPTION", gate)
        self.assertIn(parked, gate["detail"])

    def _assert_closed(self, plan):
        state = (self.root / ".saipen/STATE.md").read_text(encoding="utf-8")
        board = (self.root / ".saipen/BOARD.md").read_text(encoding="utf-8")
        log = (self.root / ".saipen/LOG.md").read_text(encoding="utf-8")
        digest = (self.root / ".saipen/kitchen/digest.md").read_text(encoding="utf-8")
        receipt = json.loads(
            (self.root / ".saipen/kitchen/release_receipt.json").read_text(encoding="utf-8")
        )
        self.assertIn("phase: DONE", state)
        self.assertIn("task: none", state)
        self.assertIn("- [x] T-001", board)
        self.assertIn("ship v8.0.1 -> skipped publish (no-publish: no git)", log)
        self.assertIn("done: ship v8.0.1 -> skipped publish", digest)
        self.assertEqual(receipt["op_id"], plan.op_id)
        self.assertEqual(receipt["ticket_id"], "T-001")
        self.assertEqual(receipt["mode"], "no-publish")

    def test_local_execution_closes_canonical_state_and_records_skip(self):
        self._project()
        plan = self._plan()
        with patch.object(release, "_run_gate", return_value={"ok": True}):
            result = release.execute_release(self.root, plan)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["code"], "NO_PUBLISH_MODE")
        self._assert_closed(plan)

    def test_interrupted_local_closure_recovers_all_targets(self):
        self._project()
        plan = self._plan()

        class Interrupted(Exception):
            pass

        original_mark = release._mark_target
        marked = 0

        def interrupt_after_first(journal, index):
            nonlocal marked
            original_mark(journal, index)
            marked += 1
            if marked == 1:
                raise Interrupted()

        gate_patch = patch.object(release, "_run_gate", return_value={"ok": True})
        mark_patch = patch.object(release, "_mark_target", side_effect=interrupt_after_first)
        with gate_patch, mark_patch, self.assertRaises(Interrupted):
            release.execute_release(self.root, plan)
        self.assertEqual(marked, 1)
        recovered = release.recover_release_op(self.root, plan.op_id)
        self.assertTrue(recovered["ok"], recovered)
        self.assertEqual(recovered["code"], "COMMITTED")
        self._assert_closed(plan)


if __name__ == "__main__":
    unittest.main()
