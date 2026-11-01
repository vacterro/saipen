"""T-1443: ticket/event identity reuse must be PROVEN, never assumed (R007).

THE DEFECT, measured on FastPrompter at HEAD e1f0cad (2026-10-30). Two
allocators ran on truncated input, so numbers were handed out twice:

    .saipen/LOG.md + sealed segments   E-4055..E-4602   02.10..04.10, 25.10..29.10
    .saipen/recovery/log-detail/       E-2006..E-5190   05.10..22.10 (308 records)

The live tail sat at 4603 while IDs through 5190 were already spent, and the
ticket frontier sat at 1443 while 26 ticket numbers (1452..1510) already
existed. Eight tickets are PROVEN reused because an archived receipt closed
before the live ticket was created -- including T-1442 and T-1443 themselves.

The controls below pin three things that are easy to get wrong:

1. **Proof, not pattern.** A naive "several receipts" rule flagged 48 tickets
   and a naive "two date epochs" rule flagged 42, because amendment chains
   (`SRC-007..009` on T-1207) and blocked-then-resumed tickets look identical
   to reuse. Only a receipt closing before the opening is reported as reuse;
   the weaker signatures stay advisory.

2. **Provenance is separate from identity.** All 308 detail records hash to
   their recorded digest, so the 05..22.10 events are authentic. The history is
   trustworthy; only its NUMBERS collide. Collapsing those two verdicts would
   either discredit real evidence or excuse a broken allocator.

3. **Nothing is rewritten.** The module has no write path. A validator that
   renamed the collided IDs would destroy the identity the historical documents
   assert, which is indistinguishable from forging the record.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import identity_audit  # noqa: E402


def _detail(root: Path, event: int, ticket: str | None, day: str, text: str) -> None:
    """Write one authenticated externalization record plus its detail file."""
    base = root / identity_audit.DETAIL_ROOT
    base.mkdir(parents=True, exist_ok=True)
    stamp = f"{event:04d}deadbeef"
    tag = f" [T-{ticket[2:]}]" if ticket else ""
    line = f"- {day} 12:00 [E-{event}] [parent: E-{event - 1}]{tag} RUN: {text}\n"
    detail_path = base / f"E-{stamp}.LOG.md"
    # Bytes, not text: Windows text mode rewrites '\n' to '\r\n', so a digest
    # recorded over the str would not match the bytes on disk -- and the
    # validator would (correctly) reject its own fixture as tampered.
    payload = line.encode("utf-8")
    detail_path.write_bytes(payload)
    import hashlib

    meta = {
        "schema_version": 1,
        "event_id": f"E-{event}",
        "ticket_id": ticket,
        "project_identity": "fixture",
        "project_lineage": "lineage-fixture",
        "operation": "log_event_externalization",
        "reason": "new LOG event exceeds the live cap",
        "status": "COMMITTED",
        "lossless": True,
        "source": ".saipen/LOG.md",
        "metadata_path": f"{identity_audit.DETAIL_ROOT}/E-{stamp}.json",
        "original_event_path": f"{identity_audit.DETAIL_ROOT}/E-{stamp}.LOG.md",
        "original_event_bytes": len(payload),
        "original_event_sha256": hashlib.sha256(payload).hexdigest(),
            "externalization_event": {"operation_id": "checkpoint-fixture"},
    }
    (base / f"E-{stamp}.json").write_text(json.dumps(meta), encoding="utf-8")


def _sealed(root: Path, lines: list[str]) -> None:
    """Write the sealed+active history the live allocator reads."""
    logs = root / ".saipen" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "LOG-001.md").write_text(
        "# ASP Log\n\n" + "\n".join(lines) + "\n", encoding="utf-8"
    )


def _receipt(root: Path, rid: str, work: str, closed: str, received: str) -> None:
    base = root / identity_audit.SOURCE_ROOT
    base.mkdir(parents=True, exist_ok=True)
    meta = {
        "schema_version": 1,
        "receipt_id": rid,
        "linked_work": work,
        "status": "CLOSED",
        "received_at": received,
        "closed_at": closed,
        "archive_ref": f"{identity_audit.SOURCE_ROOT}/{rid}.md",
    }
    (base / f"{rid}.meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _evidence(root: Path, ticket_dir: str, name: str, body: str) -> None:
    base = root / identity_audit.EVIDENCE_ROOT / ticket_dir
    base.mkdir(parents=True, exist_ok=True)
    (base / name).write_text(body, encoding="utf-8")


class ProvenanceIsSeparateFromIdentity(unittest.TestCase):
    """A tampered detail record must never be read as content."""

    def test_intact_record_is_attested(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _sealed(root, ["- 01.10.26 10:00 [E-10] [parent: E-9] [T-1] RUN: x"])
            _detail(root, 11, "T-2", "02.10.26", "continued")
            attested, rejected = identity_audit.detail_events(root)
            self.assertEqual(len(attested), 1)
            self.assertEqual(rejected, [])
            self.assertEqual(attested[0].ticket, "T-2")

    def test_tampered_bytes_are_rejected_not_trusted(self):
        """Editing the detail file must drop the record, not rewrite its claim."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _sealed(root, ["- 01.10.26 10:00 [E-10] [parent: E-9] [T-1] RUN: x"])
            _detail(root, 11, "T-2", "02.10.26", "original")
            target = next((root / identity_audit.DETAIL_ROOT).glob("*.LOG.md"))
            target.write_text(
                target.read_text(encoding="utf-8").replace("original", "forged"),
                encoding="utf-8",
            )
            attested, rejected = identity_audit.detail_events(root)
            self.assertEqual(attested, [])
            self.assertEqual(len(rejected), 1)
            self.assertFalse(rejected[0]["digest_ok"])

    def test_report_separates_the_two_verdicts(self):
        """Provenance can hold while identity collisions remain."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _sealed(root, ["- 01.10.26 10:00 [E-10] [parent: E-9] [T-1] RUN: x"])
            _detail(root, 11, "T-2", "02.10.26", "continued")
            report = identity_audit.audit(root)
            self.assertTrue(report["verdicts"]["detail_provenance_intact"])
            self.assertTrue(report["verdicts"]["live_history_readable"])

    def test_unreadable_history_is_reported_not_raised(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = identity_audit.audit(root)
            self.assertFalse(report["verdicts"]["live_history_readable"])
            self.assertIsNotNone(report["live_error"])
            self.assertTrue(report["blocks_acceptance"])


class EventIdCollisions(unittest.TestCase):
    """The same number used by two different tickets on two different days."""

    def test_different_ticket_same_id_is_a_collision(self):
        live = [identity_audit.Attested(4522, None, "T-1439", "RUN", "x", "history")]
        detail = [
            identity_audit.Attested(4522, None, "T-1442", "RUN", "y", "log-detail")
        ]
        findings = identity_audit.event_collisions(live, detail)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["event"], "E-4522")
        self.assertEqual(findings[0]["live"]["ticket"], "T-1439")
        self.assertEqual(findings[0]["detail"][0]["ticket"], "T-1442")

    def test_same_ticket_same_day_is_one_event_seen_twice(self):
        """A compacted LOG line and its own externalized detail agree."""
        from datetime import date

        day = date(2026, 10, 29)
        live = [identity_audit.Attested(4575, day, "T-1442", "RUN", "x", "history")]
        detail = [
            identity_audit.Attested(4575, day, "T-1442", "RUN", "x", "log-detail")
        ]
        self.assertEqual(identity_audit.event_collisions(live, detail), [])

    def test_same_ticket_different_day_still_collides(self):
        from datetime import date

        live = [
            identity_audit.Attested(4575, date(2026, 10, 29), "T-1442", "RUN", "x", "history")
        ]
        detail = [
            identity_audit.Attested(4575, date(2026, 10, 7), "T-1442", "RUN", "y", "log-detail")
        ]
        self.assertEqual(len(identity_audit.event_collisions(live, detail)), 1)

    def test_live_only_ids_are_not_collisions(self):
        live = [identity_audit.Attested(100, None, "T-1", "RUN", "x", "history")]
        self.assertEqual(identity_audit.event_collisions(live, []), [])


class TicketReuseNeedsProof(unittest.TestCase):
    """Only a receipt closing BEFORE the opening is proof."""

    def _reuse(self, closed: str, received: str) -> list[dict]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _sealed(root, [
                "- 29.10.26 20:00 [E-50] [parent: E-49] [T-1442] DEC: ticket added via SAIOPS",
                "- 29.10.26 20:01 [E-51] [parent: E-50] [T-1442] DEC: claimed via SAIOPS",
            ])
            _receipt(root, "SRC-101", "T-1442", closed, received)
            events = identity_audit.live_events(root)
            receipts = identity_audit.receipt_index(root)
            return identity_audit.ticket_reuse(events, receipts)

    def test_receipt_closed_before_opening_proves_reuse(self):
        findings = self._reuse(
            "2026-10-07T03:47:36Z", "2026-10-06T23:45:45Z"
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["ticket"], "T-1442")
        self.assertEqual(findings[0]["proof"], "receipt_predates_ticket")
        self.assertEqual(
            findings[0]["receipts_closed_before_opening"], ["2026-10-07"]
        )

    def test_receipt_closed_after_opening_is_not_reuse(self):
        """A normal ticket: the receipt arrives, then closes, then work happens."""
        findings = self._reuse(
            "2026-10-30T03:47:36Z", "2026-10-28T23:45:45Z"
        )
        self.assertEqual(findings, [])

    def test_no_opening_means_no_verdict(self):
        """Without a create/claim anchor nothing can be asserted."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _sealed(root, ["- 29.10.26 20:00 [E-50] [parent: E-49] [T-1442] RUN: x"])
            _receipt(root, "SRC-101", "T-1442", "2026-10-07T03:47:36Z", "2026-10-06T23:45:45Z")
            findings = identity_audit.ticket_reuse(
                identity_audit.live_events(root), identity_audit.receipt_index(root)
            )
            self.assertEqual(findings, [])

    def test_amendment_chain_is_not_reuse(self):
        """T-1207 shape: the ticket opened ONCE, before the receipts closed."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _sealed(root, [
                "- 05.09.26 08:00 [E-49] [parent: E-48] [T-1207] DEC: ticket added via SAIOPS",
                "- 27.09.26 20:00 [E-50] [parent: E-49] [T-1207] DEC: ticket claimed via SAIOPS",
            ])
            for rid, when in (
                ("SRC-007", "2026-09-05T10:00:00Z"),
                ("SRC-008", "2026-09-05T11:00:00Z"),
                ("SRC-009", "2026-09-06T10:00:00Z"),
            ):
                _receipt(root, rid, "T-1207", when, "2026-09-05T09:00:00Z")
            findings = identity_audit.ticket_reuse(
                identity_audit.live_events(root), identity_audit.receipt_index(root)
            )
            self.assertEqual(findings, [])

    def test_blocked_then_resumed_is_not_reuse(self):
        """T-800 shape: two openings, no receipt, so no verdict."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _sealed(root, [
                "- 13.09.26 10:00 [E-50] [parent: E-49] [T-800] DEC: ticket claimed via SAIOPS",
                "- 27.09.26 10:00 [E-51] [parent: E-50] [T-800] DEC: ticket claimed via SAIOPS",
            ])
            events = identity_audit.live_events(root)
            proven = identity_audit.ticket_reuse(events, {})
            self.assertEqual(proven, [])
            candidates = identity_audit.reuse_candidates(events, {}, proven)
            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0]["status"][:10], "UNRESOLVED")


class CitationResolution(unittest.TestCase):
    """A document claims an event only when it names its own ticket on the line."""

    def test_own_ticket_with_foreign_event_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _sealed(root, [
                "- 29.10.26 01:58 [E-4520] [parent: E-4519] [T-1439] RUN: ledger"
            ])
            _evidence(
                root, "t1442", "FINAL_REPORT.md",
                "STATUS: T-1442 DONE (E-4520), SRC-101 closed.\n",
            )
            live = identity_audit.live_events(root)
            findings = identity_audit.unresolved_citations(root, live, [])
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["event"], "E-4520")
            self.assertEqual(findings[0]["resolves_to"], ["T-1439"])
            self.assertEqual(findings[0]["kind"], "misassigned")
            self.assertEqual(findings[0]["line"], 1)

    def test_foreign_ticket_mention_is_not_a_claim(self):
        """`Delivered by T-1453 (E-4450)` in a T-1454 doc is legitimate."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _sealed(root, [
                "- 13.10.26 10:00 [E-4450] [parent: E-4449] [T-1453] RUN: delivered"
            ])
            _evidence(
                root, "t1454", "README.md",
                "Delivered by T-1453 (DONE, own_patch, E-4450). Re-verified live.\n",
            )
            live = identity_audit.live_events(root)
            self.assertEqual(identity_audit.unresolved_citations(root, live, []), [])

    def test_bare_event_mention_is_not_a_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _sealed(root, [
                "- 13.10.26 10:00 [E-4450] [parent: E-4449] [T-1453] RUN: delivered"
            ])
            _evidence(
                root, "t1453", "README.md",
                "First anchored pair (LOG E-4450): verifier matched.\n",
            )
            live = identity_audit.live_events(root)
            self.assertEqual(identity_audit.unresolved_citations(root, live, []), [])

    def test_self_consistent_citation_is_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _sealed(root, [
                "- 29.10.26 20:00 [E-4575] [parent: E-4574] [T-1442] RUN: scout"
            ])
            _evidence(root, "t1442", "README.md", "T-1442 SCOUT at E-4575.\n")
            live = identity_audit.live_events(root)
            self.assertEqual(identity_audit.unresolved_citations(root, live, []), [])

    def test_ambiguous_mapping_is_named_as_ambiguous(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _sealed(root, [
                "- 29.10.26 20:00 [E-900] [parent: E-899] [T-1] RUN: a"
            ])
            detail = [
                identity_audit.Attested(900, None, "T-2", "RUN", "b", "log-detail")
            ]
            _evidence(root, "t1442", "README.md", "T-1442 done at E-900.\n")
            live = identity_audit.live_events(root)
            findings = identity_audit.unresolved_citations(root, live, detail)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["kind"], "ambiguous")
            self.assertEqual(findings[0]["resolves_to"], ["T-1", "T-2"])

    def test_document_outside_a_ticket_dir_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _sealed(root, [
                "- 29.10.26 20:00 [E-900] [parent: E-899] [T-1] RUN: a"
            ])
            _evidence(root, "notes", "scratch.md", "T-1442 done at E-900.\n")
            live = identity_audit.live_events(root)
            self.assertEqual(identity_audit.unresolved_citations(root, live, []), [])


class AllocatorFrontier(unittest.TestCase):
    """The reissue window is measured, not guessed."""

    def test_ids_above_the_live_tail_are_counted(self):
        live = [identity_audit.Attested(100, None, "T-10", "RUN", "x", "history")]
        detail = [
            identity_audit.Attested(200, None, "T-11", "RUN", "y", "log-detail"),
            identity_audit.Attested(300, None, "T-12", "RUN", "z", "log-detail"),
        ]
        frontier = identity_audit.allocator_frontier(live, detail, [])
        self.assertEqual(frontier["live_tail"], "E-100")
        self.assertEqual(frontier["attested_max"], "E-300")
        self.assertEqual(frontier["reissue_window_events"], 2)
        self.assertEqual(frontier["reissue_window_first"], "E-200")
        self.assertEqual(frontier["tickets_spent_above_frontier"], 2)

    def test_ticket_numbers_above_the_frontier_are_counted(self):
        live = [identity_audit.Attested(100, None, "T-10", "RUN", "x", "history")]
        detail = [
            identity_audit.Attested(101, None, "T-50", "RUN", "y", "log-detail"),
            identity_audit.Attested(102, None, "T-9", "RUN", "z", "log-detail"),
        ]
        frontier = identity_audit.allocator_frontier(live, detail, [])
        self.assertEqual(frontier["ticket_frontier"], "T-10")
        self.assertEqual(frontier["tickets_above_frontier"], ["T-50"])

    def test_compound_ticket_tags_do_not_crash(self):
        live = [
            identity_audit.Attested(100, None, "T-812/T-813/T-814", "RUN", "x", "history"),
            identity_audit.Attested(101, None, "T-none", "RUN", "y", "history"),
        ]
        frontier = identity_audit.allocator_frontier(live, [], [])
        self.assertEqual(frontier["ticket_frontier"], "T-812")


class NoWritePath(unittest.TestCase):
    """A validator that repaired history would be forging it."""

    def test_module_exposes_no_mutating_function(self):
        forbidden = {
            "rename",
            "rewrite",
            "repair",
            "fix",
            "delete",
            "remove",
            "renumber",
            "migrate",
        }
        public = {
            name
            for name in dir(identity_audit)
            if not name.startswith("_") and callable(getattr(identity_audit, name))
        }
        self.assertEqual(public & forbidden, set())

    def test_running_the_audit_leaves_the_tree_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _sealed(root, [
                "- 29.10.26 20:00 [E-50] [parent: E-49] [T-1442] DEC: ticket added via SAIOPS"
            ])
            _detail(root, 51, "T-1442", "29.10.26", "x")
            _receipt(root, "SRC-101", "T-1442", "2026-10-07T03:47:36Z", "2026-10-06T23:45:45Z")
            _evidence(root, "t1442", "FINAL_REPORT.md", "T-1442 DONE (E-4520).\n")

            def snapshot() -> dict[str, bytes]:
                return {
                    p.relative_to(root).as_posix(): p.read_bytes()
                    for p in sorted(root.rglob("*"))
                    if p.is_file()
                }

            before = snapshot()
            identity_audit.audit(root)
            self.assertEqual(snapshot(), before)


class ReportShape(unittest.TestCase):
    """The report is a document other tools read; its shape is a contract."""

    def test_counts_match_the_lists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _sealed(root, [
                "- 29.10.26 20:00 [E-50] [parent: E-49] [T-1442] DEC: ticket added via SAIOPS",
                "- 29.10.26 01:58 [E-4520] [parent: E-4519] [T-1439] RUN: ledger",
            ])
            _receipt(root, "SRC-101", "T-1442", "2026-10-07T03:47:36Z", "2026-10-06T23:45:45Z")
            _evidence(root, "t1442", "FINAL_REPORT.md", "T-1442 DONE (E-4520).\n")
            report = identity_audit.audit(root)
            counts = report["counts"]
            self.assertEqual(counts["reused_ticket_ids"], len(report["ticket_reuse"]))
            self.assertEqual(
                counts["unresolved_citations"], len(report["unresolved_citations"])
            )
            self.assertEqual(
                counts["event_id_collisions"], len(report["event_id_collisions"])
            )
            self.assertEqual(report["schema_version"], 1)
            self.assertTrue(report["blocks_acceptance"])

    def test_clean_project_does_not_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _sealed(root, [
                "- 29.10.26 20:00 [E-50] [parent: E-49] [T-1442] DEC: ticket added via SAIOPS"
            ])
            report = identity_audit.audit(root)
            self.assertFalse(report["blocks_acceptance"])
            self.assertEqual(report["ticket_reuse"], [])
            self.assertEqual(report["unresolved_citations"], [])

    def test_cli_exits_one_when_findings_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _sealed(root, [
                "- 29.10.26 20:00 [E-50] [parent: E-49] [T-1442] DEC: ticket added via SAIOPS"
            ])
            _receipt(root, "SRC-101", "T-1442", "2026-10-07T03:47:36Z", "2026-10-06T23:45:45Z")
            self.assertEqual(identity_audit.main(["--root", str(root)]), 1)

    def test_cli_exits_zero_on_a_clean_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _sealed(root, [
                "- 29.10.26 20:00 [E-50] [parent: E-49] [T-1442] DEC: ticket added via SAIOPS"
            ])
            self.assertEqual(identity_audit.main(["--root", str(root)]), 0)


if __name__ == "__main__":
    unittest.main()
