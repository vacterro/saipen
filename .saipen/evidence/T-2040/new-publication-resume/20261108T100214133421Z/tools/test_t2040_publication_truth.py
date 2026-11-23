"""T-2040: publication truth uses read-only owners, never caller flags.

Git writes, synthetic receipts and authority endpoints belong only to disposable
fixtures. Owner-minted Python carriers separate inputs; they do not authenticate
human consent. The same oracle runs before and after the production correction.
"""
from __future__ import annotations

import copy
import dataclasses
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from saipen_engine import outcome_truth
from saipen_engine.paths import identity_file_content, project_identity
from test_fixture_support import CURRENT_STYLE_CONTRACT
from test_hermetic_env import hermetic_env, isolate_host_session

LINEAGE = "lineage-" + "a" * 32
OP_ID = "release-" + "a" * 32


def setUpModule():
    isolate_host_session()


def simulated_native_release_grant(case, root, remote, head, scope):
    """Fixture-native owner only; production has no native release reservation.

    Real simulated-native broker reproduces the exact scoped instruction. This
    test owner interprets it, constructs a disposable capsule, never bypasses or
    mocks the production release approval consumer, never claims real consent.
    """
    import hashlib
    from saipen_engine import isolated_release, release_authority
    from saipen_engine.pending_ingress import ingress_digest
    from test_t1844_origin_broker import OriginKernelWithSimulatedNativeIdentity

    root, remote = Path(root).resolve(), Path(remote).resolve()
    case.assertNotEqual(root, Path(__file__).resolve().parents[1])
    case.assertEqual(remote.parent, root.parent)
    protected, _ = isolated_release.snapshot_shared_index(root)
    transaction = {"target_remote": "origin", "target_branch": "main",
                   "target_url": str(remote), "base_commit": head,
                   "protected_staging_hash": protected, "reviewed_scope": sorted(scope)}
    text = json.dumps({"evidence_class": "simulated-native-fixture", **transaction}, sort_keys=True)
    native = OriginKernelWithSimulatedNativeIdentity()
    native.setUp()
    case.addCleanup(native.doCleanups)
    native.root = root
    proof = native.issue(action="start", text=text)
    native.register(proof)
    verdict = native.verify(proof, request_digest=ingress_digest(text))
    case.assertTrue(verdict.get("ok"), verdict)
    case.assertFalse(native.verify(proof, request_digest=ingress_digest(text + " changed"))["ok"])
    grant = release_authority.create_release_grant(
        root, **transaction, operator_intent="SIMULATED native fixture; not real release consent",
    )
    path = release_authority.persist_grant(root, grant)
    marker = root / ".saipen/evidence/simulated-native-release.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({"evidence_class": "simulated-native-fixture",
                                 "grant_id": grant["grant_id"], "operator_origin": proof,
                                 "scope_sha256": hashlib.sha256(text.encode()).hexdigest(),
                                 "production_release_consumer": "not exercised"}), encoding="utf-8")
    case.assertEqual(json.loads(path.read_text(encoding="utf-8")), grant)
    return grant


class PublicationTruthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-publication-truth-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "project"
        self.root.mkdir()
        memory = self.root / ".saipen"
        memory.mkdir()
        (memory / "IDENTITY.md").write_text(identity_file_content(LINEAGE), encoding="utf-8")
        (memory / "STATE.md").write_text(
            "---\nphase: DONE\ntask: none\nnext_action: saipen continue\n"
            "blocker: none\nagent: fixture\nmode: no-publish\nsaipen_version: 7\n"
            "schema_version: 3\ntransition_from: SHIP\nupdated: 2026-11-07T20:00:00Z\n"
            f"style_contract: {CURRENT_STYLE_CONTRACT}\n---\n", encoding="utf-8",
        )
        (memory / "BOARD.md").write_text(
            "# Board\n## DOING\n## TODO\n## DONE\n- [x] T-1 fixture | verify: fixture\n## BLOCKED\n",
            encoding="utf-8",
        )
        (self.root / "code.py").write_text("value = 1\n", encoding="utf-8")
        self.tickets = {"T-1": {"id": "T-1", "section": "## DONE", "checkbox": "x",
                                  "fields": {"publication_state": "pending"}}}
        self.env = mock.patch.dict(os.environ, hermetic_env(
            GIT_OPTIONAL_LOCKS="0", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
            GIT_TERMINAL_PROMPT="0", GIT_ALLOW_PROTOCOL="file", GIT_CONFIG_COUNT="0",
            GIT_DIR=None, GIT_WORK_TREE=None, GIT_INDEX_FILE=None,
            SAIPEN_USER_CONFIG_HOME=str(Path(self.tmp.name) / "config"),
        ), clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def truth(self, root=None, **kwargs):
        return outcome_truth.compute_outcome_truth(root, tickets=kwargs.pop("tickets", self.tickets), **kwargs)

    def evidence(self, **kwargs):
        reader = getattr(outcome_truth, "read_publication_evidence", None)
        self.assertTrue(callable(reader), "read-only publication evidence owner missing")
        return reader(self.root, tickets=kwargs.pop("tickets", self.tickets), **kwargs)

    def assert_publication(self, result, status, lane):
        self.assertEqual(result["publication_status"], status, result)
        self.assertEqual(result["publication_lane"], lane, result)
        self.assertEqual(result["lanes"]["PUBLICATION_LANE"], lane)
        self.assertEqual(result["campaign_status"], "CAMPAIGN_" + result["campaign_lane"])

    def git(self, *args, root=None):
        if not shutil.which("git"):
            self.skipTest("git unavailable")
        return subprocess.run(["git", "-C", str(root or self.root), *args],
                              capture_output=True, text=True, check=True, timeout=30).stdout.strip()

    def full_receipt(self, **changes):
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "core.hooksPath", str(Path(self.tmp.name) / "no-hooks"))
        self.git("add", "code.py")
        self.git("commit", "-m", "fixture")
        self.remote = Path(self.tmp.name) / "remote.git"
        self.remote.mkdir()
        self.git("init", "--bare", root=self.remote)
        self.git("remote", "add", "origin", str(self.remote))
        head = self.git("rev-parse", "HEAD")
        simulated_native_release_grant(self, self.root, self.remote, head, ["code.py"])
        self.git("tag", "-a", "v1.0.0", "-m", "fixture")
        self.git("push", "origin", "main", "v1.0.0")
        return self.receipt(source_head=head, closure_commit=head, mode="full", branch="main",
                            remote_push_endpoint=str(self.remote), tag="v1.0.0", version="1.0.0",
                            stages=["REMOTE_VERIFIED"], **changes)

    def receipt(self, **changes):
        record = {"operation": "release", "op_id": OP_ID, "status": "COMMITTED",
                  "release_stage": "COMMITTED", "created_at": "2026-11-07T20:00:00Z",
                  "agent": "fixture", "project_identity": project_identity(self.root),
                  "project_lineage": LINEAGE, "semantic_payload_hash": "fixture",
                  "verification_policy": "none", "targets": [], "progress_index": 0,
                  "ticket_id": "T-1", **changes}
        self.write_receipt(record)
        return record

    def write_receipt(self, record, namespace="settled"):
        path = self.root / ".saipen" / "recovery" / namespace / record["op_id"] / "operation.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record), encoding="utf-8")
        return path

    def local_receipt(self):
        from freshness import compute_source_identity
        identity = compute_source_identity(self.root)
        return self.receipt(mode="no-publish", source_head=identity.source_head,
                            source_tree_fingerprint=identity.source_tree_fingerprint)

    def test_pending_without_hold_is_not_blocked(self):
        result = self.truth()
        self.assert_publication(result, "RELEASE_PENDING", "PENDING")
        self.assertEqual(result["release_lane"], "CLEAR")

    def test_pv15_exact_old_pending_oracle_has_no_blocker(self):
        result = self.truth(self.root, state={"phase": "DONE", "publication_state": "pending"})
        self.assert_publication(result, "RELEASE_PENDING", "PENDING")
        self.assertEqual(result["release_lane"], "CLEAR")

    def test_pv21_executable_budgeted_work_does_not_invent_release_hold(self):
        tickets = {"T-1": {"id": "T-1", "section": "## TODO", "checkbox": " ", "blocked": False}}
        result = self.truth(self.root, tickets=tickets, state={"phase": "PLAN", "authority_until": "budget"})
        self.assertEqual(result["queue_status"], "QUEUE_HAS_WORK")
        self.assert_publication(result, "RELEASE_PENDING", "PENDING")

    def test_fabricated_verified_release_id_never_publishes(self):
        result = self.truth(publication_state="published",
                            publication_evidence={"verified": True, "release_id": "invented"})
        self.assert_publication(result, "RELEASE_UNKNOWN", "UNKNOWN")

    def test_claimed_published_without_owner_proof_is_unknown(self):
        self.assert_publication(self.truth(publication_state="published"), "RELEASE_UNKNOWN", "UNKNOWN")

    def test_done_published_field_is_not_proof(self):
        self.tickets["T-1"]["fields"]["publication_state"] = "published"
        self.assert_publication(self.truth(), "RELEASE_UNKNOWN", "UNKNOWN")

    def test_explicit_unknown_remains_unknown(self):
        self.assert_publication(self.truth(publication_state="unknown"), "RELEASE_UNKNOWN", "UNKNOWN")

    def test_no_publish_intent_is_local_not_pending_or_published(self):
        self.assert_publication(self.truth(publication_state="no-publish"), "LOCAL_NO_PUBLISH", "LOCAL_NO_PUBLISH")

    def test_explicit_blocker_remains_blocked(self):
        result = self.truth(publication_state="blocked")
        self.assert_publication(result, "RELEASE_BLOCKED", "BLOCKED")
        self.assertEqual(result["release_lane"], "BLOCKED")

    def test_foreign_staging_context_survives_outcome_projection(self):
        result = self.truth(foreign_staged=True, has_continuous_maintenance=True)
        self.assert_publication(result, "RELEASE_BLOCKED", "BLOCKED")
        self.assertEqual(result["release_lane"], "BLOCKED_FOREIGN_INDEX")
        self.assertEqual(result["campaign_status"], "CAMPAIGN_WAIT_EXTERNAL")

    def test_external_hold_does_not_suppress_executable_work_or_budget_veto(self):
        tickets = {"T-2": {"id": "T-2", "section": "## TODO", "checkbox": " ", "blocked": False}}
        running = self.truth(tickets=tickets, foreign_staged=True)
        self.assertEqual(running["campaign_status"], "CAMPAIGN_RUNNING")
        budget = self.truth(foreign_staged=True, is_budget_exhausted=True)
        self.assertEqual(budget["campaign_status"], "CAMPAIGN_WAIT_AUTHORITY")

    def test_primary_blocker_context_survives_outcome_projection(self):
        result = self.truth(primary_blocker={"cause": "publication-staging", "blocker_class": "EXTERNAL"})
        self.assertEqual(result["release_lane"], "BLOCKED_FOREIGN_INDEX")
        self.assertEqual(result["campaign_status"], "CAMPAIGN_WAIT_EXTERNAL")

    def test_owner_reads_absence_as_pending(self):
        self.assert_publication(self.truth(publication_evidence=self.evidence()), "RELEASE_PENDING", "PENDING")

    def test_exact_canonical_receipt_and_local_remote_prove_publication(self):
        self.full_receipt()
        before = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        evidence = self.evidence()
        self.assert_publication(self.truth(publication_evidence=evidence), "RELEASE_PUBLISHED", "PUBLISHED")
        after = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(after, before, "read-only owner changed fixture bytes")

    def test_root_none_consumes_owner_carrier_without_io(self):
        self.full_receipt()
        evidence = self.evidence()
        with mock.patch("saipen_engine.journal.semantic_receipt_snapshot", side_effect=AssertionError("IO")), \
             mock.patch("saipen_engine.release.release_verdict", side_effect=AssertionError("IO")), \
             mock.patch.object(Path, "read_bytes", side_effect=AssertionError("IO")), \
             mock.patch.object(Path, "read_text", side_effect=AssertionError("IO")):
            self.assert_publication(self.truth(publication_evidence=evidence), "RELEASE_PUBLISHED", "PUBLISHED")
            lanes = outcome_truth.compute_lane_statuses(None, tickets=self.tickets, publication_evidence=evidence)
            self.assertEqual(lanes["PUBLICATION_LANE"], "PUBLISHED")

    def test_copied_replaced_constructed_and_mutated_carriers_are_not_owner_proof(self):
        self.local_receipt()
        evidence = self.evidence()
        values = {field.name: getattr(evidence, field.name) for field in dataclasses.fields(evidence)}
        forged = [copy.copy(evidence), copy.deepcopy(evidence), dataclasses.replace(evidence), type(evidence)(**values)]
        for candidate in forged:
            with self.subTest(candidate=type(candidate).__name__):
                self.assert_publication(self.truth(publication_evidence=candidate), "RELEASE_UNKNOWN", "UNKNOWN")
        object.__setattr__(evidence, "receipt_digest", "invented")
        self.assert_publication(self.truth(publication_evidence=evidence), "RELEASE_UNKNOWN", "UNKNOWN")

    def test_foreign_root_replay_is_unknown(self):
        self.local_receipt()
        evidence = self.evidence()
        foreign = Path(self.tmp.name) / "foreign"
        foreign.mkdir()
        self.assert_publication(self.truth(foreign, publication_evidence=evidence), "RELEASE_UNKNOWN", "UNKNOWN")

    def test_foreign_ticket_or_changed_ticket_snapshot_replay_is_unknown(self):
        self.local_receipt()
        evidence = self.evidence()
        foreign = {"T-2": {"id": "T-2", "section": "## DONE", "checkbox": "x", "fields": {}}}
        self.assert_publication(self.truth(tickets=foreign, publication_evidence=evidence), "RELEASE_UNKNOWN", "UNKNOWN")
        self.tickets["T-1"]["fields"]["verify"] = "changed"
        self.assert_publication(self.truth(publication_evidence=evidence), "RELEASE_UNKNOWN", "UNKNOWN")

    def test_mixed_ticket_snapshot_cannot_borrow_or_hide_pending_publication(self):
        self.full_receipt()
        self.tickets["T-2"] = {"id": "T-2", "section": "## DONE", "fields": {"publication_state": "pending"}}
        result = self.truth(publication_evidence=self.evidence())
        self.assert_publication(result, "RELEASE_PENDING", "PENDING")
        states = {item["ticket_id"]: item["status"] for item in result["publication_details"]["tickets"]}
        self.assertEqual(states, {"T-1": "published", "T-2": "pending"})
        selected = {"T-1": self.tickets["T-1"]}
        evidence = self.evidence(ticket_id="T-1")
        self.assert_publication(self.truth(tickets=selected, publication_evidence=evidence), "RELEASE_PUBLISHED", "PUBLISHED")

    def test_other_ticket_receipt_cannot_publish_this_ticket(self):
        record = self.full_receipt()
        record["ticket_id"] = "T-2"
        self.write_receipt(record)
        self.assert_publication(self.truth(publication_evidence=self.evidence()), "RELEASE_PENDING", "PENDING")

    def test_partial_or_competing_matching_receipts_remain_unknown(self):
        record = self.full_receipt()
        record.update(op_id="release-" + "b" * 32, status="APPLYING", release_stage="BRANCH_PUBLISHED")
        path = self.write_receipt(record, "ops")
        self.assert_publication(self.truth(publication_evidence=self.evidence()), "RELEASE_UNKNOWN", "UNKNOWN")
        path.unlink()
        record.update(status="COMMITTED", release_stage="COMMITTED", closure_commit="b" * 40)
        self.write_receipt(record)
        self.assert_publication(self.truth(publication_evidence=self.evidence()), "RELEASE_UNKNOWN", "UNKNOWN")

    def test_corrupt_or_duplicate_receipts_remain_unknown(self):
        self.local_receipt()
        path = self.root / ".saipen" / "recovery" / "ops" / ("release-" + "c" * 32) / "operation.json"
        path.parent.mkdir(parents=True)
        path.write_text("{", encoding="utf-8")
        self.assert_publication(self.truth(publication_evidence=self.evidence()), "RELEASE_UNKNOWN", "UNKNOWN")
        path.unlink()
        record = self.local_receipt()
        record["source_head"] = "foreign"
        self.write_receipt(record, "ops")
        self.assert_publication(self.truth(publication_evidence=self.evidence()), "RELEASE_UNKNOWN", "UNKNOWN")

    def test_missing_or_foreign_project_binding_never_publishes(self):
        record = self.full_receipt()
        record.pop("project_lineage")
        record["project_identity"] = ""
        self.write_receipt(record)
        self.assert_publication(self.truth(publication_evidence=self.evidence()), "RELEASE_UNKNOWN", "UNKNOWN")
        record["project_lineage"] = "lineage-" + "f" * 32
        self.write_receipt(record)
        self.assert_publication(self.truth(publication_evidence=self.evidence()), "RELEASE_UNKNOWN", "UNKNOWN")

    def test_missing_remote_git_proof_is_unknown(self):
        record = self.full_receipt()
        record["remote_push_endpoint"] = str(Path(self.tmp.name) / "missing.git")
        self.write_receipt(record)
        self.assert_publication(self.truth(publication_evidence=self.evidence()), "RELEASE_UNKNOWN", "UNKNOWN")

    def test_stale_git_proof_is_rejected_at_explicit_root_boundary(self):
        self.full_receipt()
        evidence = self.evidence()
        self.git("push", "origin", ":refs/tags/v1.0.0")
        self.assert_publication(self.truth(self.root, publication_evidence=evidence), "RELEASE_UNKNOWN", "UNKNOWN")

    def test_bound_no_publish_receipt_is_local_only(self):
        self.local_receipt()
        result = self.truth(publication_evidence=self.evidence())
        self.assert_publication(result, "LOCAL_NO_PUBLISH", "LOCAL_NO_PUBLISH")
        self.assertNotEqual(result["publication_status"], "RELEASE_PUBLISHED")

    def test_stale_local_no_publish_source_is_unknown(self):
        self.local_receipt()
        (self.root / "code.py").write_text("value = 2\n", encoding="utf-8")
        self.assert_publication(self.truth(publication_evidence=self.evidence()), "RELEASE_UNKNOWN", "UNKNOWN")


    def zero_delta_finish(self, *, tracked=False):
        from freshness import compute_source_identity
        from saipen_engine.journal import hash_bytes
        from saipen_engine.plan import semantic_payload_hash

        self.git("init", "-b", "main")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "core.hooksPath", str(Path(self.tmp.name) / "no-hooks"))
        (self.root / ".gitignore").write_text(".saipen/\n", encoding="utf-8")
        relative = "code.py" if tracked else ".saipen/producer/payload.txt"
        payload = self.root / relative
        payload.parent.mkdir(parents=True, exist_ok=True)
        if not tracked:
            payload.write_bytes(b"identical ignored package bytes\n")
        self.git("add", "code.py", ".gitignore")
        self.git("commit", "-m", "fixture base")
        identity = compute_source_identity(self.root)
        self.tickets["T-1"]["fields"].update(owner="fixture", claim_time="2026-11-07T20:00:00Z")
        (self.root / ".saipen/BOARD.md").write_text(
            "# Board\n## DOING\n## TODO\n## DONE\n- [x] T-1 fixture | verify: fixture"
            " | owner: fixture | claim_time: 2026-11-07T20:00:00Z"
            " | closure_mode: own_patch | publication_state: pending\n## BLOCKED\n", encoding="utf-8",
        )
        finish_id = "finish-" + "d" * 32
        (self.root / ".saipen/LOG.md").write_text(
            "# Log\n- 07.11.26 20:00 [E-1] [T-1] [agent: fixture] [op: transition-fixture]"
            " RUN: transition to VERIFY\n"
            "- 07.11.26 20:00 [E-2] [parent: E-1] [T-1] [agent: fixture] [op: checkpoint-fixture]"
            " RUN: verify -> PASS [target: T-1] conf: high -- exact producer zero-delta hashes verified\n"
            f"- 07.11.26 20:00 [E-3] [parent: E-2] [T-1] [agent: fixture] [op: {finish_id}]"
            " DEC: ticket finished via SAIOPS -- completion (from SHIP); publication_state pending\n",
            encoding="utf-8",
        )
        common = {"status": "COMMITTED", "created_at": "2026-11-07T20:00:00Z",
                  "agent": "fixture", "project_identity": project_identity(self.root),
                  "project_lineage": LINEAGE, "verification_policy": "core_fast"}
        package = "sha256:" + "e" * 64
        target_hash = hash_bytes(payload.read_bytes())
        producer = {**common, "operation": "producer_integration", "op_id": "producer-integrate-fixture",
                    "semantic_payload_hash": package, "progress_index": 1,
                    "targets": [{"path": relative, "role": "generic", "action": "write",
                                 "before_hash": target_hash, "after_hash": target_hash, "applied": True}],
                    "receipt_metadata": {"operation": "producer_integration", "status": "COMMITTED",
                                         "ticket_id": "T-1", "producer": "fixture", "package_identity": package,
                                         "input_source": identity.source_head,
                                         "resulting_source": identity.source_head,
                                         "input_source_fingerprint": identity.source_tree_fingerprint,
                                         "resulting_source_fingerprint": identity.source_tree_fingerprint}}
        finish = {**common, "operation": "finish", "op_id": finish_id,
                  "semantic_payload_hash": semantic_payload_hash({"operation": "finish", "ticket": "T-1"}),
                  "progress_index": 3, "targets": [
                      {"path": f".saipen/{name}.md", "role": role, "action": "write",
                       "before_hash": "f" * 16, "after_hash": hash_bytes((self.root / f".saipen/{name}.md").read_bytes()),
                       "applied": True} for name, role in (("LOG", "log"), ("BOARD", "board"), ("STATE", "state"))]}
        self.write_receipt(producer)
        self.finish_path = self.write_receipt(finish)
        self.producer_path = self.root / ".saipen/recovery/settled/producer-integrate-fixture/operation.json"
        return producer, finish, payload

    def test_wave_d_no_publish_closure_is_compatible_but_not_publication(self):
        from saipen_engine import closure
        self.local_receipt()
        self.assertEqual(closure.publication_state(self.root, "T-1"), "pending")
        verdict = closure.resolve_implementation_source(self.root, "T-1")
        self.assertTrue(verdict.ok, verdict.to_dict())
        self.assertFalse(verdict.published, verdict.to_dict())
        self.assertFalse(verdict.to_dict()["published"])

    def test_wave_d_legacy_commit_and_no_publish_op_id_are_not_publication(self):
        from saipen_engine import closure
        path = self.root / ".saipen/kitchen/release_receipt.json"
        path.parent.mkdir(parents=True)
        for artifact in ({"commit": "c0ffee", "version": "1.0.0", "op_id": OP_ID},
                         {"mode": "no-publish", "op_id": OP_ID}):
            with self.subTest(artifact=artifact):
                path.write_text(json.dumps({"ticket_id": "T-1", **artifact}), encoding="utf-8")
                self.assertEqual(closure.publication_state(self.root, "T-1"), "pending")
                verdict = closure.resolve_implementation_source(self.root, "release:" + OP_ID)
                self.assertTrue(verdict.ok, verdict.to_dict())
                self.assertFalse(verdict.published, verdict.to_dict())

    def test_wave_d_canonical_full_closure_has_explicit_publication_flag(self):
        from saipen_engine import closure
        self.full_receipt()
        verdict = closure.resolve_implementation_source(self.root, "T-1")
        self.assertTrue(verdict.ok, verdict.to_dict())
        self.assertTrue(verdict.published, verdict.to_dict())
        self.assertEqual(closure.publication_state(self.root, "T-1"), "published")

    def test_wave_d_duplicate_terminal_operations_cannot_publish(self):
        from saipen_engine import closure
        record = self.full_receipt()
        record["op_id"] = "release-" + "b" * 32
        self.write_receipt(record)
        self.assert_publication(self.truth(publication_evidence=self.evidence()), "RELEASE_UNKNOWN", "UNKNOWN")
        self.assertEqual(closure.publication_state(self.root, "T-1"), "pending")

    def test_wave_d_corrupt_receipt_cannot_borrow_kitchen_publication(self):
        from saipen_engine import closure
        record = self.full_receipt()
        kitchen = self.root / ".saipen/kitchen/release_receipt.json"
        kitchen.parent.mkdir(parents=True)
        kitchen.write_text(json.dumps({**record, "commit": record["closure_commit"]}), encoding="utf-8")
        self.write_receipt({"op_id": "release-corrupt"}).write_text("{", encoding="utf-8")
        self.assertEqual(closure.publication_state(self.root, "T-1"), "pending")
        self.assertFalse(closure.resolve_implementation_source(self.root, "T-1").published)

    def test_wave_d_verified_ignored_zero_delta_finish_is_local_only(self):
        self.zero_delta_finish()
        evidence = self.evidence()
        self.assert_publication(self.truth(publication_evidence=evidence), "LOCAL_NO_PUBLISH", "LOCAL_NO_PUBLISH")
        with mock.patch.object(Path, "read_text", side_effect=AssertionError("IO")), \
             mock.patch.object(Path, "read_bytes", side_effect=AssertionError("IO")), \
             mock.patch.object(outcome_truth, "read_publication_evidence", side_effect=AssertionError("IO")):
            result = outcome_truth.aggregate_publication_evidence(tickets=self.tickets, publication_evidence=evidence)
            self.assertTrue(result["checked"], result)
            self.assertEqual(result["tickets"][0]["status"], "no-publish")
            self.assert_publication(self.truth(publication_evidence=evidence), "LOCAL_NO_PUBLISH", "LOCAL_NO_PUBLISH")

    def test_wave_d_local_finish_stale_payload_rejected_at_explicit_root(self):
        _producer, _finish, payload = self.zero_delta_finish()
        evidence = self.evidence()
        payload.write_bytes(b"changed bytes\n")
        self.assert_publication(self.truth(self.root, publication_evidence=evidence), "RELEASE_UNKNOWN", "UNKNOWN")

    def test_wave_d_finish_and_owner_receipt_binding_cannot_be_borrowed(self):
        producer, finish, _payload = self.zero_delta_finish()
        for change in ({"project_lineage": "lineage-" + "f" * 32}, {"agent": "foreign"},
                       {"semantic_payload_hash": "f" * 16}, {"status": "PREPARED"}):
            with self.subTest(change=change):
                self.finish_path.write_text(json.dumps({**finish, **change}), encoding="utf-8")
                self.assertNotEqual(self.evidence().tickets[0][1], "no-publish")
        self.finish_path.write_text(json.dumps(finish), encoding="utf-8")
        producer["receipt_metadata"]["ticket_id"] = "T-2"
        self.producer_path.write_text(json.dumps(producer), encoding="utf-8")
        self.assertEqual(self.evidence().tickets[0][1], "pending")

    def test_wave_d_identical_tracked_producer_bytes_do_not_discharge_adopted_delta(self):
        self.zero_delta_finish(tracked=True)
        self.assertEqual(self.evidence().tickets[0][1], "pending")

    def test_wave_d_no_new_code_prose_is_not_zero_delta_authority(self):
        self.zero_delta_finish(tracked=True)
        shutil.rmtree(self.producer_path.parent)
        path = self.root / ".saipen/LOG.md"
        path.write_text(path.read_text(encoding="utf-8").replace(
            "exact producer zero-delta hashes verified", "no new code; adopted existing unpublished implementation"),
            encoding="utf-8")
        self.assertEqual(self.evidence().tickets[0][1], "pending")

    def test_wave_d_pure_aggregation_rejects_hints_and_carrier_reconstruction(self):
        self.tickets["T-1"]["fields"]["publication_state"] = "no-publish"
        evidence = self.evidence()
        result = outcome_truth.aggregate_publication_evidence(tickets=self.tickets, publication_evidence=evidence)
        self.assertTrue(result["checked"], result)
        self.assertEqual(result["tickets"][0]["status"], "pending")
        for candidate in (None, copy.copy(evidence), copy.deepcopy(evidence), dataclasses.replace(evidence)):
            result = outcome_truth.aggregate_publication_evidence(tickets=self.tickets, publication_evidence=candidate)
            self.assertFalse(result["checked"], result)
            self.assertEqual(result["status"], "unknown")
        empty = outcome_truth.read_publication_evidence(self.root, tickets={})
        result = outcome_truth.aggregate_publication_evidence(tickets={}, publication_evidence=empty)
        self.assertTrue(result["checked"], result)
        self.assertEqual(result["tickets"], [])

    def test_wave_d_context_captures_publication_and_source_identity_once(self):
        from freshness import compute_source_identity
        from saipen_engine import context
        (self.root / ".saipen/LOG.md").write_text("# Log\n", encoding="utf-8")
        evidence, identity = self.evidence(), compute_source_identity(self.root)
        with mock.patch.object(outcome_truth, "read_publication_evidence", return_value=evidence) as publication, \
             mock.patch("freshness.compute_source_identity", return_value=identity) as source:
            inputs = context._load_context_inputs(self.root)
        self.assertEqual(publication.call_count, 1)
        self.assertEqual(source.call_count, 1)
        self.assertIs(inputs["publication_evidence"], evidence)
        self.assertIs(inputs["source_identity"], identity)
        self.assertIs(publication.call_args.kwargs["history"], inputs["snap"].history)

    def test_wave_d_context_explicitly_forwards_same_carrier_outside_discovery_result(self):
        from freshness import compute_source_identity
        from saipen_engine import context, router
        (self.root / ".saipen/LOG.md").write_text("# Log\n", encoding="utf-8")
        inputs = context._load_context_inputs(self.root)
        carrier = self.evidence()
        identity = compute_source_identity(self.root)
        inputs.update(publication_evidence=carrier, source_identity=identity)
        discovery_result = {"persistent_goals": [], "source_evidence": {},
                            "continuous_maintenance_authorized": False,
                            "source_generation": "fixture", "discovery_dispatch": None}

        class Routed(Exception):
            pass

        for command in (context.context_cold, context.context_hot, context.context_audit):
            with self.subTest(command=command.__name__), \
                 mock.patch.object(context, "_load_inputs_checked", return_value=inputs), \
                 mock.patch.object(context, "discovery_evidence", return_value=discovery_result) as discovery, \
                 mock.patch.object(router, "route_next", side_effect=Routed) as route, \
                 mock.patch.object(router, "queued_source_projection", return_value=None), \
                 mock.patch.object(router, "pending_append_projection", return_value=None), \
                 mock.patch("saipen_engine.capability.negotiate_capability", return_value="read-only"):
                with self.assertRaises(Routed):
                    command(self.root)
                self.assertIs(discovery.call_args.kwargs.get("publication_evidence"), carrier)
                self.assertIs(discovery.call_args.kwargs.get("source_identity"), identity)
                self.assertIs(discovery.call_args.kwargs.get("history"), inputs["snap"].history)
                self.assertIs(route.call_args.kwargs.get("publication_evidence"), carrier)
                self.assertEqual(set(discovery_result), {"persistent_goals", "source_evidence",
                                 "continuous_maintenance_authorized", "source_generation", "discovery_dispatch"})


if __name__ == "__main__":
    unittest.main()
