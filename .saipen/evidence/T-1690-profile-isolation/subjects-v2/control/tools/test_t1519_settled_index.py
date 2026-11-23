"""T-1519: a snapshot of a settled project does not decode its history again.

Every committed mutation settles its receipt into `.saipen/recovery/settled/`.
A whole-history receipt snapshot used to decode every one of them on every
call (live: 6879 receipts, 6879 decodes, 5.9 s per snapshot), because the
index that cached the decoded records died at the first settlement. T-1519
kept that index alive by re-authenticating and rewriting it whole at every
settlement.

SRC-026:R009 (T-1304) measured what that cost -- 6.06 s of a 7.3 s checkpoint
at 10829 receipts, one 37 MB document rewritten per command -- and moved the
same service to the bounded projection: settlement folds one receipt into it,
and the projection's decode memo answers for every receipt whose exact bytes
were already decoded. The property this file holds is unchanged; the mechanism
it names is the memo.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import journal as journal_mod  # noqa: E402
from saipen_engine import settled_projection as SP  # noqa: E402
from saipen_engine.operations import apply_claim, checkpoint  # noqa: E402
from saipen_engine.paths import project_identity  # noqa: E402
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


def strict_records(project: Path) -> list[dict]:
    """The snapshot with the memo switched off: every receipt decoded."""
    with patch.object(SP, "record_memo", lambda root: {}):
        return list(journal_mod.semantic_receipt_snapshot(project).records)


class SettledIndexTests(OrchestrationFixture):
    def busy_project(self) -> tuple[Path, str]:
        project = self.make_project()
        ticket = self.add(project, "settled index fixture")
        self.assertTrue(apply_claim(project, ticket, "tester").ok)
        for step in range(2):
            self.assertTrue(checkpoint(project, "tester", "RUN", ticket, f"step {step}").ok)
        return project, ticket

    def assert_projection_covers_every_receipt(self, project: Path) -> None:
        self.assertEqual(SP.state(project), SP.STATE_CURRENT)
        self.assertEqual(SP.validate_projection_deep(project), (True, []))
        memoized = sorted(name for name, _manifest, _progress in SP.record_memo(project))
        self.assertEqual(memoized, settled_names(project))

    def test_the_projection_is_current_after_every_settlement(self):
        project = self.make_project()
        ticket = self.add(project, "settled index fixture")
        self.assert_projection_covers_every_receipt(project)
        self.assertTrue(apply_claim(project, ticket, "tester").ok)
        self.assert_projection_covers_every_receipt(project)
        for step in range(3):
            self.assertTrue(checkpoint(project, "tester", "RUN", ticket, f"step {step}").ok)
            self.assert_projection_covers_every_receipt(project)

    def test_a_snapshot_of_a_settled_project_decodes_no_settled_receipt(self):
        project, _ = self.busy_project()
        self.assertGreaterEqual(len(settled_names(project)), 4)
        self.assertEqual(settled_decodes(project), 0)
        self.assertEqual(
            list(journal_mod.semantic_receipt_snapshot(project).records), strict_records(project)
        )

    def test_a_stale_projection_is_rebuilt_at_the_next_settlement(self):
        project, ticket = self.busy_project()
        # The crash-shaped state: the namespace moved and no advance followed.
        stray = project / journal_mod.SETTLED_DIR / ".touched"
        stray.write_bytes(b"")
        stray.unlink()
        self.assertEqual(SP.state(project), SP.STATE_STALE)
        self.assertTrue(checkpoint(project, "tester", "RUN", ticket, "heal").ok)
        self.assert_projection_covers_every_receipt(project)

    def test_a_broken_memo_costs_decodes_and_never_a_wrong_record(self):
        project, _ = self.busy_project()
        expected = strict_records(project)
        memo = project / SP.RECORDS_DIR_REL / "active.json"
        memo.write_bytes(memo.read_bytes().replace(b'"COMMITTED"', b'"ABORTED"', 1))
        self.assertEqual(SP.record_memo(project), {}, "a memo that fails its root is not used")
        self.assertEqual(settled_decodes(project), len(settled_names(project)))
        self.assertEqual(list(journal_mod.semantic_receipt_snapshot(project).records), expected)

    def test_a_tampered_settled_receipt_is_never_answered_from_the_memo(self):
        project, _ = self.busy_project()
        victim = project / journal_mod.SETTLED_DIR / settled_names(project)[0] / "operation.json"
        victim.write_bytes(victim.read_bytes() + b"\n")
        # Exactly the receipt whose bytes changed is decoded; the rest still
        # match the digests they were memoized under.
        self.assertEqual(settled_decodes(project), 1)
        self.assertEqual(
            list(journal_mod.semantic_receipt_snapshot(project).records), strict_records(project)
        )

    def test_settlement_never_rewrites_the_retired_whole_history_index(self):
        project, ticket = self.busy_project()
        retired = project / journal_mod.SETTLED_INDEX_REL
        self.assertFalse(retired.exists())
        self.assertTrue(checkpoint(project, "tester", "RUN", ticket, "one more").ok)
        self.assertFalse(retired.exists())

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
