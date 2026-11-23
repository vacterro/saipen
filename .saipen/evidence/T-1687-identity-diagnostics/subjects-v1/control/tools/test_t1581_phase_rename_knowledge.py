"""T-1581: phase-rename fixtures keep the knowledge projection fresh.

Exercise the actual rename probe over a small tree, with the canonical
knowledge validator standing in for the full conformance subprocess. A
separate real-tree probe supplies whole-validator integration evidence.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import audit_checks as A  # noqa: E402
from saipen_engine.knowledge import (  # noqa: E402
    INDEX_REL,
    validate_knowledge,
    write_index,
)


class PhaseRenameKnowledgeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="saipen-phase-knowledge-")
        self.addCleanup(temporary.cleanup)
        self.source = Path(temporary.name) / "source"
        self.destination = Path(temporary.name) / "destination"
        self.source.mkdir()
        self.destination.mkdir()
        phase = self.source / "saipen/phases/scout.md"
        phase.parent.mkdir(parents=True)
        phase.write_text("# Phase: SCOUT\n", encoding="utf-8")
        self.cards = self.source / ".saipen/KNOWLEDGE/cards"
        self.cards.mkdir(parents=True)
        self.card = self.cards / "rename-control.md"
        self.card.write_text(
            "<!-- SAIPEN KNOWLEDGE CARD v1 -->\n"
            "kind: convention\n"
            "scope: phase rename\n"
            "trigger: choosing a phase\n"
            "status: active\n"
            "evidence: T-1581\n"
            "supersedes: none\n\n"
            "# Phase naming\n\n"
            "Read SCOUT before entering scout.\n\n"
            "Why:\n"
            "The phase name and its document must agree.\n",
            encoding="utf-8",
        )
        self.assertTrue(write_index(self.source)["ok"])
        self.assertEqual(validate_knowledge(self.source)["errors"], [])

    def run_probe(self, before_validation=None):
        def run(command, **kwargs):
            tree = Path(kwargs["cwd"])
            if Path(command[1]).name == "conformance_corpus.py":
                return subprocess.CompletedProcess(command, 0, "", "")
            if before_validation:
                before_validation(tree)
            errors = validate_knowledge(tree)["errors"]
            return subprocess.CompletedProcess(
                command,
                int(bool(errors)),
                "\n".join(f"FAIL: KNOWLEDGE/ structured card/index: {e}" for e in errors),
                "",
            )

        with mock.patch.object(A.subprocess, "run", side_effect=run):
            return A.phase_rename_probe(self.source, self.destination)

    def test_renamed_card_body_gets_a_fresh_index(self):
        self.assertIsNone(self.run_probe())
        tree = self.destination / "phase-rename"
        text = (tree / ".saipen/KNOWLEDGE/cards/rename-control.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("SCOUTX", text)
        self.assertIn("scoutx", text)
        self.assertEqual(validate_knowledge(tree)["index"], "fresh")
        self.assertNotEqual(
            (tree / INDEX_REL).read_bytes(), (self.source / INDEX_REL).read_bytes()
        )
        self.assertEqual(validate_knowledge(self.source)["index"], "fresh")

    def test_a_wrong_digest_still_fails_the_same_validator(self):
        def corrupt_digest(tree):
            index = tree / INDEX_REL
            lines = index.read_text(encoding="utf-8").splitlines()
            lines[1] = "source-digest: sha256:" + "0" * 64
            index.write_text("\n".join(lines) + "\n", encoding="utf-8")

        error = self.run_probe(corrupt_digest)
        self.assertIsNotNone(error)
        self.assertIn("INDEX.md is stale", error)

    def test_invalid_card_is_not_repaired_into_valid_evidence(self):
        text = self.card.read_text(encoding="utf-8")
        self.card.write_text(text.replace("kind: convention", "kind: invented"), encoding="utf-8")
        error = self.run_probe()
        self.assertIsNotNone(error)
        self.assertIn("invalid kind", error)

    def test_existing_wrong_digest_is_not_restamped(self):
        index = self.source / INDEX_REL
        lines = index.read_text(encoding="utf-8").splitlines()
        lines[1] = "source-digest: sha256:" + "0" * 64
        index.write_text("\n".join(lines) + "\n", encoding="utf-8")
        error = self.run_probe()
        self.assertIsNotNone(error)
        self.assertIn("INDEX.md is stale", error)

    def test_absent_knowledge_remains_absent(self):
        self.card.unlink()
        self.cards.rmdir()
        (self.source / INDEX_REL).unlink()
        self.cards.parent.rmdir()
        self.assertIsNone(self.run_probe())
        self.assertFalse((self.destination / "phase-rename" / INDEX_REL).exists())



class RetirementEvidenceRenameTests(PhaseRenameKnowledgeTests):
    """The same rename preserves byte-bound proofs and rejects corrupt input."""

    def setUp(self):
        super().setUp()
        import json
        from saipen_engine.retirement import (
            artifact_digest, board_record_digest, load_ticket_retirement,
        )

        self.evidence_rel = ".saipen/evidence/incident/proof.txt"
        self.evidence = self.source / self.evidence_rel
        self.evidence.parent.mkdir(parents=True)
        self.evidence.write_bytes(b"SCOUT finding\r\nscout source preserved\r\n")
        self.mutable = self.evidence.parent / "live.txt"
        self.mutable.write_bytes(b"SCOUT ordinary live content\n")
        row = "- [ ] T-1580 SCOUT misroute | verify: prove binding"
        record = {
            "schema_version": 2, "ticket": "T-1580", "section": "## BLOCKED",
            "board_record": row, "board_record_sha256": board_record_digest(row),
            "source_receipts": ["SRC-157", "SRC-158"],
            "reason": "MISROUTED_PROJECT_BINDING",
            "authority_receipt": "SRC-160", "authority_sha256": "a" * 64,
            "authority_grant": "T-1580 / SRC-157,SRC-158",
            "retired_by": "tester", "retired_at": "2026-10-01T00:00:00Z",
            "retirement_event": "E-101", "evidence_bound_event": "E-101",
            "discovery_event": None, "evidence_note": None,
            "restored_parent": None, "restored_parent_owner": None,
            "evidence": {"kind": "artifact", "ref": self.evidence_rel,
                         "sha256": artifact_digest(self.evidence.read_bytes())},
        }
        self.record = self.source / ".saipen/archive/retired/T-1580.json"
        self.record.parent.mkdir(parents=True)
        self.record.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        self.assertEqual(load_ticket_retirement(self.source, "T-1580")[1], [])

    def run_probe(self, before_validation=None):
        from saipen_engine.retirement import bound_artifact_errors, load_ticket_retirement

        def validate_proof(tree):
            if before_validation:
                before_validation(tree)
            record, errors, _exists = load_ticket_retirement(tree, "T-1580")
            if not errors:
                errors = bound_artifact_errors(tree, "T-1580", record["evidence"])
            if errors:
                raise AssertionError("; ".join(errors))

        return super().run_probe(validate_proof)

    def test_bound_artifact_and_retired_record_remain_exact_bytes(self):
        original_evidence = self.evidence.read_bytes()
        original_record = self.record.read_bytes()
        self.assertIsNone(self.run_probe())
        tree = self.destination / "phase-rename"
        self.assertEqual((tree / self.evidence_rel).read_bytes(), original_evidence)
        self.assertEqual(
            (tree / ".saipen/archive/retired/T-1580.json").read_bytes(), original_record
        )
        self.assertEqual(self.evidence.read_bytes(), original_evidence)
        self.assertIn(b"SCOUTX", (tree / ".saipen/evidence/incident/live.txt").read_bytes())

    def test_corrupt_original_artifact_is_refused_before_rename(self):
        self.evidence.write_bytes(b"SCOUT corrupt evidence\n")
        try:
            error = self.run_probe()
        except AssertionError:
            return
        self.assertIsNotNone(error)
        self.assertIn("retirement evidence", error)

    def test_missing_original_artifact_is_refused_before_rename(self):
        self.evidence.unlink()
        try:
            error = self.run_probe()
        except AssertionError:
            return
        self.assertIsNotNone(error)
        self.assertIn("retirement evidence", error)

if __name__ == "__main__":
    unittest.main()
