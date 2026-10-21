"""T-1752: DONE audit Work closes its Source without a second command."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import audit_inbox, board_scrub, intake, operations  # noqa: E402
from saipen_engine.board import parse_board  # noqa: E402
from test_dependency_resume_liveness import AGENT  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_t1666_receipt_close import _Receipts  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


class AuditSourceAutoClosureTests(_Receipts):
    def captured(self, *, settled: bool = True) -> tuple[Path, str, str]:
        project = self.make_project()
        layer = project / "audit/1.md"
        layer.parent.mkdir()
        layer.write_text("# audit\n\nRepair one bounded existing workflow.\n", encoding="utf-8")
        ingested = self.cli(project, "audit", "ingest")
        self.assertTrue(ingested.get("ok"), ingested)
        work, receipt = ingested["work"], ingested["receipt"]
        added = intake.add_requirement(project, receipt, rid="R1", text="repair the workflow")
        self.assertTrue(added.get("ok"), added)
        if settled:
            self.settle(project, receipt, work)
        self.ready_to_finish(project, work)
        return project, work, receipt

    def test_ticket_done_closes_before_ingest_consumes_and_before_a_new_capture(self):
        project, work, receipt = self.captured()
        finished = self.finish(project, work)
        self.assertEqual(finished.get("source_closed", {}).get("closed"), [receipt], finished)
        self.assertEqual(self.status(project, receipt), "CLOSED")
        self.assertEqual(
            audit_inbox.classify(project)["layers"][0]["state"],
            audit_inbox.CLOSED_PENDING_DELETE,
        )
        self.assertTrue((project / "audit/1.md").is_file())
        second = project / "audit/2.md"
        second.write_text("# audit\n\nA distinct next request.\n", encoding="utf-8")
        consumed = self.cli(project, "audit", "ingest")
        self.assertTrue(consumed.get("ok"), consumed)
        self.assertEqual(consumed.get("code"), "AUDIT_CONSUMED", consumed)
        self.assertFalse((project / "audit/1.md").exists())
        self.assertTrue(second.is_file())
        self.assertEqual(set(intake._read_index(project).get("active") or {}), set())

    def test_continue_finish_uses_the_same_automatic_source_closure(self):
        project, _work, receipt = self.captured()
        result = self.cli(project, "continue")
        self.assertTrue(result.get("ok"), result)
        self.assertEqual(self.status(project, receipt), "CLOSED", result)
        steps = result.get("continue_trace") or []
        self.assertEqual([step["operation"] for step in steps[:2]], ["ticket_done", "audit_ingest"])
        self.assertEqual(steps[0].get("source_closed", {}).get("closed"), [receipt])
        self.assertEqual(steps[1].get("result"), "AUDIT_CONSUMED")
        self.assertEqual(
            audit_inbox.read_binding(project)["layers"]["audit/1.md"]["state"],
            audit_inbox.DELETED,
        )
        self.assertFalse((project / "audit/1.md").exists())

    def test_clean_retains_the_pending_work_and_releases_it_after_consumption(self):
        project, work, receipt = self.captured()
        self.finish(project, work)
        # Isolate retention even on the old subject, whose auto-close is broken.
        closed = intake.close_receipt(project, receipt)
        self.assertTrue(closed.get("ok"), closed)
        entered = self.cli(project, "transition", "CLEAN")
        self.assertTrue(entered.get("ok"), entered)
        with patch.object(board_scrub, "SCRUB_DUE_BYTES", 0):
            operations.scrub_board(project, AGENT)
        tickets = parse_board((project / ".saipen/BOARD.md").read_text(encoding="utf-8"))["tickets"]
        self.assertIn(work, tickets, "the pending consume still resolves this DONE row")
        consumed = audit_inbox.consume_layer(project, "audit/1.md", AGENT)
        self.assertTrue(consumed.get("ok"), consumed)
        with patch.object(board_scrub, "SCRUB_DUE_BYTES", 0):
            scrubbed = operations.scrub_board(project, AGENT)
        self.assertTrue(scrubbed.ok, scrubbed.to_dict())
        self.assertIn(work, scrubbed.to_dict().get("pruned") or [])

    def test_unresolved_coverage_keeps_the_source_and_layer(self):
        project, work, receipt = self.captured(settled=False)
        result = self.cli(project, "ticket", "done", work, "--closure-mode", "own_patch")
        self.assertFalse(result.get("ok"), result)
        self.assertEqual(self.status(project, receipt), "ACTIVE")
        self.assertTrue((project / "audit/1.md").is_file())

    def test_another_open_work_prevents_source_closure(self):
        project, work, receipt = self.captured()
        other = self.add(project, "another required part")
        linked = intake.link_work_to(project, receipt, other)
        self.assertTrue(linked.get("ok"), linked)
        finished = self.finish(project, work)
        self.assertNotIn("source_closed", finished)
        self.assertEqual(self.status(project, receipt), "ACTIVE")

    def test_changed_generation_cannot_be_deleted_after_source_closure(self):
        project, work, receipt = self.captured()
        self.finish(project, work)
        self.assertEqual(self.status(project, receipt), "CLOSED")
        layer = project / "audit/1.md"
        changed = b"# audit\n\nNew bytes remain new Work.\n"
        layer.write_bytes(changed)
        result = audit_inbox.consume_layer(project, "audit/1.md", AGENT)
        self.assertFalse(result.get("ok"), result)
        self.assertEqual(result.get("code"), "AUDIT_GENERATION_CHANGED", result)
        self.assertEqual(layer.read_bytes(), changed)

    def test_corrupt_binding_does_not_reopen_a_source_or_allow_pruning(self):
        project, work, receipt = self.captured()
        (project / audit_inbox.BINDING_REL).write_bytes(b"{broken binding")
        self.finish(project, work)
        self.assertEqual(self.status(project, receipt), "CLOSED")
        consumed = audit_inbox.consume_layer(project, "audit/1.md", AGENT)
        self.assertEqual(consumed.get("code"), "AUDIT_BINDING_CORRUPT", consumed)
        entered = self.cli(project, "transition", "CLEAN")
        self.assertTrue(entered.get("ok"), entered)
        with patch.object(board_scrub, "SCRUB_DUE_BYTES", 0):
            refused = operations.scrub_board(project, AGENT)
        self.assertFalse(refused.ok, refused.to_dict())
        tickets = parse_board((project / ".saipen/BOARD.md").read_text(encoding="utf-8"))["tickets"]
        self.assertIn(work, tickets)
        self.assertTrue((project / "audit/1.md").is_file())


if __name__ == "__main__":
    unittest.main()
