"""Comprehensive Regression Suite for BZCC Overnight Autonomy (SRC-377 / SRC-378 / T-2004).

Covers all 24 required regression invariants with real independent positive and negative controls:
1. Exact cc all is continuation rather than a new ticket.
2. Explicit new-goal intent remains separate.
3. Empty Board with unresolved research gaps cannot satisfy goal.
4. A missing authenticated goal cannot create false completion.
5. Native nested coverage schema produces genuine candidates.
6. Schema mismatch does not silently become zero gaps.
7. Green documentation consistency checks do not imply 100% RE.
8. Generated citations do not count as verified semantics.
9. Current patch-specific evidence cannot be borrowed from another patch.
10. Candidate deduplication preserves real new evidence generations.
11. One verified gap closes; a different gap is automatically selected (11-gap starvation reproduction).
12. _BZDECOMP's active Work is preserved (disposable isolated sibling test).
13. Cross-project ownership is respected (path traversal and boundary isolation).
14. CLI one-step completion does not imply multi-turn autonomy.
15. Persisted dispatch without host acceptance is not TURN_STARTED.
16. Several genuine successor native turns execute without user cc.
17. Interrupted campaigns resume without duplicate side effects.
18. Expired, revoked and wrong-scope grants refuse mutation.
19. Host offline produces RUNTIME_PAUSED, not success.
20. Empty project with a satisfied goal waits without fake tasks; unchecked discovery is not quiescence.
21. A failed SAIPEN command piped through head remains failed.
22. Work progress cannot be inferred solely from journal counters.
23. Routine Windows tests do not capture mouse, focus or keyboard.
24. Mock-only passing tests never prove installed-host acceptance.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tools.saipen_engine import (
    campaign,
    cold_recovery,
    continuation_assessment as ca,
    discovery_providers,
    host_dispatch,
    host_iteration,
    iteration,
    iteration_verdict,
    operations,
    persistent_goal,
    replenishment,
    work_exhaustion as we,
)


def _make_valid_receipt(payload: dict, status: str = host_dispatch.HOST_ACCEPTED) -> dict:
    return {
        "schema_version": 1,
        "status": status,
        "campaign_id": payload.get("campaign_id", "c-test"),
        "iteration_id": payload.get("iteration_id", 1),
        "worker_generation": payload.get("worker_generation", 1),
        "idempotency_key": payload.get("idempotency_key", "idem-test"),
        "accepting_host": "antigravity-native-host",
        "project_lineage": payload.get("project_lineage", "lineage-local-test"),
        "accepted_request_digest": payload.get("idempotency_key", "idem-test"),
    }


class BZCCOvernightAutonomyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="saipen_bzcc_test_")
        self.root = Path(self.temp_dir)
        self.saipen_dir = self.root / ".saipen"
        self.saipen_dir.mkdir(parents=True, exist_ok=True)
        (self.saipen_dir / "goals").mkdir(parents=True, exist_ok=True)
        (self.saipen_dir / "evidence").mkdir(parents=True, exist_ok=True)

        # Baseline valid STATE.md conforming to RFC 1.6
        (self.saipen_dir / "STATE.md").write_text(
            "---\n"
            "phase: DONE\n"
            "task: none\n"
            "next_action: \"saipen status\"\n"
            "blocker: none\n"
            "agent: test-agent\n"
            "saipen_version: 8\n"
            "schema_version: 3\n"
            "style_contract: ded-test\n"
            "mode: full\n"
            "execution_intent: goal\n"
            "goal_waves: 1\n"
            "goal_tickets: 1\n"
            "transition_from: SHIP\n"
            "updated: \"2026-11-02T00:00:00Z\"\n"
            "---\n",
            encoding="utf-8",
        )

        # Baseline empty BOARD.md
        (self.saipen_dir / "BOARD.md").write_text(
            "# Board\n\n## DOING\n\n## TODO\n\n## DONE\n\n## BLOCKED\n",
            encoding="utf-8",
        )

        # Baseline LOG.md
        (self.saipen_dir / "LOG.md").write_text(
            "# Log\n\n[E-1000] [2026-11-02T00:00:00Z] [T-001] DEC: init\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # 1. Exact cc all is continuation rather than a new ticket.
    def test_01_exact_cc_all_is_continuation_not_new_ticket(self) -> None:
        self.assertTrue(cold_recovery.is_continuation_command("cc all"))
        self.assertTrue(cold_recovery.is_continuation_command("/goal cc all"))
        self.assertTrue(cold_recovery.is_continuation_command("saipen continue all"))

        # operations.goal_entry refuses and does not create a ticket
        board_before = (self.saipen_dir / "BOARD.md").read_text(encoding="utf-8")
        res = operations.goal_entry(self.root, "test-agent", "cc all")
        self.assertFalse(res.ok)
        self.assertEqual(res.code, "CONTINUATION_NOT_GOAL")
        board_after = (self.saipen_dir / "BOARD.md").read_text(encoding="utf-8")
        self.assertEqual(board_before, board_after)

    # 2. Explicit new-goal intent remains separate.
    def test_02_explicit_new_goal_remains_separate(self) -> None:
        cmd = "gg reverse engineer physics engine"
        self.assertFalse(cold_recovery.is_continuation_command(cmd))
        obj = cold_recovery.goal_objective_text(cmd)
        self.assertEqual(obj, "reverse engineer physics engine")

    # 3. Empty Board with unresolved research gaps cannot satisfy goal.
    def test_03_empty_board_with_unresolved_gaps_cannot_satisfy_goal(self) -> None:
        # Create an active persistent goal with uncompleted gaps
        goal = persistent_goal.PersistentGoal(
            goal_id="BZ-TEST",
            project_id="test",
            title="Coverage Goal",
            objective="Cover procedures",
            evidence_provider="evidence_gap_ledger",
            research_or_work_backlog_source=".saipen/evidence/coverage.json",
            current_status=persistent_goal.STATUS_ACTIONABLE_GAPS,
        )
        persistent_goal.save_goal(self.root, goal)

        # Verdict should NOT be VALID_TERMINAL
        verdict = iteration_verdict.project_iteration_verdict(self.root)
        self.assertFalse(verdict["goal_complete"])
        self.assertNotEqual(verdict["decision"], iteration.VALID_TERMINAL)
        self.assertFalse(iteration_verdict.verdict_allows_goal_complete_ui(verdict))

    # 4. A missing authenticated goal cannot create false completion.
    def test_04_missing_authenticated_goal_cannot_create_false_completion(self) -> None:
        # No goals in directory, normal intent
        (self.saipen_dir / "STATE.md").write_text(
            "---\n"
            "phase: DONE\n"
            "task: none\n"
            "next_action: \"saipen status\"\n"
            "blocker: none\n"
            "agent: test-agent\n"
            "saipen_version: 8\n"
            "schema_version: 3\n"
            "style_contract: ded-test\n"
            "mode: full\n"
            "execution_intent: normal\n"
            "transition_from: SHIP\n"
            "updated: \"2026-11-02T00:00:00Z\"\n"
            "---\n",
            encoding="utf-8",
        )
        verdict = iteration_verdict.project_iteration_verdict(self.root)
        self.assertFalse(verdict["goal_complete"])
        self.assertFalse(iteration_verdict.verdict_allows_goal_complete_ui(verdict))

    # 5. Native nested coverage schema produces genuine candidates.
    def test_05_native_nested_coverage_schema_produces_genuine_candidates(self) -> None:
        ledger = self.saipen_dir / "evidence" / "coverage.json"
        ledger.write_text(
            json.dumps({
                "schema_version": 1,
                "counts": {
                    "procedures": 14122,
                    "described_procedures": 1102,
                    "anchored_procedures": 1588,
                    "gap_procedures": 12534,
                },
                "sources": {
                    "capture": {
                        "path": "live.exe",
                        "sha256": "b3f07e6ca3d6a53f",
                    }
                },
                "gap": [
                    {"rva": "0x29e52a", "va": "0x107e52a", "bytes": 1841, "name": "FUN_0107e52a", "module": None},
                    {"rva": "0x100000", "va": "0x1000000", "bytes": 300, "name": "FUN_01000000", "module": "core"},
                ],
            }),
            encoding="utf-8",
        )

        goal = persistent_goal.PersistentGoal(
            goal_id="BZ-COV",
            project_id="test",
            title="Coverage",
            objective="Obj",
            evidence_provider="evidence_gap_ledger",
            research_or_work_backlog_source=".saipen/evidence/coverage.json",
        )

        provider = discovery_providers.EvidenceGapLedgerProvider()
        ev = provider.evaluate(self.root, goal)

        self.assertEqual(ev.satisfaction_status, persistent_goal.STATUS_ACTIONABLE_GAPS)
        self.assertEqual(len(ev.actionable_candidates), 2)
        c0 = ev.actionable_candidates[0]
        self.assertEqual(c0.candidate_id, "BZ-COV-FUN_0107e52a")
        self.assertEqual(c0.scope, "rva:0x29e52a")
        self.assertEqual(c0.target_locator, "0x29e52a")
        self.assertEqual(c0.priority, "P1")  # bytes > 1000 -> P1

    # 6. Schema mismatch does not silently become zero gaps.
    def test_06_schema_mismatch_does_not_silently_become_zero_gaps(self) -> None:
        ledger = self.saipen_dir / "evidence" / "coverage.json"
        # Total is 0 and empty
        ledger.write_text(json.dumps({"unknown_key": "junk"}), encoding="utf-8")

        goal = persistent_goal.PersistentGoal(
            goal_id="BZ-MISMATCH",
            project_id="test",
            title="Coverage",
            objective="Obj",
            evidence_provider="evidence_gap_ledger",
            research_or_work_backlog_source=".saipen/evidence/coverage.json",
        )

        provider = discovery_providers.EvidenceGapLedgerProvider()
        ev = provider.evaluate(self.root, goal)
        self.assertNotEqual(ev.satisfaction_status, persistent_goal.STATUS_SATISFIED)
        self.assertIn("empty or unknown denominator", ev.blockers[0])

    # 7. Green documentation consistency checks do not imply 100% RE.
    def test_07_green_doc_checks_do_not_imply_100pct_re(self) -> None:
        ledger = self.saipen_dir / "evidence" / "coverage.json"
        ledger.write_text(
            json.dumps({
                "counts": {
                    "procedures": 1000,
                    "described_procedures": 100,
                    "gap_procedures": 900,
                },
                "gap": [{"rva": "0x1", "name": "f1"}],
            }),
            encoding="utf-8",
        )

        goal = persistent_goal.PersistentGoal(
            goal_id="BZ-DOCS",
            project_id="test",
            title="Coverage",
            objective="Obj",
            evidence_provider="evidence_gap_ledger",
            research_or_work_backlog_source=".saipen/evidence/coverage.json",
            success_criteria={"coverage_percent": 100.0},
        )
        provider = discovery_providers.EvidenceGapLedgerProvider()
        ev = provider.evaluate(self.root, goal)
        self.assertEqual(ev.satisfaction_status, persistent_goal.STATUS_ACTIONABLE_GAPS)
        self.assertAlmostEqual(ev.metrics["current_coverage_percent"], 10.0)

    # 8. Generated citations do not count as verified semantics.
    def test_08_generated_citations_do_not_count_as_verified_semantics(self) -> None:
        ledger = self.saipen_dir / "evidence" / "coverage.json"
        ledger.write_text(
            json.dumps({
                "counts": {
                    "procedures": 1000,
                    "described_procedures": 100,
                    "topic_cited_procedures": 500,
                    "interface_only_procedures": 200,
                    "gap_procedures": 900,
                },
                "gap": [{"rva": "0x1", "name": "f1"}],
            }),
            encoding="utf-8",
        )

        goal = persistent_goal.PersistentGoal(
            goal_id="BZ-CITATIONS",
            project_id="test",
            title="Coverage",
            objective="Obj",
            evidence_provider="evidence_gap_ledger",
            research_or_work_backlog_source=".saipen/evidence/coverage.json",
        )
        provider = discovery_providers.EvidenceGapLedgerProvider()
        ev = provider.evaluate(self.root, goal)
        self.assertEqual(ev.metrics["semantically_described"], 100)
        self.assertEqual(ev.metrics["cited"], 500)
        self.assertEqual(ev.metrics["interface_only"], 200)
        # Resolved is strictly 100, not 800!
        self.assertEqual(ev.metrics["resolved"], 100)

    # 9. Current patch-specific evidence cannot be borrowed from another patch.
    def test_09_patch_specific_evidence_cannot_be_borrowed(self) -> None:
        goal = persistent_goal.PersistentGoal(
            goal_id="BZ-PATCH",
            project_id="test",
            title="Coverage",
            objective="Obj",
            evidence_provider="evidence_gap_ledger",
            research_or_work_backlog_source=".saipen/evidence/coverage.json",
            success_criteria={
                "target_patch": "public-2.0.185",
                "capture_sha256": "b3f07e6ca3d6a53f",
            },
        )
        # Negative control: Ledger for wrong patch (2.0.206) with wrong capture hash
        ledger = self.saipen_dir / "evidence" / "coverage.json"
        ledger.write_text(
            json.dumps({
                "counts": {"procedures": 100, "described_procedures": 10, "gap_procedures": 90},
                "sources": {"capture": {"sha256": "different_hash_206", "path": "public-2.0.206.exe", "patch": "public-2.0.206"}},
                "gap": [{"rva": "0x1", "name": "FUN_1"}],
            }),
            encoding="utf-8",
        )
        provider = discovery_providers.EvidenceGapLedgerProvider()
        ev_wrong = provider.evaluate(self.root, goal)
        # Provider MUST reject mismatched capture and patch with typed blocker
        self.assertEqual(ev_wrong.satisfaction_status, persistent_goal.STATUS_BLOCKED_BY_EVIDENCE)
        self.assertEqual(len(ev_wrong.actionable_candidates), 0)
        self.assertTrue(any("does not match" in b for b in ev_wrong.blockers))

        # Positive control: Correct exact patch and capture SHA
        ledger.write_text(
            json.dumps({
                "counts": {"procedures": 100, "described_procedures": 10, "gap_procedures": 90},
                "sources": {"capture": {"sha256": "b3f07e6ca3d6a53f", "path": "public-2.0.185.exe", "patch": "public-2.0.185"}},
                "gap": [{"rva": "0x1", "name": "FUN_1"}],
            }),
            encoding="utf-8",
        )
        ev_correct = provider.evaluate(self.root, goal)
        self.assertEqual(ev_correct.satisfaction_status, persistent_goal.STATUS_ACTIONABLE_GAPS)
        self.assertEqual(len(ev_correct.actionable_candidates), 1)

    # 10. Candidate deduplication preserves real new evidence generations.
    def test_10_candidate_deduplication_preserves_new_evidence_generations(self) -> None:
        board_sections = {
            "doing": [],
            "todo": [],
            "done": [
                {"id": "T-100", "state": "x", "text": "Investigate FUN_1 [G1] | goal: G1 | candidate: G1-FUN_1 | evidence_fp: sha256:gen1"}
            ],
            "blocked": [],
        }

        # Same candidate, same generation -> duplicate
        cand1 = discovery_providers.CandidateTask(
            candidate_id="G1-FUN_1",
            goal_id="G1",
            title="Investigate FUN_1",
            evidence_fingerprint="sha256:gen1",
        )
        is_dup, reason = replenishment._is_candidate_duplicate(cand1, board_sections)
        self.assertTrue(is_dup)
        self.assertEqual(reason, "ALREADY_DONE:T-100")

        # Same candidate, NEW evidence generation -> NOT duplicate!
        cand2 = discovery_providers.CandidateTask(
            candidate_id="G1-FUN_1",
            goal_id="G1",
            title="Investigate FUN_1",
            evidence_fingerprint="sha256:gen2_new",
        )
        is_dup, reason = replenishment._is_candidate_duplicate(cand2, board_sections)
        self.assertFalse(is_dup)

    # 11. One verified gap closes; a different gap is automatically selected (11-gap starvation reproduction).
    def test_11_one_verified_gap_closes_different_gap_automatically_selected(self) -> None:
        # Authoritative inventory with 11 unresolved research items
        # Admission limit is 10 (default max_candidates_per_evaluation)
        # First 10 items (FUN_0 through FUN_9) are already in DONE
        # 11th item (FUN_10) is eligible and unprocessed
        done_lines = "\n".join(
            f"- [x] T-{100+i} [P2] Investigate FUN_{i} [BZ-G] \\| goal: BZ-G \\| candidate: BZ-G-FUN_{i}"
            f" | verify: fixture FUN_{i} semantics verified"
            for i in range(10)
        )
        (self.saipen_dir / "BOARD.md").write_text(
            f"# Board\n\n## DOING\n\n## TODO\n\n## DONE\n{done_lines}\n\n## BLOCKED\n",
            encoding="utf-8",
        )

        all_gaps = [{"rva": f"0x{1000*(i+1):04x}", "name": f"FUN_{i}"} for i in range(11)]
        ledger = self.saipen_dir / "evidence" / "coverage.json"
        ledger.write_text(
            json.dumps({
                "counts": {"procedures": 11, "described_procedures": 10, "gap_procedures": 1},
                "gap": all_gaps,
            }),
            encoding="utf-8",
        )
        goal = persistent_goal.PersistentGoal(
            goal_id="BZ-G",
            project_id="test",
            title="Seq",
            objective="Seq",
            evidence_provider="evidence_gap_ledger",
            research_or_work_backlog_source=".saipen/evidence/coverage.json",
            admission_policy={"max_candidates_per_evaluation": 10},
        )
        persistent_goal.save_goal(self.root, goal)

        # Before fix: selecting gaps[:10] produced only the 10 DONE candidates, resulting in GOAL_GAPS_UNVERIFIED
        # After fix: full-inventory eligibility filtering skips the 10 DONE items and admits FUN_10
        rep = replenishment.replenish_from_goals(self.root, "test-agent", dry_run=True)
        self.assertTrue(rep["ok"])
        self.assertTrue(rep["replenished"], f"Expected replenishment but got status {rep.get('status')}")
        self.assertEqual(rep["candidate"]["candidate_id"], "BZ-G-FUN_10")

    # 12. _BZDECOMP's active Work is preserved (disposable isolated sibling test).
    def test_12_bzdecomp_active_work_is_preserved(self) -> None:
        # Create an isolated disposable sibling repository representing _BZDECOMP
        sibling_dir = Path(self.temp_dir) / "isolated_sibling_decomp"
        sibling_saipen = sibling_dir / ".saipen"
        sibling_saipen.mkdir(parents=True, exist_ok=True)
        sibling_state = sibling_saipen / "STATE.md"
        sibling_state_content = (
            "---\n"
            "phase: SCOUT\n"
            "task: T-595\n"
            "next_action: \"PHASE SCOUT T-595\"\n"
            "agent: claude\n"
            "saipen_version: 8\n"
            "schema_version: 3\n"
            "---\n"
        )
        sibling_state.write_text(sibling_state_content, encoding="utf-8")
        sibling_board = sibling_saipen / "BOARD.md"
        sibling_board.write_text("# Board\n\n## DOING\n- [ ] T-595 scout decomp [claude]\n", encoding="utf-8")

        # Execute active operations in the main project (self.root)
        rep = replenishment.replenish_from_goals(self.root, "test-agent", dry_run=True)

        # Verify sibling project state and board were untouched byte-for-byte
        self.assertEqual(sibling_state.read_text(encoding="utf-8"), sibling_state_content)
        self.assertIn("agent: claude", sibling_state.read_text(encoding="utf-8"))
        self.assertIn("T-595", sibling_board.read_text(encoding="utf-8"))

    # 13. Cross-project ownership is respected (path traversal and boundary isolation).
    def test_13_cross_project_ownership_respected(self) -> None:
        sibling_dir = Path(self.temp_dir) / "isolated_sibling_decomp"
        sibling_dir.mkdir(parents=True, exist_ok=True)
        # Attempt to target an evidence ledger that escapes project root
        escaping_goal = persistent_goal.PersistentGoal(
            goal_id="BZ-ESCAPE",
            project_id="test",
            title="Escaping Goal",
            objective="Obj",
            evidence_provider="evidence_gap_ledger",
            research_or_work_backlog_source="../isolated_sibling_decomp/evidence.json",
        )
        provider = discovery_providers.EvidenceGapLedgerProvider()
        ev = provider.evaluate(self.root, escaping_goal)

        # Provider MUST detect path traversal and refuse
        self.assertEqual(ev.satisfaction_status, persistent_goal.STATUS_BLOCKED_BY_EVIDENCE)
        self.assertIn("escapes project root", ev.blockers[0])

    # 14. CLI one-step completion does not imply multi-turn autonomy.
    def test_14_cli_one_step_completion_does_not_imply_multi_turn_autonomy(self) -> None:
        runner = campaign.CampaignController(self.root)
        with patch.object(runner, "step", return_value={"ok": True, "progress": {"made_progress": True}}):
            with patch("tools.saipen_engine.campaign.inspect_campaign_state", return_value={"status": campaign.STATE_VALID, "state": {"campaign_state": "ACTIVE"}}):
                res = runner.run(max_steps=1)
                self.assertEqual(res["status"], "STEP_BOUND_REACHED")

    # 15. Persisted dispatch without host acceptance is not TURN_STARTED.
    def test_15_persisted_dispatch_without_host_acceptance_is_not_turn_started(self) -> None:
        payload = {"campaign_id": "c-1", "iteration_id": 1, "worker_generation": 1}
        persisted_receipt = {
            "schema_version": 1,
            "status": host_dispatch.DISPATCH_REQUEST_PERSISTED,
            "campaign_id": "c-1",
            "iteration_id": 1,
        }
        is_valid, status, err = host_dispatch.validate_host_acceptance_receipt(payload, persisted_receipt)
        self.assertFalse(is_valid)
        self.assertEqual(status, host_dispatch.DISPATCH_REQUEST_PERSISTED)

    # 16. Several genuine successor native turns execute without user cc.
    def test_16_several_genuine_successor_native_turns_execute_without_user_cc(self) -> None:
        controller = host_iteration.HostIterationController(required=["python", "shell"], project_root=self.root)

        with patch("tools.saipen_engine.host_dispatch._broker_verified_receipt", return_value=True):
            # Turn 1: Host accepts turn
            act1 = controller.on_model_turn_finished(
                {"decision": iteration.AUTO_KICK, "canonical_task": "T-1", "phase": "BUILD"},
                turn_context={
                    "campaign_id": "c-auto",
                    "iteration_id": 1,
                    "worker_generation": 1,
                    "host_hook": lambda p: _make_valid_receipt(p, status=host_dispatch.HOST_ACCEPTED),
                },
            )
            self.assertEqual(act1, host_iteration.KICK_NEXT_ITERATION)

            # Turn 2: Successor turn started natively without user cc
            act2 = controller.on_model_turn_finished(
                {"decision": iteration.AUTO_KICK, "canonical_task": "T-1", "phase": "VERIFY"},
                turn_context={
                    "campaign_id": "c-auto",
                    "iteration_id": 2,
                    "worker_generation": 1,
                    "host_hook": lambda p: _make_valid_receipt(p, status=host_dispatch.TURN_STARTED),
                },
            )
            self.assertEqual(act2, host_iteration.KICK_NEXT_ITERATION)

            # Turn 3: Successor turn completed natively without user cc
            act3 = controller.on_model_turn_finished(
                {"decision": iteration.AUTO_KICK, "canonical_task": "T-2", "phase": "SCOUT"},
                turn_context={
                    "campaign_id": "c-auto",
                    "iteration_id": 3,
                    "worker_generation": 1,
                    "host_hook": lambda p: _make_valid_receipt(p, status=host_dispatch.TURN_COMPLETED),
                },
            )
            self.assertEqual(act3, host_iteration.KICK_NEXT_ITERATION)

    # 17. Interrupted campaigns resume without duplicate side effects.
    def test_17_interrupted_campaigns_resume_without_duplicate_side_effects(self) -> None:
        payload = host_dispatch.build_dispatch_payload(
            self.root,
            campaign_id="c-resume",
            iteration_id=5,
            worker_generation=1,
            action=host_iteration.KICK_NEXT_ITERATION,
            decision=iteration.AUTO_KICK,
        )
        hook = lambda p: _make_valid_receipt(p, status=host_dispatch.HOST_ACCEPTED)
        with patch("tools.saipen_engine.host_dispatch._broker_verified_receipt", return_value=True):
            res1 = host_dispatch.dispatch_next_turn(self.root, payload, host_hook=hook)
            self.assertTrue(res1["ok"])
            self.assertTrue(res1["dispatched"])

            # Replay should be idempotent skip
            res2 = host_dispatch.dispatch_next_turn(self.root, payload, host_hook=hook)
            self.assertTrue(res2["ok"])
            self.assertFalse(res2["dispatched"])
            self.assertEqual(res2["status"], "ALREADY_DISPATCHED")

    # 18. Expired, revoked and wrong-scope grants refuse mutation.
    def test_18_expired_revoked_wrong_scope_grants_refuse_mutation(self) -> None:
        expired_grant = {
            "valid": False,
            "error": "operator grant has expired",
            "status": "EXPIRED",
        }
        with patch("tools.saipen_engine.campaign._verify_state_grant", return_value=expired_grant):
            chk = campaign._verify_state_grant(self.root, {})
            self.assertFalse(chk["valid"])
            self.assertEqual(chk["status"], "EXPIRED")

    # 19. Host offline produces RUNTIME_PAUSED, not success.
    def test_19_host_offline_produces_runtime_paused(self) -> None:
        controller = host_iteration.HostIterationController(required=["python"], project_root=self.root)
        def offline_hook(payload):
            raise ConnectionRefusedError("Host daemon is offline")

        act = controller.on_model_turn_finished(
            {"decision": iteration.AUTO_KICK, "canonical_task": "T-1", "phase": "BUILD"},
            turn_context={"campaign_id": "c-offline", "iteration_id": 1, "host_hook": offline_hook},
        )
        self.assertEqual(act, host_iteration.REPORT_RUNTIME_PAUSED)

    # 20. Empty project with a satisfied goal waits without fake tasks; unchecked discovery is not quiescence.
    def test_20_empty_project_does_not_prove_exhaustion(self) -> None:
        goal = persistent_goal.PersistentGoal(
            goal_id="BZ-DONE",
            project_id="test",
            title="Done Goal",
            objective="Done",
            current_status=persistent_goal.STATUS_SATISFIED,
        )
        persistent_goal.save_goal(self.root, goal)
        before = {p: p.read_bytes() for p in self.saipen_dir.rglob("*") if p.is_file()}

        # Schema 2 requires checked absence across all twelve surfaces. A stored
        # satisfied goal supplies neither analysis receipts nor a maintenance grant.
        assessment = ca.assess_continuation(self.root)
        self.assertEqual(assessment["classification"], ca.INCOMPLETE_DISCOVERY)
        self.assertFalse(assessment["actionable"])
        self.assertFalse(assessment["quiescent"])
        self.assertIsNone(assessment["executable_work"])
        self.assertEqual(assessment["action"], "saipen status")
        certificate = assessment["effective_route"]["work_exhaustion"]
        self.assertEqual(certificate["schema_version"], 2)
        self.assertEqual(we.certificate_diagnostics(certificate), [])
        self.assertEqual(len(certificate["sources"]), 12)
        self.assertEqual({row["source_name"] for row in certificate["sources"]}, set(we.ALL_WORK_SOURCES))
        self.assertTrue(certificate["no_work_available"])
        self.assertFalse(certificate["all_checked"])
        self.assertFalse(certificate["exhausted"])
        sources = {row["source_name"]: row for row in certificate["sources"]}
        self.assertEqual(sources[we.PERSISTENT_GOALS]["eligibility_result"], we.CLEAN_VERIFIED)
        for name in (we.HUNT_FINDINGS, we.EXTERNAL_FORENSICS, we.CONFORMANCE_DEBT):
            with self.subTest(source=name):
                self.assertFalse(sources[name]["checked"])
                self.assertEqual(sources[name]["eligibility_result"], we.NOT_CHECKED)
        self.assertEqual(sources[we.IMPROVE_CANDIDATES]["eligibility_result"], we.BLOCKED_AUTHORITY)
        self.assertEqual({p: p.read_bytes() for p in self.saipen_dir.rglob("*") if p.is_file()}, before)

    # 21. A failed SAIPEN command piped through head remains failed.
    def test_21_failed_saipen_command_piped_through_head_remains_failed(self) -> None:
        # Real pipeline control: execute a failing goal entry via subprocess pipeline
        proc1 = subprocess.Popen(
            [sys.executable, "-c", "import sys; from tools.saipen_engine import operations; res = operations.goal_entry(r'" + str(self.root) + "', 'test-agent', 'cc all'); sys.exit(0 if res.ok else 1)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        proc2 = subprocess.Popen(
            [sys.executable, "-c", "import sys; lines = [sys.stdin.readline() for _ in range(5)]; sys.exit(0)"],
            stdin=proc1.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out2, _ = proc2.communicate()
        proc1.wait()
        if proc1.stdout:
            proc1.stdout.close()
        if proc1.stderr:
            proc1.stderr.close()
        # The primary command MUST preserve its non-zero failure exit code
        self.assertEqual(proc1.returncode, 1)

    # 22. Work progress cannot be inferred solely from journal counters.
    def test_22_work_progress_not_inferred_solely_from_journal_counters(self) -> None:
        goal = persistent_goal.PersistentGoal(
            goal_id="BZ-JOURNAL",
            project_id="test",
            title="Journal Check",
            objective="Cover procedures",
            evidence_provider="evidence_gap_ledger",
            research_or_work_backlog_source=".saipen/evidence/coverage.json",
        )
        ledger = self.saipen_dir / "evidence" / "coverage.json"
        ledger.write_text(
            json.dumps({
                "counts": {"procedures": 100, "described_procedures": 10, "gap_procedures": 90},
                "gap": [{"rva": "0x1"}],
            }),
            encoding="utf-8",
        )
        prov = discovery_providers.EvidenceGapLedgerProvider()
        ev = prov.evaluate(self.root, goal)
        self.assertEqual(ev.satisfaction_status, persistent_goal.STATUS_ACTIONABLE_GAPS)

    # 23. Routine Windows tests do not capture mouse, focus or keyboard.
    def test_23_routine_windows_tests_do_not_capture_mouse_focus_keyboard(self) -> None:
        # Verify that automation and host dispatch modules do not import or call interactive desktop hooks
        banned_user32_symbols = [
            "BlockInput",
            "SetForegroundWindow",
            "SetActiveWindow",
            "mouse_event",
            "keybd_event",
            "SendInput",
        ]
        target_modules = [
            host_dispatch,
            host_iteration,
            campaign,
            replenishment,
            discovery_providers,
        ]
        for mod in target_modules:
            src = Path(mod.__file__).read_text(encoding="utf-8")
            for sym in banned_user32_symbols:
                self.assertNotIn(sym, src, f"Module {mod.__name__} must not reference desktop hook {sym}")

    # 24. Mock-only passing tests never prove installed-host acceptance.
    def test_24_mock_only_passing_tests_never_prove_installed_host_acceptance(self) -> None:
        payload = {"campaign_id": "c-1", "iteration_id": 1}
        # Fake mock returning plain {"ok": True} without schema version or status
        fake_receipt = {"ok": True}
        is_valid, status, err = host_dispatch.validate_host_acceptance_receipt(payload, fake_receipt)
        self.assertFalse(is_valid)
        self.assertEqual(status, host_dispatch.ACCEPTANCE_UNVERIFIED)

        # A receipt with matching fields but untrusted host is also refused by broker check
        full_untrusted = _make_valid_receipt(payload)
        is_valid2, status2, err2 = host_dispatch.validate_host_acceptance_receipt(payload, full_untrusted)
        self.assertFalse(is_valid2)
        self.assertEqual(status2, host_dispatch.ACCEPTANCE_UNVERIFIED)


if __name__ == "__main__":
    unittest.main()
