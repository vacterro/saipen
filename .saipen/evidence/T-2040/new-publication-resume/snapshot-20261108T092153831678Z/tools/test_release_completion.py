"""Release completion controls for SRC-373 and T-2040 publication truth.

All Git writes, local bare remotes, receipts and simulated operator events belong
only to disposable fixtures. A synthetic release observation is not consent;
historical staging counts, remote heads and STATE prose are not live proof.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from uuid import uuid4

from saipen_engine import (
    core_unit,
    focused_unit,
    goal_authority,
    host_authority_client,
    host_integration,
    operations,
    outcome_truth,
    release,
    release_authority,
)
from saipen_engine.decision_request import validate_decision_request
from saipen_engine.isolated_release import (
    IsolatedReleaseError,
    create_isolated_worktree,
    execute_isolated_release,
    generate_release_approval_packet,
    inventory_staged_entries,
    reconcile_remote_ancestry,
    snapshot_shared_index,
    transfer_reviewed_scope,
    verify_shared_index_unchanged,
    verify_staged_manifest_integrity,
)
from saipen_engine.paths import identity_file_content, new_project_lineage, project_identity
from saipen_engine.state import parse_state
from test_fixture_support import CURRENT_STYLE_CONTRACT
from test_hermetic_env import hermetic_env, isolate_host_session


def setUpModule() -> None:
    isolate_host_session()


class ReleaseCompletionTests(unittest.TestCase):
    def setUp(self) -> None:
        if not shutil.which("git"):
            self.skipTest("git unavailable")
        temp = tempfile.TemporaryDirectory(prefix="saipen-release-completion-")
        self.addCleanup(temp.cleanup)
        self.tmp = Path(temp.name)
        self.repo = self.tmp / "project"
        self.repo.mkdir()
        self.remote = self.tmp / "remote.git"
        self.remote.mkdir()
        env = hermetic_env(
            GIT_CONFIG_GLOBAL=os.devnull,
            GIT_CONFIG_NOSYSTEM="1",
            GIT_OPTIONAL_LOCKS="0",
            GIT_TERMINAL_PROMPT="0",
            GIT_ALLOW_PROTOCOL="file",
            GIT_DIR=None,
            GIT_WORK_TREE=None,
            GIT_INDEX_FILE=None,
            GIT_CONFIG_COUNT="0",
            SAIPEN_USER_CONFIG_HOME=str(self.tmp / "config"),
        )
        patch = mock.patch.dict(os.environ, env, clear=True)
        patch.start()
        self.addCleanup(patch.stop)
        self.git("init", "--bare", root=self.remote)
        self.git("symbolic-ref", "HEAD", "refs/heads/main", root=self.remote)
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "core.hooksPath", str(self.tmp / "no-hooks"))
        self.git("remote", "add", "origin", str(self.remote))
        self.memory = self.repo / ".saipen"
        self.memory.mkdir()
        self.lineage = new_project_lineage()
        (self.memory / "IDENTITY.md").write_text(
            identity_file_content(self.lineage), encoding="utf-8"
        )
        (self.memory / "STATE.md").write_text(
            "---\nphase: DONE\ntask: none\nnext_action: saipen continue\nblocker: none\n"
            "transition_from: SHIP\nagent: fixture\nmode: full\nsaipen_version: 8\n"
            "schema_version: 3\nlast_event: 1\nupdated: 2026-11-08T00:00:00Z\n"
            f"style_contract: {CURRENT_STYLE_CONTRACT}\n---\n",
            encoding="utf-8",
        )
        (self.memory / "BOARD.md").write_text(
            "# Board\n## DOING\n## TODO\n## DONE\n"
            "- [x] T-1 fixture | verify: fixture\n## BLOCKED\n",
            encoding="utf-8",
        )
        (self.memory / "LOG.md").write_text(
            "# Log\n- 08.11.26 00:00 [E-1] [agent: fixture] RUN: fixture\n",
            encoding="utf-8",
        )
        for name, text in {
            ".gitignore": ".saipen/\n",
            "code.py": "value = 1\n",
            "old.txt": "rename me\n",
            "delete.txt": "delete me\n",
            "VERSION": "1.0.0\n",
        }.items():
            (self.repo / name).write_text(text, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-m", "fixture base")
        self.base = self.git("rev-parse", "HEAD")
        self.git("push", "origin", "main")
        self.tickets = {
            "T-1": {
                "id": "T-1",
                "section": "## DONE",
                "checkbox": "x",
                "fields": {"publication_state": "pending"},
            }
        }

    def git(self, *args: str, root: Path | None = None) -> str:
        return subprocess.run(
            ["git", "-C", str(root or self.repo), *args],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
            timeout=30,
        ).stdout.strip()

    def foreign_staging(self) -> bytes:
        (self.repo / "foreign.txt").write_bytes(b"operator bytes\x00\xff\n")
        self.git("add", "foreign.txt")
        return (self.repo / ".git/index").read_bytes()

    def truth(self) -> dict:
        evidence = outcome_truth.read_publication_evidence(self.repo, tickets=self.tickets)
        return outcome_truth.compute_outcome_truth(
            None, tickets=self.tickets, publication_evidence=evidence
        )

    def write_receipt(self, **changes) -> dict:
        record = {
            "operation": "release",
            "op_id": "release-" + uuid4().hex,
            "status": "COMMITTED",
            "release_stage": "COMMITTED",
            "agent": "fixture",
            "created_at": "2026-11-08T00:00:00Z",
            "project_lineage": self.lineage,
            "project_identity": project_identity(self.repo),
            "semantic_payload_hash": "fixture",
            "verification_policy": "none",
            "targets": [],
            "progress_index": 0,
            "ticket_id": "T-1",
            **changes,
        }
        self.receipt_path = self.memory / "recovery/settled" / record["op_id"] / "operation.json"
        self.receipt_path.parent.mkdir(parents=True)
        self.receipt_path.write_text(json.dumps(record), encoding="utf-8")
        return record

    def published_receipt(self) -> dict:
        self.git("tag", "-a", "v1.0.0", "-m", "fixture")
        self.git("push", "origin", "v1.0.0")
        return self.write_receipt(
            mode="full",
            source_head=self.base,
            closure_commit=self.base,
            branch="main",
            remote_push_endpoint=str(self.remote),
            tag="v1.0.0",
            version="1.0.0",
            stages=["REMOTE_VERIFIED"],
        )

    def test_r001_shared_index_and_staged_manifest_are_exact(self) -> None:
        self.foreign_staging()
        self.git("mv", "old.txt", "renamed.txt")
        self.git("rm", "delete.txt")
        before = (self.repo / ".git/index").read_bytes()
        cached = self.git("diff", "--cached", "--name-status")
        manifest = inventory_staged_entries(self.repo)
        self.assertEqual(manifest["verification_status"], "VERIFIED_COMPLETE", manifest)
        path = self.memory / "manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        check = verify_staged_manifest_integrity(self.repo, path)
        self.assertTrue(check["logical_staged_state_preserved"], check)
        self.assertEqual(check["raw_index_sha256"], hashlib.sha256(before).hexdigest())
        report = execute_isolated_release(
            self.repo, "fixture", remote="origin", branch="main", dry_run=True
        )
        self.assertEqual(report["code"], "DRY_RUN", report)
        self.assertIsNone(report["active_grant_id"])
        self.assertEqual((self.repo / ".git/index").read_bytes(), before)
        self.assertEqual(self.git("diff", "--cached", "--name-status"), cached)
        (self.repo / "foreign.txt").write_bytes(b"changed\n")
        self.git("add", "foreign.txt")
        self.assertFalse(
            verify_staged_manifest_integrity(self.repo, path)["logical_staged_state_preserved"]
        )

    def test_r001_concurrent_index_is_never_restored_over(self) -> None:
        before, _ = snapshot_shared_index(self.repo)
        concurrent = self.foreign_staging()
        with self.assertRaises(IsolatedReleaseError) as caught:
            verify_shared_index_unchanged(self.repo, before)
        self.assertEqual(caught.exception.code, "CONCURRENT_WRITER_DETECTED")
        self.assertEqual((self.repo / ".git/index").read_bytes(), concurrent)

    def test_r002_diverged_ancestry_is_reconciled_only_in_isolated_tree(self) -> None:
        (self.repo / "local.txt").write_text("local\n", encoding="utf-8")
        self.git("add", "local.txt")
        self.git("commit", "-m", "local change")
        local = self.git("rev-parse", "HEAD")
        clone = self.tmp / "other"
        self.git("clone", str(self.remote), str(clone), root=self.tmp)
        self.git("config", "user.name", "Fixture", root=clone)
        self.git("config", "user.email", "fixture@example.invalid", root=clone)
        (clone / "remote.txt").write_text("remote\n", encoding="utf-8")
        self.git("add", "remote.txt", root=clone)
        self.git("commit", "-m", "remote change", root=clone)
        self.git("push", "origin", "main", root=clone)
        remote = self.git("rev-parse", "HEAD", root=clone)
        self.git("fetch", "origin", "main")
        ancestry = reconcile_remote_ancestry(self.repo, remote="origin", branch="main")
        self.assertEqual(
            (ancestry["local_head"], ancestry["remote_head"], ancestry["merge_base"]),
            (local, remote, self.base),
        )
        self.assertEqual((ancestry["ahead_count"], ancestry["behind_count"]), (1, 1))
        self.assertTrue(ancestry["requires_integration"])
        before = self.foreign_staging()
        worktree, cleanup = create_isolated_worktree(self.repo)
        try:
            self.git("merge", "--no-ff", remote, "-m", "fixture integration", root=worktree)
            integrated = self.git("rev-parse", "HEAD", root=worktree)
            current = reconcile_remote_ancestry(
                self.repo, remote="origin", branch="main", local_ref=integrated
            )
            self.assertTrue(current["is_fast_forward"], current)
            self.assertFalse(current["requires_integration"])
        finally:
            cleanup()
        self.assertEqual(self.git("rev-parse", "HEAD"), local)
        self.assertEqual((self.repo / ".git/index").read_bytes(), before)
        self.assertEqual(self.git("rev-parse", "refs/heads/main", root=self.remote), remote)

    def test_r003_only_exact_reviewed_bytes_and_deletions_transfer(self) -> None:
        before = self.foreign_staging()
        (self.repo / "reviewed.bin").write_bytes(b"reviewed\x00\xff")
        (self.repo / "unreviewed.py").write_text("unreviewed\n", encoding="utf-8")
        archive = self.memory / "archive/private.md"
        archive.parent.mkdir()
        archive.write_text("not release scope\n", encoding="utf-8")
        (self.repo / "delete.txt").unlink()
        worktree, cleanup = create_isolated_worktree(self.repo)
        try:
            transferred = transfer_reviewed_scope(
                self.repo, worktree, ["reviewed.bin", "delete.txt"]
            )
            self.assertEqual(set(transferred), {"reviewed.bin", "deleted:delete.txt"})
            self.assertEqual((worktree / "reviewed.bin").read_bytes(), b"reviewed\x00\xff")
            for name in (
                "delete.txt",
                "foreign.txt",
                "unreviewed.py",
                ".saipen/archive/private.md",
            ):
                self.assertFalse((worktree / name).exists(), name)
            with self.assertRaises(IsolatedReleaseError):
                transfer_reviewed_scope(self.repo, worktree, ["../escape.txt"])
        finally:
            cleanup()
        self.assertEqual((self.repo / ".git/index").read_bytes(), before)

    def test_r004_baseline_does_not_hide_new_red_or_incomplete_execution(self) -> None:
        inherited = "test_legacy.Case.test_known"
        run = {
            "status": "FAIL",
            "exit_code": 1,
            "ran": 2,
            "red": [inherited],
            "headers": 1,
            "tallied": 1,
            "unparsed": 0,
        }
        self.assertEqual(core_unit.judge(run, [inherited])["verdict"], "PASS")
        for changed in (
            {"red": [inherited, "test_new.Case.test_new"], "headers": 2, "tallied": 2},
            {"ran": 0},
            {"status": "TIMEOUT"},
            {"exit_code": 0},
        ):
            with self.subTest(changed=changed):
                self.assertEqual(
                    core_unit.judge({**run, **changed}, [inherited])["verdict"], "FAIL"
                )
        self.assertEqual(
            core_unit.judge(
                {**run, "status": "PASS", "exit_code": 0, "red": [], "headers": 0, "tallied": 0},
                [inherited],
            )["fixed"],
            [inherited],
        )

    def test_r004_focused_evidence_cannot_authorize_publication(self) -> None:
        declaration = self.repo / core_unit.DECLARATION_REL
        declaration.parent.mkdir(parents=True)
        declaration.write_text("# fixture declaration\n", encoding="utf-8")
        (self.repo / focused_unit.POLICY_REL).write_text(
            json.dumps(focused_unit.POLICY), encoding="utf-8"
        )
        (self.repo / core_unit.BASELINE_REL).write_text(
            json.dumps({"schema": 1, "family": "unit", "red": []}),
            encoding="utf-8",
        )
        directory = self.repo / focused_unit.RECORD_DIR_REL
        directory.mkdir(parents=True)
        (directory / "focused.json").write_text(
            json.dumps({"verdict": "PASS", "ran": 99}), encoding="utf-8"
        )
        self.assertIn("one full core-unit run", focused_unit.publication_gate(self.repo))
        with mock.patch(
            "saipen_engine.release.subprocess.run", side_effect=AssertionError("validator reached")
        ):
            result = release._run_gate(self.repo, "ship")
        self.assertFalse(result["ok"], result)
        self.assertIn("publication", result["detail"])

    def test_r005_approval_packet_is_current_proposal_not_a_grant(self) -> None:
        before = self.foreign_staging()
        packet = generate_release_approval_packet(
            self.repo,
            reviewed_scope=["code.py"],
            target_remote="origin",
            target_branch="main",
            destination_url=str(self.remote),
        )
        self.assertEqual(validate_decision_request(packet), [])
        self.assertEqual(packet["existing_authority"], "operator_required")
        self.assertEqual(packet["reviewed_scope"], "code.py")
        self.assertEqual(packet["ancestry"]["remote_head"], self.base)
        self.assertEqual(packet["paths_protected"], "1 staged paths in primary shared index")
        self.assertFalse((self.memory / "authority/release_grants").exists())
        self.assertEqual((self.repo / ".git/index").read_bytes(), before)

    def test_r005_unavailable_inventory_cannot_claim_protected_staging(self) -> None:
        with self.assertRaises(IsolatedReleaseError):
            generate_release_approval_packet(
                self.tmp / "missing-project", reviewed_scope=["code.py"],
                target_remote="origin", target_branch="main", destination_url=str(self.remote),
            )

    def test_r006_host_contract_does_not_prove_broker_availability(self) -> None:
        adapters = host_integration.load_registry()["adapters"]
        contracts = {a["id"]: host_integration.capability_contract(a) for a in adapters}
        self.assertTrue(contracts["zaicode"]["separated_authority"])
        self.assertFalse(contracts["antigravity"]["separated_authority"])
        self.assertIsNone(host_authority_client.health(runtime=self.tmp / "absent-endpoint"))
        self.assertFalse(goal_authority.continuous_maintenance_proven(self.repo, {}))

    def test_r007_confirm_tty_and_forged_carrier_never_authorize(self) -> None:
        before = self.foreign_staging()
        for provenance, origin in (
            (None, None),
            ({"witness": "model_supplied"}, None),
            ({"witness": "operator_carrier"}, {"signature": "invented"}),
        ):
            with self.subTest(provenance=provenance):
                result = release_authority.approve_release_command(
                    self.repo,
                    remote="origin",
                    branch="main",
                    reviewed_scope=["code.py"],
                    standing=True,
                    max_releases=2,
                    confirm=True,
                    stdin_isatty=True,
                    provenance=provenance,
                    operator_origin=origin,
                )
                self.assertEqual(result["code"], "REFUSED_SYNTHETIC_APPROVAL", result)
                self.assertFalse(result["mutated"])
                shown = result["presentation"]
                self.assertEqual(
                    shown["protected_staging_hash"], hashlib.sha256(before).hexdigest()
                )
                self.assertEqual(shown["protected_paths"], "1 staged paths in primary shared index")
                self.assertEqual(shown["target_url"], str(self.remote))
                self.assertTrue(shown["no_force"])
                self.assertEqual(shown["max_releases"], 2)
        self.assertEqual(list((self.memory / "authority/release_grants").glob("*.json")), [])
        self.assertEqual((self.repo / ".git/index").read_bytes(), before)

    def test_r008_unapproved_release_is_held_and_dry_run_is_not_publication(self) -> None:
        before = self.foreign_staging()
        result = execute_isolated_release(self.repo, "fixture", remote="origin", branch="main")
        self.assertEqual(result["code"], "BLOCKED_AUTHORITY_GATE", result)
        self.assertTrue(result["foreign_staging_preserved"])
        preview = execute_isolated_release(
            self.repo, "fixture", remote="origin", branch="main", dry_run=True
        )
        self.assertEqual(preview["code"], "DRY_RUN", preview)
        self.assertEqual(self.truth()["publication_status"], "RELEASE_PENDING")
        self.assertEqual((self.repo / ".git/index").read_bytes(), before)
        self.assertEqual(self.git("rev-parse", "refs/heads/main", root=self.remote), self.base)
        self.assertFalse((self.memory / "recovery").exists())

    def test_r009_owner_requires_ticket_project_and_actual_remote_git(self) -> None:
        record = self.published_receipt()
        before = {
            p.relative_to(self.repo).as_posix(): p.read_bytes()
            for p in self.repo.rglob("*")
            if p.is_file()
        }
        self.assertEqual(self.truth()["publication_status"], "RELEASE_PUBLISHED")
        after = {
            p.relative_to(self.repo).as_posix(): p.read_bytes()
            for p in self.repo.rglob("*")
            if p.is_file()
        }
        self.assertEqual(after, before)
        for changes, expected in (
            ({"ticket_id": "T-2"}, "RELEASE_PENDING"),
            ({"project_lineage": "lineage-" + "f" * 32}, "RELEASE_UNKNOWN"),
            ({"remote_push_endpoint": str(self.tmp / "missing.git")}, "RELEASE_UNKNOWN"),
        ):
            with self.subTest(changes=changes):
                self.receipt_path.write_text(json.dumps({**record, **changes}), encoding="utf-8")
                self.assertEqual(self.truth()["publication_status"], expected)
        self.receipt_path.write_text(json.dumps(record), encoding="utf-8")
        self.git("push", "origin", ":refs/tags/v1.0.0")
        self.assertEqual(self.truth()["publication_status"], "RELEASE_UNKNOWN")

    def test_r009_local_closure_and_caller_prose_are_not_published(self) -> None:
        from freshness import compute_source_identity

        source = compute_source_identity(self.repo)
        self.write_receipt(
            mode="no-publish",
            source_head=source.source_head,
            source_tree_fingerprint=source.source_tree_fingerprint,
        )
        self.assertEqual(self.truth()["publication_status"], "LOCAL_NO_PUBLISH")
        forged = outcome_truth.compute_outcome_truth(
            None,
            tickets=self.tickets,
            publication_state="published",
            publication_evidence={"verified": True, "release_id": "invented"},
        )
        self.assertEqual(forged["publication_status"], "RELEASE_UNKNOWN")

    def test_r010_state_prose_is_not_a_standing_maintenance_grant(self) -> None:
        legacy = {
            "execution_intent": "goal",
            "authority_source": "E-18977",
            "continuation_authority": "operator_required",
            "authority_until": "budget",
            "safety_valve_mode": "hard_wait",
        }
        self.assertFalse(goal_authority.continuous_maintenance_proven(self.repo, legacy))
        claimed = {
            **legacy,
            "continuation_authority": "operator_persistent",
            "authority_until": "continuous_maintenance",
            "safety_valve_mode": "checkpoint",
            "goal_ingress": "goal-" + "a" * 16,
        }
        self.assertFalse(goal_authority.continuous_maintenance_proven(self.repo, claimed))

    def test_r010_exact_fixture_grant_survives_only_its_bound_policy_and_origin(self) -> None:
        from saipen_engine.persistent_goal import get_goal, save_goal
        from test_t2023_goal_management_and_maintenance_binding import (
            MAINTENANCE_OBJECTIVE,
            _project,
            _read_history,
            _register_maintenance,
            _witnessed_apply,
        )

        for mutation in ("revoked", "policy", "source"):
            with self.subTest(mutation=mutation):
                root = _project(self, objective=MAINTENANCE_OBJECTIVE)
                _register_maintenance(root)
                state = parse_state((root / ".saipen/STATE.md").read_text(encoding="utf-8"))
                self.assertFalse(goal_authority.continuous_maintenance_proven(root, state))
                proposed = goal_authority.propose_capsule(
                    root, state, _read_history(root), until="continuous_maintenance"
                )
                self.assertTrue(proposed["ok"], proposed)
                applied = _witnessed_apply(
                    self, root, proposed["capsule_text"], revoke_after=mutation == "revoked"
                )
                self.assertTrue(applied.ok, applied.to_dict())
                state = parse_state((root / ".saipen/STATE.md").read_text(encoding="utf-8"))
                if mutation != "revoked":
                    self.assertTrue(goal_authority.continuous_maintenance_proven(root, state))
                if mutation == "policy":
                    goal = get_goal(root, "self-maintenance-core")
                    goal.success_criteria = {"require_independent_verification": False}
                    save_goal(root, goal)
                elif mutation == "source":
                    state["authority_source"] = "E-99999"
                self.assertFalse(goal_authority.continuous_maintenance_proven(root, state))

    def test_r010_independent_work_is_claimed_despite_external_publication_hold(self) -> None:
        (self.memory / "BOARD.md").write_text(
            "# Board\n## DOING\n## TODO\n- [ ] T-2 [P2] independent | verify: fixture\n"
            "## DONE\n- [x] T-1 fixture | verify: fixture | closure_mode: own_patch"
            " | publication_state: pending\n"
            "## BLOCKED\n- [ ] T-3 release | blocker: PUBLICATION_STAGING_BLOCKED_EXTERNAL\n",
            encoding="utf-8",
        )
        before = self.foreign_staging()
        result = operations.apply_claim(self.repo, "T-2", "fixture")
        self.assertTrue(result.ok, result.to_dict())
        state = parse_state((self.memory / "STATE.md").read_text(encoding="utf-8"))
        self.assertEqual(state["task"], "T-2")
        self.assertEqual((self.repo / ".git/index").read_bytes(), before)
        self.assertIn(
            "PUBLICATION_STAGING_BLOCKED_EXTERNAL",
            (self.memory / "BOARD.md").read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
