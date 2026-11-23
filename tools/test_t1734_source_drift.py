"""T-1734: the read-only source-drift advisory for closed Work.

A DONE Work can close citing a core-unit family record whose fingerprint is a
digest of the verified source tree. Nothing re-reads that binding afterwards,
so the tree can drift away from the verified bytes silently. ``source_binding``
is the bounded read-only observation: CURRENT, DRIFTED or UNBOUND, naming the
Work and both fingerprints, mutating no history. The manual remedy
(``saipen work reverify``) is unchanged and is not exercised here.

Run standalone:
    python tools/test_t1734_source_drift.py
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import core_unit, source_binding  # noqa: E402

FAMILY_RECORD = ".saipen/evidence/core-unit/abcdef0123456789-20260101T000000Z.json"


def _citation_line(fingerprint: str, record: str = FAMILY_RECORD) -> str:
    sha = hashlib.sha256(b"record").hexdigest()
    return (
        "- 01.01.26 00:00 [E-002] [parent: E-001] [T-100] [agent: saipen-cli] "
        "RUN: CORE-UNIT-EVIDENCE PASS family:unit ran:6336 red:0 new_red:0 "
        f"fixed:0 fingerprint:{fingerprint} record:{record} sha256:{sha}"
    )


def _make_project(tmp: Path) -> Path:
    root = tmp / "project"
    (root / "tools" / "saipen_engine").mkdir(parents=True)
    (root / ".saipen" / "evidence" / "core-unit").mkdir(parents=True)
    (root / "tools" / "saipen_engine" / "test_runner.py").write_text("", encoding="utf-8")
    (root / "tools" / "core_unit_baseline.json").write_text(
        json.dumps({"schema": 1, "family": "unit", "command": ["python", "-m", "unittest"],
                    "red": []}) + "\n",
        encoding="utf-8",
    )
    (root / ".saipen" / "BOARD.md").write_text(
        "# BOARD\n\n## DOING\n\n## TODO\n\n## DONE\n"
        "- [x] T-100 closed work | verify: proof exists\n\n## BLOCKED\n",
        encoding="utf-8",
    )
    return root


class SourceDrift(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="saipen-source-drift-")
        self.addCleanup(self.temporary.cleanup)
        self.root = _make_project(Path(self.temporary.name))
        self.log = self.root / ".saipen" / "LOG.md"
        self.record = self.root / FAMILY_RECORD

    def _write_citation(self, fingerprint: str) -> None:
        self.log.write_text(_citation_line(fingerprint) + "\n", encoding="utf-8")
        self.record.write_text(
            json.dumps({"family": "unit", "fingerprint": fingerprint}) + "\n", encoding="utf-8"
        )

    def test_current_when_the_tree_matches_the_verified_bytes(self) -> None:
        self._write_citation(core_unit.tree_fingerprint(self.root))
        block = source_binding.advisory(self.root)
        self.assertEqual(block["works"][0]["binding"], source_binding.CURRENT)
        self.assertEqual(block["drifted"], [])
        self.assertEqual(block["unbound"], [])

    def test_drifted_when_the_tree_changed_after_closure(self) -> None:
        self._write_citation("0" * 16)
        block = source_binding.advisory(self.root)
        self.assertEqual(block["works"][0]["binding"], source_binding.DRIFTED)
        self.assertEqual(block["drifted"], ["T-100"])
        self.assertEqual(block["works"][0]["recorded_fingerprint"], "0" * 16)
        self.assertEqual(
            block["works"][0]["current_fingerprint"], core_unit.tree_fingerprint(self.root)[:16]
        )

    def test_unbound_when_no_family_run_is_cited(self) -> None:
        self.log.write_text("- 01.01.26 00:00 [E-001] [T-100] RUN: transition to VERIFY\n",
                            encoding="utf-8")
        block = source_binding.advisory(self.root)
        self.assertEqual(block["unbound"], ["T-100"])
        self.assertEqual(block["unbound_count"], 1)
        self.assertEqual(block["works"], [])

    def test_silent_when_the_project_declares_no_family(self) -> None:
        (self.root / "tools" / "saipen_engine" / "test_runner.py").unlink()
        self.assertEqual(source_binding.advisory(self.root), {})

    def test_read_only_no_history_is_mutated(self) -> None:
        self._write_citation("0" * 16)
        def snapshot() -> dict:
            return {
                str(p.relative_to(self.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.root.rglob("*")
                if p.is_file()
            }
        before = snapshot()
        source_binding.advisory(self.root)
        self.assertEqual(before, snapshot())


class SharedHistoryReuse(unittest.TestCase):
    """T-2089: the advisory must not re-read history when handed the events.

    ``_status`` already holds the parsed history from its single
    ``ProjectSnapshot`` pass; a second ``read_history_snapshot`` walk over a
    21k-event ledger is the O(DONE x LOG) cost this Work removes. The events
    argument keeps exact old semantics: absent -> the advisory keeps reading
    for itself, unreadable -> the historical safe fallback {}.
    """

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="saipen-source-drift-reuse-")
        self.addCleanup(self.temporary.cleanup)
        self.root = _make_project(Path(self.temporary.name))
        self.log = self.root / ".saipen" / "LOG.md"
        self.record = self.root / FAMILY_RECORD
        self._write_citation("0" * 16)

    def _write_citation(self, fingerprint: str) -> None:
        self.log.write_text(_citation_line(fingerprint) + "\n", encoding="utf-8")
        self.record.write_text(
            json.dumps({"family": "unit", "fingerprint": fingerprint}) + "\n", encoding="utf-8"
        )

    def test_shared_events_answer_without_a_second_history_read(self) -> None:
        from saipen_engine import log as log_module
        from saipen_engine.log import read_history_snapshot

        calls = {"snapshot": 0}
        original = log_module.read_history_snapshot

        def counting(project_root, *, lean=False):
            calls["snapshot"] += 1
            return original(project_root, lean=lean)

        log_module.read_history_snapshot = counting
        try:
            from saipen_engine import log as reimported

            reimported.read_history_events = lambda root: list(
                counting(root, lean=True).events
            )
            events = read_history_snapshot(self.root, lean=True).events
            calls["snapshot"] = 0
            block = source_binding.advisory(self.root, events=events)
        finally:
            log_module.read_history_snapshot = original
        self.assertEqual(calls["snapshot"], 0)
        self.assertEqual(block["works"][0]["binding"], source_binding.DRIFTED)
        self.assertEqual(block["drifted"], ["T-100"])

    def test_absent_events_still_read_for_direct_callers(self) -> None:
        block = source_binding.advisory(self.root)
        self.assertEqual(block["works"][0]["binding"], source_binding.DRIFTED)

    def test_failed_read_keeps_the_historical_fallback(self) -> None:
        original = source_binding.read_history_events

        def unreadable(root):
            raise OSError("history unreadable")

        source_binding.read_history_events = unreadable
        try:
            self.assertEqual(source_binding.advisory(self.root, events=None), {})
        finally:
            source_binding.read_history_events = original


class CitationParity(unittest.TestCase):
    """Old reverse-scan vs one-pass lookup must agree on every fixture.

    The historical rule: per DONE ticket, walk events newest-first; the first
    RUN line whose citation parses and whose record reads clean binds the
    ticket; a cited record that fails to load makes the ticket UNBOUND and
    STOPS the scan (not skipped). One reverse pass reproducing that rule must
    return identical fingerprints.
    """

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="saipen-source-drift-parity-")
        self.addCleanup(self.temporary.cleanup)
        self.root = _make_project(Path(self.temporary.name))
        self.log = self.root / ".saipen" / "LOG.md"
        self.record = self.root / FAMILY_RECORD
        self.record.write_text(
            json.dumps({"family": "unit", "fingerprint": "a" * 16}) + "\n", encoding="utf-8"
        )

    def _line(self, eid: int, ticket: str, text: str) -> str:
        return f"- 01.01.26 00:00 [E-{eid:03d}] [{ticket}] RUN: {text}\n"

    def _legacy_citations(self, events: list[dict]) -> dict:
        root = self.root
        done = source_binding._done_ids(root)
        return {tid: source_binding._citation(root, events, tid) for tid in done}

    def _advisory_citations(self, events: list[dict]) -> dict:
        return source_binding.citation_map(self.root, events, source_binding._done_ids(self.root))

    def _events(self) -> list[dict]:
        from saipen_engine.log import read_history_events

        return read_history_events(self.root)

    def test_newest_citation_wins_per_ticket(self) -> None:
        # One record file per citation: the legacy and one-pass rules read the
        # fingerprint from the CITED RECORD, not from the line, so a shared
        # record would make both lines report the same fingerprint and prove
        # nothing about newest-wins.
        for tag, eid in (("b", 2), ("c", 3)):
            record = f".saipen/evidence/core-unit/{tag}-20260101T000000Z.json"
            (self.root / record).parent.mkdir(parents=True, exist_ok=True)
            (self.root / record).write_text(
                json.dumps({"family": "unit", "fingerprint": tag * 16}) + "\n", encoding="utf-8"
            )
            line = self._line(
                eid,
                "T-100",
                "CORE-UNIT-EVIDENCE PASS family:unit ran:1 red:0 new_red:0 fixed:0 "
                f"fingerprint:{tag * 16} record:{record} sha256:"
                + hashlib.sha256(b"record").hexdigest(),
            )
            with self.log.open("a", encoding="utf-8") as fh:
                fh.write(line)
        events = self._events()
        self.assertEqual(self._legacy_citations(events), self._advisory_citations(events))
        self.assertEqual(self._advisory_citations(events)["T-100"], "c" * 16)

    def test_unparsable_run_lines_are_skipped_not_stopping(self) -> None:
        noise = self._line(2, "T-100", "transition to VERIFY")
        good = self._line(3, "T-100", "CORE-UNIT-EVIDENCE PASS family:unit ran:1 red:0 "
                           "new_red:0 fixed:0 fingerprint:" + "d" * 16
                           + f" record:{FAMILY_RECORD} sha256:" + hashlib.sha256(b"record").hexdigest())
        self.log.write_text(noise + good, encoding="utf-8")
        events = self._events()
        self.assertEqual(self._legacy_citations(events), self._advisory_citations(events))

    def test_corrupt_cited_record_makes_ticket_unbound(self) -> None:
        (self.root / FAMILY_RECORD).write_text("{not json", encoding="utf-8")
        line = self._line(2, "T-100", "CORE-UNIT-EVIDENCE PASS family:unit ran:1 red:0 "
                          "new_red:0 fixed:0 fingerprint:" + "e" * 16
                          + f" record:{FAMILY_RECORD} sha256:" + hashlib.sha256(b"record").hexdigest())
        self.log.write_text(line, encoding="utf-8")
        events = self._events()
        legacy = self._legacy_citations(events)
        self.assertEqual(legacy["T-100"], None)
        self.assertEqual(self._advisory_citations(events), legacy)

    def test_missing_record_path_makes_ticket_unbound(self) -> None:
        line = self._line(2, "T-100", "CORE-UNIT-EVIDENCE PASS family:unit ran:1 red:0 "
                          "new_red:0 fixed:0 fingerprint:" + "f" * 16
                          + " record:.saipen/evidence/core-unit/nope-1.json"
                          + " sha256:" + hashlib.sha256(b"record").hexdigest())
        self.log.write_text(line, encoding="utf-8")
        events = self._events()
        self.assertEqual(self._advisory_citations(events), self._legacy_citations(events))

    def test_corrupt_newest_record_is_not_substituted_by_older_valid(self) -> None:
        """T-2089 P1: the newest citation with a corrupt record ends the scan.

        The legacy rule returns None (UNBOUND) the moment the newest cited
        record fails to load -- it must NOT fall back to an older valid
        citation. The one-pass map reproduces that stop exactly.
        """
        good_rec = ".saipen/evidence/core-unit/older-valid.json"
        bad_rec = ".saipen/evidence/core-unit/newest-corrupt.json"
        (self.root / good_rec).write_text(
            json.dumps({"family": "unit", "fingerprint": "a" * 16}) + "\n", encoding="utf-8"
        )
        (self.root / bad_rec).write_text("{corrupt", encoding="utf-8")
        sha = hashlib.sha256(b"record").hexdigest()
        older = self._line(
            2,
            "T-100",
            "CORE-UNIT-EVIDENCE PASS family:unit ran:1 red:0 new_red:0 fixed:0 "
            f"fingerprint:{'a' * 16} record:{good_rec} sha256:{sha}",
        )
        newer = self._line(
            3,
            "T-100",
            "CORE-UNIT-EVIDENCE PASS family:unit ran:1 red:0 new_red:0 fixed:0 "
            f"fingerprint:{'b' * 16} record:{bad_rec} sha256:{sha}",
        )
        self.log.write_text(older + newer, encoding="utf-8")
        events = self._events()
        self.assertIsNone(self._legacy_citations(events)["T-100"])
        self.assertIsNone(self._advisory_citations(events)["T-100"])

    def test_randomized_fixture_parity_with_legacy(self) -> None:
        """T-2089 P1: property parity, legacy reverse scan vs one-pass map."""
        import random

        random.seed(2089)
        for _ in range(10):
            lines = []
            eid = 1
            for _ in range(random.randint(0, 5)):
                eid += 1
                kind = random.choice(("noise", "good", "corrupt", "missing"))
                rec = f".saipen/evidence/core-unit/p{eid}.json"
                fp = "".join(random.choice("0123456789abcdef") for _ in range(16))
                sha = hashlib.sha256(b"record").hexdigest()
                if kind == "noise":
                    lines.append(self._line(eid, "T-100", "transition to VERIFY"))
                    continue
                if kind == "corrupt":
                    (self.root / rec).write_text("{corrupt", encoding="utf-8")
                elif kind == "good":
                    (self.root / rec).write_text(
                        json.dumps({"family": "unit", "fingerprint": fp}) + "\n",
                        encoding="utf-8",
                    )
                lines.append(
                    self._line(
                        eid,
                        "T-100",
                        "CORE-UNIT-EVIDENCE PASS family:unit ran:1 red:0 new_red:0 fixed:0 "
                        f"fingerprint:{fp} record:{rec} sha256:{sha}",
                    )
                )
            self.log.write_text("".join(lines), encoding="utf-8")
            events = self._events()
            self.assertEqual(self._advisory_citations(events), self._legacy_citations(events))

    def test_empty_events_and_absent_events_agree_on_counts(self) -> None:
        """T-2089 P1: events=[] is a successful empty read, None reads itself.

        With no LOG at all, passing [] (a legitimately empty history) and
        passing None (the advisory reads for itself and gets nothing) must
        both classify the DONE ticket as UNBOUND -- never crash, never
        silently treat a missing citation as CURRENT.
        """
        block = source_binding.advisory(self.root, events=[])
        self.assertEqual(block.get("unbound_count"), 1)
        block_none = source_binding.advisory(self.root, events=None)
        self.assertEqual(block_none.get("unbound_count"), 1)


if __name__ == "__main__":
    unittest.main()
