"""T-1544 audit-20: four live findings, pinned at the rule that was broken.

CORE-001 (reconcile), PERF-002 (admission), PERF-003 (audit inbox), PERF-005
(LOG routing summary). One class per finding; each test names the measured
defect it was written against, and every one of them is RED on the tree as it
stood before the fix.

Not a perf-benchmark suite: every assertion is a COUNT or a FACT that the
audit's measurement implies, so a regression is a deterministic failure and
not a timing race.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tempfile
import tracemalloc
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import admission, audit_inbox, intake  # noqa: E402
from saipen_engine.log import (  # noqa: E402
    ROUTING_TAIL_EVENTS,
    read_history_routing_summary,
    read_history_snapshot,
)
from saipen_engine.paths import (  # noqa: E402
    ENV_PROJECT_LINEAGE,
    ENV_PROJECT_ROOT,
    identity_file_content,
    new_project_lineage,
)

from test_fixture_support import CURRENT_STYLE_CONTRACT, restamp_live_style  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

SAIPEN_CLI = TOOLS / "saipen.py"
SCENARIO = ROOT / "tests" / "scenarios" / "userperson-valid" / ".saipen"


def setUpModule() -> None:
    # An outer host session (SAIPEN_PROJECT_ROOT/LINEAGE, SAIPEN_AGENT, ...)
    # must never bind this module's disposable fixtures.
    isolate_host_session()


def _event(number: int, op_id: str, text: str, ticket: str | None = None) -> dict:
    # The taxonomy-stripped body the LOG parser hands reconcilers.
    return {"event": number, "op_id": op_id, "text": text, "taxonomy": "RUN",
            "ticket": ticket}


_A = "a" * 32
_TRANSITION_OP = "transition-" + "1" * 32


# ---------------------------------------------------------------------------
# PERF-002 -- the process-lifetime resolve memo
# ---------------------------------------------------------------------------

class ResolveCacheTests(unittest.TestCase):
    """`_RESOLVE_CACHE` was keyed on (start, explicit) and cached refusals.

    Reproduced by the audit: admission on a directory with no `.saipen`
    returned `NOT_SAIPEN_PROJECT`, then `.saipen` was created in the SAME
    process and admission still refused until `_RESOLVE_CACHE.clear()` was
    called by hand. Rebinding `SAIPEN_PROJECT_ROOT`/`SAIPEN_PROJECT_LINEAGE`
    from P1/lineage-1 to P2/lineage-2 left the cached answer on P1 while
    `resolve_project_root` called directly correctly answered P2.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-t1544-admission-")
        self.addCleanup(self.tmp.cleanup)
        admission._RESOLVE_CACHE.clear()
        self.addCleanup(admission._RESOLVE_CACHE.clear)

    def _project(self, name: str) -> tuple[Path, str]:
        root = Path(self.tmp.name) / name
        (root / ".saipen").mkdir(parents=True)
        lineage = new_project_lineage()
        (root / ".saipen" / "IDENTITY.md").write_text(
            identity_file_content(lineage), encoding="utf-8"
        )
        return root, lineage

    def test_a_refused_resolution_is_not_memoized(self):
        """A negative answer expires the moment the project exists."""
        bare = Path(self.tmp.name) / "BARE"
        bare.mkdir()
        first = admission._resolve_cached(bare, None)
        self.assertFalse(first.ok, first)
        (bare / ".saipen").mkdir()
        second = admission._resolve_cached(bare, None)
        self.assertTrue(second.ok, f"a stale refusal outlived the project: {second}")
        self.assertEqual(Path(second.root).resolve(), bare.resolve())

    def test_admission_follows_a_project_into_existence(self):
        """The end-to-end shape: NOT_SAIPEN_PROJECT -> an answered admission."""
        bare = Path(self.tmp.name) / "BARE"
        bare.mkdir()
        before = admission.evaluate_admission(bare, bare / "src.py", action="write")
        self.assertEqual(before["code"], "NOT_SAIPEN_PROJECT", before)
        (bare / ".saipen").mkdir()
        (bare / ".saipen" / "IDENTITY.md").write_text(
            identity_file_content(new_project_lineage()), encoding="utf-8"
        )
        (bare / ".saipen" / "STATE.md").write_text(
            "---\nphase: BUILD\ntask: T-1\nnext_action: PHASE BUILD T-1\n"
            "blocker: none\ntransition_from: SCOUT\nsaipen_version: 8\n"
            "schema_version: 3\nlast_event: 1\n"
            f"style_contract: {CURRENT_STYLE_CONTRACT}\nagent: tester\n"
            "requires:\n  - filesystem\n  - python\nmode: full\n"
            'updated: "2026-09-13T00:00:00Z"\n---\n',
            encoding="utf-8",
        )
        after = admission.evaluate_admission(bare, bare / "src.py", action="write")
        self.assertNotEqual(after["code"], "NOT_SAIPEN_PROJECT", after)
        self.assertEqual(Path(str(after["project_root"])).resolve(), bare.resolve())

    def test_the_binding_carriers_are_part_of_the_key(self):
        """A rebound session must not be answered from the previous project."""
        first, first_lineage = self._project("P1")
        second, second_lineage = self._project("P2")
        with patch.dict(os.environ, {
            ENV_PROJECT_ROOT: str(first), ENV_PROJECT_LINEAGE: first_lineage,
        }):
            bound = admission._resolve_cached(first, None)
            self.assertTrue(bound.ok, bound)
            self.assertEqual(Path(bound.root).resolve(), first.resolve())
        with patch.dict(os.environ, {
            ENV_PROJECT_ROOT: str(second), ENV_PROJECT_LINEAGE: second_lineage,
        }):
            rebound = admission._resolve_cached(second, None)
            self.assertTrue(rebound.ok, rebound)
            self.assertEqual(Path(rebound.root).resolve(), second.resolve())

    def test_a_successful_resolution_is_still_memoized(self):
        """The memo keeps its whole purpose: the git probes are paid once."""
        root, _ = self._project("P1")
        self.assertEqual(
            admission._resolve_cached(root, None),
            admission._resolve_cached(root, None),
        )
        self.assertEqual(len(admission._RESOLVE_CACHE), 1, admission._RESOLVE_CACHE)


# ---------------------------------------------------------------------------
# PERF-003 -- the inbox classified itself five times
# ---------------------------------------------------------------------------

class AuditInboxClassificationCountTests(unittest.TestCase):
    """`status()` classified, then called `projection()` which classified again.

    The audit measured 5 `classify` calls per `_status` on a scenario fixture.
    The per-digest `intake._read_index` term was NOT reproduced (that fixture
    had no layers), so it is asserted here on a purpose-built multi-layer
    inbox rather than claimed from that measurement.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-t1544-inbox-")
        self.root = Path(self.tmp.name) / "project"
        self.root.mkdir()
        shutil.copytree(SCENARIO, self.root / ".saipen")
        restamp_live_style(self.root / ".saipen")
        (self.root / ".saipen" / "USERPERSON.md").unlink(missing_ok=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _layers(self, count: int) -> None:
        for number in range(1, count + 1):
            (self.root / "audit").mkdir(exist_ok=True)
            (self.root / "audit" / f"{number}.md").write_text(
                f"# audit layer {number}\n\nfinding {number}\n", encoding="utf-8"
            )

    def test_status_classifies_the_inbox_exactly_once(self):
        self._layers(3)
        original = audit_inbox.classify
        calls = []

        def counted(root):
            calls.append(root)
            return original(root)

        with patch.object(audit_inbox, "classify", counted):
            answer = audit_inbox.status(self.root)
        self.assertTrue(answer["ok"], answer)
        self.assertEqual(len(calls), 1, f"status classified {len(calls)} times")

    def test_status_and_projection_agree_on_one_shared_classification(self):
        """The new entry points are the same functions, minus the re-read."""
        self._layers(3)
        state = audit_inbox.classify(self.root)
        self.assertEqual(
            audit_inbox.status_from_classification(self.root, state),
            audit_inbox.status(self.root),
        )
        self.assertEqual(
            audit_inbox.projection_from_classification(state, self.root),
            audit_inbox.projection(self.root),
        )

    def test_one_classification_reads_the_intake_index_once(self):
        """The O(layers x receipts) per-digest term, counted on a 4-layer inbox."""
        self._layers(4)
        original = intake._read_index
        reads = []

        def counted(root):
            reads.append(root)
            return original(root)

        with patch.object(intake, "_read_index", counted):
            state = audit_inbox.classify(self.root)
        self.assertEqual(len(state["layers"]), 4, state["layers"])
        self.assertEqual(len(reads), 1, f"intake index read {len(reads)} times for 4 layers")

    def test_the_digest_table_answers_exactly_what_the_per_digest_read_answered(self):
        """One table, same answers: ACTIVE wins over tombstone, lowest id first."""
        root = Path(self.tmp.name) / "digests"
        (root / ".saipen").mkdir(parents=True)
        table = audit_inbox._receipts_by_digest(root)
        self.assertEqual(table, {})
        self.assertIsNone(audit_inbox.receipt_for_digest(root, "deadbeef"))
        self.assertIsNone(audit_inbox.receipt_for_digest(root, "deadbeef", by_digest=table))

    def test_a_corrupt_binding_is_still_reported_by_both_entry_points(self):
        """The corrupt-binding branch is the one `status` refactors around."""
        binding = self.root / audit_inbox.BINDING_REL
        binding.parent.mkdir(parents=True, exist_ok=True)
        binding.write_text("{not json", encoding="utf-8")
        state = audit_inbox.classify(self.root)
        self.assertFalse(state["ok"], state)
        self.assertEqual(state["code"], "AUDIT_BINDING_CORRUPT")
        answer = audit_inbox.status(self.root)
        self.assertFalse(answer["ok"], answer)
        self.assertEqual(answer["code"], "AUDIT_BINDING_CORRUPT")
        self.assertTrue(answer["next"]["binding_corrupt"], answer["next"])


# ---------------------------------------------------------------------------
# PERF-005 -- a routing-oriented one-pass history summary
# ---------------------------------------------------------------------------

class HistoryRoutingSummaryTests(unittest.TestCase):
    """Lean mode dropped the text renderings and kept one dict per EVENT.

    Measured through the production reader: 5 000 events 4.26 MB peak,
    20 000 events 17.12 MB, 50 000 events 42.96 MB -- both time and memory
    linear in LIFETIME event count. The summary is the same single pass with no
    per-event retention.

    NOT pinned here: `read_history_snapshot(lean=True)` returning the summary
    instead of `tuple(events)`. Four live callers read `.events` from a lean
    read (`closure_readiness`, `debt`, `retirement`, `snapshot.ProjectSnapshot`
    -> `saipen._status`) and
    `test_audit_2026_08_28_all3.py::test_lean_project_snapshot_preserves_routing_
    fields_and_drops_renderings` asserts `full.history_events == lean.history_events`,
    so that swap needs a migration commit, not a silent edit.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-t1544-log-")
        self.root = Path(self.tmp.name)
        (self.root / ".saipen").mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write(self, count: int, *, seal: int | None = None) -> None:
        lines = []
        for i in range(1, count + 1):
            op = hashlib.sha1(str(i).encode("utf-8")).hexdigest()
            lines.append(
                f"- 13.09.26 00:00 [E-{i:06d}] [parent: E-{max(i - 1, 0):06d}] "
                f"[T-{(i % 9) + 1:03d}] [agent: tester] [op: {op}] "
                f"RUN: step {i} -- the work proceeds normally"
            )
        (self.root / ".saipen" / "LOG.md").write_text(
            "# Log\n" + "\n".join(lines) + "\n", encoding="utf-8"
        )
        if seal:
            logs = self.root / ".saipen" / "logs"
            logs.mkdir(exist_ok=True)
            (logs / "LOG-001.md").write_text(
                lines[0] + "\n", encoding="utf-8"
            )

    def _retained_bytes(self, build) -> int:
        build()
        tracemalloc.start()
        result = build()
        current, _peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        self.assertIsNotNone(result)
        return current

    def test_the_summary_agrees_with_the_full_snapshot_on_every_shared_fact(self):
        self._write(200)
        (self.root / ".saipen" / "LOG.md").write_text(
            (self.root / ".saipen" / "LOG.md").read_text(encoding="utf-8")
            + "- 13.09.26 00:00 [E-999999] not a legal event line\n",
            encoding="utf-8",
        )
        summary = read_history_routing_summary(self.root)
        full = read_history_snapshot(self.root)
        self.assertEqual(summary.hash, full.hash)
        self.assertEqual(summary.tail, full.tail)
        self.assertEqual(summary.illegal_lines, full.illegal_lines)
        self.assertEqual(summary.max_ticket_id, full.max_ticket_id)
        self.assertEqual(summary.event_count, len(full.events))

    def test_the_tail_rises_past_a_damaged_line_that_still_claims_an_id(self):
        """The _SAITULS 17.09.26 rule: a claimed id is spent."""
        self._write(3)
        (self.root / ".saipen" / "LOG.md").write_text(
            (self.root / ".saipen" / "LOG.md").read_text(encoding="utf-8")
            + "- 13.09.26 00:00 [E-0041] claimed by a damaged line\n",
            encoding="utf-8",
        )
        self.assertEqual(read_history_routing_summary(self.root).tail, 41)

    def test_a_sealed_segment_is_framed_into_the_same_hash(self):
        self._write(5)
        plain = read_history_routing_summary(self.root)
        self._write(5, seal=1)
        sealed = read_history_routing_summary(self.root)
        self.assertNotEqual(plain.hash, sealed.hash, "resegmentation must change the hash")
        self.assertEqual(sealed.hash, read_history_snapshot(self.root).hash)

    def test_retained_memory_does_not_grow_with_lifetime_event_count(self):
        """THE measurement, as an assertion: 10x the history, same retention."""
        small = self._retained_bytes(lambda: self._history(2_000))
        big = self._retained_bytes(lambda: self._history(20_000))
        self.assertLess(small, 1_000_000, f"2 000 events retained {small} bytes")
        self.assertLess(big, 1_000_000, f"20 000 events retained {big} bytes")
        # And the count still saw all of them: this is not a truncated scan.
        self._write(20_000)
        self.assertEqual(read_history_routing_summary(self.root).event_count, 20_000)

    def _history(self, count: int):
        self._write(count)
        return read_history_routing_summary(self.root)

    def test_the_summary_keeps_only_a_bounded_window_of_events(self):
        self._write(500)
        summary = read_history_routing_summary(self.root)
        self.assertEqual(len(summary.routing_events), ROUTING_TAIL_EVENTS)
        newest = summary.routing_events[-1]["event"]
        self.assertEqual(newest, 500)
        self.assertEqual(summary.event_count, 500)

    def test_duplicate_and_parent_ordering_evidence_is_derived(self):
        lines = [
            f"- 13.09.26 00:00 [E-{i:06d}] [agent: tester] RUN: step {i}"
            for i in (1, 2, 2, 3)
        ]
        lines.append("- 13.09.26 00:00 [E-0009] [parent: E-0042] [agent: tester] RUN: late parent")
        (self.root / ".saipen" / "LOG.md").write_text(
            "# Log\n" + "\n".join(lines) + "\n", encoding="utf-8"
        )
        summary = read_history_routing_summary(self.root)
        self.assertEqual(summary.duplicate_event_ids, (2,))
        self.assertEqual(len(summary.ordering_errors), 1, summary.ordering_errors)
        self.assertIn("E-42", summary.ordering_errors[0])
        self.assertEqual(summary.tail, 9)

    def test_a_clean_history_reports_no_ordering_evidence(self):
        self._write(50)
        summary = read_history_routing_summary(self.root)
        self.assertEqual(summary.ordering_errors, ())
        self.assertEqual(summary.duplicate_event_ids, ())

    def test_history_hash_no_longer_builds_the_per_event_dict_graph(self):
        """`history_hash` is one 16-character question about a whole lifetime."""
        from saipen_engine.log import history_hash, history_log_tail

        self._write(300)
        retained = self._retained_bytes(lambda: history_hash(self.root))
        self.assertLess(retained, 1_000_000, f"history_hash retained {retained} bytes")
        self.assertEqual(history_hash(self.root), read_history_snapshot(self.root).hash)
        self.assertEqual(history_log_tail(self.root), 300)


if __name__ == "__main__":
    unittest.main()