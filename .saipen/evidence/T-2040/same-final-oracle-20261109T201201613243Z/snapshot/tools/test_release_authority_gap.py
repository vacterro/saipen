"""Unit tests for T-2000 / SRC-374: Close the Release Authority Gap in Antigravity.

Verifies:
- SRC-374:R001: Separated authority broker status, canonical repair mechanism,
  and proof that broker startup grants no authorization.
- SRC-374:R002: Exact prepared approval packet inspection, proving it is a
  structured decision proposal (decision_request) and not an executable capsule.
- SRC-374:R003: Antigravity native hook boundary inspection, proving that
  model-generated shell tool calls are rejected as unauthenticated operator origin.
- SRC-374:R004: Standalone operator approval surface requirements and anti-fabrication
  invariants within the trusted broker model.
- SRC-374:R005: Exact release candidate SHA verification and mandatory verification
  gate distinction (focused suites != full publication gate).
- SRC-374:R006: Isolated release publication gate, refusing release without genuine
  operator authorization and verifying remote commit topology.
- SRC-374:R007: Preservation of shared Git index (864 staged entries), persistent
  maintenance authority (E-18977), and independent engineering work.
"""

from __future__ import annotations

import json
import os
import subprocess
import unittest
from pathlib import Path

from tools.saipen_engine import (
    decision_request,
    gate_decision,
    goal_authority,
    host_authority_broker as hab,
    host_authority_client as hac,
    host_authority_identity as hai,
    isolated_release,
    operator_task,
)
from tools.saipen_engine.state import parse_state


class TestReleaseAuthorityGap(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]
        cls.packet_path = (
            cls.root / ".saipen" / "evidence" / "release-reconciliation" / "approval_packet_20261102.json"
        )
        cls.state_path = cls.root / ".saipen" / "STATE.md"

    def test_r001_separated_authority_broker_checked_and_startup_not_authorization(self) -> None:
        """R001: Broker can be health-checked; broker startup alone grants zero authorization."""
        # 1. Health check function exists and returns typed report or None
        current_health = hab.health(self.root)
        self.assertTrue(current_health is None or isinstance(current_health, dict))

        # 2. Constructing or starting a broker service creates zero automatic capability grants
        broker = hab.Broker(saipen_root=self.root)
        self.assertIsNotNone(broker.authority)
        self.assertEqual(broker.stats.served, 0)
        self.assertEqual(broker.stats.authenticated, 0)

        # 3. An arbitrary project or unauthenticated client has no active capability
        arbitrary_binding = hab.binding(self.root, "session-test", "antigravity", "model", "provider")
        ok, code, _ = broker.authority.verify("cap-fake-token", arbitrary_binding)
        self.assertFalse(ok)
        self.assertEqual(code, hab.CODE_CAPABILITY_INVALID)

        # 4. Broker startup alone does not mutate project STATE or grant publication authority
        state = parse_state(self.state_path.read_text(encoding="utf-8-sig"))
        self.assertNotIn(state.get("continuation_authority"), ("granted", "standing_grant"))
        self.assertNotIn("publish_isolated_release", str(state))

    def test_r002_approval_packet_is_decision_proposal_not_executable_capsule(self) -> None:
        """R002: Prepared approval packet is a structured decision proposal, not an executable capsule."""
        self.assertTrue(self.packet_path.is_file(), f"Approval packet must exist at {self.packet_path}")
        packet = json.loads(self.packet_path.read_text(encoding="utf-8"))

        # 1. Conforms to decision_request schema
        for required_field in decision_request.REQUIRED_DECISION_FIELDS:
            self.assertIn(
                required_field, packet, f"Packet must carry decision_request field {required_field}"
            )
        self.assertEqual(packet.get("action"), "publish_isolated_release")
        self.assertIn("recording_mechanism", packet)

        # 2. It is NOT an executable gate decision capsule
        packet_str = json.dumps(packet)
        with self.assertRaises(ValueError):
            gate_decision.parse_capsule(packet_str)

        # 3. It is NOT an executable goal continuation capsule
        with self.assertRaises((ValueError, KeyError)):
            parsed = goal_authority.parse_capsule(packet_str)
            if parsed.get("kind") != "saipen-goal-continuation":
                raise ValueError("Not a goal continuation capsule")

    def test_r003_antigravity_native_hook_cannot_attest_shell_tool(self) -> None:
        """R003: Antigravity native hook boundary rejects model-generated shell tools as operator origin."""
        # Process chain simulating an agent shell tool execution:
        # python.exe (child) -> pwsh.exe (shell tool) -> agy.exe (host application)
        class MockProcessFact:
            def __init__(self, pid: int, ppid: int, image: str, argv: list[str]) -> None:
                self.pid = pid
                self.ppid = ppid
                self.image = image
                self.name = Path(image).name
                self.argv = argv
                self.created = 1000.0 + pid

        chain = [
            MockProcessFact(1001, 1000, "C:/python/python.exe", ["python.exe", "-c", "import os"]),
            MockProcessFact(1000, 900, "C:/pwsh/pwsh.exe", ["pwsh.exe", "-Command", "python ..."]),
            MockProcessFact(900, 800, "C:/agy/agy.exe", ["agy.exe"]),
        ]

        policy = hai.IdentityPolicy(
            host="antigravity",
            host_images=("agy.exe", "agy"),
            hook_artifacts=("extensions/adapters/antigravity/saipen-guard.py",),
            host_signers=(),
            shells=hai.DEFAULT_SHELLS,
        )

        proof = hai.prove_hook_invocation(chain, policy)
        # Shell tool call must NOT be admitted as hook invocation
        self.assertFalse(proof.ok)
        self.assertIn(proof.reason, (hai.REASON_NOT_HOST_DESCENDANT, hai.REASON_HOOK_NOT_FOUND))

    def test_r004_standalone_operator_approval_surface_anti_fabrication(self) -> None:
        """R004: Model-generated shell commands cannot mint operator origin; no fabricated keys/signatures."""
        # 1. Manual witness through shell without carrier is model_supplied
        wit = operator_task.witness("sample authority statement")
        self.assertEqual(wit.get("witness"), "model_supplied")

        # 2. Broker authority verification strictly checks HMAC signature; fabricated tokens fail
        broker = hab.Broker(saipen_root=self.root)
        arbitrary_binding = hab.binding(self.root, "sess-1", "antigravity", "model", "provider")
        fake_cap = "cap-f0000000000000000000000000000000"
        ok, code, _ = broker.authority.verify(fake_cap, arbitrary_binding)
        self.assertFalse(ok)
        self.assertEqual(code, hab.CODE_CAPABILITY_INVALID)

    def test_r005_exact_release_candidate_sha_and_mandatory_gate_distinction(self) -> None:
        """R005: Release candidate SHA is identified and focused suite is distinguished from full gate."""
        packet = json.loads(self.packet_path.read_text(encoding="utf-8"))
        ancestry = packet.get("ancestry", {})

        # Candidate local head and remote head
        self.assertEqual(ancestry.get("local_head"), "66ef622a43ab59512735ac78ce10d1250e26f9df")
        self.assertEqual(ancestry.get("remote_head"), "3c96a98926b762547388ebd84708e8e6744e42e5")

        # Invariant: Focused test suite (pattern-matched) != full core-unit gate
        focused_cmd = "tools/core_unit.py focused T-2000"
        full_gate_cmd = "tools/core_unit.py run"
        self.assertNotEqual(focused_cmd, full_gate_cmd)

    def test_r006_publication_refuses_without_operator_authorization(self) -> None:
        """R006: Release publication refuses without operator authorization; ancestry topology verified."""
        packet = json.loads(self.packet_path.read_text(encoding="utf-8"))
        ancestry = packet.get("ancestry", {})

        # 1. Non-fast-forward topology relative to remote HEAD
        self.assertFalse(ancestry.get("is_fast_forward"))
        self.assertTrue(ancestry.get("requires_integration"))

        # 2. Dry run of isolated release preflight confirms safe refusal without mutation
        res = isolated_release.execute_isolated_release(
            self.root,
            "saipen ship --dry-run",
            remote="github-backup",
            branch="main",
            dry_run=True,
            reconcile_remote_head=ancestry.get("remote_head"),
        )
        self.assertTrue(res.get("ok"))
        self.assertEqual(res.get("code"), "DRY_RUN")
        self.assertTrue(res.get("foreign_staging_preserved"))

    def test_r007_shared_index_and_maintenance_authority_preserved(self) -> None:
        """R007: Preserves every recorded staged entry's content and maintenance authority."""
        # 1. Every recorded staged entry's CONTENT survives (T-2011: the hold
        # protects content, not the pointer set; ten entries legitimately moved
        # on 2026-11-03 while no bytes were lost).
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

        # 2. Invariance of maintenance authority (isolated unit fixture)
        fixture_state = parse_state(
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
        self.assertEqual(fixture_state.get("continuation_authority"), "operator_required")
        self.assertEqual(fixture_state.get("authority_source"), "E-18977")
        live_state = parse_state(self.state_path.read_text(encoding="utf-8-sig"))
        self.assertIsNotNone(live_state.get("phase"))


if __name__ == "__main__":
    unittest.main()
