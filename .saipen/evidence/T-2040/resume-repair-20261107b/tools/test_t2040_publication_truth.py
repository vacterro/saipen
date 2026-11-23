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
from test_hermetic_env import hermetic_env, isolate_host_session

LINEAGE = "lineage-" + "a" * 32
OP_ID = "release-" + "a" * 32


def setUpModule():
    isolate_host_session()


class PublicationTruthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-publication-truth-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "project"
        self.root.mkdir()
        memory = self.root / ".saipen"
        memory.mkdir()
        (memory / "IDENTITY.md").write_text(identity_file_content(LINEAGE), encoding="utf-8")
        (memory / "STATE.md").write_text("---\nphase: DONE\ntask: none\n---\n", encoding="utf-8")
        (memory / "BOARD.md").write_text(
            "# Board\n## DOING\n## TODO\n## DONE\n- [x] T-1 fixture | verify: fixture\n## BLOCKED\n",
            encoding="utf-8",
        )
        (self.root / "code.py").write_text("value = 1\n", encoding="utf-8")
        self.tickets = {"T-1": {"id": "T-1", "section": "## DONE", "checkbox": "x",
                                  "fields": {"publication_state": "pending"}}}
        self.env = mock.patch.dict(os.environ, hermetic_env(
            GIT_OPTIONAL_LOCKS="0", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
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
        self.git("add", "code.py")
        self.git("commit", "-m", "fixture")
        self.remote = Path(self.tmp.name) / "remote.git"
        self.remote.mkdir()
        self.git("init", "--bare", root=self.remote)
        self.git("remote", "add", "origin", str(self.remote))
        self.git("tag", "-a", "v1.0.0", "-m", "fixture")
        self.git("push", "origin", "main", "v1.0.0")
        head = self.git("rev-parse", "HEAD")
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


if __name__ == "__main__":
    unittest.main()
