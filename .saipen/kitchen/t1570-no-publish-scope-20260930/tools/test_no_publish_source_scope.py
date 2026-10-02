"""Local closure keeps its own source obligations without publication scope debt."""

from dataclasses import replace
import hashlib
from unittest.mock import patch
import unittest

import test_source_receipts as fixtures
from saipen_engine import release


class LocalSourceClosure(unittest.TestCase):
    setUp = fixtures.SourceReceiptTests.setUp
    tearDown = fixtures.SourceReceiptTests.tearDown
    resolve = fixtures.SourceReceiptTests.resolve
    _scope_file = fixtures.SourceReceiptTests._scope_file
    _record_scope = fixtures.SourceReceiptTests._record_scope
    _complete_work = fixtures.SourceReceiptTests._complete_work
    _incomplete_work = fixtures.SourceReceiptTests._incomplete_work

    def _project(self, *, complete=True):
        (self.root / ".saipen/BOARD.md").write_text(
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
        self._scope_file("current.py")
        self._record_scope("T-001", ["current.py"])
        state = self.root / ".saipen/STATE.md"
        state.write_text(
            state.read_text(encoding="utf-8").replace("phase: PLAN", "phase: SHIP")
            .replace("task: none", "task: T-001")
            .replace("transition_from: INIT", "transition_from: REVIEW")
            .replace('next_action: "saipen plan"', 'next_action: "PHASE SHIP T-001"'),
            encoding="utf-8",
        )
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


if __name__ == "__main__":
    unittest.main()
