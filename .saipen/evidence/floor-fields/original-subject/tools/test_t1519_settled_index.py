"""T-1519: the settled receipt index survives its own settlement.

Every committed mutation settles its receipt (moves it into
`.saipen/recovery/settled/` and extends the content-authenticated index), and
every `mark("COMMITTED")` site then dropped the `.staged` payloads from the
already-settled directory. That moved the directory's mtime after the index
had recorded it, the stat hint stopped matching, and `_settle_journal` rebuilt
only an ABSENT index -- so the index died at the first settlement and every
reader paid the strict scan (live: 6879 receipts, 6879 decodes, 5.9 s per
snapshot). The payloads are now dropped before the receipt moves, and a stale
index is rebuilt at the next settlement.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import journal as journal_mod  # noqa: E402
from saipen_engine.operations import apply_claim, checkpoint  # noqa: E402
from saipen_engine.paths import project_identity, project_lineage_identity  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_orchestration_repair import OrchestrationFixture  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


def settled_names(project: Path) -> list[str]:
    settled = project / journal_mod.SETTLED_DIR
    return sorted(
        entry.name
        for entry in settled.iterdir()
        if entry.name not in {".cleanup-needed", journal_mod.SETTLED_INDEX_NAME}
    )


def live_index(project: Path) -> dict | None:
    return journal_mod._read_settled_index(
        project.resolve(), live_lineage=project_lineage_identity(project)
    )


def settled_decodes(project: Path) -> int:
    """Strict decodes one receipt snapshot performs."""
    calls = []
    real = journal_mod.decode_operation_record

    def counting(*args, **kwargs):
        calls.append(args[1] if len(args) > 1 else kwargs.get("op_dir"))
        return real(*args, **kwargs)

    with patch.object(journal_mod, "decode_operation_record", counting):
        journal_mod.semantic_receipt_snapshot(project)
    return len(calls)


class SettledIndexTests(OrchestrationFixture):
    def busy_project(self) -> tuple[Path, str]:
        project = self.make_project()
        ticket = self.add(project, "settled index fixture")
        self.assertTrue(apply_claim(project, ticket, "tester").ok)
        for step in range(2):
            self.assertTrue(checkpoint(project, "tester", "RUN", ticket, f"step {step}").ok)
        return project, ticket

    def assert_index_covers_every_receipt(self, project: Path) -> None:
        index = live_index(project)
        self.assertIsNotNone(index, "the settled index does not validate")
        self.assertEqual([entry["name"] for entry in index["entries"]], settled_names(project))

    def test_the_index_validates_after_every_settlement(self):
        project = self.make_project()
        ticket = self.add(project, "settled index fixture")
        self.assert_index_covers_every_receipt(project)
        self.assertTrue(apply_claim(project, ticket, "tester").ok)
        self.assert_index_covers_every_receipt(project)
        for step in range(3):
            self.assertTrue(checkpoint(project, "tester", "RUN", ticket, f"step {step}").ok)
            self.assert_index_covers_every_receipt(project)

    def test_a_snapshot_over_a_valid_index_decodes_no_settled_receipt(self):
        project, _ = self.busy_project()
        self.assertGreaterEqual(len(settled_names(project)), 4)
        self.assertEqual(settled_decodes(project), 0)

    def test_a_stale_index_is_rebuilt_at_the_next_settlement(self):
        project, ticket = self.busy_project()
        index_path = project / journal_mod.SETTLED_INDEX_REL
        document = json.loads(index_path.read_text(encoding="utf-8"))
        document["entries"] = document["entries"][:1]
        index_path.write_text(json.dumps(document), encoding="utf-8")
        self.assertIsNone(live_index(project))
        self.assertTrue(checkpoint(project, "tester", "RUN", ticket, "heal").ok)
        self.assert_index_covers_every_receipt(project)

    def test_a_tampered_settled_receipt_still_forces_the_strict_scan(self):
        project, _ = self.busy_project()
        victim = project / journal_mod.SETTLED_DIR / settled_names(project)[0] / "operation.json"
        victim.write_bytes(victim.read_bytes() + b"\n")
        self.assertIsNone(live_index(project))
        self.assertEqual(settled_decodes(project), len(settled_names(project)))

    def test_a_failed_payload_drop_is_still_reported(self):
        project = self.make_project()
        real_unlink = Path.unlink

        def stuck(path, *args, **kwargs):
            if path.suffix == ".staged":
                raise PermissionError("held open")
            return real_unlink(path, *args, **kwargs)

        content = b"cleanup probe\n"
        target = ".saipen/recovery/t1519-probe.txt"
        with patch.object(Path, "unlink", stuck):
            result = journal_mod.run_mutation(
                project,
                op_id="t1519-cleanup-probe",
                operation="t1519.probe",
                agent="tester",
                project_identity=project_identity(project),
                semantic_payload_hash=journal_mod.hash_bytes(content),
                targets=[
                    {
                        "path": target,
                        "role": "report",
                        "action": "write",
                        "content": content,
                        "before_hash": "",
                        "after_hash": journal_mod.hash_bytes(content),
                    }
                ],
                preconditions={target: ""},
            )
        self.assertTrue(result["ok"], result)
        self.assertEqual(
            result.get("cleanup_pending"),
            ["staged payloads unlink failed for t1519-cleanup-probe; cleanup queued"],
        )
        marker = project / journal_mod.CLEANUP_QUEUE_DIR / "t1519-cleanup-probe"
        self.assertTrue(marker.is_file(), "the cleanup-debt marker was not published")
        leftovers = list(
            (project / journal_mod.SETTLED_DIR / "t1519-cleanup-probe").glob("*.staged")
        )
        self.assertTrue(leftovers, "the stuck payload should remain for compact_committed")
