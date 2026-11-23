"""T-1681: the closure a release writes stands on an operation record.

Measured on this project on 2026-10-08 (T-1679): `saipen ship` in no-publish
mode closed the ticket, and the next `saipen continue` answered
RECONCILE_REAUTH_REQUIRED and proposed reopening it. The release applies the
finish plan's targets inside its own journal, so the settled record is
`release-...` while the two LOG lines it writes carry the finish plan's
`[op: finish-...]`, an id no record stands behind. `lifecycle_authority`
(T-1672) reads such lines as typed by hand. A full publish closes through
the same `_apply_finish_targets`.

The repaired contract: the release journal names the closure's op id, and
the ledger (`journal.resolvable_op_ids`) resolves it, so the closure is
judged an operation, right after the ship and after a crash recovery alike.
"""

from __future__ import annotations

import json
import re
import unittest
from dataclasses import replace
from unittest.mock import patch

import test_no_publish_source_scope as fixture
from saipen_engine import journal, lifecycle_authority, release
from saipen_engine.log import parse_log_line

_OP = re.compile(r"\[op: ([^\]]+)\]")


class ReleaseClosureOpTests(unittest.TestCase):
    setUp = fixture.LocalSourceClosure.setUp
    tearDown = fixture.LocalSourceClosure.tearDown
    resolve = fixture.LocalSourceClosure.resolve
    _scope_file = fixture.LocalSourceClosure._scope_file
    _record_scope = fixture.LocalSourceClosure._record_scope
    _complete_work = fixture.LocalSourceClosure._complete_work
    _incomplete_work = fixture.LocalSourceClosure._incomplete_work
    _project = fixture.LocalSourceClosure._project
    _plan = fixture.LocalSourceClosure._plan

    def closure_lines(self) -> list[str]:
        log = (self.root / ".saipen/LOG.md").read_text(encoding="utf-8")
        return [
            line
            for line in log.splitlines()
            if "[T-001]" in line and ("ship v8.0.1" in line or "ticket finished" in line)
        ]

    def assert_closure_stands_on_a_record(self, plan) -> None:
        lines = self.closure_lines()
        self.assertEqual(len(lines), 2, lines)
        ids = {_OP.search(line).group(1) for line in lines}
        self.assertEqual(len(ids), 1, ids)
        closure_id = ids.pop()
        self.assertTrue(closure_id.startswith("finish-"), closure_id)
        self.assertIn(closure_id, journal.resolvable_op_ids(self.root))
        record = json.loads(
            (self.root / journal.SETTLED_DIR / plan.op_id / "operation.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(record["closure_op_id"], closure_id)
        events = [
            parsed
            for parsed in map(
                parse_log_line,
                (self.root / ".saipen/LOG.md").read_text(encoding="utf-8").splitlines(),
            )
            if parsed is not None
        ]
        floor, head = lifecycle_authority.journal_floor(self.root, events)
        self.assertEqual([event.get("event") for event in head], [], head)
        state = (self.root / ".saipen/STATE.md").read_text(encoding="utf-8")
        self.assertRegex(state, rf"(?m)^last_event: {floor}$")

    def test_a_no_publish_ship_closes_under_an_id_the_ledger_resolves(self):
        self._project()
        plan = self._plan()
        with patch.object(release, "_run_gate", return_value={"ok": True}):
            result = release.execute_release(self.root, plan)
        self.assertTrue(result["ok"], result)
        self.assert_closure_stands_on_a_record(plan)

    def test_a_recovered_ship_closes_under_an_id_the_ledger_resolves(self):
        self._project()
        plan = self._plan()

        class Interrupted(Exception):
            pass

        original_mark = release._mark_target
        marked = 0

        def interrupt_after_first(journal_, index):
            nonlocal marked
            original_mark(journal_, index)
            marked += 1
            if marked == 1:
                raise Interrupted()

        gate_patch = patch.object(release, "_run_gate", return_value={"ok": True})
        mark_patch = patch.object(release, "_mark_target", side_effect=interrupt_after_first)
        with gate_patch, mark_patch, self.assertRaises(Interrupted):
            release.execute_release(self.root, plan)
        recovered = release.recover_release_op(self.root, plan.op_id)
        self.assertTrue(recovered["ok"], recovered)
        self.assert_closure_stands_on_a_record(plan)

    def test_the_full_publish_closure_records_the_same_id(self):
        # A full publish reaches the closure through the same helper; the git
        # stages before it are not this defect, so the closure runs alone here.
        self._project()
        plan = replace(self._plan(), mode="full")
        handle = journal.Journal(self.root, plan.op_id)
        handle.start("release", "saipen-cli", plan.project_identity, "0" * 16, [])
        release._apply_finish_targets(self.root, handle, plan, "done: fixture\n", "ship v8.0.1")
        record = handle.read()
        closure_id = record.get("closure_op_id")
        self.assertTrue(str(closure_id).startswith("finish-"), record.keys())
        lines = self.closure_lines()
        self.assertTrue(lines)
        self.assertEqual({_OP.search(line).group(1) for line in lines}, {closure_id})
        self.assertIn(closure_id, journal.resolvable_op_ids(self.root))

    def test_a_typed_finish_id_with_no_release_behind_it_still_does_not_resolve(self):
        self._project()
        self.assertNotIn("finish-" + "0" * 32, journal.resolvable_op_ids(self.root))

    def test_a_release_record_vouches_only_for_a_well_formed_id(self):
        self._project()
        settled = self.root / journal.SETTLED_DIR
        for number, alias in enumerate(
            ("verify-" + "1" * 32, "finish-../x", 7, "finish-" + "2" * 32)
        ):
            record_dir = settled / f"release-{number:032x}"
            record_dir.mkdir(parents=True)
            (record_dir / "operation.json").write_text(
                json.dumps({"op_id": record_dir.name, "closure_op_id": alias}), encoding="utf-8"
            )
        ids = journal.resolvable_op_ids(self.root)
        self.assertNotIn("verify-" + "1" * 32, ids)
        self.assertNotIn("finish-../x", ids)
        self.assertIn("finish-" + "2" * 32, ids)


if __name__ == "__main__":
    unittest.main()
