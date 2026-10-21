"""T-1801: journal settlement of a closed capture whose transport vanished."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import audit_inbox, intake, journal  # noqa: E402
from test_dependency_resume_liveness import AGENT  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_t1666_receipt_close import _Receipts  # noqa: E402
import test_t1752_audit_auto_close as audit_fixture  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


class MissingAuditSettlementTests(_Receipts):
    def missing_closed(self) -> tuple[Path, str, str]:
        project, work, receipt = audit_fixture.AuditSourceAutoClosureTests.captured(self)
        self.finish(project, work)
        self.assertEqual(self.status(project, receipt), "CLOSED")
        (project / "audit/1.md").unlink()
        return project, work, receipt

    def test_ingest_settles_the_absent_capture_and_releases_its_work(self):
        project, work, receipt = self.missing_closed()
        self.assertIn(work, intake.active_receipt_works(project)[1])
        result = self.cli(project, "audit", "ingest")
        self.assertEqual(result.get("code"), "AUDIT_CONSUMED", result)
        self.assertTrue(result["consumed"][0].get("already_absent"), result)
        self.assertEqual(
            audit_inbox.read_binding(project)["layers"]["audit/1.md"]["state"],
            audit_inbox.DELETED,
        )
        self.assertNotIn(work, intake.active_receipt_works(project)[1])
        self.assertEqual(self.status(project, receipt), "CLOSED")
        settled = list((project / ".saipen/recovery/settled").glob("audit-consume-*"))
        self.assertTrue(settled, "metadata settlement must use the real journal")

    def test_read_only_projection_names_cleanup_without_rewriting_the_binding(self):
        project, _work, _receipt = self.missing_closed()
        binding = project / audit_inbox.BINDING_REL
        before = binding.read_bytes()
        route = audit_inbox.projection(project)
        self.assertIsNotNone(route)
        self.assertEqual(route["action"], "saipen audit ingest")
        self.assertEqual(route["path"], "audit/1.md")
        self.assertIn("absent", route["detail"])
        self.assertEqual(binding.read_bytes(), before)

    def test_a_missing_audit_directory_still_settles_its_closed_capture(self):
        project, work, _receipt = self.missing_closed()
        (project / "audit").rmdir()
        result = self.cli(project, "audit", "ingest")
        self.assertEqual(result.get("code"), "AUDIT_CONSUMED", result)
        self.assertNotIn(work, intake.active_receipt_works(project)[1])

    def test_absent_closed_capture_is_settled_before_a_new_drop_is_captured(self):
        project, _work, _receipt = self.missing_closed()
        new_layer = project / "audit/2.md"
        new_layer.write_text("# audit\n\nA distinct next generation.\n", encoding="utf-8")
        result = self.cli(project, "audit", "ingest")
        self.assertEqual(result.get("code"), "AUDIT_CONSUMED", result)
        self.assertTrue(new_layer.is_file())
        self.assertEqual(set(intake._read_index(project).get("active") or {}), set())

    def test_repeated_ingest_after_settlement_is_a_canonical_byte_noop(self):
        project, _work, _receipt = self.missing_closed()
        first = self.cli(project, "audit", "ingest")
        self.assertEqual(first.get("code"), "AUDIT_CONSUMED", first)
        paths = [".saipen/STATE.md", ".saipen/BOARD.md", ".saipen/LOG.md", audit_inbox.BINDING_REL]
        before = {path: (project / path).read_bytes() for path in paths}
        second = self.cli(project, "audit", "ingest")
        self.assertTrue(second.get("ok"), second)
        self.assertEqual({path: (project / path).read_bytes() for path in paths}, before)

    def test_an_active_source_with_a_missing_transport_is_not_settled(self):
        project, _work, receipt = audit_fixture.AuditSourceAutoClosureTests.captured(
            self, settled=False,
        )
        (project / "audit/1.md").unlink()
        self.cli(project, "audit", "ingest")
        self.assertEqual(self.status(project, receipt), "ACTIVE")
        self.assertEqual(
            audit_inbox.read_binding(project)["layers"]["audit/1.md"]["state"],
            audit_inbox.ACTIVE,
        )

    def test_a_changed_surviving_generation_and_uncaptured_residue_are_preserved(self):
        project, _work, _receipt = self.missing_closed()
        changed = project / "audit/1.md"
        changed.write_bytes(b"# audit\nNew surviving generation.\n")
        residue = project / "audit/keep.bin"
        residue.write_bytes(b"uncaptured bytes")
        state = audit_inbox.classify(project)
        self.assertEqual(state["layers"][0]["state"], audit_inbox.NEW)
        refused = audit_inbox.consume_layer(project, "audit/1.md", AGENT)
        self.assertEqual(refused.get("code"), "AUDIT_GENERATION_CHANGED", refused)
        self.assertEqual(changed.read_bytes(), b"# audit\nNew surviving generation.\n")
        self.assertEqual(residue.read_bytes(), b"uncaptured bytes")

    def test_reappearance_after_the_absence_proof_refuses_metadata_commit(self):
        project, _work, _receipt = self.missing_closed()
        binding = project / audit_inbox.BINDING_REL
        before = binding.read_bytes()
        real_mutation = journal.run_mutation
        appeared = b"# audit\nAppeared between the gate and APPLY.\n"

        def reappear(*args, **kwargs):
            (project / "audit/1.md").write_bytes(appeared)
            return real_mutation(*args, **kwargs)

        with patch.object(journal, "run_mutation", side_effect=reappear):
            result = audit_inbox.consume_layer(project, "audit/1.md", AGENT)
        self.assertFalse(result.get("ok"), result)
        self.assertEqual(result.get("code"), "STALE_STATE", result)
        self.assertEqual(binding.read_bytes(), before)
        self.assertEqual((project / "audit/1.md").read_bytes(), appeared)


if __name__ == "__main__":
    unittest.main()
