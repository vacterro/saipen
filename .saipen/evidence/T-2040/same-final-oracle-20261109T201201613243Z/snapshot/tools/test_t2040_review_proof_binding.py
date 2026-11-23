"""T-2040: exact independent review proof; native no-patch closure, no live writes."""

from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import crew, focused_unit, journal, operations, subs
from saipen_engine.producer import ProducerPackage, SETTLED_DIRNAME, producer_namespace
from test_hermetic_env import isolate_host_session
import test_sub_dispose_after_collect as original


def setUpModule():
    isolate_host_session()


class ExactReviewBindingTests(unittest.TestCase):
    def setUp(self):
        self.fixture = original.CoreReviewProofTests()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()

    def _proof(self):
        f = self.fixture
        return subs._independent_core_review(
            f.root, f.package, f.ticket, f.collect_op, tuple(f.records))

    def _reviewed_metadata(self):
        f = self.fixture
        path = f._review()
        metadata = {**f._metadata(), "record": path.relative_to(f.root).as_posix(),
                    "record_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        f.outbox.write_text(subs._mark_package_reviewed(
            f.outbox.read_text(encoding="utf-8"), f.package.package_id), encoding="utf-8")
        return metadata

    def test_dedup_cannot_substitute_hypothesis_for_exact_digest(self):
        f = self.fixture
        meta = {"package_identities": ["sha256:" + "9" * 64], "tickets": ["T-8"],
                "hypotheses": [{"producer": original.ROLE,
                    "package_id": f.package.package_id, "source_head": original.AGED_HEAD,
                    "source_tree_fingerprint": original.AGED_FINGERPRINT,
                    "role_revision": original.FIXTURE_ROLE_REVISION}]}
        record = {**f.records[0], "receipt_metadata": meta}
        self.assertFalse(subs._durable_collect_witness(
            f.root, f.identity, f.identity, (record,), f.package))

    def test_resolved_collect_deduplicates_but_is_not_committed_review_authority(self):
        f = self.fixture
        f._review()
        self.assertIsNotNone(self._proof()[0])
        collect = f.records[0]
        collect.update(status="RESOLVED", resolution="accept_live",
            resolution_applied_targets=[target["path"] for target in collect["targets"]],
            resolution_skipped_targets=[])
        collect["receipt_metadata"].update(operation="sub_collect", status="COMMITTED")
        self.assertTrue(subs._durable_collect_witness(
            f.root, f.identity, f.identity, tuple(f.records), f.package))
        self.assertIsNone(self._proof()[0], "RESOLVED receipt became COMMITTED review authority")

    def test_collect_hypotheses_cannot_contradict_exact_generation(self):
        f = self.fixture
        f._review()
        original_metadata = copy.deepcopy(f.records[0]["receipt_metadata"])
        hypothesis = {"producer": original.ROLE, "package_id": f.package.package_id,
            "source_head": original.AGED_HEAD,
            "source_tree_fingerprint": original.AGED_FINGERPRINT,
            "role_revision": original.FIXTURE_ROLE_REVISION}
        for field, wrong in (("producer", "saihunt"), ("package_id", "UI-999"),
                ("source_head", "d" * 40),
                ("source_tree_fingerprint", "git-delta-v1:" + "7" * 64),
                ("role_revision", "sha256:" + "8" * 64)):
            with self.subTest(field=field):
                f.records[0]["receipt_metadata"] = {**original_metadata,
                    "hypotheses": [{**hypothesis, field: wrong}]}
                self.assertIsNone(self._proof()[0])
        for malformed in ([], "not-an-array", [None], [hypothesis, hypothesis]):
            with self.subTest(hypotheses=malformed):
                f.records[0]["receipt_metadata"] = {**original_metadata,
                                                   "hypotheses": malformed}
                self.assertIsNone(self._proof()[0])
        f.records[0]["receipt_metadata"] = {**original_metadata, "hypotheses": [hypothesis]}
        self.assertIsNotNone(self._proof()[0], self._proof()[1])

    def test_duplicate_collect_owner_cannot_prove_review(self):
        f = self.fixture
        f._review()
        f.records.append(copy.deepcopy(f.records[0]))
        self.assertIsNone(self._proof()[0])

    def test_producer_cannot_supply_its_own_independent_core_review(self):
        f = self.fixture
        f._review()
        f.log_path.write_text(f.log_path.read_text(encoding="utf-8").replace(
            "agent: core-reviewer", "agent: " + original.ROLE), encoding="utf-8")
        for record in f.records:
            record["agent"] = original.ROLE
        self.assertIsNone(self._proof()[0])

    def test_shared_proof_returns_entire_receipt_binding(self):
        metadata = self._reviewed_metadata()
        proof, problem = self._proof()
        self.assertIsNotNone(proof, problem)
        self.assertEqual(proof, metadata)

    def test_disposition_verifier_requires_exact_executed_record_metadata(self):
        metadata = self._reviewed_metadata()
        self.assertEqual(self.fixture._postcondition(metadata), [])
        for key in ("record", "record_sha256"):
            legacy = dict(metadata)
            legacy.pop(key)
            self.assertEqual(self.fixture._postcondition(legacy), [])
            for value in ("wrong-record" if key == "record" else "0" * 64, None, 7, []):
                changed = {**metadata, key: value}
                with self.subTest(field=key, value=value):
                    self.assertTrue(self.fixture._postcondition(changed),
                                    "unbound executed record satisfied disposition verifier")

    def test_collect_verifier_requires_exact_disposition_record_metadata(self):
        f = self.fixture
        metadata = self._reviewed_metadata()
        manifest = f.root / subs.MANIFEST_REL
        manifest.write_text(subs._manifest_with_collects(
            manifest.read_text(encoding="utf-8"),
            {original.ROLE: f.identity + "@2026-11-08T00:00:00Z"}), encoding="utf-8")
        board = f.root / ".saipen/BOARD.md"
        board.write_text(board.read_text(encoding="utf-8").replace(
            "Core review", "Core review " + f.identity), encoding="utf-8")
        disposition = {"op_id": "sub-disposition-00000009", "operation": "sub_disposition",
            "status": "COMMITTED", "receipt_metadata": metadata,
            "targets": [{"path": rel, "applied": True} for rel in (
                ".saipen/LOG.md", ".saipen/STATE.md", f.outbox.relative_to(f.root).as_posix())]}
        targets = [{"path": rel} for rel in (
            ".saipen/LOG.md", ".saipen/BOARD.md", ".saipen/STATE.md", subs.MANIFEST_REL)]
        with mock.patch("saipen_engine.fast_check.validate_project", return_value=[]), \
                mock.patch.object(journal, "semantic_receipt_snapshot", side_effect=lambda _root:
                                  (tuple([*f.records, disposition]), ())):
            def check():
                return journal.verify_sub_collect(f.root, targets,
                                                   {"producers": [original.ROLE]})
            self.assertEqual(check(), [])
            for key in ("record", "record_sha256"):
                legacy = dict(metadata)
                legacy.pop(key)
                disposition["receipt_metadata"] = legacy
                self.assertEqual(check(), [])
                for value in ("wrong-record" if key == "record" else "0" * 64, None, 7, []):
                    disposition["receipt_metadata"] = {**metadata, key: value}
                    with self.subTest(field=key, value=value):
                        self.assertTrue(check(), "collect verifier laundered unbound disposition")


class IntegrationSourceBindingTests(unittest.TestCase):
    def test_settled_integration_requires_exact_input_source(self):
        with tempfile.TemporaryDirectory(prefix="t2040-integration-") as directory:
            root = Path(directory)
            role = SimpleNamespace(name="saiwiki", outbox_path=
                subs.SUBS_REL + "/saiwiki/kitchen/OUTBOX.md")
            package = ProducerPackage(producer=role.name, role_revision="sha256:" + "a" * 64,
                base_source_head="b" * 40, base_source_tree_fingerprint="git-delta-v1:" + "c" * 64,
                base_discovery_model="fixture-discovery", scope="wiki", status="ready")
            path = producer_namespace(root, role.name) / SETTLED_DIRNAME / "package.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({**package.to_dict(), "payload_hashes": {},
                                        "payload_bytes": {}}), encoding="utf-8")
            metadata = {"producer": role.name, "crew_epoch": "crew-epoch-00000001",
                "package_identity": package.package_identity,
                "input_source": package.base_source_head,
                "input_source_fingerprint": package.base_source_tree_fingerprint,
                "resulting_source": "d" * 40,
                "resulting_source_fingerprint": "git-delta-v1:" + "e" * 64}
            record = {"operation": "producer_integration", "status": "COMMITTED",
                "op_id": "producer-integration-00000001", "created_at": "2026-11-08T00:00:00Z",
                "receipt_metadata": metadata}
            snapshot = SimpleNamespace(root=root, epoch=SimpleNamespace(op_id=metadata["crew_epoch"]),
                source_id=SimpleNamespace(source_head=metadata["resulting_source"],
                    source_tree_fingerprint=metadata["resulting_source_fingerprint"]),
                op_records=(record,))
            self.assertIsNotNone(crew._producer_integration_edge(snapshot, role))
            for key in ("input_source", "input_source_fingerprint"):
                expected = metadata.pop(key)
                with self.subTest(field=key, missing=True):
                    self.assertIsNone(crew._producer_integration_edge(snapshot, role))
                metadata[key] = "wrong-source"
                with self.subTest(field=key, mismatch=True):
                    self.assertIsNone(crew._producer_integration_edge(snapshot, role))
                metadata[key] = expected
            self.assertIsNotNone(crew._producer_integration_edge(snapshot, role))


class NativeNoPatchRoundtripTests(unittest.TestCase):
    def test_actual_core_disproof_closes_but_generic_negative_finding_does_not(self):
        from freshness import compute_source_identity
        from saipen_engine.board import parse_board
        from saipen_engine.log import read_history_snapshot
        from test_t1363_zero_manual_entry import healthy

        root = healthy(self)
        (root / "tools").mkdir()
        (root / "tools/test_review.py").write_text(
            "import unittest\nclass Review(unittest.TestCase):\n"
            "    def test_premise(self): self.assertEqual(2 + 2, 4)\n", encoding="utf-8")
        self.assertTrue(subs.sub_spawn(root, original.ROLE, str(TOOLS.parent),
                                       agent="test-agent").ok)
        source = compute_source_identity(root)
        revision = subs.current_local_role_revision(root, original.ROLE, str(TOOLS.parent))
        outbox = root / subs.SUBS_REL / original.ROLE / "kitchen/OUTBOX.md"
        outbox.write_text(
            "# OUTBOX\n\n## UI-001: hypothesis claims two plus two differs from four\n"
            "- **status:** ready\n- **summary:** Independently test the arithmetic premise\n"
            "- **main_project_refs:** [tools/test_review.py]\n- **critical:** false\n"
            f"- **severity:** P3\n- **producer:** {original.ROLE}\n"
            f"- **source_head:** {source.source_head}\n"
            f"- **source_tree_fingerprint:** {source.source_tree_fingerprint}\n"
            f"- **role_revision:** {revision}\n- **coverage:** tools/test_review.py\n"
            "- **payload:** []\n- **verified:** PASS -- producer report only\n"
            "- **instructions:** Core independently rejects the arithmetic premise\n",
            encoding="utf-8")
        package = subs.parse_outbox(outbox.read_text(encoding="utf-8"), original.ROLE).packages[0]
        collected = subs.sub_collect(root, original.ROLE, agent="test-agent")
        self.assertTrue(collected.ok, collected.to_dict())
        ticket = collected.data["tickets"][0]["ticket"]
        self.assertTrue(operations.apply_claim(root, ticket, "test-agent").ok)
        for phase in ("BUILD", "VERIFY"):
            self.assertTrue(operations.transition_phase(root, phase, "test-agent", ticket).ok)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = focused_unit.evidence(root, SimpleNamespace(pattern=["test_review.py"],
                timeout=30, fresh=True, agent="test-agent", ticket=ticket))
        evidence = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0, evidence)
        self.assertTrue(evidence["ok"], evidence)
        relative = evidence["record"]
        digest = hashlib.sha256((root / relative).read_bytes()).hexdigest()
        binding_text = "; ".join(f"{key}={value}" for key, value in
                                subs._package_review_bindings(package, collected.op_id).items())
        citation = f"record:{relative} sha256:{digest}"

        def review(description):
            result = operations.checkpoint(root, "test-agent", "RUN", ticket,
                "review -> PASS conf: high -- " + description + "; " + binding_text + "; " + citation)
            self.assertTrue(result.ok, result.to_dict())
            proof, problem = subs._independent_core_review(root, package, ticket,
                collected.op_id, tuple(subs._iter_operation_records(root)))
            self.assertIsNotNone(proof, problem)
            return proof

        generic_proof = review("independent bounded negative finding; no defects reproduced")
        for phase in ("REVIEW", "SHIP"):
            self.assertTrue(operations.transition_phase(root, phase, "test-agent", ticket).ok)
        before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
        refused = operations.finish_ticket(root, ticket, "test-agent",
            closure_mode="finding_invalidated", invalidation_evidence=generic_proof["review_event"])
        self.assertFalse(refused.ok, refused.to_dict())
        self.assertEqual(refused.code, "PREMISE_NOT_DISPROVEN", refused.to_dict())
        self.assertEqual(before, {path: path.read_bytes() for path in root.rglob("*") if path.is_file()})
        proof = review("premise disproven: actual independent arithmetic test proves two plus two equals four")
        finished = operations.finish_ticket(root, ticket, "test-agent",
            closure_mode="finding_invalidated", invalidation_evidence=proof["review_event"])
        self.assertTrue(finished.ok, finished.to_dict())
        fields = parse_board((root / ".saipen/BOARD.md").read_text(encoding="utf-8"))["tickets"][ticket]["fields"]
        self.assertEqual(fields["closure_mode"], "finding_invalidated")
        self.assertEqual(fields["implementation_delta"], "none")
        disposed = subs.sub_disposition(root, original.ROLE, package.package_id, agent="test-agent")
        self.assertTrue(disposed.ok, disposed.to_dict())
        receipt = journal.Journal(root, disposed.op_id).read()
        for key, value in proof.items():
            self.assertEqual(receipt["receipt_metadata"].get(key), value, key)
        self.assertEqual(journal.verify_sub_disposition(root, receipt["targets"],
                                                       receipt["receipt_metadata"]), [])
        restarted_records = journal.semantic_receipt_snapshot(root)
        self.assertEqual(restarted_records.errors, ())
        restarted_proof, problem = subs._independent_core_review(root, package, ticket,
            collected.op_id, restarted_records.records)
        self.assertEqual(restarted_proof, proof, problem)
        self.assertEqual(subs.sub_collect(root, original.ROLE, agent="test-agent").code,
                         "ALREADY_COLLECTED")
        self.assertEqual(subs.package_identity(subs.parse_outbox(
            outbox.read_text(encoding="utf-8"), original.ROLE).packages[0]), subs.package_identity(package))
        self.assertFalse(any(record["operation"] in ("release", "ticket_supersede")
                             for record in restarted_records.records))
        if destination := os.environ.get("T2040_REVIEW_ROUNDTRIP_EVIDENCE"):
            Path(destination).write_text(json.dumps({"ticket": ticket, "proof": proof,
                "generic_negative_closure": refused.to_dict(), "finish": finished.to_dict(),
                "disposition": disposed.to_dict(), "closure_fields": fields,
                "events": read_history_snapshot(root).events,
                "receipts": restarted_records.records}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
