"""T-1581: phase-rename fixtures keep the knowledge projection fresh.

Exercise the actual rename probe over a small tree, with the canonical
knowledge validator standing in for the full conformance subprocess. A
separate real-tree probe supplies whole-validator integration evidence.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
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
        self.assertIn("TRACE", text)
        self.assertIn("trace", text)
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
        self.assertIn(b"TRACE", (tree / ".saipen/evidence/incident/live.txt").read_bytes())


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


class NativeHistoryFixtureTests(unittest.TestCase):
    def setUp(self):
        import stat
        from test_t1586_scenario_inputs import source_runtime_fixture

        temporary = tempfile.TemporaryDirectory(prefix="saipen-native-history-fixture-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.source = self.base / "source"
        source_runtime_fixture(A.HOME, self.source)
        self.proof = self.source / ".saipen/evidence/opaque/proof.json"
        self.proof.parent.mkdir(parents=True)
        self.original = b'{"phase": "SCOUT", "note": "synthetic immutable control"}\r\n'
        self.proof.write_bytes(self.original)
        self.proof.chmod(stat.S_IREAD)

    def test_real_rename_preserves_read_only_history_outside_fresh_authority(self):
        destination = self.base / "rename"
        destination.mkdir()
        error = A.phase_rename_probe(self.source, destination)
        self.assertIsNone(error, error)
        retained = destination / "phase-rename-history/evidence/opaque/proof.json"
        self.assertEqual(retained.read_bytes(), self.original)
        self.assertEqual(self.proof.read_bytes(), self.original)
        tree = destination / "phase-rename"
        self.assertTrue((tree / "saipen/phases/trace.md").is_file())
        self.assertFalse((tree / ".saipen/evidence/opaque/proof.json").exists())

    def test_real_warn_ownership_control_is_not_masked_by_copied_historical_work(self):
        import shutil
        from saipen_engine import lifecycle_authority
        from saipen_engine.log import parse_log_line
        from saipen_engine.state import parse_state

        for name in ("CHANGELOG_ARCHIVE.md", "GUIDE.md"):
            shutil.copyfile(A.HOME / name, self.source / name)
        (self.source / ".saipen/kitchen").mkdir(parents=True, exist_ok=True)
        board = self.source / ".saipen/BOARD.md"
        foreign = board.read_text("utf-8").replace(
            "## DONE\n", "## DONE\n- [x] T-1680 [P2] foreign historical closure "
            "| verify: not this fixture | closure_mode: inherited_verified "
            "| implementation_source: T-1630\n")
        board.write_text(foreign, encoding="utf-8")
        original_board = board.read_bytes()
        destination = self.base / "warn"
        destination.mkdir()
        error = A.warn_ownership_probe(self.source, destination)
        self.assertIsNone(error, error)
        self.assertEqual(board.read_bytes(), original_board)
        retained = destination / "warn-ownership-history"
        self.assertEqual((retained / "BOARD.md").read_bytes(), original_board)
        self.assertEqual((retained / "evidence/opaque/proof.json").read_bytes(), self.original)
        self.assertEqual(self.proof.read_bytes(), self.original)
        project = destination / "warn-ownership"
        events = list(filter(None, map(parse_log_line,
                      (project / ".saipen/LOG.md").read_text("utf-8").splitlines())))
        floor, unbacked = lifecycle_authority.journal_floor(project, events)
        self.assertFalse(unbacked, unbacked)
        state = parse_state((project / ".saipen/STATE.md").read_text("utf-8"))
        self.assertEqual(state["last_event"], floor)

    def test_real_tag_query_control_is_not_masked_by_copied_historical_work(self):
        destination = self.base / "query"
        destination.mkdir()
        context = A.ProbeContext(destination, [], None)
        context.pristine = self.source
        self.assertIsNone(A.tag_query_probe(context))
        self.assertEqual(self.proof.read_bytes(), self.original)

class FullAuditCacheTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="saipen-audit-cache-control-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "tools").mkdir()
        (self.root / "tools/validate.py").write_bytes(b"validator input\n")
        (self.root / "tools/audit_checks.py").write_bytes(b"audit input\n")
        self.cache = self.root / ".saipen/cache/audit_checks_cache.json"

    def execute(self, *, arguments=(), overrides=None, move_source=False, partial=False):
        def verdicts(probes, _context):
            self.probes_seen = {probe.name for probe in probes}
            result = {probe.name: "PASS" for probe in probes}
            result.update(overrides or {})
            if partial:
                result.pop("mutation-sweep")
            if move_source:
                (self.root / "tools/validate.py").write_bytes(b"changed validator input\n")
            return result

        with mock.patch.object(A, "HOME", self.root), \
                mock.patch.object(sys, "argv", ["audit_checks.py", *arguments]), \
                mock.patch.object(A, "run_probes", side_effect=verdicts), \
                contextlib.redirect_stdout(io.StringIO()):
            return A.main()

    def test_completed_full_audit_publishes_the_existing_consumer_key(self):
        self.assertEqual(self.execute(), 0)
        self.assertTrue(self.cache.is_file(), "real full PASS has no reusable canonical proof")
        expected = hashlib.sha256(b"validator input\naudit input\n").hexdigest()[:16]
        self.assertEqual(json.loads(self.cache.read_text("utf-8"))["key"], expected)

    def test_missing_cache_binding_does_not_hide_independent_probe_failures(self):
        (self.root / "tools/validate.py").unlink()
        self.probes_seen = set()
        try:
            result = self.execute(overrides={"validator-baseline": "FAIL"})
        except OSError as error:
            self.fail(f"optional cache binding prevented mandatory probe dispatch: {error}")
        self.assertEqual(result, 1)
        self.assertTrue({"root-nul-snapshot", "symlink-restore", "audit-tags-batch",
                         "gated-producer-cases"} <= self.probes_seen)
        self.assertFalse(self.cache.exists())

    def test_scoped_success_never_publishes_full_suite_proof(self):
        self.assertEqual(self.execute(arguments=("--changed", "saipen/STYLE.md")), 0)
        self.assertFalse(self.cache.exists())

    def test_required_failure_never_publishes_passing_proof(self):
        self.assertEqual(self.execute(overrides={"validator-baseline": "FAIL"}), 1)
        self.assertFalse(self.cache.exists())

    def test_required_skip_never_publishes_passing_proof(self):
        self.assertEqual(self.execute(overrides={"mutation-sweep": "SKIP"}), 1)
        self.assertFalse(self.cache.exists())

    def test_advisory_host_gap_remains_named_in_the_completed_proof(self):
        self.assertEqual(self.execute(overrides={"symlink-restore": "UNPROVEN"}), 0)
        self.assertTrue(self.cache.is_file(), "completed advisory result was not reusable")
        self.assertEqual(json.loads(self.cache.read_text("utf-8"))["unproven"],
                         ["symlink-restore"])

    def test_moving_inputs_cannot_publish_current_source_proof(self):
        self.assertEqual(self.execute(move_source=True), 0)
        self.assertFalse(self.cache.exists())

    def test_incomplete_probe_verdicts_cannot_publish_full_suite_proof(self):
        self.assertEqual(self.execute(partial=True), 0)
        self.assertFalse(self.cache.exists())


if __name__ == "__main__":
    unittest.main()
