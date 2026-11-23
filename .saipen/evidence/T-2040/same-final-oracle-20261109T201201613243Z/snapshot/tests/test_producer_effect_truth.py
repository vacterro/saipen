import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from test_fixture_support import CURRENT_STYLE_CONTRACT
from saipen_engine import campaign, intent, operations, producer as P, subs
from freshness import compute_source_identity


def wf(root: Path, rel: str, content: str | bytes) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        p.write_text(content, encoding="utf-8")
    else:
        p.write_bytes(content)
    return p


class TestProducerEffectTruth(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="eff_truth_"))
        self.root = self.tmp / "project"
        self.root.mkdir()
        subprocess.run(["git", "init", str(self.root)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "-C", str(self.root), "config", "user.name", "Test"], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.email", "test@example.com"], check=True)
        wf(self.root, ".gitignore", "kitchen/\n")
        wf(self.root, "src/wiki.md", "# Wiki Source\n")
        wf(self.root, ".saipen/IDENTITY.md", "---\nproject_lineage: lineage-b512942bac884a8691f6c98afcd6ddb9\n---\n")
        wf(self.root, ".saipen/STATE.md", f"""---
phase: DONE
task: none
next_action: "saipen crew"
blocker: none
transition_from: SCOUT
saipen_version: 8
schema_version: 3
last_event: 1
style_contract: {CURRENT_STYLE_CONTRACT}
saipen_home: "{self.root.as_posix()}"
agent: test-agent
mode: full
updated: "2026-11-07T05:00:52Z"
execution_intent: normal
---
""")
        wf(self.root, ".saipen/BOARD.md", "## DOING\n## TODO\n## DONE\n## BLOCKED\n")
        wf(self.root, ".saipen/LOG.md", "# Log\n- 01.01.26 00:00 [E-0001] [agent: test] RUN: init\n")
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-m", "init"], check=True, stdout=subprocess.DEVNULL)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _publish_pkg(self, ns: Path, producer: str, scope: str, content: str):
        read_paths = ["src/wiki.md"]
        write_paths = ["kitchen/wiki/index.md"]
        read_set = P.read_set_from(self.root, read_paths)
        write_set = P.write_set_before(self.root, write_paths)
        epoch = P.ProducerEpoch.current(ns)
        source_id = compute_source_identity(self.root)
        try:
            role_rev = subs.current_local_role_revision(self.root, producer) or "sha256:rev1"
        except Exception:
            role_rev = "sha256:rev1"
        pkg = P.ProducerPackage(
            producer=producer,
            role_revision=role_rev,
            base_source_head=source_id.source_head,
            base_source_tree_fingerprint=source_id.source_tree_fingerprint,
            base_discovery_model=source_id.discovery_model,
            scope=scope,
            read_set=read_set,
            write_set=write_set,
            epoch=epoch,
        )
        gen = P.StagingGeneration(ns, producer).begin()
        gen.set_package(pkg)
        gen.add_payload("kitchen/wiki/index.md", content)
        pub = gen.publish()
        self.assertTrue(pub["ok"])
        ready, errors = P.StagingGeneration.scan_ready(ns)
        self.assertEqual(errors, [])
        matching = [p for p in ready if p.package_identity == pkg.package_identity]
        self.assertEqual(len(matching), 1)
        return matching[0]

    # -----------------------------------------------------------------------
    # P0-01: Stale Receipt Hides Missing Output / Live Proof Revalidation
    # -----------------------------------------------------------------------

    def test_p0_01_deleted_output_cannot_return_already_current_and_restores(self) -> None:
        """Deleted output target cannot return ALREADY_CURRENT and is restored."""
        ns = P.producer_namespace(self.root, "saiwiki")
        P.ProducerEpoch.claim(ns)

        # 1. First integration writes output successfully
        pkg1 = self._publish_pkg(ns, "saiwiki", "Initial scope", "# Wiki content\n")
        res1 = P.integrate_packages_core([pkg1], self.root, agent="test")
        self.assertTrue(res1["results"][0]["wrote"])
        doc_path = self.root / "kitchen/wiki/index.md"
        self.assertTrue(doc_path.is_file())
        self.assertEqual(doc_path.read_text(encoding="utf-8"), "# Wiki content\n")

        # 2. Target file is deleted without modifying source
        doc_path.unlink()
        self.assertFalse(doc_path.exists())

        # 3. Publish same package again under same source identity
        pkg2 = self._publish_pkg(ns, "saiwiki", "Initial scope", "# Wiki content\n")

        # 4. Must NOT return ALREADY_CURRENT; must restore output file
        res2 = P.integrate_packages_core([pkg2], self.root, agent="test")
        self.assertNotEqual(res2["results"][0]["code"], "ALREADY_CURRENT")
        self.assertTrue(res2["results"][0]["wrote"])
        self.assertTrue(doc_path.is_file(), "Missing output must be restored")
        self.assertEqual(doc_path.read_text(encoding="utf-8"), "# Wiki content\n")

    def test_p0_01_modified_output_drift_cannot_return_already_current_and_refuses(self) -> None:
        """Modified output cannot return ALREADY_CURRENT and refuses overwrite on drift."""
        ns = P.producer_namespace(self.root, "saiwiki")
        P.ProducerEpoch.claim(ns)

        pkg1 = self._publish_pkg(ns, "saiwiki", "Scope 1", "# Original\n")
        res1 = P.integrate_packages_core([pkg1], self.root, agent="test")
        self.assertTrue(res1["results"][0]["wrote"])

        # Drift target output on disk
        doc_path = self.root / "kitchen/wiki/index.md"
        doc_path.write_text("# Unrelated human edit\n", encoding="utf-8")

        # Try to re-integrate pkg1 whose write_set expected the original before-hash
        res2 = P.integrate_packages_core([pkg1], self.root, agent="test")

        # Cannot return ALREADY_CURRENT and cannot silently overwrite human edit
        self.assertNotEqual(res2["results"][0]["code"], "ALREADY_CURRENT")
        self.assertEqual(res2["results"][0]["code"], "STALE")
        self.assertFalse(res2["results"][0]["wrote"])
        self.assertEqual(doc_path.read_text(encoding="utf-8"), "# Unrelated human edit\n")

    def test_p0_01_valid_unchanged_output_still_deduplicates(self) -> None:
        """Valid unchanged output with committed receipt returns ALREADY_CURRENT."""
        ns = P.producer_namespace(self.root, "saiwiki")
        P.ProducerEpoch.claim(ns)

        pkg1 = self._publish_pkg(ns, "saiwiki", "Scope 1", "# Stable\n")
        res1 = P.integrate_packages_core([pkg1], self.root, agent="test")
        self.assertTrue(res1["results"][0]["wrote"])

        # Re-publish same content
        pkg2 = self._publish_pkg(ns, "saiwiki", "Scope 2", "# Stable\n")
        res2 = P.integrate_packages_core([pkg2], self.root, agent="test")
        self.assertEqual(res2["results"][0]["code"], "ALREADY_CURRENT")
        self.assertFalse(res2["results"][0]["wrote"])

    def test_p0_01_new_authenticated_payload_generates_real_work(self) -> None:
        """Changed payload bytes bypass ALREADY_CURRENT and perform write."""
        ns = P.producer_namespace(self.root, "saiwiki")
        P.ProducerEpoch.claim(ns)

        pkg1 = self._publish_pkg(ns, "saiwiki", "Scope 1", "# V1\n")
        res1 = P.integrate_packages_core([pkg1], self.root, agent="test")
        self.assertTrue(res1["results"][0]["wrote"])

        pkg2 = self._publish_pkg(ns, "saiwiki", "Scope 2", "# V2\n")
        res2 = P.integrate_packages_core([pkg2], self.root, agent="test")
        self.assertTrue(res2["results"][0]["wrote"])
        doc_path = self.root / "kitchen/wiki/index.md"
        self.assertEqual(doc_path.read_text(encoding="utf-8"), "# V2\n")

    # -----------------------------------------------------------------------
    # P0-02: Worker-Controlled Progress Class is NOT Trusted
    # -----------------------------------------------------------------------

    def test_p0_02_self_reported_source_changed_with_no_delta_is_no_effect(self) -> None:
        """Worker claiming SOURCE_CHANGED without verified source delta is NO_EFFECT."""
        ctrl = campaign.CampaignController(self.root)
        worker_result = {"progress_class": "SOURCE_CHANGED", "ok": True}
        observation = {
            "before_event": "E-1",
            "after_event": "E-1",
            "before_state": "X",
            "after_state": "X",
        }
        res = ctrl._verify_progress_evidence(worker_result, observation=observation)
        self.assertFalse(res["made_progress"])
        self.assertEqual(res["progress_class"], campaign.ProgressClass.NO_EFFECT.value)

    def test_p0_02_self_reported_semantic_evidence_without_evidence_is_no_effect(self) -> None:
        """Worker claiming SEMANTIC_EVIDENCE_ADDED without evidence delta is NO_EFFECT."""
        ctrl = campaign.CampaignController(self.root)
        worker_result = {"progress_class": "SEMANTIC_EVIDENCE_ADDED", "ok": True}
        observation = {"before_event": "E-1", "after_event": "E-1"}
        res = ctrl._verify_progress_evidence(worker_result, observation=observation)
        self.assertFalse(res["made_progress"])
        self.assertEqual(res["progress_class"], campaign.ProgressClass.NO_EFFECT.value)

    def test_p0_02_journal_only_changes_cannot_count_as_source_changed(self) -> None:
        """Journal-only changes (LOG.md advanced) cannot count as productive progress."""
        ctrl = campaign.CampaignController(self.root)
        worker_result = {"ok": True}
        observation = {
            "before_event": "E-1",
            "after_event": "E-2",
            "before_state": "X",
            "after_state": "X",
        }
        res = ctrl._verify_progress_evidence(worker_result, observation=observation)
        self.assertFalse(res["made_progress"])
        self.assertEqual(res["progress_class"], campaign.ProgressClass.NO_EFFECT.value)

    def test_p0_02_state_only_changes_cannot_count_as_semantic_progress(self) -> None:
        """STATE-only mutations cannot count as productive engineering progress."""
        ctrl = campaign.CampaignController(self.root)
        worker_result = {"ok": True}
        observation = {
            "before_event": "E-1",
            "after_event": "E-1",
            "before_state": "X",
            "after_state": "Y",
        }
        res = ctrl._verify_progress_evidence(worker_result, observation=observation)
        self.assertFalse(res["made_progress"])
        self.assertEqual(res["progress_class"], campaign.ProgressClass.NO_EFFECT.value)

    def test_p0_02_unattributed_source_changed_hint_with_no_op_id_is_unverified_effect(self) -> None:
        """Negative control: Worker claiming SOURCE_CHANGED without attributed op_id is UNVERIFIED_EFFECT."""
        ctrl = campaign.CampaignController(self.root)
        worker_result = {"progress_class": "SOURCE_CHANGED", "ok": True}
        observation = {
            "before_event": "E-1",
            "after_event": "E-2",
            "source_delta": True,
        }
        res = ctrl._verify_progress_evidence(worker_result, observation=observation)
        self.assertFalse(res["made_progress"])
        self.assertEqual(res["progress_class"], "UNVERIFIED_EFFECT")

    def test_p0_02_genuinely_current_worker_bound_committed_mutation_verified(self) -> None:
        """Positive control: Genuinely current-worker-bound COMMITTED mutation proves SOURCE_CHANGED."""
        from saipen_engine.journal import _hash_file
        import datetime
        ctrl = campaign.CampaignController(self.root)
        attempt = {
            "attempt_id": "attempt-bound-1",
            "campaign_id": "CAMP-BOUND-TEST",
            "generation": 1,
            "started_at": "2026-11-07T09:00:00Z",
        }
        target_path = self.root / "src" / "mutation.txt"
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text("mutation line\n", encoding="utf-8")
        op_id = "op-bound-00000001"
        op_dir = self.root / ".saipen" / "recovery" / "ops" / op_id
        op_dir.mkdir(parents=True, exist_ok=True)
        rec = {
            "op_id": op_id,
            "status": "COMMITTED",
            "operation": "worker_mutation",
            "semantic_payload_hash": "sha256:0",
            "created_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "agent": "test",
            "project_identity": "test-project",
            "project_lineage": "lineage-b512942bac884a8691f6c98afcd6ddb9",
            "progress_index": 0,
            "targets": [{
                "path": "src/mutation.txt",
                "role": "generic",
                "action": "write",
                "applied": True,
                "before_hash": "",
                "after_hash": _hash_file(target_path),
            }],
            "receipt_metadata": {
                "attempt_id": "attempt-bound-1",
                "campaign_id": "CAMP-BOUND-TEST",
                "worker_generation": 1,
            },
        }
        (op_dir / "operation.json").write_text(json.dumps(rec), encoding="utf-8")
        worker_result = {
            "progress_class": "SOURCE_CHANGED",
            "ok": True,
            "wrote": True,
            "op_id": op_id,
        }
        observation = {
            "before_event": "E-1",
            "after_event": "E-2",
            "source_delta": True,
        }
        res = ctrl._verify_progress_evidence(
            worker_result, observation=observation, attempt=attempt
        )
        self.assertTrue(res["made_progress"])
        self.assertEqual(res["progress_class"], campaign.ProgressClass.SOURCE_CHANGED.value)


    def test_p0_02_verified_evidence_delta_counts_as_semantic_evidence(self) -> None:
        """Bare evidence_delta=True without authenticated verifier receipt is UNVERIFIED_EFFECT."""
        ctrl = campaign.CampaignController(self.root)
        worker_result = {"progress_class": "SEMANTIC_EVIDENCE_ADDED", "ok": True}
        observation = {
            "before_event": "E-1",
            "after_event": "E-2",
            "evidence_delta": True,
        }
        res = ctrl._verify_progress_evidence(worker_result, observation=observation)
        self.assertFalse(res["made_progress"])
        self.assertEqual(res["progress_class"], "UNVERIFIED_EFFECT")

    def test_p0_02_mock_only_progress_does_not_certify_progress(self) -> None:
        """Mock-only injected worker assertion without verified delta does not certify progress."""
        ctrl = campaign.CampaignController(self.root)
        worker_result = {"progress_verified": True, "ok": True}
        observation = {"before_event": "E-1", "after_event": "E-1"}
        res = ctrl._verify_progress_evidence(
            worker_result, observation=observation, injected_worker=True
        )
        self.assertFalse(res["made_progress"])
        self.assertEqual(res["progress_class"], campaign.ProgressClass.NO_EFFECT.value)

    # -----------------------------------------------------------------------
    # P1-03: Dry-Run Purity (zero mutations, READY packages preserved)
    # -----------------------------------------------------------------------

    def test_p1_03_dry_run_preserves_ready_package_and_does_not_mutate(self) -> None:
        """integrate_packages_core(..., dry_run=True) does not delete READY files."""
        ns = P.producer_namespace(self.root, "saiwiki")
        P.ProducerEpoch.claim(ns)

        # 1. Integrate once
        pkg1 = self._publish_pkg(ns, "saiwiki", "Scope 1", "# Page\n")
        res1 = P.integrate_packages_core([pkg1], self.root, agent="test")
        self.assertTrue(res1["results"][0]["wrote"])

        # 2. Publish another READY package with same content
        pkg2 = self._publish_pkg(ns, "saiwiki", "Scope 2", "# Page\n")
        ready_before, _ = P.StagingGeneration.scan_ready(ns)
        self.assertEqual(len(ready_before), 1)

        # 3. Dry-run integration
        res_dry = P.integrate_packages_core([pkg2], self.root, dry_run=True, agent="test")
        self.assertFalse(res_dry["results"][0]["wrote"])
        self.assertIn(res_dry["results"][0]["code"], ("ALREADY_CURRENT", "NO_EFFECT"))

        # 4. READY package MUST still exist
        ready_after, _ = P.StagingGeneration.scan_ready(ns)
        self.assertEqual(len(ready_after), 1, "Dry-run must not delete READY packages")

    # -----------------------------------------------------------------------
    # P1-04: Dry-Run Plan Matches NO_EFFECT Execution
    # -----------------------------------------------------------------------

    def test_p1_04_dry_run_plan_matches_no_effect_execution(self) -> None:
        """Dry-run plan returns NO_EFFECT for already-current package instead of CREATE_CORE_TICKET."""
        ns = P.producer_namespace(self.root, "saiwiki")
        P.ProducerEpoch.claim(ns)

        # Integrate first package
        pkg1 = self._publish_pkg(ns, "saiwiki", "Scope 1", "# Content\n")
        res1 = P.integrate_packages_core([pkg1], self.root, agent="test")
        self.assertTrue(res1["results"][0]["wrote"])

        # Publish second package with same content
        pkg2 = self._publish_pkg(ns, "saiwiki", "Scope 2", "# Content\n")

        with mock.patch.object(subs, "current_local_role_revision", return_value="sha256:rev1"):
            # Dry run must plan NO_EFFECT
            plan = intent.collect_and_ship_producer(self.root, "saiwiki", dry_run=True)
            self.assertTrue(plan["ok"])
            self.assertEqual(plan["code"], "NO_EFFECT")
            self.assertFalse(plan.get("wrote", True))
            self.assertEqual(plan.get("actions"), [])

            # Real execution must also return NO_EFFECT
            real = intent.collect_and_ship_producer(self.root, "saiwiki", dry_run=False)
            self.assertTrue(real["ok"])
            self.assertEqual(real["code"], "NO_EFFECT")
            self.assertFalse(real.get("wrote", True))

        # Ensure no spurious tickets were created on BOARD
        board_text = (self.root / ".saipen/BOARD.md").read_text()
        self.assertNotIn("T-", board_text)

    # -----------------------------------------------------------------------
    # P0-01 / P1-02 / P1-03: Negative Controls & Strict Verification
    # -----------------------------------------------------------------------

    def test_repro_a_worker_wrote_plus_fictional_op_id_refused(self) -> None:
        """Worker wrote=true + fictional op_id does not certify progress without controller observation."""
        ctrl = campaign.CampaignController(self.root)
        worker_result = {
            "progress_class": "SOURCE_CHANGED",
            "wrote": True,
            "op_id": "fictional",
            "ok": True,
        }
        observation = {
            "before_event": "E-1",
            "after_event": "E-1",
            "before_state": "X",
            "after_state": "X",
            "before_source_head": "a",
            "after_source_head": "a",
            "before_tree": "same",
            "after_tree": "same",
        }
        res = ctrl._verify_progress_evidence(worker_result, observation=observation)
        self.assertFalse(res["made_progress"])
        self.assertEqual(res["progress_class"], campaign.ProgressClass.NO_EFFECT.value)

        # Injected worker must also be refused
        res_injected = ctrl._verify_progress_evidence(
            worker_result, observation=observation, injected_worker=True
        )
        self.assertFalse(res_injected["made_progress"])
        self.assertEqual(res_injected["progress_class"], campaign.ProgressClass.NO_EFFECT.value)

    def test_repro_b_worker_evidence_verified_plus_filenames_refused(self) -> None:
        """Worker evidence_verified=true + evidence_files does not certify progress without controller observation."""
        ctrl = campaign.CampaignController(self.root)
        worker_result = {
            "progress_class": "SEMANTIC_EVIDENCE_ADDED",
            "evidence_verified": True,
            "evidence_files": ["x"],
            "ok": True,
        }
        observation = {
            "before_event": "E-1",
            "after_event": "E-1",
            "before_state": "X",
            "after_state": "X",
            "before_source_head": "a",
            "after_source_head": "a",
            "before_tree": "same",
            "after_tree": "same",
        }
        res = ctrl._verify_progress_evidence(worker_result, observation=observation)
        self.assertFalse(res["made_progress"])
        self.assertEqual(res["progress_class"], campaign.ProgressClass.NO_EFFECT.value)

        # Injected worker must also be refused
        res_injected = ctrl._verify_progress_evidence(
            worker_result, observation=observation, injected_worker=True
        )
        self.assertFalse(res_injected["made_progress"])
        self.assertEqual(res_injected["progress_class"], campaign.ProgressClass.NO_EFFECT.value)

    def test_empty_dry_run_leaves_zero_filesystem_artifacts(self) -> None:
        """integrate_packages_core([], root, dry_run=True) on bare project creates no locks or dirs."""
        bare_project = self.tmp / "bare_project"
        bare_project.mkdir()
        (bare_project / ".saipen").mkdir()
        res = P.integrate_packages_core([], bare_project, dry_run=True)
        self.assertTrue(res.get("serialized"))
        self.assertEqual(res.get("results"), [])
        self.assertFalse((bare_project / ".saipen" / "locks").exists(), "Empty dry run must not create locks dir")

    def test_target_hash_completeness_fails_closed(self) -> None:
        """Incomplete or missing target hashes in verify_output_targets_live_proof must fail closed."""
        ns = P.producer_namespace(self.root, "saiwiki")
        P.ProducerEpoch.claim(ns)
        pkg = self._publish_pkg(ns, "saiwiki", "Incomplete hash test", "# Content\n")

        # 1. Tamper package: clear payload_hashes
        tampered_pkg = P.ProducerPackage(
            producer=pkg.producer,
            role_revision=pkg.role_revision,
            base_source_head=pkg.base_source_head,
            base_source_tree_fingerprint=pkg.base_source_tree_fingerprint,
            base_discovery_model=pkg.base_discovery_model,
            scope=pkg.scope,
            read_set=pkg.read_set,
            write_set=pkg.write_set,
            payload_hashes={},
            payloads={},
            epoch=pkg.epoch,
        )
        ok, diag, _ = P.verify_output_targets_live_proof(self.root, tampered_pkg)
        self.assertFalse(ok)
        self.assertIn("missing authenticated payload hash", diag)

    def test_unrelated_concurrent_mutation_not_attributed_to_read_only_worker(self) -> None:
        """Unrelated concurrent source delta is not attributed to a worker that did not write."""
        ctrl = campaign.CampaignController(self.root)
        worker_result = {"ok": True, "wrote": False}
        observation = {
            "before_source_head": "a",
            "after_source_head": "b",
            "source_delta": True,
        }
        res = ctrl._verify_progress_evidence(worker_result, observation=observation)
        self.assertFalse(res["made_progress"])
        self.assertEqual(res["progress_class"], campaign.ProgressClass.NO_EFFECT.value)

    def test_uncertain_worker_effect_preserved_without_no_effect_mask(self) -> None:
        """An uncertain/unverified effect remains UNKNOWN/UNVERIFIED, not masked as NO_EFFECT."""
        ctrl = campaign.CampaignController(self.root)
        worker_result = {"ok": True, "progress_class": "UNKNOWN", "uncertain": True}
        res = ctrl._verify_progress_evidence(worker_result, observation={})
        self.assertFalse(res["made_progress"])
        self.assertEqual(res["progress_class"], "UNKNOWN")

    # -----------------------------------------------------------------------
    # Canonical Progress Receipt Integrity (P0-01, P0-02, P1-03, P1-04)
    # -----------------------------------------------------------------------

    def test_p0_01_safeid_validator_import_oracle(self) -> None:
        """validate_op_id does not exist in safeid; importing from safeid fails while journal succeeds."""
        with self.assertRaises(ImportError):
            from saipen_engine.safeid import validate_op_id  # type: ignore

        from saipen_engine.journal import validate_op_id
        self.assertTrue(callable(validate_op_id))

    def test_p0_01_genuine_committed_producer_mutation_verified(self) -> None:
        """Genuine newly committed producer integration receipt passes canonical receipt verification."""
        ns = P.producer_namespace(self.root, "saiwiki")
        P.ProducerEpoch.claim(ns)
        pkg = self._publish_pkg(ns, "saiwiki", "Scope A", "# Wiki index\n")
        res = P.integrate_packages_core([pkg], self.root, agent="test")
        self.assertTrue(res["results"][0]["wrote"])
        op_id = res["results"][0]["op_id"]
        self.assertIsNotNone(op_id)

        ctrl = campaign.CampaignController(self.root)
        self.assertTrue(ctrl._verify_canonical_mutation_receipt(op_id))

        worker_res = {
            "ok": True,
            "wrote": True,
            "op_id": op_id,
            "progress_class": campaign.ProgressClass.SOURCE_CHANGED.value,
        }
        observation = {
            "before_event": "E-1",
            "after_event": "E-2",
            "source_delta": True,
        }
        ver = ctrl._verify_progress_evidence(worker_res, observation=observation)
        self.assertTrue(ver["made_progress"])
        self.assertEqual(ver["progress_class"], campaign.ProgressClass.SOURCE_CHANGED.value)

    def test_p0_02_historical_receipt_replay_rejected_by_credited_operations_and_timing(self) -> None:
        """Historical committed op_id cannot be replayed once credited or when attempt starts after creation."""
        ns = P.producer_namespace(self.root, "saiwiki")
        P.ProducerEpoch.claim(ns)
        pkg = self._publish_pkg(ns, "saiwiki", "Scope B", "# Historical\n")
        res = P.integrate_packages_core([pkg], self.root, agent="test")
        op_id = res["results"][0]["op_id"]

        ctrl = campaign.CampaignController(self.root)

        # 1. Credited operations dictionary blocks replay
        credited = {op_id: {"attempt_id": "prev-attempt", "generation": 1}}
        self.assertFalse(ctrl._verify_canonical_mutation_receipt(op_id, credited_operations=credited))
        ver = ctrl._verify_progress_evidence(
            {"ok": True, "wrote": True, "op_id": op_id, "progress_class": campaign.ProgressClass.SOURCE_CHANGED.value},
            observation={"before_event": "E-2", "after_event": "E-3", "source_delta": False},
            credited_operations=credited,
        )
        self.assertFalse(ver["made_progress"])
        self.assertEqual(ver["progress_class"], campaign.ProgressClass.NO_EFFECT.value)

        # 2. Attempt started in the future relative to old receipt is rejected
        future_attempt = {
            "attempt_id": "attempt-future",
            "generation": 5,
            "started_at": "2099-01-01T00:00:00Z",
        }
        self.assertFalse(ctrl._verify_canonical_mutation_receipt(op_id, attempt=future_attempt))

    def test_p1_03_concurrent_source_delta_without_canonical_receipt_reports_unverified_effect(self) -> None:
        """Changed source tree with worker claim wrote=True but unverified receipt reports UNVERIFIED_EFFECT."""
        ctrl = campaign.CampaignController(self.root)
        worker_res = {
            "ok": True,
            "wrote": True,
            "progress_class": campaign.ProgressClass.SOURCE_CHANGED.value,
        }
        observation = {
            "before_event": "E-1",
            "after_event": "E-2",
            "source_delta": True,
        }
        ver = ctrl._verify_progress_evidence(worker_res, observation=observation)
        self.assertFalse(ver["made_progress"])
        self.assertEqual(ver["progress_class"], "UNVERIFIED_EFFECT")

    def test_p1_04_corrupted_ready_package_refuses_revalidation_and_integrate_core(self) -> None:
        """Metadata-only scanned READY package corrupted on disk refuses revalidation and core integration."""
        ns = P.producer_namespace(self.root, "saiwiki")
        P.ProducerEpoch.claim(ns)

        # 1. Integrate valid output
        pkg1 = self._publish_pkg(ns, "saiwiki", "Initial", "# Base doc\n")
        res1 = P.integrate_packages_core([pkg1], self.root, agent="test")
        self.assertTrue(res1["results"][0]["wrote"])

        # 2. Publish second identical package
        pkg2 = self._publish_pkg(ns, "saiwiki", "Duplicate", "# Base doc\n")

        # 3. Load via metadata-only READY scan
        scanned, errors = P.StagingGeneration.scan_ready(ns, materialize_payloads=False)
        self.assertEqual(errors, [])
        self.assertEqual(len(scanned), 1)
        target_pkg = scanned[0]
        self.assertIsNotNone(target_pkg.ready_path)
        self.assertEqual(target_pkg.payloads, {})

        # 4. Corrupt the READY artifact on disk
        target_pkg.ready_path.write_bytes(b"{CORRUPT_JSON_DATA: invalid")

        # 5. Live proof must return False
        ok, diag, _ = P.verify_output_targets_live_proof(self.root, target_pkg)
        self.assertFalse(ok)
        self.assertIn("corrupt", diag.lower())

        # 6. integrate_packages_core must refuse with CORRUPT_READY_PACKAGE and recovery_required=True
        res = P.integrate_packages_core([target_pkg], self.root, agent="test")
        self.assertEqual(len(res["results"]), 1)
        r0 = res["results"][0]
        self.assertEqual(r0["result"], "REFUSED")
        self.assertEqual(r0["code"], "CORRUPT_READY_PACKAGE")
        self.assertTrue(r0["recovery_required"])
        self.assertFalse(r0["wrote"])

        # 7. Corrupt READY artifact remains preserved on disk
        self.assertTrue(target_pkg.ready_path.is_file())
        self.assertEqual(target_pkg.ready_path.read_bytes(), b"{CORRUPT_JSON_DATA: invalid")

    # -----------------------------------------------------------------------
    # SAIHANDOFF Strict Worker-Attempt Provenance & READY Integrity Tests
    # -----------------------------------------------------------------------

    def test_p0_01_repro_unbound_receipt_refused_for_unrelated_attempt(self) -> None:
        """Unbound receipt (missing attempt metadata) refused when verifying against worker attempt."""
        ns = P.producer_namespace(self.root, "saiwiki")
        P.ProducerEpoch.claim(ns)
        pkg = self._publish_pkg(ns, "saiwiki", "Unbound", "# Unbound content\n")
        res = P.integrate_packages_core([pkg], self.root, agent="test")
        op_id = res["results"][0]["op_id"]
        self.assertIsNotNone(op_id)

        ctrl = campaign.CampaignController(self.root)

        # Legacy historical verification without attempt remains True
        self.assertTrue(ctrl._verify_canonical_mutation_receipt(op_id, attempt=None))

        # But verifying against an attempt where receipt has no attribution MUST refuse
        foreign_attempt = {
            "attempt_id": "unrelated-attempt-uuid",
            "campaign_id": "unrelated-campaign",
            "generation": 2,
            "started_at": "2020-01-01T00:00:00Z",
        }
        self.assertFalse(ctrl._verify_canonical_mutation_receipt(op_id, attempt=foreign_attempt))

        ver = ctrl._verify_progress_evidence(
            {"ok": True, "wrote": True, "op_id": op_id, "progress_class": campaign.ProgressClass.SOURCE_CHANGED.value},
            observation={"before_event": "E-1", "after_event": "E-2", "source_delta": True},
            attempt=foreign_attempt,
        )
        self.assertFalse(ver["made_progress"])

    def test_p0_01_attempt_attribution_matrix_and_replay_prevention(self) -> None:
        """Attribution contract: correct attempt accepted; wrong campaign/attempt/gen refused."""
        ns = P.producer_namespace(self.root, "saiwiki")
        P.ProducerEpoch.claim(ns)
        pkg = self._publish_pkg(ns, "saiwiki", "BoundScope", "# Bound content\n")
        att_id = "test-att-001"
        camp_id = "test-camp-001"
        gen = 1
        res = P.integrate_packages_core(
            [pkg],
            self.root,
            agent="test",
            attempt_id=att_id,
            campaign_id=camp_id,
            worker_generation=gen,
        )
        op_id = res["results"][0]["op_id"]
        self.assertIsNotNone(op_id)

        ctrl = campaign.CampaignController(self.root)
        matching_attempt = {
            "attempt_id": att_id,
            "campaign_id": camp_id,
            "generation": gen,
            "started_at": "2020-01-01T00:00:00Z",
        }

        # 1. Matching attempt accepted
        self.assertTrue(ctrl._verify_canonical_mutation_receipt(op_id, attempt=matching_attempt))

        # 2. Wrong campaign refused
        wrong_camp = dict(matching_attempt, campaign_id="other-camp")
        self.assertFalse(ctrl._verify_canonical_mutation_receipt(op_id, attempt=wrong_camp))

        # 3. Wrong attempt refused
        wrong_att = dict(matching_attempt, attempt_id="other-att")
        self.assertFalse(ctrl._verify_canonical_mutation_receipt(op_id, attempt=wrong_att))

        # 4. Wrong generation refused
        wrong_gen = dict(matching_attempt, generation=2)
        self.assertFalse(ctrl._verify_canonical_mutation_receipt(op_id, attempt=wrong_gen))

        # 5. Future started_at refused
        future_start = dict(matching_attempt, started_at="2099-01-01T00:00:00Z")
        self.assertFalse(ctrl._verify_canonical_mutation_receipt(op_id, attempt=future_start))

        # 6. Credited replay refused
        self.assertFalse(
            ctrl._verify_canonical_mutation_receipt(
                op_id, attempt=matching_attempt, credited_operations={op_id: {}}
            )
        )

    def test_p0_02_repro_unattributed_source_delta_reports_unverified_effect(self) -> None:
        """Worker with no hint + source delta without attribution reports UNVERIFIED_EFFECT."""
        ctrl = campaign.CampaignController(self.root)
        worker_result = {"ok": True}
        observation = {
            "before_event": "E-1",
            "after_event": "E-1",
            "source_delta": True,
        }
        res = ctrl._verify_progress_evidence(worker_result, observation=observation)
        self.assertFalse(res["made_progress"])
        self.assertEqual(res["progress_class"], "UNVERIFIED_EFFECT")

    def test_p0_03_repro_semantic_evidence_list_refused_without_independent_proof(self) -> None:
        """Caller unverified path list without independent receipt does not certify progress."""
        ctrl = campaign.CampaignController(self.root)
        worker_result = {
            "ok": True,
            "progress_class": "SEMANTIC_EVIDENCE_ADDED",
        }
        observation = {
            "before_event": "E-1",
            "after_event": "E-1",
            "new_evidence_files": ["unverified-file"],
        }
        res = ctrl._verify_progress_evidence(worker_result, observation=observation)
        self.assertFalse(res["made_progress"])
        self.assertEqual(res["progress_class"], "UNVERIFIED_EFFECT")

    def test_p0_03_authenticated_evidence_delta_receipt_verified(self) -> None:
        """Independently verified evidence delta receipt certifies SEMANTIC_EVIDENCE_ADDED."""
        import hashlib
        ctrl = campaign.CampaignController(self.root)
        ev_rel = ".saipen/evidence/audit_report.md"
        target = wf(self.root, ev_rel, b"# Audit Report\n")
        ev_hash = hashlib.sha256(target.read_bytes()).hexdigest()
        op_id = "op-sem-00000001"
        op_dir = self.root / ".saipen" / "recovery" / "ops" / op_id
        op_dir.mkdir(parents=True, exist_ok=True)
        rec = {
            "op_id": op_id,
            "status": "COMMITTED",
            "operation": "semantic_evidence",
            "semantic_payload_hash": "sha256:0",
            "created_at": "2026-11-07T10:00:00Z",
            "agent": "test",
            "project_identity": "test-project",
            "project_lineage": "lineage-b512942bac884a8691f6c98afcd6ddb9",
            "progress_index": 0,
            "targets": [{
                "path": ev_rel,
                "role": "generic",
                "action": "write",
                "applied": True,
                "before_hash": "",
                "after_hash": ev_hash,
            }],
            "receipt_metadata": {
                "attempt_id": "att-sem-1",
                "campaign_id": "camp-sem-1",
                "worker_generation": 1,
            },
        }
        (op_dir / "operation.json").write_text(json.dumps(rec), encoding="utf-8")
        receipt = {
            "verifier_id": "verifier-auditor",
            "verifier_result": "PASS",
            "op_id": op_id,
            "attempt_id": "att-sem-1",
            "campaign_id": "camp-sem-1",
            "worker_generation": 1,
            "project_lineage": "lineage-b512942bac884a8691f6c98afcd6ddb9",
            "evidence_files": [{
                "path": ev_rel,
                "after_hash": ev_hash,
                "created": True,
            }],
        }
        payload = {k: v for k, v in receipt.items() if k != "receipt_digest"}
        receipt["receipt_digest"] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        observation = {
            "before_event": "E-1",
            "after_event": "E-2",
            "evidence_delta_receipt": receipt,
        }
        attempt = {
            "attempt_id": "att-sem-1",
            "campaign_id": "camp-sem-1",
            "generation": 1,
            "started_at": "2000-01-01T00:00:00Z",
        }
        res = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "SEMANTIC_EVIDENCE_ADDED"},
            observation=observation,
            attempt=attempt,
        )
        self.assertTrue(res["made_progress"])
        self.assertEqual(res["progress_class"], campaign.ProgressClass.SEMANTIC_EVIDENCE_ADDED.value)

    def test_required_regressions_contract_closure(self) -> None:
        """Verify all progress verifier contract closure rules (P0-03/Finding 1)."""
        import hashlib
        ctrl = campaign.CampaignController(self.root)
        attempt = {
            "attempt_id": "att-reg-1",
            "campaign_id": "camp-reg-1",
            "generation": 1,
            "started_at": "2026-11-07T09:00:00Z",
        }
        ev_rel = ".saipen/evidence/test_reg.md"
        target_reg = wf(self.root, ev_rel, b"# Reg\n")
        ev_hash = hashlib.sha256(target_reg.read_bytes()).hexdigest()

        # 1. Unattributed source_delta_verified=True cannot prove progress (Rule 14)
        res1 = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "SOURCE_CHANGED"},
            observation={"before_event": "E-1", "after_event": "E-2", "source_delta_verified": True},
        )
        self.assertFalse(res1["made_progress"])
        self.assertEqual(res1["progress_class"], "UNVERIFIED_EFFECT")

        # 2. Bare evidence_delta=True cannot prove semantic progress (Rule 4)
        res2 = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "SEMANTIC_EVIDENCE_ADDED"},
            observation={"before_event": "E-1", "after_event": "E-2", "evidence_delta": True},
        )
        self.assertFalse(res2["made_progress"])
        self.assertEqual(res2["progress_class"], "UNVERIFIED_EFFECT")

        # 3. Existing unchanged evidence file cannot prove a new delta (Rule 3)
        rec3 = {
            "verifier_id": "verifier-auditor",
            "verifier_result": "PASS",
            "authenticated": True,
            "attempt_id": "att-reg-1",
            "campaign_id": "camp-reg-1",
            "worker_generation": 1,
            "project_lineage": "lineage-b512942bac884a8691f6c98afcd6ddb9",
            "evidence_files": [{
                "path": ev_rel,
                "before_hash": ev_hash,
                "after_hash": ev_hash,
            }],
        }
        rec3["receipt_digest"] = hashlib.sha256(json.dumps({k: v for k, v in rec3.items() if k != "receipt_digest"}, sort_keys=True).encode()).hexdigest()
        res3 = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "SEMANTIC_EVIDENCE_ADDED"},
            observation={"before_event": "E-1", "after_event": "E-2", "evidence_delta_receipt": rec3},
            attempt=attempt,
        )
        self.assertFalse(res3["made_progress"])
        self.assertEqual(res3["progress_class"], "UNVERIFIED_EFFECT")

        # 4. Fabricated verifier_id/PASS dictionary without authenticated origin is rejected (Rule 1 & Rule 6)
        rec4 = {
            "verifier_id": "fabricated",
            "verifier_result": "PASS",
            "attempt_id": "att-reg-1",
            "campaign_id": "camp-reg-1",
            "worker_generation": 1,
            "evidence_files": [{"path": ev_rel, "after_hash": ev_hash, "created": True}],
        }
        rec4["receipt_digest"] = hashlib.sha256(json.dumps(rec4, sort_keys=True).encode()).hexdigest()
        res4 = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "SEMANTIC_EVIDENCE_ADDED"},
            observation={"before_event": "E-1", "after_event": "E-2", "evidence_delta_receipt": rec4},
            attempt=attempt,
        )
        self.assertFalse(res4["made_progress"])
        self.assertEqual(res4["progress_class"], "UNVERIFIED_EFFECT")

        # 5. Wrong project lineage is rejected (Rule 5)
        rec5 = {
            "verifier_id": "verifier-auditor",
            "verifier_result": "PASS",
            "authenticated": True,
            "attempt_id": "att-reg-1",
            "campaign_id": "camp-reg-1",
            "worker_generation": 1,
            "project_lineage": "lineage-WRONG000000000000000000000000",
            "evidence_files": [{"path": ev_rel, "after_hash": ev_hash, "created": True}],
        }
        rec5["receipt_digest"] = hashlib.sha256(json.dumps({k: v for k, v in rec5.items() if k != "receipt_digest"}, sort_keys=True).encode()).hexdigest()
        res5 = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "SEMANTIC_EVIDENCE_ADDED"},
            observation={"before_event": "E-1", "after_event": "E-2", "evidence_delta_receipt": rec5},
            attempt=attempt,
        )
        self.assertFalse(res5["made_progress"])

        # 6. Pre-existing file with created=true refused when created before started_at (Rule 2)
        # target_reg was created before attempt started_at ("2026-11-07T09:00:00Z" vs future/past)
        attempt_future = {
            "attempt_id": "att-reg-1",
            "campaign_id": "camp-reg-1",
            "generation": 1,
            "started_at": "2099-01-01T00:00:00Z",
        }
        rec_old = {
            "verifier_id": "verifier-auditor",
            "verifier_result": "PASS",
            "authenticated": True,
            "attempt_id": "att-reg-1",
            "campaign_id": "camp-reg-1",
            "worker_generation": 1,
            "project_lineage": "lineage-b512942bac884a8691f6c98afcd6ddb9",
            "evidence_files": [{"path": ev_rel, "after_hash": ev_hash, "created": True}],
        }
        rec_old["receipt_digest"] = hashlib.sha256(json.dumps({k: v for k, v in rec_old.items() if k != "receipt_digest"}, sort_keys=True).encode()).hexdigest()
        res_old = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "SEMANTIC_EVIDENCE_ADDED"},
            observation={"before_event": "E-1", "after_event": "E-2", "evidence_delta_receipt": rec_old},
            attempt=attempt_future,
        )
        self.assertFalse(res_old["made_progress"])
        self.assertEqual(res_old["progress_class"], "UNVERIFIED_EFFECT")

        # 7. Historical receipts are not credited again (Rule 7: anti-replay)
        rec7 = {
            "verifier_id": "verifier-auditor",
            "verifier_result": "PASS",
            "authenticated": True,
            "attempt_id": "att-reg-1",
            "campaign_id": "camp-reg-1",
            "worker_generation": 1,
            "receipt_id": "rec-already-credited",
            "project_lineage": "lineage-b512942bac884a8691f6c98afcd6ddb9",
            "evidence_files": [{"path": ev_rel, "after_hash": ev_hash, "created": True}],
        }
        rec7["receipt_digest"] = hashlib.sha256(json.dumps({k: v for k, v in rec7.items() if k != "receipt_digest"}, sort_keys=True).encode()).hexdigest()
        res7 = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "SEMANTIC_EVIDENCE_ADDED"},
            observation={"before_event": "E-1", "after_event": "E-2", "evidence_delta_receipt": rec7},
            attempt=attempt,
            credited_operations={"rec-already-credited": True},
        )
        self.assertFalse(res7["made_progress"])

        # 8. Correct independently authenticated new evidence accepted (Rule 8)
        attempt_past = {
            "attempt_id": "att-reg-1",
            "campaign_id": "camp-reg-1",
            "generation": 1,
            "started_at": "2000-01-01T00:00:00Z",
        }
        op_id_8 = "op-reg-00000008"
        op_dir_8 = self.root / ".saipen" / "recovery" / "ops" / op_id_8
        op_dir_8.mkdir(parents=True, exist_ok=True)
        rec_j8 = {
            "op_id": op_id_8,
            "status": "COMMITTED",
            "operation": "semantic_evidence",
            "semantic_payload_hash": "sha256:0",
            "created_at": "2026-11-07T10:00:00Z",
            "agent": "test",
            "project_identity": "test-project",
            "project_lineage": "lineage-b512942bac884a8691f6c98afcd6ddb9",
            "progress_index": 0,
            "targets": [{
                "path": ev_rel,
                "role": "generic",
                "action": "write",
                "applied": True,
                "before_hash": "",
                "after_hash": ev_hash,
            }],
            "receipt_metadata": {
                "attempt_id": "att-reg-1",
                "campaign_id": "camp-reg-1",
                "worker_generation": 1,
            },
        }
        (op_dir_8 / "operation.json").write_text(json.dumps(rec_j8), encoding="utf-8")
        rec8 = {
            "verifier_id": "verifier-auditor",
            "verifier_result": "PASS",
            "op_id": op_id_8,
            "attempt_id": "att-reg-1",
            "campaign_id": "camp-reg-1",
            "worker_generation": 1,
            "project_lineage": "lineage-b512942bac884a8691f6c98afcd6ddb9",
            "evidence_files": [{"path": ev_rel, "after_hash": ev_hash, "created": True}],
        }
        rec8["receipt_digest"] = hashlib.sha256(json.dumps({k: v for k, v in rec8.items() if k != "receipt_digest"}, sort_keys=True).encode()).hexdigest()
        res8 = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "SEMANTIC_EVIDENCE_ADDED"},
            observation={"before_event": "E-1", "after_event": "E-2", "evidence_delta_receipt": rec8},
            attempt=attempt_past,
        )
        self.assertTrue(res8["made_progress"])
        self.assertEqual(res8["progress_class"], campaign.ProgressClass.SEMANTIC_EVIDENCE_ADDED.value)

        # 10. Valid canonical regression pair accepted (Rule 10 & P0-01)
        reg_rel = ".saipen/evidence/regression/valid_reg_10.json"
        wf(self.root, reg_rel, json.dumps({
            "schema": 1,
            "command": ["python", "-m", "unittest"],
            "verifier": "v_hash_exact_1",
            "test_case": "test_bug_fix",
            "subject_before": "sub_pre_fix_1",
            "subject_after": "sub_post_fix_2",
            "before": {"result": "FAIL", "verifier": "v_hash_exact_1", "subject": "sub_pre_fix_1"},
            "after": {"result": "PASS", "verifier": "v_hash_exact_1", "subject": "sub_post_fix_2"},
            "attempt_id": "att-reg-1",
            "campaign_id": "camp-reg-1",
            "worker_generation": 1,
            "project_lineage": "lineage-b512942bac884a8691f6c98afcd6ddb9",
        }))
        valid_reg_pair = {
            "attempt_id": "att-reg-1",
            "campaign_id": "camp-reg-1",
            "worker_generation": 1,
            "project_lineage": "lineage-b512942bac884a8691f6c98afcd6ddb9",
            "receipt_reference": reg_rel,
            "before": {"result": "FAIL", "verifier": "v_hash_exact_1", "subject": "sub_pre_fix_1"},
            "after": {"result": "PASS", "verifier": "v_hash_exact_1", "subject": "sub_post_fix_2"},
        }
        res10 = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "REGRESSION_FIXED"},
            observation={"regression_pair": valid_reg_pair},
            attempt=attempt,
        )
        self.assertTrue(res10["made_progress"])
        self.assertEqual(res10["progress_class"], campaign.ProgressClass.REGRESSION_FIXED.value)

        # 11. Forged regression pair refused as productive progress (Rule 11)
        # 11a: verifier changed
        forged_pair_v = {
            "attempt_id": "att-reg-1",
            "campaign_id": "camp-reg-1",
            "before": {"result": "FAIL", "verifier": "v_hash_old", "subject": "sub_1"},
            "after": {"result": "PASS", "verifier": "v_hash_different", "subject": "sub_2"},
        }
        res11a = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "REGRESSION_FIXED"},
            observation={"regression_pair": forged_pair_v},
            attempt=attempt,
        )
        self.assertFalse(res11a["made_progress"])
        self.assertEqual(res11a["progress_class"], "UNVERIFIED_EFFECT")

        # 11b: subject unchanged
        forged_pair_s = {
            "attempt_id": "att-reg-1",
            "campaign_id": "camp-reg-1",
            "before": {"result": "FAIL", "verifier": "v_same", "subject": "sub_same"},
            "after": {"result": "PASS", "verifier": "v_same", "subject": "sub_same"},
        }
        res11b = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "REGRESSION_FIXED"},
            observation={"regression_pair": forged_pair_s},
            attempt=attempt,
        )
        self.assertFalse(res11b["made_progress"])
        self.assertEqual(res11b["progress_class"], "UNVERIFIED_EFFECT")

        # 12. Unauthenticated gate PASS and score increase refused (Rule 12 & P1-03)
        fake_gate = {
            "verifier_result": "PASS",
            "before_score": 0,
            "after_score": 100,
            "attempt_id": "att-reg-1",
        }
        res12 = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "TEST_GATE_IMPROVED"},
            observation={"gate_receipt": fake_gate},
            attempt=attempt,
        )
        self.assertFalse(res12["made_progress"])
        self.assertEqual(res12["progress_class"], "UNVERIFIED_EFFECT")

        # 13. Genuine gate improvement accepted only once (Rule 13)
        suite_rel = ".saipen/evidence/suite/gate_suite_1.json"
        wf(self.root, suite_rel, json.dumps({
            "schema": 1,
            "kind": "saipen-suite-record",
            "command": ["python", "-m", "unittest"],
            "command_sha256": "gate-verifier-auth",
            "verifier_id": "gate-verifier-auth",
            "verdict": "PASS",
            "exit_code": 0,
            "totals": {"runner": "unittest", "ran": 25, "passed": 25, "red": 0, "skipped": 0},
            "attempt_id": "att-reg-1",
            "campaign_id": "camp-reg-1",
            "worker_generation": 1,
            "project_lineage": "lineage-b512942bac884a8691f6c98afcd6ddb9",
        }))
        real_gate = {
            "verifier_id": "gate-verifier-auth",
            "verifier_result": "PASS",
            "receipt_reference": suite_rel,
            "before_score": 10,
            "after_score": 25,
            "gate_id": "gate-suite-1",
            "attempt_id": "att-reg-1",
            "campaign_id": "camp-reg-1",
            "worker_generation": 1,
            "project_lineage": "lineage-b512942bac884a8691f6c98afcd6ddb9",
        }
        res13_first = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "TEST_GATE_IMPROVED"},
            observation={"gate_receipt": real_gate},
            attempt=attempt,
        )
        self.assertTrue(res13_first["made_progress"])
        self.assertEqual(res13_first["progress_class"], campaign.ProgressClass.TEST_GATE_IMPROVED.value)

        # Replay of the same gate_id must be refused
        res13_replay = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "TEST_GATE_IMPROVED"},
            observation={"gate_receipt": real_gate},
            attempt=attempt,
            credited_operations={"gate-suite-1": True},
        )
        self.assertFalse(res13_replay["made_progress"])
        self.assertEqual(res13_replay["progress_class"], "UNVERIFIED_EFFECT")

        # 16. Synthetic operator approval or host dispatch receipts refused (Rule 16)
        res16 = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "AUTHORITY_RECONCILED"},
            observation={"authority_reconciled": True},
            attempt=attempt,
        )
        self.assertFalse(res16["made_progress"])
        self.assertEqual(res16["progress_class"], "UNVERIFIED_EFFECT")

    def test_p0_04_repro_deleted_ready_artifact_refused_before_write(self) -> None:
        """Deleted READY artifact refuses verify_output_targets and integrate_packages_core."""
        ns = P.producer_namespace(self.root, "saiwiki")
        P.ProducerEpoch.claim(ns)
        pkg = self._publish_pkg(ns, "saiwiki", "DeleteScope", "# Content to delete\n")
        self.assertIsNotNone(pkg.ready_path)
        self.assertTrue(pkg.ready_path.is_file())

        # Materialize payload into in-memory object
        pkg.materialize_payload()

        # Delete the original READY artifact
        pkg.ready_path.unlink()
        self.assertFalse(pkg.ready_path.exists())

        # verify_output_targets_live_proof must return False
        ok, diag, _ = P.verify_output_targets_live_proof(self.root, pkg)
        self.assertFalse(ok)
        self.assertIn("missing", diag.lower())

        # integrate_packages_core must refuse with READY_MISSING and wrote=False
        res = P.integrate_packages_core([pkg], self.root, agent="test")
        self.assertEqual(len(res["results"]), 1)
        r0 = res["results"][0]
        self.assertEqual(r0["result"], "REFUSED")
        self.assertEqual(r0["code"], "READY_MISSING")
        self.assertFalse(r0["wrote"])

    def test_p1_05_repro_empty_payload_hashes_refuses_authenticated_proof(self) -> None:
        """In-memory package with empty payload_hashes refuses live proof as unauthenticated."""
        doc_path = self.root / "kitchen/wiki/index.md"
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        doc_path.write_bytes(b"# Existing doc\n")

        pkg = P.ProducerPackage(
            producer="saiwiki",
            role_revision="rev1",
            base_source_head="head1",
            base_source_tree_fingerprint="fp1",
            base_discovery_model="model1",
            scope="Scope1",
            write_set={"kitchen/wiki/index.md": "sha256:..."},
            payloads={"kitchen/wiki/index.md": b"# Existing doc\n"},
        )
        object.__setattr__(pkg, "payload_hashes", {})
        ok, diag, _ = P.verify_output_targets_live_proof(self.root, pkg)
        self.assertFalse(ok)
        self.assertIn("missing authenticated payload hashes", diag)

    def test_p0_06_foreign_receipt_does_not_reset_no_progress_count(self) -> None:
        """Foreign COMMITTED receipt created during attempt window does not credit or reset counter."""
        ctrl = campaign.CampaignController(self.root)
        # Register a foreign receipt with another attempt_id
        ns = P.producer_namespace(self.root, "saiwiki")
        P.ProducerEpoch.claim(ns)
        pkg = self._publish_pkg(ns, "saiwiki", "ForeignScope", "# Foreign content\n")
        res = P.integrate_packages_core(
            [pkg],
            self.root,
            agent="test",
            attempt_id="foreign-worker-attempt",
            campaign_id="camp-1",
            worker_generation=1,
        )
        op_id = res["results"][0]["op_id"]

        current_attempt = {
            "attempt_id": "current-worker-attempt",
            "campaign_id": "camp-1",
            "generation": 1,
            "started_at": "2020-01-01T00:00:00Z",
        }

        # The receipt belongs to foreign-worker-attempt, not current-worker-attempt
        ver = ctrl._verify_progress_evidence(
            {"ok": True, "wrote": True, "op_id": op_id, "progress_class": campaign.ProgressClass.SOURCE_CHANGED.value},
            observation={"before_event": "E-1", "after_event": "E-2", "source_delta": True},
            attempt=current_attempt,
        )
        self.assertFalse(ver["made_progress"])
        self.assertEqual(ver["progress_class"], "UNVERIFIED_EFFECT")

    def test_hostile_probes_h1_through_h5(self) -> None:
        """Formal adversarial test suite for probes H1 through H5."""
        ctrl = campaign.CampaignController(self.root)
        attempt = {
            "attempt_id": "att-hostile-1",
            "campaign_id": "camp-hostile-1",
            "generation": 1,
            "started_at": "2026-11-07T12:00:00Z",
        }

        # H1: TEST_GATE_IMPROVED with fictitious verifier, authenticated=True, no attempt
        h1_gate = {
            "verifier_id": "fictitious_verifier",
            "verifier_result": "PASS",
            "authenticated": True,
            "before_score": 0,
            "after_score": 100,
        }
        res_h1 = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "TEST_GATE_IMPROVED"},
            observation={"gate_receipt": h1_gate},
            attempt=None,
        )
        self.assertFalse(res_h1["made_progress"])
        self.assertEqual(res_h1["progress_class"], "UNVERIFIED_EFFECT")

        # H2: Same gate with aliased gate_id passes declared ID check but fails canonical effect proof
        proof_id = "gate_improvement:fictitious_verifier:0.0:100.0"
        res_h2 = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "TEST_GATE_IMPROVED"},
            observation={"gate_receipt": dict(h1_gate, gate_id="new_aliased_gate_id")},
            attempt=attempt,
            credited_operations={proof_id: True},
        )
        self.assertFalse(res_h2["made_progress"])
        self.assertEqual(res_h2["progress_class"], "UNVERIFIED_EFFECT")

        # H3: REGRESSION_FIXED with invented FAIL/PASS pair without authentic execution record on disk
        h3_pair = {
            "before": {"result": "FAIL", "verifier": "v_fake", "subject": "sub_1"},
            "after": {"result": "PASS", "verifier": "v_fake", "subject": "sub_2"},
        }
        res_h3 = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "REGRESSION_FIXED"},
            observation={"regression_pair": h3_pair},
            attempt=attempt,
        )
        self.assertFalse(res_h3["made_progress"])
        self.assertEqual(res_h3["progress_class"], "UNVERIFIED_EFFECT")

        # H4: SEMANTIC_EVIDENCE_ADDED with self-created evidence file, authenticated=True, no journal op_id
        ev_file = self.root / ".saipen" / "evidence" / "hostile_ev.txt"
        ev_file.parent.mkdir(parents=True, exist_ok=True)
        ev_file.write_text("hostile evidence", encoding="utf-8")
        ev_hash = hashlib.sha256(ev_file.read_bytes()).hexdigest()
        h4_rec = {
            "verifier_id": "fake_verifier",
            "verifier_result": "PASS",
            "authenticated": True,
            "attempt_id": "att-hostile-1",
            "campaign_id": "camp-hostile-1",
            "worker_generation": 1,
            "evidence_files": [{"path": ".saipen/evidence/hostile_ev.txt", "after_hash": ev_hash, "created": True}],
        }
        h4_payload = {k: v for k, v in h4_rec.items() if k != "receipt_digest"}
        h4_rec["receipt_digest"] = hashlib.sha256(json.dumps(h4_payload, sort_keys=True).encode()).hexdigest()
        res_h4 = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "SEMANTIC_EVIDENCE_ADDED"},
            observation={"evidence_delta_receipt": h4_rec},
            attempt=attempt,
        )
        self.assertFalse(res_h4["made_progress"])
        self.assertEqual(res_h4["progress_class"], "UNVERIFIED_EFFECT")

        # H5: Self-claimed op_id not committed in canonical journal
        h5_rec = dict(h4_rec, op_id="nonexistent_op_99999999")
        h5_payload = {k: v for k, v in h5_rec.items() if k != "receipt_digest"}
        h5_rec["receipt_digest"] = hashlib.sha256(json.dumps(h5_payload, sort_keys=True).encode()).hexdigest()
        res_h5 = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "SEMANTIC_EVIDENCE_ADDED"},
            observation={"evidence_delta_receipt": h5_rec},
            attempt=attempt,
        )
        self.assertFalse(res_h5["made_progress"])
        self.assertEqual(res_h5["progress_class"], "UNVERIFIED_EFFECT")

    def test_hostile_numerical_score_and_delta_manipulation(self) -> None:
        """Adversarial testing of score edge cases (NaN, Inf, negative, non-positive delta)."""
        ctrl = campaign.CampaignController(self.root)
        attempt = {
            "attempt_id": "att-score-1",
            "campaign_id": "camp-score-1",
            "generation": 1,
            "started_at": "2026-11-07T12:00:00Z",
        }

        bad_scores = [
            (float("nan"), 100.0),
            (0.0, float("nan")),
            (float("inf"), 100.0),
            (0.0, float("inf")),
            (-10.0, -5.0),
            (0.0, -1.0),
            (50.0, 50.0),  # zero delta
            (80.0, 70.0),  # negative delta
        ]

        for b, a in bad_scores:
            gate_rec = {
                "verifier_id": "suite_verifier",
                "verifier_result": "PASS",
                "before_score": b,
                "after_score": a,
                "attempt_id": "att-score-1",
                "campaign_id": "camp-score-1",
                "worker_generation": 1,
            }
            res = ctrl._verify_progress_evidence(
                {"ok": True, "progress_class": "TEST_GATE_IMPROVED"},
                observation={"gate_receipt": gate_rec},
                attempt=attempt,
            )
            self.assertFalse(res["made_progress"], f"Failed to reject invalid scores: before={b}, after={a}")
            self.assertEqual(res["progress_class"], "UNVERIFIED_EFFECT")

    def test_hostile_regression_manipulations(self) -> None:
        """Adversarial testing of regression pairs (identical subjects, non-red, non-green, missing verifier)."""
        ctrl = campaign.CampaignController(self.root)
        attempt = {
            "attempt_id": "att-reg-test",
            "campaign_id": "camp-reg-test",
            "generation": 1,
            "started_at": "2026-11-07T12:00:00Z",
        }

        # 1. Identical before and after subjects (no defect reproduction distinction)
        pair_same_subject = {
            "before": {"result": "FAIL", "verifier": "v_hash", "subject": "same_sub"},
            "after": {"result": "PASS", "verifier": "v_hash", "subject": "same_sub"},
        }
        res1 = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "REGRESSION_FIXED"},
            observation={"regression_pair": pair_same_subject},
            attempt=attempt,
        )
        self.assertFalse(res1["made_progress"])

        # 2. Before is not FAIL (PASS -> PASS is not a bug fix)
        pair_pass_pass = {
            "before": {"result": "PASS", "verifier": "v_hash", "subject": "sub_pre"},
            "after": {"result": "PASS", "verifier": "v_hash", "subject": "sub_post"},
        }
        res2 = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "REGRESSION_FIXED"},
            observation={"regression_pair": pair_pass_pass},
            attempt=attempt,
        )
        self.assertFalse(res2["made_progress"])

        # 3. After is not PASS (FAIL -> FAIL is not fixed)
        pair_fail_fail = {
            "before": {"result": "FAIL", "verifier": "v_hash", "subject": "sub_pre"},
            "after": {"result": "FAIL", "verifier": "v_hash", "subject": "sub_post"},
        }
        res3 = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "REGRESSION_FIXED"},
            observation={"regression_pair": pair_fail_fail},
            attempt=attempt,
        )
        self.assertFalse(res3["made_progress"])

        # 4. Verifiers do not match
        pair_mismatched_v = {
            "before": {"result": "FAIL", "verifier": "v_hash_1", "subject": "sub_pre"},
            "after": {"result": "PASS", "verifier": "v_hash_2", "subject": "sub_post"},
        }
        res4 = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "REGRESSION_FIXED"},
            observation={"regression_pair": pair_mismatched_v},
            attempt=attempt,
        )
        self.assertFalse(res4["made_progress"])

    def test_restart_replay_resistance(self) -> None:
        """Verify that proof identities in credited_operations survive across restart and prevent replay."""
        ctrl = campaign.CampaignController(self.root)
        attempt_2 = {
            "attempt_id": "att-session-2",
            "campaign_id": "camp-session-1",
            "generation": 2,
            "started_at": "2026-11-07T13:00:00Z",
        }

        # Simulated state credited operations dictionary
        credited = {
            "gate_improvement:suite_main:10.0:20.0": True,
            "regression_fix:v_main:sub_a:sub_b": True,
            "evidence_delta:414de8418ffcc844": True,
        }

        # Replay gate in session 2 under new envelope
        res_gate = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "TEST_GATE_IMPROVED"},
            observation={
                "gate_receipt": {
                    "verifier_id": "suite_main",
                    "verifier_result": "PASS",
                    "before_score": 10.0,
                    "after_score": 20.0,
                    "attempt_id": "att-session-2",
                    "campaign_id": "camp-session-1",
                    "worker_generation": 2,
                }
            },
            attempt=attempt_2,
            credited_operations=credited,
        )
        self.assertFalse(res_gate["made_progress"])

        # Replay regression in session 2 under new envelope
        res_reg = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "REGRESSION_FIXED"},
            observation={
                "regression_pair": {
                    "before": {"result": "FAIL", "verifier": "v_main", "subject": "sub_a"},
                    "after": {"result": "PASS", "verifier": "v_main", "subject": "sub_b"},
                }
            },
            attempt=attempt_2,
            credited_operations=credited,
        )
        self.assertFalse(res_reg["made_progress"])

    def test_semantic_snapshot_fidelity_and_noop_detection(self) -> None:
        """Verify snapshot semantic payload fingerprinting and comparison fidelity."""
        from saipen_engine import audit_manifest
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            (p / ".saipen").mkdir()
            (p / ".saipen" / "STATE.md").write_text("# State\n", encoding="utf-8")

            # Same bytes -> identical hash
            fp1 = audit_manifest.compute_semantic_snapshot_fingerprint(p, include_source=False)
            fp2 = audit_manifest.compute_semantic_snapshot_fingerprint(p, include_source=False)
            self.assertEqual(fp1["semantic_payload_hash"], fp2["semantic_payload_hash"])

            # Clean tree comparison -> UNCHANGED_SOURCE_SNAPSHOT
            cmp_clean = audit_manifest.compare_snapshot_payloads(fp1, fp2, live_source_changed=False)
            self.assertTrue(cmp_clean["ok"])
            self.assertEqual(cmp_clean["status"], "UNCHANGED_SOURCE_SNAPSHOT")
            self.assertTrue(cmp_clean["identical"])

            # Modified tree comparison with identical export hash -> EXPORT_FIDELITY_FAILURE
            cmp_dirty = audit_manifest.compare_snapshot_payloads(fp1, fp2, live_source_changed=True)
            self.assertFalse(cmp_dirty["ok"])
            self.assertEqual(cmp_dirty["status"], "EXPORT_FIDELITY_FAILURE")
            self.assertTrue(cmp_dirty["identical"])

            # Real change in payload -> PAYLOAD_CHANGED
            (p / ".saipen" / "STATE.md").write_text("# State Modified\n", encoding="utf-8")
            fp3 = audit_manifest.compute_semantic_snapshot_fingerprint(p, include_source=False)
            self.assertNotEqual(fp1["semantic_payload_hash"], fp3["semantic_payload_hash"])
            cmp_diff = audit_manifest.compare_snapshot_payloads(fp1, fp3, live_source_changed=True)
            self.assertTrue(cmp_diff["ok"])
            self.assertEqual(cmp_diff["status"], "PAYLOAD_CHANGED")
            self.assertFalse(cmp_diff["identical"])

    def test_r1_and_g6_missing_loader_fail_closed_and_no_worker_crash(self) -> None:
        """R1 & G6: Missing or invalid receipt fails closed without unhandled AttributeError/crash."""
        ctrl = campaign.CampaignController(self.root)
        self.assertTrue(hasattr(ctrl, "_load_and_verify_receipt_reference"))

        # 1. Missing file reference fails closed
        ok, data, err = ctrl._load_and_verify_receipt_reference("nonexistent/receipt.json", ("saipen-gate-record",))
        self.assertFalse(ok)
        self.assertIsNone(data)
        self.assertTrue(err.startswith("RECEIPT_LOAD_ERROR") or err in ("INVALID_REFERENCE", "PATH_NOT_CONTAINED"))

        # 2. Worker outcome with nonexistent reference produces UNVERIFIED_EFFECT, never crash
        attempt = {
            "attempt_id": "att-r1-crash",
            "campaign_id": "camp-r1",
            "generation": 1,
            "started_at": "2026-11-07T00:00:00Z",
        }
        res = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "TEST_GATE_IMPROVED"},
            observation={"gate_receipt": {"receipt_reference": "nonexistent/rec.json"}},
            attempt=attempt,
        )
        self.assertFalse(res["made_progress"])
        self.assertEqual(res["progress_class"], "UNVERIFIED_EFFECT")

    def test_r2_and_h6_fake_gate_text_file_rejected(self) -> None:
        """R2 & H6: Fabricated gate with unrelated regular text file gets UNVERIFIED_EFFECT."""
        ctrl = campaign.CampaignController(self.root)
        fake_text_path = "src/wiki.md"
        attempt = {
            "attempt_id": "att-h6-fake",
            "campaign_id": "camp-h6",
            "generation": 1,
            "started_at": "2026-11-07T00:00:00Z",
        }
        res = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "TEST_GATE_IMPROVED"},
            observation={
                "gate_receipt": {
                    "receipt_reference": fake_text_path,
                    "before_score": 0,
                    "after_score": 100,
                    "verifier_result": "PASS",
                }
            },
            attempt=attempt,
        )
        self.assertFalse(res["made_progress"])
        self.assertEqual(res["progress_class"], "UNVERIFIED_EFFECT")

    def test_r3_and_h7_fake_regression_text_file_rejected(self) -> None:
        """R3 & H7: Fabricated regression with unrelated regular text file gets UNVERIFIED_EFFECT."""
        ctrl = campaign.CampaignController(self.root)
        fake_text_path = "src/wiki.md"
        attempt = {
            "attempt_id": "att-h7-fake",
            "campaign_id": "camp-h7",
            "generation": 1,
            "started_at": "2026-11-07T00:00:00Z",
        }
        res = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "REGRESSION_FIXED"},
            observation={
                "regression_pair": {
                    "receipt_reference": fake_text_path,
                    "before": {"result": "FAIL", "verifier": "v1", "subject": "s1"},
                    "after": {"result": "PASS", "verifier": "v1", "subject": "s2"},
                }
            },
            attempt=attempt,
        )
        self.assertFalse(res["made_progress"])
        self.assertEqual(res["progress_class"], "UNVERIFIED_EFFECT")

    def test_r4_and_h8_self_hashed_semantic_evidence_rejected(self) -> None:
        """R4 & H8: Self-created semantic evidence with self-computed SHA256 and unrelated reference is rejected."""
        ctrl = campaign.CampaignController(self.root)
        ev_file = wf(self.root, ".saipen/evidence/rogue.md", b"# Rogue Evidence\n")
        ev_hash = hashlib.sha256(ev_file.read_bytes()).hexdigest()
        attempt = {
            "attempt_id": "att-h8-fake",
            "campaign_id": "camp-h8",
            "generation": 1,
            "started_at": "2026-11-07T00:00:00Z",
        }
        unrelated_ref = "src/wiki.md"
        res = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "SEMANTIC_EVIDENCE_ADDED"},
            observation={
                "evidence_delta_receipt": {
                    "verifier_id": "self-asserted-verifier",
                    "verifier_result": "PASS",
                    "receipt_reference": unrelated_ref,
                    "receipt_digest": hashlib.sha256(b"dummy").hexdigest(),
                    "evidence_files": [{"path": ".saipen/evidence/rogue.md", "after_hash": ev_hash, "created": True}],
                }
            },
            attempt=attempt,
        )
        self.assertFalse(res["made_progress"])
        self.assertEqual(res["progress_class"], "UNVERIFIED_EFFECT")

    def test_r5_worker_selected_issuer_or_digest_policy_ignored(self) -> None:
        """R5: Worker cannot choose its own issuer or bypass digest requirement."""
        ctrl = campaign.CampaignController(self.root)
        wf(
            self.root,
            ".saipen/evidence/gate_rec.json",
            json.dumps({"kind": "saipen-gate-record", "verifier_id": "v1", "verifier_result": "PASS", "before_score": 0, "after_score": 10}),
        )
        ok, _, err = ctrl._load_and_verify_receipt_reference(
            ".saipen/evidence/gate_rec.json",
            ("saipen-gate-record",),
            receipt_digest="sha256:0000000000000000000000000000000000000000000000000000000000000000",
            require_digest=True,
        )
        self.assertFalse(ok)
        self.assertEqual(err, "DIGEST_MISMATCH")

    def test_r6_malicious_record_claims_mismatch_actual_persisted_content(self) -> None:
        """R6: Discrepancy between worker claims and actual disk receipt fails verification."""
        ctrl = campaign.CampaignController(self.root)
        disk_rec = {
            "kind": "saipen-gate-record",
            "verifier_id": "gate-truth",
            "verifier_result": "FAIL",
            "before_score": 10,
            "after_score": 5,
            "attempt_id": "att-r6",
            "campaign_id": "camp-r6",
            "worker_generation": 1,
            "project_lineage": "lineage-b512942bac884a8691f6c98afcd6ddb9",
        }
        rec_path = wf(self.root, ".saipen/evidence/suite/r6_rec.json", json.dumps(disk_rec))
        rec_digest = hashlib.sha256(rec_path.read_bytes()).hexdigest()

        attempt = {
            "attempt_id": "att-r6",
            "campaign_id": "camp-r6",
            "generation": 1,
            "started_at": "2026-11-07T00:00:00Z",
        }
        res = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "TEST_GATE_IMPROVED"},
            observation={
                "gate_receipt": {
                    "receipt_reference": ".saipen/evidence/suite/r6_rec.json",
                    "receipt_digest": rec_digest,
                    "verifier_result": "PASS",
                    "before_score": 10,
                    "after_score": 100,
                }
            },
            attempt=attempt,
        )
        self.assertFalse(res["made_progress"])
        self.assertEqual(res["progress_class"], "UNVERIFIED_EFFECT")

    def test_r7_old_authentic_verifier_record_reused_in_wrong_attempt(self) -> None:
        """R7: Stale authentic verifier record from previous attempt is rejected in new attempt."""
        ctrl = campaign.CampaignController(self.root)
        disk_rec = {
            "kind": "saipen-gate-record",
            "verifier_id": "gate-truth",
            "verifier_result": "PASS",
            "before_score": 10,
            "after_score": 20,
            "attempt_id": "att-old-01",
            "campaign_id": "camp-r7",
            "worker_generation": 1,
            "project_lineage": "lineage-b512942bac884a8691f6c98afcd6ddb9",
        }
        rec_path = wf(self.root, ".saipen/evidence/suite/r7_rec.json", json.dumps(disk_rec))
        rec_digest = hashlib.sha256(rec_path.read_bytes()).hexdigest()

        attempt_new = {
            "attempt_id": "att-new-02",
            "campaign_id": "camp-r7",
            "generation": 2,
            "started_at": "2026-11-07T01:00:00Z",
        }
        res = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "TEST_GATE_IMPROVED"},
            observation={
                "gate_receipt": {
                    "receipt_reference": ".saipen/evidence/suite/r7_rec.json",
                    "receipt_digest": rec_digest,
                }
            },
            attempt=attempt_new,
        )
        self.assertFalse(res["made_progress"])
        self.assertEqual(res["progress_class"], "UNVERIFIED_EFFECT")

    def test_r8_and_g7_interrupted_attempt_and_restart(self) -> None:
        """R8 & G7: Restart preserves results in credited_operations and rejects double-credit."""
        ctrl = campaign.CampaignController(self.root)
        suite_rel = ".saipen/evidence/suite/gate_r8.json"
        disk_rec = {
            "schema": 1,
            "kind": "saipen-suite-record",
            "command": ["python", "-m", "unittest"],
            "command_sha256": "gate-verifier-r8",
            "verifier_id": "gate-verifier-r8",
            "verdict": "PASS",
            "exit_code": 0,
            "totals": {"runner": "unittest", "ran": 10, "passed": 10, "red": 0, "skipped": 0},
            "attempt_id": "att-r8",
            "campaign_id": "camp-r8",
            "worker_generation": 1,
            "project_lineage": "lineage-b512942bac884a8691f6c98afcd6ddb9",
        }
        wf(self.root, suite_rel, json.dumps(disk_rec))
        attempt = {
            "attempt_id": "att-r8",
            "campaign_id": "camp-r8",
            "generation": 1,
            "started_at": "2026-11-07T00:00:00Z",
        }
        res1 = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "TEST_GATE_IMPROVED"},
            observation={
                "gate_receipt": {
                    "receipt_reference": suite_rel,
                    "before_score": 5,
                    "after_score": 10,
                    "gate_id": "gate-r8",
                }
            },
            attempt=attempt,
        )
        self.assertTrue(res1["made_progress"])
        proof_ids = res1.get("proof_identities", [])
        self.assertTrue(len(proof_ids) > 0)

        ctrl_restart = campaign.CampaignController(self.root)
        credited = {pid: True for pid in proof_ids}
        res_replay = ctrl_restart._verify_progress_evidence(
            {"ok": True, "progress_class": "TEST_GATE_IMPROVED"},
            observation={
                "gate_receipt": {
                    "receipt_reference": suite_rel,
                    "before_score": 5,
                    "after_score": 10,
                    "gate_id": "gate-r8",
                }
            },
            attempt=attempt,
            credited_operations=credited,
        )
        self.assertFalse(res_replay["made_progress"])

    def test_r9_concurrent_duplicate_verified_effects(self) -> None:
        """R9: Concurrent attempts attempting to credit the same verified effect fail."""
        ctrl = campaign.CampaignController(self.root)
        suite_rel = ".saipen/evidence/suite/gate_r9.json"
        disk_rec = {
            "schema": 1,
            "kind": "saipen-suite-record",
            "command": ["python", "-m", "unittest"],
            "command_sha256": "gate-verifier-r9",
            "verifier_id": "gate-verifier-r9",
            "verdict": "PASS",
            "exit_code": 0,
            "totals": {"runner": "unittest", "ran": 10, "passed": 10, "red": 0, "skipped": 0},
            "attempt_id": "att-r9-worker-1",
            "campaign_id": "camp-r9",
            "worker_generation": 1,
            "project_lineage": "lineage-b512942bac884a8691f6c98afcd6ddb9",
        }
        wf(self.root, suite_rel, json.dumps(disk_rec))
        attempt1 = {
            "attempt_id": "att-r9-worker-1",
            "campaign_id": "camp-r9",
            "generation": 1,
            "started_at": "2026-11-07T00:00:00Z",
        }
        res1 = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "TEST_GATE_IMPROVED"},
            observation={
                "gate_receipt": {
                    "receipt_reference": suite_rel,
                    "before_score": 5,
                    "after_score": 10,
                    "gate_id": "gate-r9",
                }
            },
            attempt=attempt1,
        )
        self.assertTrue(res1["made_progress"])
        credited = {pid: True for pid in res1.get("proof_identities", [])}

        attempt2 = {
            "attempt_id": "att-r9-worker-2",
            "campaign_id": "camp-r9",
            "generation": 1,
            "started_at": "2026-11-07T00:00:00Z",
        }
        res2 = ctrl._verify_progress_evidence(
            {"ok": True, "progress_class": "TEST_GATE_IMPROVED"},
            observation={
                "gate_receipt": {
                    "receipt_reference": suite_rel,
                    "before_score": 5,
                    "after_score": 10,
                    "gate_id": "gate-r9",
                }
            },
            attempt=attempt2,
            credited_operations=credited,
        )
        self.assertFalse(res2["made_progress"])

    def test_r10_and_g8_unchanged_zip_payload_with_altered_timestamps_identical_hash(self) -> None:
        """R10 & G8: ZIP payload semantic hash is invariant to member packaging timestamps."""
        import zipfile
        from saipen_engine import audit_manifest

        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            zip1_path = p / "archive1.zip"
            zip2_path = p / "archive2.zip"

            content = b"def foo():\n    return 'bar'\n"
            with zipfile.ZipFile(zip1_path, "w") as z1:
                zinfo1 = zipfile.ZipInfo("src/foo.py", date_time=(2026, 1, 1, 0, 0, 0))
                z1.writestr(zinfo1, content)

            with zipfile.ZipFile(zip2_path, "w") as z2:
                zinfo2 = zipfile.ZipInfo("src/foo.py", date_time=(2026, 11, 7, 16, 0, 0))
                z2.writestr(zinfo2, content)

            fp1 = audit_manifest.compute_semantic_snapshot_fingerprint(zip1_path)
            fp2 = audit_manifest.compute_semantic_snapshot_fingerprint(zip2_path)
            self.assertEqual(fp1["semantic_payload_hash"], fp2["semantic_payload_hash"])

    def test_r11_and_g9_dirty_live_source_omitted_from_exported_zip_detected(self) -> None:
        """R11 & G9: Live source changes omitted from snapshot are detected as fidelity failure."""
        import zipfile
        from saipen_engine import audit_manifest

        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            subprocess.run(["git", "init", str(p)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["git", "-C", str(p), "config", "user.name", "Test"], check=True)
            subprocess.run(["git", "-C", str(p), "config", "user.email", "test@example.com"], check=True)
            (p / "src").mkdir()
            (p / "src" / "code.py").write_text("v1", encoding="utf-8")
            subprocess.run(["git", "-C", str(p), "add", "."], check=True)
            subprocess.run(["git", "-C", str(p), "commit", "-m", "init"], check=True, stdout=subprocess.DEVNULL)

            zip_path = p / "export.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("src/code.py", b"v1")

            (p / "src" / "code.py").write_text("v2_modified", encoding="utf-8")
            (p / "src" / "untracked.py").write_text("v2_new", encoding="utf-8")

            res = audit_manifest.verify_snapshot_manifest_fidelity(zip_path, p)
            self.assertFalse(res["ok"])
            self.assertEqual(res["status"], "EXPORT_FIDELITY_FAILURE")
            self.assertTrue(len(res.get("missing_in_archive", [])) > 0 or len(res.get("content_mismatches", [])) > 0)

    def test_r12_and_g10_repeated_clean_subsaipen_hypothesis_deduplicated(self) -> None:
        """R12 & G10: Clean SubSaipen hypothesis intake is deduplicated on repeated collection."""
        from saipen_engine import subs
        # Create MANIFEST and charter
        wf(self.root, ".saipen/MANIFEST.json", json.dumps({
            "version": 1,
            "roles": [{"name": "saitest", "policy": "core-review"}],
        }))
        wf(self.root, ".saipen/extensions/subs/saitest/CHARTER.md", "---\ncollect_policy: core-review\n---\n")

        # Simulate existing ticket on board with provenance
        board_with_ticket = (
            "## DOING\n"
            "## TODO\n"
            "- [ ] T-2035 [P2] Review SubSaipen hypothesis saitest/TEST-12 | verify: producer=saitest; package=TEST-12; source_head=66ef622a; source_tree_fingerprint=tree-1; role_revision=rev-1\n"
            "## DONE\n"
            "## BLOCKED\n"
        )
        wf(self.root, ".saipen/BOARD.md", board_with_ticket)

        # Now test _durable_collect_witness with matching hypothesis
        class DummyPackage:
            package_id = "TEST-12"
            fields = {
                "producer": "saitest",
                "source_head": "66ef622a",
                "source_tree_fingerprint": "tree-1",
                "role_revision": "rev-1",
            }

        pkg = DummyPackage()
        is_witnessed = subs._durable_collect_witness(
            self.root,
            "",
            "sha256:different_raw_block_hash",
            records=(),
            package=pkg,
            board_text=board_with_ticket,
        )
        self.assertTrue(is_witnessed)


if __name__ == "__main__":
    unittest.main()
