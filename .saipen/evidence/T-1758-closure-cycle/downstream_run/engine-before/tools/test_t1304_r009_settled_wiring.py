"""SRC-026:R009 (T-1304): the journal settles into the bounded projection.

`settled_projection` was built and proven in isolation (SRC-025:R010) and then
never called: `_settle_journal` went on re-authenticating and rewriting one
monolithic index of every settled receipt, and `semantic_receipts_for_operation`
went on materializing the lifetime snapshot to filter it. Measured on this
repository's own memory, 10829 settled receipts: 6.06 s of a 7.3 s checkpoint
was that index, a 37 MB document written back on every command.

Held here, on real settlements made by real operations: a settlement folds the
one receipt it moved and never rebuilds or lists the namespace; a zero-match
operation query opens no settled receipt; a matching one opens only its own;
the bounded answer equals the strict filter; a projection that is absent or
stale is answered from the receipts and healed by the next settlement; a
projection whose bytes fail verification refuses; and the retired index is
neither written nor left behind.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import journal as journal_mod  # noqa: E402
from saipen_engine import runtime_namespace as RN  # noqa: E402
from saipen_engine import settled_projection as SP  # noqa: E402
from saipen_engine.operations import (  # noqa: E402
    apply_claim,
    checkpoint,
    ticket_move,
)
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_orchestration_repair import OrchestrationFixture  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


def settled_names(project: Path) -> list[str]:
    settled = project / journal_mod.SETTLED_DIR
    return sorted(
        entry.name
        for entry in settled.iterdir()
        if entry.is_dir() and entry.name != ".cleanup-needed"
    )


def strict_snapshot(project: Path):
    """The whole-history snapshot with the decode memo switched off."""
    with patch.object(SP, "record_memo", lambda root: {}):
        return journal_mod.semantic_receipt_snapshot(project)


class _Settled(OrchestrationFixture):
    def busy_project(self, checkpoints: int = 3) -> tuple[Path, str]:
        project = self.make_project()
        ticket = self.add(project, "settled wiring fixture")
        self.assertTrue(apply_claim(project, ticket, "tester").ok)
        for step in range(checkpoints):
            self.assertTrue(checkpoint(project, "tester", "RUN", ticket, f"step {step}").ok)
        return project, ticket

    def settled_reads(self, project: Path, function):
        """Run `function`; return its value and the settled receipt files it read."""
        settled = (project / journal_mod.SETTLED_DIR).resolve()
        real = Path.read_bytes
        seen: list[str] = []

        def counting(path, *args, **kwargs):
            try:
                relative = Path(path).resolve().relative_to(settled)
            except ValueError:
                relative = None
            if relative is not None:
                seen.append(relative.as_posix())
            return real(path, *args, **kwargs)

        with patch.object(Path, "read_bytes", counting):
            value = function()
        return value, seen


class SettlementTests(_Settled):
    def test_a_settlement_folds_the_one_receipt_it_moved(self):
        project, ticket = self.busy_project()
        before = SP._read_head(project)[0]["settled_count"]
        names_before = set(settled_names(project))
        listed: list[Path] = []
        real_entries = journal_mod._receipt_namespace_entries

        def watching(ns_dir):
            listed.append(Path(ns_dir))
            return real_entries(ns_dir)

        rebuilt = AssertionError("a settlement rebuilt the projection")
        with patch.object(SP, "rebuild_projection", side_effect=rebuilt), patch.object(
            journal_mod, "_receipt_namespace_entries", watching
        ):
            result = checkpoint(project, "tester", "RUN", ticket, "the measured settlement")
        self.assertTrue(result.ok, result.to_dict())

        settled = project / journal_mod.SETTLED_DIR
        self.assertNotIn(settled.resolve(), [path.resolve() for path in listed])
        moved = set(settled_names(project)) - names_before
        self.assertEqual(len(moved), 1)
        head = SP._read_head(project)[0]
        self.assertEqual(head["settled_count"], before + 1)
        tail_names = {member["name"] for member in SP._read_segment(project, SP.ACTIVE_ID)[1]}
        self.assertTrue(moved <= tail_names)
        self.assertEqual(SP.state(project), SP.STATE_CURRENT)
        self.assertEqual(SP.validate_projection_deep(project), (True, []))

    def test_a_settlement_reads_no_other_settled_receipt(self):
        project, ticket = self.busy_project()
        names_before = set(settled_names(project))
        result, seen = self.settled_reads(
            project, lambda: checkpoint(project, "tester", "RUN", ticket, "bounded settlement")
        )
        self.assertTrue(result.ok, result.to_dict())
        moved = set(settled_names(project)) - names_before
        self.assertEqual(len(moved), 1)
        touched = {entry.split("/", 1)[0] for entry in seen}
        self.assertTrue(touched <= moved, f"a settlement read other receipts: {touched - moved}")

    def test_the_retired_index_is_never_written_and_a_leftover_is_removed(self):
        project, ticket = self.busy_project()
        retired = project / journal_mod.SETTLED_INDEX_REL
        self.assertFalse(retired.exists())
        # A project settled by an older engine still holds one.
        retired.write_bytes(b'{"schema_version": 2, "entries": []}\n')
        self.assertEqual(SP.state(project), SP.STATE_STALE)
        self.assertTrue(checkpoint(project, "tester", "RUN", ticket, "first new settlement").ok)
        self.assertFalse(retired.exists(), "the rebuild left the retired index behind")
        self.assertEqual(SP.state(project), SP.STATE_CURRENT)
        self.assertTrue(checkpoint(project, "tester", "RUN", ticket, "second").ok)
        self.assertFalse(retired.exists())
        self.assertEqual(strict_snapshot(project).errors, ())

    def test_a_failed_advance_never_fails_the_settlement_and_heals_at_the_next(self):
        project, ticket = self.busy_project()
        with patch.object(SP, "advance_after_settlement", side_effect=OSError("disk full")):
            interrupted = checkpoint(project, "tester", "RUN", ticket, "advance lost")
        self.assertTrue(interrupted.ok, interrupted.to_dict())
        self.assertEqual(SP.state(project), SP.STATE_STALE)
        # Stale is answered from the receipts: nothing is missing, nothing refuses.
        snapshot = journal_mod.semantic_receipt_snapshot(project)
        self.assertEqual(snapshot.errors, ())
        self.assertEqual(list(snapshot.records), list(strict_snapshot(project).records))
        found = journal_mod.semantic_receipts_for_operation(project, "checkpoint")
        self.assertEqual(found, [r for r in snapshot.records if r.get("operation") == "checkpoint"])

        self.assertTrue(checkpoint(project, "tester", "RUN", ticket, "next settlement").ok)
        self.assertEqual(SP.state(project), SP.STATE_CURRENT)
        self.assertEqual(SP.validate_projection_deep(project), (True, []))

    def test_the_projection_is_machine_local_and_the_receipts_stay_durable(self):
        self.assertEqual(
            RN.runtime_class(SP.INDEX_DIR_REL + "/head.json"), "rebuildable-projection"
        )
        self.assertEqual(
            RN.runtime_class(SP.RECORDS_DIR_REL + "/active.json"), "rebuildable-projection"
        )
        self.assertIsNone(RN.runtime_class(journal_mod.SETTLED_DIR + "/op/operation.json"))
        self.assertTrue(RN.is_durable_protected(journal_mod.SETTLED_DIR + "/op/operation.json"))
        self.assertIn(SP.INDEX_DIR_REL + "/", RN.ignore_block())


class OperationQueryTests(_Settled):
    def test_a_zero_match_query_opens_no_settled_receipt_and_lists_nothing(self):
        project, _ = self.busy_project()
        listed: list[Path] = []
        real_entries = journal_mod._receipt_namespace_entries

        def watching(ns_dir):
            listed.append(Path(ns_dir).resolve())
            return real_entries(ns_dir)

        with patch.object(journal_mod, "_receipt_namespace_entries", watching):
            found, seen = self.settled_reads(
                project,
                lambda: journal_mod.semantic_receipts_for_operation(project, "no-such-operation"),
            )
        self.assertEqual(found, [])
        self.assertEqual(seen, [])
        self.assertNotIn((project / journal_mod.SETTLED_DIR).resolve(), listed)

    def test_a_matching_query_opens_only_its_own_receipts(self):
        project, _ = self.busy_project(checkpoints=4)
        strict = strict_snapshot(project)
        expected = [r for r in strict.records if r.get("operation") == "checkpoint"]
        self.assertEqual(len(expected), 4)
        found, seen = self.settled_reads(
            project, lambda: journal_mod.semantic_receipts_for_operation(project, "checkpoint")
        )
        self.assertEqual(found, expected)
        self.assertEqual(
            {entry.split("/", 1)[0] for entry in seen}, {record["op_id"] for record in expected}
        )

    def test_the_bounded_answer_equals_the_strict_filter_for_every_operation(self):
        project, _ = self.busy_project()
        strict = strict_snapshot(project)
        self.assertEqual(strict.errors, ())
        operations = {record.get("operation") for record in strict.records}
        self.assertGreaterEqual(len(operations), 3, operations)
        for operation in sorted(operations):
            with self.subTest(operation=operation):
                self.assertEqual(
                    journal_mod.semantic_receipts_for_operation(project, operation),
                    [r for r in strict.records if r.get("operation") == operation],
                )
        records, errors = journal_mod.semantic_receipts_for_operation_safe(project, "checkpoint")
        self.assertEqual(errors, ())
        self.assertEqual(records, [r for r in strict.records if r.get("operation") == "checkpoint"])

    def test_an_absent_or_stale_projection_is_answered_from_the_receipts(self):
        project, _ = self.busy_project()
        expected = journal_mod.semantic_receipts_for_operation(project, "checkpoint")
        self.assertEqual(len(expected), 3)

        stray = project / journal_mod.SETTLED_DIR / ".touched"
        stray.write_bytes(b"")
        stray.unlink()
        self.assertEqual(SP.state(project), SP.STATE_STALE)
        query = journal_mod.semantic_receipts_for_operation
        self.assertEqual(query(project, "checkpoint"), expected)

        (project / SP.HEAD_REL).unlink()
        self.assertEqual(SP.state(project), SP.STATE_ABSENT)
        self.assertEqual(query(project, "checkpoint"), expected)
        self.assertEqual(query(project, "no-such-operation"), [])

    def test_projection_bytes_that_fail_verification_refuse(self):
        project, _ = self.busy_project()
        head = project / SP.HEAD_REL
        head.write_bytes(head.read_bytes().replace(b'"sealed_count":0', b'"sealed_count":9', 1))
        self.assertEqual(SP.state(project), SP.STATE_UNTRUSTED)
        with self.assertRaises(journal_mod.SemanticReceiptCorruptionError) as raised:
            journal_mod.semantic_receipts_for_operation(project, "checkpoint")
        self.assertTrue(raised.exception.errors)
        # The receipts themselves are intact, and the whole-history snapshot
        # says so: only the bounded answer is refused.
        self.assertEqual(journal_mod.semantic_receipt_snapshot(project).errors, ())

    def test_a_tampered_matched_receipt_refuses_the_bounded_answer(self):
        project, _ = self.busy_project()
        victim = journal_mod.semantic_receipts_for_operation(project, "checkpoint")[0]["op_id"]
        manifest = project / journal_mod.SETTLED_DIR / victim / "operation.json"
        manifest.write_bytes(manifest.read_bytes() + b"\n")
        with self.assertRaises(journal_mod.SemanticReceiptCorruptionError):
            journal_mod.semantic_receipts_for_operation(project, "checkpoint")


class SnapshotTests(_Settled):
    def test_the_digest_is_the_exact_byte_digest_with_or_without_the_memo(self):
        project, _ = self.busy_project()
        warm = journal_mod.semantic_receipt_snapshot(project)
        strict = strict_snapshot(project)
        self.assertEqual(warm.digest, strict.digest)
        self.assertEqual(journal_mod.semantic_receipt_digest(project), strict.digest)
        self.assertEqual(list(warm.records), list(strict.records))

    def test_a_receipt_whose_bytes_changed_is_decoded_again(self):
        project, _ = self.busy_project()
        victim = settled_names(project)[0]
        manifest = project / journal_mod.SETTLED_DIR / victim / "operation.json"
        original = manifest.read_bytes()
        manifest.write_bytes(original.replace(b'"COMMITTED"', b'"COMMITTED!"', 1))
        broken = journal_mod.semantic_receipt_snapshot(project)
        self.assertTrue(broken.errors, "a changed receipt was answered from the memo")
        self.assertIn(victim, broken.corrupt_op_ids)
        manifest.write_bytes(original)
        self.assertEqual(journal_mod.semantic_receipt_snapshot(project).errors, ())

    def test_only_a_terminal_record_is_ever_taken_from_the_memo(self):
        project, _ = self.busy_project()
        memo = SP.record_memo(project)
        self.assertTrue(memo)
        self.assertTrue(all(r.get("status") in journal_mod.SETTLED for r in memo.values()))
        # A memo entry that claims an unresolved status is not used: the
        # receipt is decoded, and the decoder's answer is the record.
        key = next(iter(memo))
        forged = dict(memo)
        forged[key] = dict(memo[key], status="APPLYING", op_id="forged")
        with patch.object(SP, "record_memo", lambda root: forged):
            snapshot = journal_mod.semantic_receipt_snapshot(project)
        self.assertEqual(list(snapshot.records), list(strict_snapshot(project).records))


class CommitPointTests(_Settled):
    """The head is what makes a reader trust the projection, so it lands last."""

    def test_a_rebuild_interrupted_before_its_head_is_never_trusted(self):
        project, _ = self.busy_project()
        expected = journal_mod.semantic_receipts_for_operation(project, "checkpoint")
        self.assertEqual(len(expected), 3)
        # No projection at all, then a rebuild that dies while writing locators.
        for document in sorted((project / SP.INDEX_DIR_REL).rglob("*.json")):
            document.unlink()
        self.assertEqual(SP.state(project), SP.STATE_ABSENT)
        lost = patch.object(SP, "_write_locator", side_effect=OSError("power lost"))
        with lost, self.assertRaises(OSError):
            SP.rebuild_projection(project)
        # Written head-first, this left a CURRENT head over no locators and
        # the query below answered [] -- an empty answer, not a refusal.
        self.assertNotEqual(SP.state(project), SP.STATE_CURRENT)
        query = journal_mod.semantic_receipts_for_operation
        self.assertEqual(query(project, "checkpoint"), expected)

    def test_an_advance_interrupted_before_its_head_is_never_trusted(self):
        project, ticket = self.busy_project()
        query = journal_mod.semantic_receipts_for_operation
        self.assertEqual(query(project, "ticket_move"), [])
        # The first settlement of an operation has no locator yet. One
        # settlement only: a second one would rebuild and hide the window.
        with patch.object(SP, "_merge_locator_active", side_effect=OSError("power lost")):
            moved = ticket_move(project, "block", ticket, "tester", "ACTIVE -- parked")
        self.assertTrue(moved.ok, moved.to_dict())
        self.assertNotEqual(SP.state(project), SP.STATE_CURRENT)
        found = query(project, "ticket_move")
        self.assertEqual([record["op_id"] for record in found], [moved.op_id])
        # The next settlement rebuilds, and the bounded answer still holds it.
        resumed = ticket_move(project, "unblock", ticket, "tester", "resume")
        self.assertTrue(resumed.ok, resumed.to_dict())
        self.assertEqual(SP.state(project), SP.STATE_CURRENT)
        # Membership, never position: `created_at` has one-second resolution
        # and the op id -- a random name -- breaks the tie, so two moves made
        # inside one second come back in either order.
        after = query(project, "ticket_move")
        self.assertEqual({record["op_id"] for record in after}, {moved.op_id, resumed.op_id})
        self.assertIn(found[0], after)
        whole = strict_snapshot(project).records
        self.assertEqual(after, [r for r in whole if r.get("operation") == "ticket_move"])


class ContentionTests(_Settled):
    """Readers hold no lock; a settlement replaces these documents under them."""

    def refusing(self, name: str, times: int):
        """`Path.read_bytes` that loses a sharing race `times` times on `name`."""
        real = Path.read_bytes
        left = {"n": times}

        def read_bytes(path, *args, **kwargs):
            if Path(path).name == name and left["n"] > 0:
                left["n"] -= 1
                raise PermissionError(13, "The process cannot access the file", str(path))
            return real(path, *args, **kwargs)

        return patch.object(Path, "read_bytes", read_bytes), left

    def test_a_read_that_meets_a_replace_is_looked_at_again(self):
        project, _ = self.busy_project()
        expected = journal_mod.semantic_receipts_for_operation(project, "checkpoint")
        for name in ("head.json", "active.json"):
            with self.subTest(document=name):
                contended, left = self.refusing(name, 3)
                with contended, patch.object(SP.time, "sleep", lambda seconds: None):
                    self.assertEqual(SP.state(project), SP.STATE_CURRENT)
                    found = journal_mod.semantic_receipts_for_operation(project, "checkpoint")
                self.assertEqual(found, expected)
                self.assertEqual(left["n"], 0, "the refused reads were never retried")

    def test_a_document_that_stays_unreadable_is_untrusted_not_absent(self):
        project, _ = self.busy_project()
        contended, _left = self.refusing("head.json", 10_000)
        with contended, patch.object(SP.time, "sleep", lambda seconds: None):
            self.assertEqual(SP.state(project), SP.STATE_UNTRUSTED)
            with self.assertRaises(journal_mod.SemanticReceiptCorruptionError):
                journal_mod.semantic_receipts_for_operation(project, "checkpoint")

    def test_one_torn_look_is_taken_again_and_two_refuse(self):
        project, _ = self.busy_project()
        expected = journal_mod.semantic_receipts_for_operation(project, "checkpoint")
        real = SP.operation_receipts_bounded
        calls: list[int] = []

        def torn_once(root, operation):
            calls.append(1)
            if len(calls) == 1:
                return [], ("active.json: tail root disagrees with head",), True
            return real(root, operation)

        query = journal_mod.semantic_receipts_for_operation
        with patch.object(SP, "operation_receipts_bounded", torn_once):
            self.assertEqual(query(project, "checkpoint"), expected)
        self.assertEqual(len(calls), 2)

        calls.clear()

        def always_torn(root, operation):
            calls.append(1)
            return [], ("active.json: tail root disagrees with head",), True

        torn = patch.object(SP, "operation_receipts_bounded", always_torn)
        with torn, self.assertRaises(journal_mod.SemanticReceiptCorruptionError) as raised:
            query(project, "checkpoint")
        self.assertEqual(len(calls), 2)
        self.assertIn("tail root disagrees", str(raised.exception))
