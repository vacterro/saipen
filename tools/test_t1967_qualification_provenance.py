"""T-1967 AC-01/AC-02/AC-03: qualification must come from the producer, not the caller.

MEASURED defect (2026-10-30, campaign P0-A). `deliver_finding_to_audit_inbox`
accepts a dict qualification receipt and validates it with a self-consistency
test only:

    artifact = receipt["artifact_path"]; digest = receipt["artifact_digest"]
    resolved = (root / artifact).resolve()      # stays inside the root
    actual   = sha256(resolved.read_bytes())    # whatever those bytes are
    accept if actual == digest

Both halves of that comparison come from the caller. Nothing asks whether any
SAIPAL producer ever qualified this finding, so a caller who can write a file
inside the project writes one, hashes it, and mints its own qualification. The
checks that DO exist on the dict route -- escape, unreadable, digest mismatch --
are consistency checks between two caller-supplied values, which is exactly the
class CORE-006 already refused on the sibling path (`{"receipt_id":
"invented-by-caller"}` was doing the work of authentication).

What binds qualification instead, and what these tests pin:

* AC-01: a caller-created artifact plus its caller-computed digest is refused,
  and `audit_enqueue.enqueue` is never called. Proven by wrapping the canonical
  enqueue with a spy, so "never called" is measured rather than inferred.
* AC-02: an authentic receipt in the project's OWN published history is still
  accepted (positive), while the same receipt bound to a different artifact
  digest or a different publication scope is refused (two mismatch cases).
* AC-03: STAGE_ONLY is untouched -- `publication_authorized=False` still returns
  STAGED_PUBLICATION for a fully authentic finding and enqueues nothing.

The binding is the producer's own qualification log,
`.saipen/campaign/saipal_qualifications.jsonl`, written only by
`SaipalAdapter.record_qualification`. The positive case is therefore recorded
through that API rather than hand-written here: a fixture row would be exactly
the thing under test.

LIMIT, stated because it bounds the guarantee (measured 2026-10-30): this raises
"a caller-supplied pair" to "a record this project's producer log binds to that
finding, those bytes and that scope". It does NOT stop a principal that can write
`.saipen/campaign/` from appending a fully shaped row, because the log is a file
in the project and has no keyed signature. Forging that row is a strictly larger
act than hashing a file you wrote, and the durable history makes it visible and
attributable after the fact, but cryptographic non-repudiation is what the broker
boundary (`_broker_verified`) provides and this log deliberately does not claim
it. A caller with that level of access can also rewrite the audit layers directly.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from producer_backends import saipal_adapter as adapter_module

PRODUCER = adapter_module.SaipalAdapter

#: A producer identity and evidence generation this project never minted.
FOREIGN_PRODUCER = "saipal-foreign-generator"
FOREIGN_DIGEST = "f" * 64


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class QualificationProvenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-t1967-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = self.root / "project"
        (self.project / ".saipen" / "campaign").mkdir(parents=True)
        self.home = self.root / "backend"
        (self.home / "tools").mkdir(parents=True)
        (self.home / ".saipal").mkdir()
        self.adapter = PRODUCER(self.home)

    # ------------------------------------------------------------- fixtures

    def finding(self, **changes):
        body = "# Audit finding PAL-1\n\nA real body.\n"
        finding = {
            "finding_id": "PAL-1",
            "state": "QUALIFIED",
            "audit_body": body,
            "artifact_digest": sha256(body),
        }
        finding.update(changes)
        return finding

    def write_artifact(self, name: str, body: str) -> Path:
        """Write the exact bytes whose sha256 the caller will claim.

        `Path.write_text` applies newline translation on Windows, so `\\n`
        becomes `\\r\\n` and the byte digest changes underneath the test. The
        adapter hashes BYTES, which is the correct product behaviour; the
        fixture must therefore not go through text mode.
        """
        path = self.project / name
        path.write_bytes(body.encode("utf-8"))
        return path

    def write_history(self, *records) -> None:
        """Write rows into the producer's qualification log.

        Used by the mismatch cases, which must plant a record the producer would
        NOT have written for these bytes.
        """
        path = self.project / ".saipen" / "campaign" / adapter_module.QUALIFICATION_LOG_NAME
        body = "".join(json.dumps(row, sort_keys=True) + "\n" for row in records)
        path.write_text(body, encoding="utf-8")

    def qualify(self, *, finding_id="PAL-1", digest=None, scope="project"):
        """Record a qualification through the PRODUCER's own API.

        The positive fixture must not be a row this test hand-wrote: the point of
        the binding is that only the producer can author the record.
        """
        digest = digest or sha256("# Audit finding PAL-1\n\nA real body.\n")
        return self.adapter.record_qualification(
            self.project,
            finding_id,
            artifact_digest=digest,
            publication_scope=scope,
        )

    def authentic_receipt(self, *, finding_id="PAL-1", digest=None, scope=None):
        """A qualification record in the shape `record_qualification` writes."""
        digest = digest or sha256("# Audit finding PAL-1\n\nA real body.\n")
        return {
            "schema_version": 1,
            "operation_id": f"{FOREIGN_PRODUCER}-qual-{finding_id.lower()}",
            "producer": FOREIGN_PRODUCER,
            "finding_id": finding_id,
            "artifact_digest": digest,
            "publication_scope": scope or "project",
            "source_generation": "",
            "digest": digest,
        }

    def delivered(self, finding, *, authorized=True):
        """Call the real method with the canonical enqueue replaced by a spy."""
        calls = []

        def spy(*args, **kwargs):
            calls.append((args, kwargs))
            return {"ok": True, "state": "COMMITTED", "producer_operation_id": "x"}

        with mock.patch.object(adapter_module.audit_enqueue, "enqueue", spy):
            result = self.adapter.deliver_finding_to_audit_inbox(
                self.project, finding, publication_authorized=authorized
            )
        return result, calls

    # ---------------------------------------------------------------- AC-01

    def test_a_caller_minted_artifact_and_digest_is_refused(self):
        """AC-01: both halves of the proof are the caller's own work."""
        planted = self.write_artifact("minted-by-caller.md", "# totally a qualification artifact\n")
        finding = self.finding(
            qualification_receipt={
                "artifact_path": "minted-by-caller.md",
                "artifact_digest": hashlib.sha256(planted.read_bytes()).hexdigest(),
            }
        )
        result, calls = self.delivered(finding)
        self.assertFalse(result.get("ok"), result)
        self.assertIn(
            str(result.get("status")),
            {"NOT_QUALIFIED", "PROVENANCE_UNVERIFIED"},
            result,
        )
        self.assertFalse(calls, "audit_enqueue.enqueue was called for caller-minted proof")

    def test_a_digest_that_matches_the_planted_file_does_not_help(self):
        """Consistency is not provenance: a matching pair is still the caller's."""
        planted = self.write_artifact("another.md", "anything at all\n")
        finding = self.finding(
            qualification_receipt={
                "artifact_path": "another.md",
                "artifact_digest": hashlib.sha256(planted.read_bytes()).hexdigest(),
            }
        )
        result, calls = self.delivered(finding)
        self.assertFalse(result.get("ok"), result)
        self.assertFalse(calls, "a self-consistent caller pair reached the allocator")

    def test_naming_a_receipt_that_history_lacks_is_refused(self):
        """The string route already did this; the property is stated once here."""
        self.write_history()  # empty history
        result, calls = self.delivered(self.finding(qualification_receipt="rcpt-invented"))
        self.assertFalse(result.get("ok"), result)
        self.assertFalse(calls, "an invented receipt id reached the allocator")

    def test_a_shapeless_row_in_the_log_does_not_authorize(self):
        """A bare {finding_id, artifact_digest, publication_scope} is not a record.

        Measured while hardening this fix: the first cut accepted such a row, so
        anyone who could write the log file minted a qualification with three
        keys. The record must carry the identity `record_qualification` writes.
        """
        digest = sha256("# Audit finding PAL-1\n\nA real body.\n")
        self.write_history(
            {
                "finding_id": "PAL-1",
                "artifact_digest": digest,
                "publication_scope": "project",
            }
        )
        finding = self.finding(
            qualification_receipt={"artifact_path": "audit.md", "artifact_digest": digest}
        )
        self.write_artifact("audit.md", finding["audit_body"])
        result, calls = self.delivered(finding)
        self.assertFalse(result.get("ok"), result)
        self.assertFalse(calls, "a shapeless row authorized a publication")

    def test_another_producers_record_does_not_authorize_this_one(self):
        """The adapter may only read back its own operations."""
        digest = sha256("# Audit finding PAL-1\n\nA real body.\n")
        self.write_history(self.authentic_receipt(digest=digest))  # FOREIGN_PRODUCER
        finding = self.finding(
            qualification_receipt={"artifact_path": "audit.md", "artifact_digest": digest}
        )
        self.write_artifact("audit.md", finding["audit_body"])
        result, calls = self.delivered(finding)
        self.assertFalse(result.get("ok"), result)
        self.assertFalse(calls, "a foreign producer's record authorized this producer")

    def test_a_proof_replayed_for_another_finding_is_refused(self):
        """A genuine qualification authorizes exactly the finding it names."""
        self.qualify(finding_id="PAL-1")
        finding = self.finding(
            finding_id="PAL-2",
            qualification_receipt={
                "artifact_path": "audit.md",
                "artifact_digest": sha256("# Audit finding PAL-1\n\nA real body.\n"),
            },
        )
        self.write_artifact("audit.md", "# Audit finding PAL-1\n\nA real body.\n")
        result, calls = self.delivered(finding)
        self.assertFalse(result.get("ok"), result)
        self.assertFalse(calls, "a proof issued for one finding authorized another")

    # ---------------------------------------------------------------- AC-02

    def test_an_authentic_history_receipt_is_still_accepted(self):
        """AC-02 positive: a real receipt in this project's own history works."""
        recorded = self.qualify()
        self.assertTrue(recorded.get("ok"), recorded)
        finding = self.finding(
            qualification_receipt={
                "artifact_path": "audit.md",
                "artifact_digest": sha256("# Audit finding PAL-1\n\nA real body.\n"),
            }
        )
        self.write_artifact("audit.md", finding["audit_body"])
        result, calls = self.delivered(finding)
        self.assertTrue(result.get("ok"), result)
        self.assertEqual(len(calls), 1, "an authentic finding must enqueue exactly once")

    def test_the_same_receipt_bound_to_another_digest_is_refused(self):
        """AC-02 mismatch 1: the receipt exists, but not for these bytes."""
        self.qualify()
        finding = self.finding(
            qualification_receipt={
                "artifact_path": "audit.md",
                "artifact_digest": FOREIGN_DIGEST,
            }
        )
        self.write_artifact("audit.md", finding["audit_body"])
        result, calls = self.delivered(finding)
        self.assertFalse(result.get("ok"), result)
        self.assertFalse(calls, "a receipt bound to a foreign digest reached the allocator")

    def test_the_same_receipt_bound_to_another_scope_is_refused(self):
        """AC-02 mismatch 2: the receipt exists, but for a different publication scope."""
        self.qualify(scope="project")
        finding = self.finding(
            qualification_receipt={
                "artifact_path": "audit.md",
                "artifact_digest": sha256("# Audit finding PAL-1\n\nA real body.\n"),
                "publication_scope": "another-project",
            }
        )
        self.write_artifact("audit.md", finding["audit_body"])
        result, calls = self.delivered(finding)
        self.assertFalse(result.get("ok"), result)
        self.assertFalse(calls, "a receipt bound to a foreign scope reached the allocator")

    # ---------------------------------------------------------------- AC-03

    def test_stage_only_is_unchanged_for_a_fully_authentic_finding(self):
        """AC-03: STAGE_ONLY precedes publication and must not move."""
        self.qualify()
        finding = self.finding(
            qualification_receipt={
                "artifact_path": "audit.md",
                "artifact_digest": sha256("# Audit finding PAL-1\n\nA real body.\n"),
            }
        )
        self.write_artifact("audit.md", finding["audit_body"])
        result, calls = self.delivered(finding, authorized=False)
        self.assertFalse(result.get("ok"), result)
        self.assertEqual(result.get("status"), adapter_module.STAGED_PUBLICATION, result)
        self.assertFalse(calls, "STAGE_ONLY must not enqueue")


if __name__ == "__main__":
    unittest.main()
