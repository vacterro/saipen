"""T-1969: a finding's revision identity, and what a legacy ack row may match.

Campaign P0-B. Two defects measured in `tools/producer_backends/saipal_adapter.py`:

  D1  SUPPRESSION BY BARE ID
      `deliver_finding_to_audit_inbox` mints its operation id as
      `f"{producer}-{fid.lower()}"` -- the finding id alone. `iter_new_qualified_findings`
      then subtracts `_committed_publication_finding_ids(root)` (a set of
      `producer_item_id`, also the bare id) from every page UNCONDITIONALLY.
      So once a finding id is committed, a LATER report carrying the same id with
      materially different bytes is skipped forever. The allocator would have
      refused the changed bytes with a typed CONFLICT -- but the walker never
      reaches the allocator, because it drops the row first. The guard is real
      and provably unreachable.

      Consequence: a finding can be revised (or re-used, or re-qualified) and the
      publisher will silently publish nothing while reporting a clean walk. That
      is the "zero silently lost findings" clause failing in the worst direction:
      not a crash, a quiet success.

  D2  LEGACY ACK ROW MATCHES EVERY CORPUS
      `_acknowledged_ids` scopes rows by source digest with
      `row.get("source_digest") not in (None, source_digest)` -- note the `None`
      in the tuple. A row written without a source digest (the legacy shape) is
      therefore NOT skipped for ANY corpus. One legacy row suppresses its ids in
      every future report, including a different corpus where those ids are
      different findings.

This module is the reproduction. It is deliberately written to fail against the
current implementation and pass once suppression is bound to a revision identity
and legacy acks are scoped through authoritative destination receipts.

SCOPE LIMIT, stated so no reader over-credits it: these are UNIT/CONTRACT
controls over an injected page iterator. They prove the suppression logic and
nothing about transport, and nothing about an installed host.
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

from producer_backends import saipal_adapter as adapter_module  # noqa: E402

PRODUCER = "saipal"


def _body(text: str) -> str:
    return f"# finding\n\n{text}\n"


class _Replay:
    """A fake page iterator: the walker never touches a CLI."""

    def __init__(self, adapter, rows, *, source_digest):
        self.adapter = adapter
        self.rows = rows
        self.source_digest = source_digest

    def __call__(self, *, page_size):
        identity = {
            "source_digest": self.source_digest,
            "finding_count": len(self.rows),
        }
        yield (0, 1, list(self.rows), identity)


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="t1969-revision-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / ".saipen").mkdir()
        (self.root / ".saipen" / "campaign").mkdir()
        self.home = self.root / "backend"
        (self.home / "tools").mkdir(parents=True)
        (self.home / ".saipal").mkdir()
        self.adapter = adapter_module.SaipalAdapter(self.home)

    def finding(self, text, *, finding_id="PAL-1", state="QUALIFIED"):
        """A finding with a real qualification artifact and its producer record."""
        body = _body(text)
        # The qualification artifact is distinct from the delivered audit body:
        # that separation is what T-1967's gate binds, and collapsing the two
        # would test a shape the producer never emits.
        artifact_rel = f"qual-{finding_id}-{text[:12].replace(' ', '-')}.md"
        artifact_bytes = f"qualification of {finding_id}: {text}\n".encode("utf-8")
        (self.root / artifact_rel).write_bytes(artifact_bytes)
        artifact_digest = hashlib.sha256(artifact_bytes).hexdigest()
        scope = adapter_module.PUBLICATION_SCOPE_DEFAULT
        self.adapter.record_qualification(
            self.root,
            finding_id,
            artifact_digest=artifact_digest,
            publication_scope=scope,
        )
        return {
            "finding_id": finding_id,
            "state": state,
            "audit_body": body,
            "artifact_digest": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            "qualification_receipt": {
                "artifact_path": artifact_rel,
                "artifact_digest": artifact_digest,
                "publication_scope": scope,
            },
        }

    def publish(self, finding):
        return self.adapter.deliver_finding_to_audit_inbox(
            self.root, finding, publication_authorized=True
        )

    def walk(self, rows, *, source_digest="corpus-a"):
        self.adapter.iter_finding_pages = _Replay(self.adapter, rows, source_digest=source_digest)
        pages = list(self.adapter.iter_new_qualified_findings(self.root, page_size=50))
        yielded = []
        for page in pages:
            if not page.get("ok"):
                continue
            yielded.extend(page.get("findings") or [])
        return pages, yielded


class ChangedFindingUnderSameIdTests(_Base):
    """D1: a changed finding under a committed id must not be suppressed."""

    def test_changed_bytes_under_a_committed_id_are_still_yielded(self):
        first = self.finding("original body")
        published = self.publish(first)
        self.assertTrue(published.get("ok"), published)
        self.assertEqual(published.get("status"), "DELIVERED_PUBLICATION", published)

        # The producer revises the finding: same id, materially different bytes.
        second = self.finding("SUBSTANTIALLY REVISED body")

        _pages, yielded = self.walk([second])
        ids = [str(row.get("finding_id")) for row in yielded]
        self.assertEqual(
            ids,
            ["PAL-1"],
            "a revised finding under a committed id was suppressed by the walk; "
            "the allocator would have accepted the new bytes as a new operation "
            "but the walk never asked it",
        )

    def test_an_unchanged_committed_finding_is_still_suppressed(self):
        # The negative control: genuine replay must stay idempotent.
        first = self.finding("original body")
        self.assertTrue(self.publish(first).get("ok"))

        _pages, yielded = self.walk([first])
        self.assertEqual(
            [str(row.get("finding_id")) for row in yielded],
            [],
            "an UNCHANGED committed finding must still be skipped: re-publishing "
            "identical bytes is the idempotent case, not the defect",
        )


class LegacyAckScopingTests(_Base):
    """D2: a legacy ack row with no digest must not match a different corpus."""

    def _append_ack(self, ids, *, source_digest):
        record = {
            "schema_version": 1,
            "source_digest": source_digest,
            "finding_ids": list(ids),
            "acknowledged_at": "2026-10-30T00:00:00Z",
        }
        path = self.root / ".saipen" / "campaign" / adapter_module.ACK_JOURNAL_NAME
        with path.open("ab") as stream:
            stream.write((json.dumps(record, sort_keys=True) + "\n").encode("utf-8"))

    def test_a_legacy_row_does_not_suppress_a_different_corpus(self):
        # A legacy row: written before source digests were recorded.
        self._append_ack(["PAL-1"], source_digest=None)

        row = self.finding("body in a brand new corpus", finding_id="PAL-1")
        _pages, yielded = self.walk([row], source_digest="corpus-brand-new")
        self.assertEqual(
            [str(r.get("finding_id")) for r in yielded],
            ["PAL-1"],
            "a legacy ack row carrying no source digest suppressed an id in a "
            "DIFFERENT corpus; an unscoped row must be scoped through an "
            "authoritative destination receipt, not trusted for every report",
        )

    def test_a_scoped_row_still_suppresses_its_own_corpus(self):
        # The negative control: a correctly scoped row keeps working.
        self._append_ack(["PAL-1"], source_digest="corpus-a")
        row = self.finding("body", finding_id="PAL-1")
        _pages, yielded = self.walk([row], source_digest="corpus-a")
        self.assertEqual(
            [str(r.get("finding_id")) for r in yielded],
            [],
            "an acknowledgment scoped to THIS corpus must still suppress",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
