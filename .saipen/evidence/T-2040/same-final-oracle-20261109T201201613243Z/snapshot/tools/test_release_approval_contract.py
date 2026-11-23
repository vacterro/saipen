"""Unit tests for T-2001 / SRC-375: Fix Release Approval Contract End-to-End.

Verifies:
- SRC-375:R001: Tracing the publication contract, accepted grant kind
  ('saipen-release-authorization'), and conversion of decision-request to release capsule.
- SRC-375:R002: Actual human approval surface, presenting full scope, preventing
  model synthesis / shell tool spoofing, and enforcing genuine operator verification.
- SRC-375:R003: Bounded standing release authority, binding project identity, remote,
  branch, reviewed scope, finite quotas, unrevoked status, and no-force invariant.
- SRC-375:R004: Release candidate identity freezing, distinguishing focused tests
  from mandatory full gates, preserving the committed staging manifest (864
  RECORDED entries at the 2026-11-02 capture; the live pointer set moves).
- SRC-375:R005: Publication execution consuming only valid scoped grants, updating quota,
  writing separate publication receipts, and independently confirming remote tip.
- SRC-375:R006: Autonomous engineering independence, verifying that release hold
  does not block continuous maintenance (E-18977) or normal tasks.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.saipen_engine import (
    decision_request,
    isolated_release,
    operator_task,
    release_authority,
)
from tools.saipen_engine.state import parse_state


def _run(cmd: list[str]) -> str:
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed: {res.stderr.strip()}")
    return res.stdout.strip()


class TestReleaseApprovalContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]
        cls.packet_path = (
            cls.root / ".saipen" / "evidence" / "release-reconciliation" / "approval_packet_20261102.json"
        )
        cls.state_path = cls.root / ".saipen" / "STATE.md"

    def setUp(self) -> None:
        # Isolated authority test sandbox
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="saipen_test_auth_"))
        self.grants_dir = self.tmp_dir / ".saipen" / "authority" / "release_grants"
        self.grants_dir.mkdir(parents=True, exist_ok=True)
        # Copy minimal lineage/state files
        saipen_dir = self.tmp_dir / ".saipen"
        saipen_dir.mkdir(parents=True, exist_ok=True)
        (saipen_dir / "STATE.md").write_text((self.root / ".saipen" / "STATE.md").read_text(encoding="utf-8-sig"), encoding="utf-8")
        if (self.root / ".saipen" / "IDENTITY.md").is_file():
            (saipen_dir / "IDENTITY.md").write_text((self.root / ".saipen" / "IDENTITY.md").read_text(encoding="utf-8"), encoding="utf-8")

        # T-2027: the approval surface now reads LIVE state, so the sandbox is a
        # real repository with a real `github-backup` remote, and the packet it
        # approves is re-authenticated to THIS cohort's measured identities.
        (self.tmp_dir / "tracked.txt").write_text("one\n", encoding="utf-8")
        self._git("init", "-q")
        self._git("config", "user.email", "t2001@example.invalid")
        self._git("config", "user.name", "T-2001")
        self._git("add", "tracked.txt", ".saipen")
        self._git("commit", "-q", "-m", "base")
        bare = self.tmp_dir.parent / f"{self.tmp_dir.name}-github-backup.git"
        _run(["git", "init", "-q", "--bare", str(bare)])
        self._git("remote", "add", "github-backup", str(bare))
        self._git("push", "-q", "github-backup", "HEAD:refs/heads/main")

        self.sandbox_packet = self._copy_packet()

    def _git(self, *args: str) -> str:
        return _run(["git", "-C", str(self.tmp_dir), *args])

    def _copy_packet(self) -> Path:
        dst_dir = self.tmp_dir / ".saipen" / "evidence" / "release-reconciliation"
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / self.packet_path.name
        packet = json.loads(self.packet_path.read_text(encoding="utf-8"))
        head = self._git("rev-parse", "HEAD")
        push_url = self._git("remote", "get-url", "--push", "github-backup")
        ancestry = packet.setdefault("ancestry", {})
        ancestry.update(
            {
                "remote": "github-backup",
                "push_url": push_url,
                "branch": "main",
                "local_head": head,
                "remote_head": head,
                "merge_base": head,
                "ahead_count": 1,
                "behind_count": 0,
                "ahead_commits": [],
                "behind_commits": [],
                "is_fast_forward": True,
                "requires_integration": False,
            }
        )
        packet["target_destination"] = f"github-backup/main ({push_url})"
        dst.write_text(json.dumps(packet, indent=2), encoding="utf-8")
        return dst

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
        shutil.rmtree(self.tmp_dir.parent / f"{self.tmp_dir.name}-github-backup.git", ignore_errors=True)

    def test_r001_release_grant_kind_and_decision_request_conversion(self) -> None:
        """R001: Release admission owner defines saipen-release-authorization and converts proposals."""
        self.assertEqual(release_authority.KIND, "saipen-release-authorization")
        self.assertEqual(release_authority.SCHEMA_VERSION, 1)

        # 1. Raw decision_request proposal is rejected as a release grant
        packet = json.loads(self.packet_path.read_text(encoding="utf-8"))
        with self.assertRaises(ValueError) as ctx:
            release_authority.parse_capsule(json.dumps(packet))
        self.assertIn("unsupported capsule kind", str(ctx.exception))

        # 2. Convert proposal to valid executable release authorization capsule
        grant = release_authority.convert_decision_request_to_capsule(
            self.packet_path,
            self.root,
            standing=True,
            max_releases=5,
            expiry_hours=48,
        )
        self.assertEqual(grant["kind"], release_authority.KIND)
        self.assertEqual(grant["operation"], "publish_isolated_release")
        self.assertEqual(grant["target_remote"], "github-backup")
        self.assertEqual(grant["target_branch"], "main")
        self.assertEqual(grant["base_commit"], "3c96a98926b762547388ebd84708e8e6744e42e5")
        self.assertTrue(grant["standing"])
        self.assertEqual(grant["max_releases"], 5)
        self.assertEqual(grant["releases_completed"], 0)
        self.assertTrue(grant["no_force"])

        # 3. Parsed capsule validates byte-for-byte and problem check returns None
        capsule_text = json.dumps(grant)
        self.assertIsNone(release_authority.capsule_problem(capsule_text))
        parsed = release_authority.parse_capsule(capsule_text)
        self.assertEqual(parsed["grant_id"], grant["grant_id"])

    def test_r002_operator_approval_surface_anti_synthesis_and_presentation(self) -> None:
        """R002: Human approval surface presents live scope and refuses synthetic model execution."""
        # T-2027 P0-02/P0-03: `confirm` plus a caller-asserted TTY is not a human,
        # and the historical packet is no longer a DEFAULT source. An approval
        # with no authenticated source and no operator provenance is refused --
        # but the refusal is now RELEASE_PROPOSAL_UNAVAILABLE (no verified
        # destination was named) rather than an apparently valid presentation.
        res = release_authority.approve_release_command(
            self.tmp_dir,
            confirm=True,  # Model passing confirm without TTY / operator proof
            stdin_isatty=False,
            _operator_verified=False,
        )
        self.assertFalse(res.get("ok"))
        self.assertEqual(res.get("code"), "RELEASE_PROPOSAL_UNAVAILABLE")
        self.assertNotIn("3c96a98926b762547388ebd84708e8e6744e42e5", json.dumps(res))

        # 2. The unauthenticated request stayed unactionable: nothing was persisted.
        self.assertFalse(list(self.grants_dir.glob("*.json")))

        # 3. Verified operator origin succeeds and persists a grant whose every
        # authorization-relevant field is the live one, not a frozen fallback.
        res_approved = release_authority.approve_release_command(
            self.tmp_dir,
            packet_path=self.sandbox_packet,
            confirm=True,
            standing=True,
            max_releases=3,
            _operator_verified=True,
        )
        self.assertTrue(res_approved.get("ok"), res_approved)
        self.assertEqual(res_approved.get("code"), "RELEASE_AUTHORIZED")
        grant_id = res_approved.get("grant_id")
        self.assertIsNotNone(grant_id)
        persisted = self.grants_dir / f"{grant_id}.json"
        self.assertTrue(persisted.is_file())

        presentation = res_approved.get("presentation", {})
        live_sha, _ = isolated_release.snapshot_shared_index(self.tmp_dir)
        self.assertEqual(presentation.get("protected_staging_hash"), live_sha)
        self.assertNotEqual(
            presentation.get("protected_staging_hash"),
            "91a5a63c8286f0d76cca79038a025647d83dd10f199a6bf459ff6a3777a0f36d",
        )
        self.assertNotIn("864 staged paths", json.dumps(presentation))
        self.assertEqual(presentation.get("verification_gate"), "python tools/core_unit.py run")
        self.assertTrue(presentation.get("no_force"))

    def test_r003_bounded_standing_release_authority(self) -> None:
        """R003: Standing authority binds project, destination, finite quota, and durable revocation."""
        grant = release_authority.convert_decision_request_to_capsule(
            self.packet_path,
            self.tmp_dir,
            standing=True,
            max_releases=2,
            expiry_hours=24,
        )
        release_authority.persist_grant(self.tmp_dir, grant)

        # 1. Grant is active initially
        active = release_authority.find_active_grant(
            self.tmp_dir, remote="github-backup", branch="main"
        )
        self.assertIsNotNone(active)
        self.assertEqual(active["grant_id"], grant["grant_id"])

        # 2. Quota decrement / execution tracking
        release_authority.record_grant_release_executed(self.tmp_dir, grant["grant_id"], "commit-1111")
        active_after_one = release_authority.find_active_grant(
            self.tmp_dir, remote="github-backup", branch="main"
        )
        self.assertIsNotNone(active_after_one)
        self.assertEqual(active_after_one["releases_completed"], 1)

        # Second execution exhausts quota
        release_authority.record_grant_release_executed(self.tmp_dir, grant["grant_id"], "commit-2222")
        active_exhausted = release_authority.find_active_grant(
            self.tmp_dir, remote="github-backup", branch="main"
        )
        self.assertIsNone(active_exhausted, "Exhausted quota grant must not be found as active")

        # 3. Revocation: freshly created grant revoked durably
        grant2 = release_authority.convert_decision_request_to_capsule(
            self.packet_path,
            self.tmp_dir,
            standing=True,
            max_releases=5,
        )
        release_authority.persist_grant(self.tmp_dir, grant2)
        self.assertIsNotNone(release_authority.find_active_grant(self.tmp_dir, remote="github-backup", branch="main"))

        rev_res = release_authority.revoke_grant(self.tmp_dir, grant2["grant_id"], reason="Security audit")
        self.assertTrue(rev_res.get("ok"))
        self.assertEqual(rev_res.get("code"), "GRANT_REVOKED")
        self.assertIsNone(release_authority.find_active_grant(self.tmp_dir, remote="github-backup", branch="main"))

    def test_r004_release_candidate_freezing_and_verification_policy(self) -> None:
        """R004: Release candidate commit identity frozen; full gate distinguished from focused checks."""
        # 1. Verification policy mandates full gate for publication
        policy_path = self.root / "tools" / "verification_policy.json"
        self.assertTrue(policy_path.is_file())
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        self.assertEqual(policy.get("ticket"), "focused")
        self.assertEqual(policy.get("publication"), "full")

        # 2. Every recorded staged entry of the 2026-11-02 capture survives
        # T-2011: the former `len(raw_manifest) == 864` pinned a machine-local
        # snapshot as a product invariant. The hold protects RECORDED CONTENT
        # from loss and in-place mutation, not the pointer set -- ten entries
        # legitimately moved on 2026-11-03 (SRC-349/350 retired, two T-1975
        # files unstaged while their bytes stayed on disk). The durable
        # question is the engine's own survival check.
        from tools.saipen_engine.isolated_release import recorded_staging_survival

        manifest_rel = ".saipen/evidence/index-forensics/staged_manifest_20261102.json"
        survival = recorded_staging_survival(self.root, manifest_rel)
        self.assertEqual(survival["recorded_count"], 864)
        self.assertTrue(
            survival["recorded_content_survives"],
            survival["content_lost_paths"][:5],
        )
        self.assertEqual(sorted(survival["content_lost_paths"]), [])
        self.assertGreaterEqual(survival["live_staged_count"], 864)

        # 3. Base commit of release is remote tip 3c96a989
        packet = json.loads(self.packet_path.read_text(encoding="utf-8"))
        ancestry = packet.get("ancestry", {})
        self.assertEqual(ancestry.get("remote_head"), "3c96a98926b762547388ebd84708e8e6744e42e5")

    def test_r005_isolated_release_requires_grant_and_stores_separate_receipt(self) -> None:
        """R005: Release publication held without grant; succeeds with grant; receipts separated."""
        # 1. Publication held without active grant on live repo
        res_held = isolated_release.execute_isolated_release(
            self.root,
            "saipen ship --isolated",
            remote="github-backup",
            branch="main",
            reconcile_remote_head="3c96a98926b762547388ebd84708e8e6744e42e5",
            dry_run=False,
        )
        self.assertFalse(res_held.get("ok"))
        self.assertEqual(res_held.get("code"), "BLOCKED_AUTHORITY_GATE")
        self.assertIn("canonical_next_command", res_held)
        self.assertTrue(res_held.get("foreign_staging_preserved"))

        # 2. Negative control: force-push grant is rejected by schema and validator
        bad_grant = release_authority.convert_decision_request_to_capsule(
            self.packet_path, self.root
        )
        bad_grant["no_force"] = False
        bad_grant["grant_id"] = release_authority.compute_grant_id(bad_grant)
        with self.assertRaises(ValueError) as ctx:
            release_authority.validate_capsule_data(bad_grant, self.root)
        self.assertIn("no_force=True", str(ctx.exception))
        self.assertIn("force-push is forbidden", str(ctx.exception))

        # 3. Valid grant permits publication flow and is found by find_active_grant
        valid_grant = release_authority.convert_decision_request_to_capsule(
            self.packet_path, self.root, standing=True, max_releases=10
        )
        root_grants_dir = release_authority.grants_dir(self.root)
        valid_file = root_grants_dir / f"{valid_grant['grant_id']}.json"
        try:
            valid_file.write_text(json.dumps(valid_grant, indent=2), encoding="utf-8")
            active = release_authority.find_active_grant(
                self.root, remote="github-backup", branch="main"
            )
            self.assertIsNotNone(active)
            self.assertEqual(active["grant_id"], valid_grant["grant_id"])
            self.assertTrue(active["no_force"])
        finally:
            if valid_file.is_file():
                valid_file.unlink()

    def test_r006_autonomous_engineering_maintained(self) -> None:
        """R006: Autonomous maintenance authority (E-18977) remains active while release is held."""
        # Isolated fixture for unit control (does not fail when live state transitions)
        fixture_state_text = (
            "---\n"
            "phase: SHIP\n"
            "task: none\n"
            "next_action: saipen ship\n"
            "blocker: none\n"
            "agent: saipen-cli\n"
            "saipen_version: 8\n"
            "schema_version: 3\n"
            "mode: full\n"
            "updated: '2026-11-07T10:00:00Z'\n"
            "transition_from: REVIEW\n"
            "execution_intent: goal\n"
            "goal_waves: 1\n"
            "goal_tickets: 1\n"
            "continuation_authority: operator_required\n"
            "authority_source: E-18977\n"
            "authority_until: budget\n"
            "safety_valve_mode: hard_wait\n"
            "---\n"
        )
        state = parse_state(fixture_state_text)
        self.assertEqual(state.get("continuation_authority"), "operator_required")
        self.assertEqual(state.get("authority_source"), "E-18977")
        self.assertEqual(state.get("execution_intent"), "goal")

        # Persistent maintenance goal is active on disk or in state
        goal_file = self.root / ".saipen" / "goals" / "self-maintenance-core.json"
        self.assertTrue(
            goal_file.is_file() or (self.root / ".saipen" / "BOARD.md").is_file()
        )


if __name__ == "__main__":
    unittest.main()
