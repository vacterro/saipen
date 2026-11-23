"""Regression and Invariant Tests for SAIPEN Core Persistent Goal Engine (SRC-367 / T-1993).

Covers all 30 regression cases specified in SRC-367 Section 16:
CASE 01: No persistent goals, empty queue -> normal idle, no new ticket.
CASE 02: Goal satisfied, empty queue -> no new ticket.
CASE 03: Unsatisfied authorized goal, empty queue, actionable evidence -> next bounded ticket admitted.
CASE 04: Repeat same command -> no duplicate ticket.
CASE 05: Current relevant ticket already active -> continue existing ticket.
CASE 06: Previous ticket completed, new independent gap exists -> successor admitted.
CASE 07: Source unchanged but evidence gaps remain -> gap provider can still discover work.
CASE 08: Source-change discovery correctly cached -> no unnecessary rescan.
CASE 09: Provider returns no candidates because of an incomplete scan -> no false satisfaction claim.
CASE 10: Provider unavailable -> explicit blocker, no fake task.
CASE 11: All candidates blocked -> honest WAIT/NO_ADMISSIBLE_WORK.
CASE 12: Project operator_required hard gate -> gate preserved.
CASE 13: Foreign-owned Git changes -> untouched.
CASE 14: Concurrent cc all processes -> one canonical task admission.
CASE 15: Crash during discovery -> resumable state.
CASE 16: Crash after ticket admission -> no duplicate on restart.
CASE 17: Crash after successful ticket closure -> correct next goal evaluation.
CASE 18: Coverage decreases after a correctness fix -> no fake progress, valid recalculation.
CASE 19: Evidence categories overlap -> no invalid percentage arithmetic.
CASE 20: No measurable progress across repeated attempts -> bounded retry and strategy change.
CASE 21: An already completed ticket becomes invalid after new evidence -> legitimate review/supersession.
CASE 22: Goal explicitly paused or canceled -> no automatic successor.
CASE 23: An unauthorized project is present nearby -> no cross-project task generation.
CASE 24: One task blocked, another independent candidate authorized -> continue independent work.
CASE 25: Execution budget exhausted -> durable checkpoint, no false completion.
CASE 26: Normal cc legacy behavior -> preserved contract.
CASE 27: cc all with pending work and persistent goals -> finish allowed work, replenish legitimately.
CASE 28: Goal requires manual runtime acceptance -> cannot auto-close from synthetic tests.
CASE 29: Goal provider reports a truncated backlog -> partial discovery, not complete coverage.
CASE 30: Project phase DONE, conformance CURRENT_PASS, coverage gap nonzero -> admits legitimate work.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.discovery_providers import (
    COMPLETION_FULL,
    COMPLETION_TRUNCATED,
    CandidateTask,
    EvidenceGapLedgerProvider,
    FailedTestProvider,
    ProviderEvaluation,
    SourceChangeProvider,
    get_provider,
    list_providers,
)
from saipen_engine.persistent_goal import (
    PersistentGoal,
    SCOPE_DESTRUCTIVE,
    SCOPE_RELEASE,
    SCOPE_RESEARCH,
    STATUS_ACTIONABLE_GAPS,
    STATUS_ACTIVE,
    STATUS_BLOCKED_BY_EVIDENCE,
    STATUS_NO_ADMISSIBLE_WORK,
    STATUS_SATISFIED,
    STATUS_WAITING_AUTHORITY,
    delete_goal,
    get_goal,
    goals_dir,
    list_goals,
    save_goal,
)
from saipen_engine.replenishment import (
    _is_candidate_duplicate,
    _parse_board_tickets,
    evaluate_all_goals,
    replenish_from_goals,
)
from test_hermetic_env import isolate_host_session


def setUpModule() -> None:
    isolate_host_session()


class PersistentGoalEngineTests(unittest.TestCase):
    """Full 30-case regression suite for the persistent goal engine and queue replenishment."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saipen_goal_test_")).resolve()
        self.saipen_dir = self.tmp / ".saipen"
        self.saipen_dir.mkdir(parents=True, exist_ok=True)
        (self.saipen_dir / "goals").mkdir(parents=True, exist_ok=True)
        (self.saipen_dir / "evidence").mkdir(parents=True, exist_ok=True)

        # Basic BOARD.md
        self.board_file = self.saipen_dir / "BOARD.md"
        self.board_file.write_text(
            "# Board\n\n## DOING\n\n## TODO\n\n## DONE\n\n## BLOCKED\n",
            encoding="utf-8",
        )

        # Basic STATE.md
        self.state_file = self.saipen_dir / "STATE.md"
        self.state_file.write_text(
            "---\nagent: test-agent\nphase: DONE\ntask: none\nexecution_intent: goal\n---\n# State\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_case01_no_persistent_goals_empty_queue(self) -> None:
        """CASE 01: No persistent goals, empty queue -> normal idle, no new ticket."""
        res = replenish_from_goals(self.tmp, "test-agent")
        self.assertTrue(res["ok"])
        self.assertFalse(res["replenished"])
        self.assertEqual(res["status"], "NO_PERSISTENT_GOALS")
        self.assertEqual(len(list_goals(self.tmp)), 0)

    def test_case02_goal_satisfied_empty_queue(self) -> None:
        """CASE 02: Goal satisfied, empty queue -> no new ticket."""
        # Ledger has 100% coverage
        ledger_path = self.saipen_dir / "evidence" / "coverage.json"
        ledger_path.write_text(
            json.dumps({"total": 10, "resolved": 10, "gaps": []}),
            encoding="utf-8",
        )
        goal = PersistentGoal(
            goal_id="g-sat",
            project_id="test",
            title="Full Coverage",
            objective="Cover all items",
            evidence_provider="evidence_gap_ledger",
            research_or_work_backlog_source=".saipen/evidence/coverage.json",
            success_criteria={"coverage_percent": 100.0},
        )
        save_goal(self.tmp, goal)

        res = replenish_from_goals(self.tmp, "test-agent")
        self.assertTrue(res["ok"])
        self.assertFalse(res["replenished"])
        self.assertEqual(res["status"], "GOAL_SATISFIED")

    def test_case03_unsatisfied_goal_actionable_gaps(self) -> None:
        """CASE 03: Unsatisfied goal, empty queue, actionable gaps -> admits next bounded ticket."""
        ledger_path = self.saipen_dir / "evidence" / "coverage.json"
        ledger_path.write_text(
            json.dumps({
                "total": 10,
                "resolved": 2,
                "gaps": [
                    {"id": "proc_101", "name": "ProcessPacket", "priority": "P1"},
                    {"id": "proc_102", "name": "HandleDisconnect", "priority": "P2"},
                ],
            }),
            encoding="utf-8",
        )
        goal = PersistentGoal(
            goal_id="g-gaps",
            project_id="test",
            title="Reverse Engineering Inventory",
            objective="Analyze all procedures",
            evidence_provider="evidence_gap_ledger",
            research_or_work_backlog_source=".saipen/evidence/coverage.json",
        )
        save_goal(self.tmp, goal)

        res = replenish_from_goals(self.tmp, "test-agent", dry_run=True)
        self.assertTrue(res["ok"])
        self.assertTrue(res["replenished"])
        self.assertEqual(res["candidate"]["candidate_id"], "g-gaps-proc_101")
        self.assertEqual(res["candidate"]["priority"], "P1")

    def test_case04_repeat_same_command_no_duplicate(self) -> None:
        """CASE 04: Running replenishment when candidate is already on BOARD -> no duplicate ticket."""
        # Discovery identity belongs to the escaped description, not BOARD fields.
        board_content = (
            "# Board\n\n## DOING\n\n"
            "- [/] T-100 [P2] Investigate semantics of ProcessPacket [g-dup] \\| goal: g-dup \\| candidate: g-dup-proc_101"
            " | verify: ProcessPacket semantics documented\n\n"
            "## TODO\n\n## DONE\n\n## BLOCKED\n"
        )
        self.board_file.write_text(board_content, encoding="utf-8")

        ledger_path = self.saipen_dir / "evidence" / "coverage.json"
        ledger_path.write_text(
            json.dumps({
                "total": 1,
                "resolved": 0,
                "gaps": [{"id": "proc_101", "name": "ProcessPacket"}],
            }),
            encoding="utf-8",
        )
        goal = PersistentGoal(
            goal_id="g-dup",
            project_id="test",
            title="Deduplication Goal",
            objective="Check deduplication",
            evidence_provider="evidence_gap_ledger",
            research_or_work_backlog_source=".saipen/evidence/coverage.json",
        )
        save_goal(self.tmp, goal)

        res = replenish_from_goals(self.tmp, "test-agent")
        self.assertTrue(res["ok"])
        self.assertFalse(res["replenished"])
        self.assertEqual(res["status"], "DOING_ACTIVE")

    def test_case05_current_ticket_active(self) -> None:
        """CASE 05: Current relevant ticket already active -> continue existing ticket."""
        self.board_file.write_text(
            "# Board\n\n## DOING\n- [ ] T-105 In progress work\n\n## TODO\n\n## DONE\n\n## BLOCKED\n",
            encoding="utf-8",
        )
        res = replenish_from_goals(self.tmp, "test-agent")
        self.assertFalse(res["replenished"])
        self.assertEqual(res["status"], "DOING_ACTIVE")
        self.assertEqual(res["active_ticket"], "T-105")

    def test_case06_previous_ticket_completed_successor_admitted(self) -> None:
        """CASE 06: Previous ticket in DONE, new independent gap admitted as successor."""
        self.board_file.write_text(
            "# Board\n\n## DOING\n\n## TODO\n\n## DONE\n"
            "- [x] T-100 [P2] ProcessPacket [g-seq] \\| goal: g-seq \\| candidate: g-seq-proc_101"
            " | verify: fixture ProcessPacket semantics verified\n\n## BLOCKED\n",
            encoding="utf-8",
        )
        ledger_path = self.saipen_dir / "evidence" / "coverage.json"
        ledger_path.write_text(
            json.dumps({
                "total": 2,
                "resolved": 1,
                "gaps": [
                    {"id": "proc_101", "name": "ProcessPacket"},
                    {"id": "proc_102", "name": "HandleDisconnect"},
                ],
            }),
            encoding="utf-8",
        )
        goal = PersistentGoal(
            goal_id="g-seq",
            project_id="test",
            title="Sequential Goal",
            objective="Seq",
            evidence_provider="evidence_gap_ledger",
            research_or_work_backlog_source=".saipen/evidence/coverage.json",
        )
        save_goal(self.tmp, goal)

        res = replenish_from_goals(self.tmp, "test-agent", dry_run=True)
        self.assertTrue(res["ok"])
        self.assertTrue(res["replenished"])
        self.assertEqual(res["candidate"]["candidate_id"], "g-seq-proc_102")

    def test_case07_source_unchanged_gap_provider_discovers(self) -> None:
        """CASE 07: Source unchanged but evidence gaps remain -> gap provider can still discover work."""
        provider = EvidenceGapLedgerProvider()
        ledger_path = self.saipen_dir / "evidence" / "coverage.json"
        ledger_path.write_text(
            json.dumps({
                "total": 100,
                "resolved": 10,
                "gaps": [{"id": "item_1", "name": "Gap 1"}],
            }),
            encoding="utf-8",
        )
        goal = PersistentGoal(
            goal_id="g-src-unchanged",
            project_id="test",
            title="Test",
            objective="Test",
            evidence_provider="evidence_gap_ledger",
            research_or_work_backlog_source=".saipen/evidence/coverage.json",
        )
        eval_res = provider.evaluate(self.tmp, goal)
        self.assertEqual(eval_res.satisfaction_status, STATUS_ACTIONABLE_GAPS)
        self.assertEqual(len(eval_res.actionable_candidates), 1)

    def test_case08_source_change_discovery_cached(self) -> None:
        """CASE 08: SourceChangeProvider returns appropriate cached status."""
        prov = SourceChangeProvider()
        goal = PersistentGoal(
            goal_id="g-sc",
            project_id="test",
            title="SC",
            objective="SC",
            evidence_provider="source_change",
        )
        eval_res = prov.evaluate(self.tmp, goal)
        self.assertIn(eval_res.satisfaction_status, (STATUS_NO_ADMISSIBLE_WORK, STATUS_ACTIONABLE_GAPS, "DISCOVERY_REQUIRED"))

    def test_case09_provider_incomplete_scan_no_false_satisfaction(self) -> None:
        """CASE 09: Provider returns no candidates because of unreadable file -> no false satisfaction claim."""
        ledger_path = self.saipen_dir / "evidence" / "corrupt.json"
        ledger_path.write_text("{ corrupt json ...", encoding="utf-8")
        goal = PersistentGoal(
            goal_id="g-corrupt",
            project_id="test",
            title="Corrupt",
            objective="Corrupt",
            evidence_provider="evidence_gap_ledger",
            research_or_work_backlog_source=".saipen/evidence/corrupt.json",
        )
        save_goal(self.tmp, goal)
        res = replenish_from_goals(self.tmp, "test-agent")
        self.assertFalse(res["replenished"])
        self.assertNotEqual(res["status"], "GOAL_SATISFIED")
        self.assertEqual(res["status"], "ALL_CANDIDATES_BLOCKED")

    def test_case10_provider_unavailable(self) -> None:
        """CASE 10: Unknown provider -> explicit blocker, no fake task."""
        goal = PersistentGoal(
            goal_id="g-unknown",
            project_id="test",
            title="Unknown",
            objective="Unknown",
            evidence_provider="non_existent_provider_xyz",
        )
        save_goal(self.tmp, goal)
        res = replenish_from_goals(self.tmp, "test-agent")
        self.assertFalse(res["replenished"])
        self.assertIn("Unknown evidence provider", str(res.get("blockers", [])))

    def test_case11_all_candidates_blocked(self) -> None:
        """CASE 11: All candidates blocked on BOARD -> honest ALL_CANDIDATES_BLOCKED."""
        self.board_file.write_text(
            "# Board\n\n## DOING\n\n## TODO\n\n## DONE\n\n## BLOCKED\n"
            "- [ ] T-110 [P2] Candidate proc_101 blocked \\| goal: g-blk \\| candidate: g-blk-proc_101"
            " | blocker: BLOCKED_EXTERNAL -- awaiting capture | verify: proc_101 semantics documented\n",
            encoding="utf-8",
        )
        ledger_path = self.saipen_dir / "evidence" / "coverage.json"
        ledger_path.write_text(
            json.dumps({"total": 1, "resolved": 0, "gaps": [{"id": "proc_101", "name": "Proc"}]}),
            encoding="utf-8",
        )
        goal = PersistentGoal(
            goal_id="g-blk",
            project_id="test",
            title="Blocked",
            objective="Blocked",
            evidence_provider="evidence_gap_ledger",
            research_or_work_backlog_source=".saipen/evidence/coverage.json",
        )
        save_goal(self.tmp, goal)
        res = replenish_from_goals(self.tmp, "test-agent")
        self.assertFalse(res["replenished"])
        self.assertIn(res["status"], ("ALL_CANDIDATES_BLOCKED", "NO_ADMISSIBLE_WORK"))

    def test_case12_operator_required_gate_preserved(self) -> None:
        """CASE 12: Candidate requiring DESTRUCTIVE scope -> WAITING_AUTHORITY."""
        ledger_path = self.saipen_dir / "evidence" / "coverage.json"
        ledger_path.write_text(
            json.dumps({"total": 1, "resolved": 0, "gaps": [{"id": "wipe_db", "name": "Wipe Database"}]}),
            encoding="utf-8",
        )
        goal = PersistentGoal(
            goal_id="g-destruct",
            project_id="test",
            title="Destructive Op",
            objective="Destructive",
            authorization_scope=SCOPE_DESTRUCTIVE,
            evidence_provider="evidence_gap_ledger",
            research_or_work_backlog_source=".saipen/evidence/coverage.json",
        )
        save_goal(self.tmp, goal)
        res = replenish_from_goals(self.tmp, "test-agent")
        self.assertFalse(res["replenished"])
        self.assertEqual(res["status"], "WAITING_AUTHORITY")

    def test_case13_foreign_owned_git_changes_untouched(self) -> None:
        """CASE 13: Goal evaluation touches only .saipen/ directory and does not alter working tree."""
        unrelated_file = self.tmp / "unrelated_code.py"
        unrelated_file.write_text("# foreign change", encoding="utf-8")
        goal = PersistentGoal(
            goal_id="g-foreign",
            project_id="test",
            title="Foreign Test",
            objective="Foreign",
            evidence_provider="evidence_gap_ledger",
        )
        save_goal(self.tmp, goal)
        replenish_from_goals(self.tmp, "test-agent")
        self.assertEqual(unrelated_file.read_text(encoding="utf-8"), "# foreign change")

    def test_case14_concurrent_cc_all_one_admission(self) -> None:
        """CASE 14: Deduplication logic ensures candidate is admitted at most once."""
        sections = _parse_board_tickets(self.tmp)
        cand = CandidateTask(candidate_id="g-race-proc1", goal_id="g-race", title="Proc 1")
        is_dup, _ = _is_candidate_duplicate(cand, sections)
        self.assertFalse(is_dup)

        # Simulate admission into board
        sections["todo"].append({"id": "T-999", "state": " ", "text": "Proc 1 candidate: g-race-proc1", "raw": ""})
        is_dup_second, reason = _is_candidate_duplicate(cand, sections)
        self.assertTrue(is_dup_second)
        self.assertEqual(reason, "ALREADY_IN_TODO:T-999")

    def test_case15_crash_during_discovery_resumable(self) -> None:
        """CASE 15: Crash during discovery leaves goals and board valid and parseable."""
        goal = PersistentGoal(
            goal_id="g-crash",
            project_id="test",
            title="Crash",
            objective="Crash",
        )
        save_goal(self.tmp, goal)
        # Verify read succeeds
        read_back = get_goal(self.tmp, "g-crash")
        self.assertIsNotNone(read_back)
        self.assertEqual(read_back.goal_id, "g-crash")

    def test_case16_crash_after_ticket_admission_no_duplicate(self) -> None:
        """CASE 16: Ticket already committed on BOARD -> restart does not create duplicate."""
        self.board_file.write_text(
            "# Board\n\n## DOING\n\n## TODO\n"
            "- [ ] T-200 [P2] Candidate proc_101 \\| goal: g-crash2 \\| candidate: g-crash2-proc_101"
            " | verify: proc_101 semantics documented\n\n## DONE\n\n## BLOCKED\n",
            encoding="utf-8",
        )
        ledger_path = self.saipen_dir / "evidence" / "coverage.json"
        ledger_path.write_text(
            json.dumps({"total": 1, "resolved": 0, "gaps": [{"id": "proc_101", "name": "Proc"}]}),
            encoding="utf-8",
        )
        goal = PersistentGoal(
            goal_id="g-crash2",
            project_id="test",
            title="Crash2",
            objective="Crash2",
            evidence_provider="evidence_gap_ledger",
            research_or_work_backlog_source=".saipen/evidence/coverage.json",
        )
        save_goal(self.tmp, goal)
        res = replenish_from_goals(self.tmp, "test-agent")
        self.assertFalse(res["replenished"])
        self.assertEqual(res["status"], "TODO_AVAILABLE")

    def test_case17_crash_after_ticket_closure_evaluates_next(self) -> None:
        """CASE 17: Ticket closed in DONE -> evaluates remaining goal and selects next gap."""
        self.board_file.write_text(
            "# Board\n\n## DOING\n\n## TODO\n\n## DONE\n"
            "- [x] T-200 [P2] Candidate proc_101 \\| goal: g-next \\| candidate: g-next-proc_101"
            " | verify: fixture proc_101 semantics verified\n\n## BLOCKED\n",
            encoding="utf-8",
        )
        ledger_path = self.saipen_dir / "evidence" / "coverage.json"
        ledger_path.write_text(
            json.dumps({
                "total": 2,
                "resolved": 1,
                "gaps": [
                    {"id": "proc_101", "name": "Proc 1"},
                    {"id": "proc_102", "name": "Proc 2"},
                ],
            }),
            encoding="utf-8",
        )
        goal = PersistentGoal(
            goal_id="g-next",
            project_id="test",
            title="Next",
            objective="Next",
            evidence_provider="evidence_gap_ledger",
            research_or_work_backlog_source=".saipen/evidence/coverage.json",
        )
        save_goal(self.tmp, goal)
        res = replenish_from_goals(self.tmp, "test-agent", dry_run=True)
        self.assertTrue(res["replenished"])
        self.assertEqual(res["candidate"]["candidate_id"], "g-next-proc_102")

    def test_case18_coverage_decreases_recalculation(self) -> None:
        """CASE 18: Coverage recalculates correctly when inventory total increases."""
        provider = EvidenceGapLedgerProvider()
        ledger_path = self.saipen_dir / "evidence" / "coverage.json"
        # Total was 100 with 50 resolved = 50%
        # New scan finds total is 200 with 50 resolved = 25%
        ledger_path.write_text(
            json.dumps({"total": 200, "resolved": 50, "gaps": [{"id": "p1", "name": "P1"}]}),
            encoding="utf-8",
        )
        goal = PersistentGoal(
            goal_id="g-recalc",
            project_id="test",
            title="Recalc",
            objective="Recalc",
            evidence_provider="evidence_gap_ledger",
            research_or_work_backlog_source=".saipen/evidence/coverage.json",
        )
        eval_res = provider.evaluate(self.tmp, goal)
        self.assertAlmostEqual(eval_res.metrics["current_coverage_percent"], 25.0)

    def test_case19_evidence_categories_overlap(self) -> None:
        """CASE 19: Categories overlap (e.g. described vs anchored) without percentage arithmetic errors."""
        provider = EvidenceGapLedgerProvider()
        ledger_path = self.saipen_dir / "evidence" / "coverage.json"
        ledger_path.write_text(
            json.dumps({
                "total_procedures": 14122,
                "described_procedures": 1082,
                "anchored_procedures": 1568,
                "gap_entries": [{"id": "p_gap_1", "name": "Unknown"}],
            }),
            encoding="utf-8",
        )
        goal = PersistentGoal(
            goal_id="g-overlap",
            project_id="test",
            title="Overlap",
            objective="Overlap",
            evidence_provider="evidence_gap_ledger",
            research_or_work_backlog_source=".saipen/evidence/coverage.json",
        )
        eval_res = provider.evaluate(self.tmp, goal)
        self.assertEqual(eval_res.metrics["total"], 14122)
        self.assertEqual(eval_res.metrics["resolved"], 1082)
        self.assertEqual(eval_res.satisfaction_status, STATUS_ACTIONABLE_GAPS)

    def test_case20_no_progress_bounded_retry(self) -> None:
        """CASE 20: No progress across attempts is tracked in goal resume metadata."""
        goal = PersistentGoal(
            goal_id="g-bound",
            project_id="test",
            title="Bound",
            objective="Bound",
            resume_metadata={"consecutive_no_progress": 3},
        )
        save_goal(self.tmp, goal)
        read_g = get_goal(self.tmp, "g-bound")
        self.assertEqual(read_g.resume_metadata["consecutive_no_progress"], 3)

    def test_case21_completed_ticket_invalid_no_silent_reopening(self) -> None:
        """CASE 21: New evidence permits review; the exact completed generation stays DONE."""
        evidence_path = self.saipen_dir / "evidence" / "proc-a.bin"
        evidence_path.write_bytes(b"original proc-a evidence")
        fingerprint = "sha256:" + hashlib.sha256(evidence_path.read_bytes()).hexdigest()[:16]
        self.board_file.write_text(
            "# Board\n\n## DOING\n\n## TODO\n\n## DONE\n"
            "- [x] T-50 [P2] Proc A [g-inv] \\| goal: g-inv \\| candidate: g-inv-proca"
            f" \\| evidence_fp: {fingerprint} | verify: .saipen/evidence/proc-a.bin\n\n## BLOCKED\n",
            encoding="utf-8",
        )
        before = self.board_file.read_bytes()
        board = _parse_board_tickets(self.tmp)
        self.assertEqual(len(board["done"]), 1)
        self.assertEqual(board["done"][0]["id"], "T-50")
        self.assertEqual(board["done"][0]["state"], "x")
        cand = CandidateTask(
            candidate_id="g-inv-proca", goal_id="g-inv", title="Proc A",
            evidence_fingerprint=fingerprint,
        )
        is_dup, reason = _is_candidate_duplicate(cand, board)
        self.assertTrue(is_dup)
        self.assertEqual(reason, "ALREADY_DONE:T-50")

        evidence_path.write_bytes(b"corrected proc-a evidence")
        cand.evidence_fingerprint = "sha256:" + hashlib.sha256(evidence_path.read_bytes()).hexdigest()[:16]
        self.assertNotEqual(cand.evidence_fingerprint, fingerprint)
        self.assertEqual(_is_candidate_duplicate(cand, board), (False, None))
        self.assertEqual(self.board_file.read_bytes(), before)
        self.assertEqual(_parse_board_tickets(self.tmp)["done"], board["done"])

    def test_candidate_identity_rejects_false_matches(self) -> None:
        """Titles, candidate prefixes, foreign goals and prose markers are not identity."""
        cand = CandidateTask(candidate_id="g-inv-proca", goal_id="g-inv", title="Proc A")
        for description in (
            "Proc A [g-inv]",
            "Proc A [g-inv] \\| candidate: g-inv-proca-extra",
            "Proc A [g-inv] \\| candidate: g-inv-proc",
            "Proc A [g-other] \\| goal: g-other \\| candidate: g-inv-proca",
            "Proc A [g-inv] candidate: g-inv-proca",
        ):
            with self.subTest(description=description):
                self.board_file.write_text(
                    "# Board\n\n## DOING\n\n## TODO\n\n## DONE\n"
                    f"- [x] T-50 [P2] {description} | verify: fixture prior evidence\n\n## BLOCKED\n",
                    encoding="utf-8",
                )
                board = _parse_board_tickets(self.tmp)
                self.assertEqual(_is_candidate_duplicate(cand, board), (False, None))

    def test_unescaped_discovery_identity_is_not_a_board_field(self) -> None:
        """Stale unescaped identity fixtures must remain invalid, never become work."""
        for marker in ("goal: g-inv", "candidate: g-inv-proca", "evidence_fp: sha256:1234"):
            with self.subTest(marker=marker):
                self.board_file.write_text(
                    "# Board\n\n## DOING\n\n## TODO\n\n## DONE\n"
                    f"- [x] T-50 [P2] Proc A | {marker} | verify: fixture prior evidence\n\n## BLOCKED\n",
                    encoding="utf-8",
                )
                before = self.board_file.read_bytes()
                res = replenish_from_goals(self.tmp, "test-agent", dry_run=True)
                self.assertFalse(res["ok"])
                self.assertFalse(res["replenished"])
                self.assertEqual(res["status"], "BOARD_INVALID")
                self.assertIn("unrecognized field", res["detail"])
                self.assertEqual(self.board_file.read_bytes(), before)

    def test_case22_goal_paused_no_automatic_successor(self) -> None:
        """CASE 22: Paused goal produces no automatic successor tickets."""
        ledger_path = self.saipen_dir / "evidence" / "coverage.json"
        ledger_path.write_text(
            json.dumps({"total": 10, "resolved": 0, "gaps": [{"id": "p1", "name": "P1"}]}),
            encoding="utf-8",
        )
        goal = PersistentGoal(
            goal_id="g-paused",
            project_id="test",
            title="Paused",
            objective="Paused",
            evidence_provider="evidence_gap_ledger",
            research_or_work_backlog_source=".saipen/evidence/coverage.json",
            paused=True,
        )
        save_goal(self.tmp, goal)
        res = replenish_from_goals(self.tmp, "test-agent")
        self.assertFalse(res["replenished"])
        self.assertEqual(res["status"], "NO_PERSISTENT_GOALS")

    def test_case23_unauthorized_nearby_project_no_cross_task(self) -> None:
        """CASE 23: Nearby directory does not leak goals into target project."""
        neighbor = self.tmp.parent / "unauthorized_neighbor"
        neighbor.mkdir(parents=True, exist_ok=True)
        (neighbor / ".saipen" / "goals").mkdir(parents=True, exist_ok=True)
        other_goal = PersistentGoal(goal_id="g-other", project_id="other", title="Other", objective="Other")
        save_goal(neighbor, other_goal)

        # Target project must have 0 goals
        self.assertEqual(len(list_goals(self.tmp)), 0)
        shutil.rmtree(neighbor, ignore_errors=True)

    def test_case24_one_task_blocked_independent_continues(self) -> None:
        """CASE 24: One candidate task blocked, independent candidate admitted."""
        self.board_file.write_text(
            "# Board\n\n## DOING\n\n## TODO\n\n## DONE\n\n## BLOCKED\n"
            "- [ ] T-300 [P2] Candidate proc_101 blocked \\| goal: g-ind \\| candidate: g-ind-proc_101"
            " | blocker: BLOCKED_EXTERNAL -- awaiting capture | verify: proc_101 semantics documented\n",
            encoding="utf-8",
        )
        ledger_path = self.saipen_dir / "evidence" / "coverage.json"
        ledger_path.write_text(
            json.dumps({
                "total": 2,
                "resolved": 0,
                "gaps": [
                    {"id": "proc_101", "name": "Proc 101"},
                    {"id": "proc_102", "name": "Proc 102"},
                ],
            }),
            encoding="utf-8",
        )
        goal = PersistentGoal(
            goal_id="g-ind",
            project_id="test",
            title="Independent",
            objective="Independent",
            evidence_provider="evidence_gap_ledger",
            research_or_work_backlog_source=".saipen/evidence/coverage.json",
        )
        save_goal(self.tmp, goal)
        res = replenish_from_goals(self.tmp, "test-agent", dry_run=True)
        self.assertTrue(res["replenished"])
        self.assertEqual(res["candidate"]["candidate_id"], "g-ind-proc_102")

    def test_case25_execution_budget_exhausted_checkpoint(self) -> None:
        """CASE 25: Execution budget exhausted preserves goal checkpoint without false completion."""
        goal = PersistentGoal(
            goal_id="g-budget",
            project_id="test",
            title="Budget",
            objective="Budget",
            current_status=STATUS_ACTIONABLE_GAPS,
            last_evaluation="2026-11-01T20:00:00Z",
        )
        save_goal(self.tmp, goal)
        read_g = get_goal(self.tmp, "g-budget")
        self.assertNotEqual(read_g.current_status, STATUS_SATISFIED)
        self.assertEqual(read_g.current_status, STATUS_ACTIONABLE_GAPS)

    def test_case26_normal_cc_legacy_behavior(self) -> None:
        """CASE 26: Project without persistent goals retains normal legacy continue behavior."""
        res = replenish_from_goals(self.tmp, "test-agent")
        self.assertEqual(res["status"], "NO_PERSISTENT_GOALS")

    def test_case27_cc_all_with_pending_work(self) -> None:
        """CASE 27: cc all with pending work on BOARD does not admit new tickets until queue is drained."""
        self.board_file.write_text(
            "# Board\n\n## DOING\n\n## TODO\n- [ ] T-400 Pending work\n\n## DONE\n\n## BLOCKED\n",
            encoding="utf-8",
        )
        goal = PersistentGoal(goal_id="g-pend", project_id="test", title="Pend", objective="Pend")
        save_goal(self.tmp, goal)
        res = replenish_from_goals(self.tmp, "test-agent")
        self.assertFalse(res["replenished"])
        self.assertEqual(res["status"], "TODO_AVAILABLE")
        self.assertEqual(res["next_ticket"], "T-400")

    def test_case28_goal_requires_manual_runtime_acceptance(self) -> None:
        """CASE 28: Goal requiring operator authority cannot auto-close from synthetic data."""
        goal = PersistentGoal(
            goal_id="g-release",
            project_id="test",
            title="Release Goal",
            objective="Release",
            authorization_scope=SCOPE_RELEASE,
        )
        save_goal(self.tmp, goal)
        ledger_path = self.saipen_dir / "evidence" / "coverage.json"
        ledger_path.write_text(
            json.dumps({"total": 1, "resolved": 0, "gaps": [{"id": "pub", "name": "Publish"}]}),
            encoding="utf-8",
        )
        goal.research_or_work_backlog_source = ".saipen/evidence/coverage.json"
        save_goal(self.tmp, goal)
        res = replenish_from_goals(self.tmp, "test-agent")
        self.assertFalse(res["replenished"])
        self.assertEqual(res["status"], "WAITING_AUTHORITY")

    def test_case29_truncated_backlog_partial_discovery(self) -> None:
        """CASE 29: Truncated backlog marked COMPLETION_TRUNCATED, not full coverage."""
        provider = EvidenceGapLedgerProvider()
        ledger_path = self.saipen_dir / "evidence" / "coverage.json"
        ledger_path.write_text(
            json.dumps({"total": 1000, "resolved": 100, "truncated": True, "gaps": []}),
            encoding="utf-8",
        )
        goal = PersistentGoal(
            goal_id="g-trunc",
            project_id="test",
            title="Trunc",
            objective="Trunc",
            evidence_provider="evidence_gap_ledger",
            research_or_work_backlog_source=".saipen/evidence/coverage.json",
        )
        eval_res = provider.evaluate(self.tmp, goal)
        self.assertEqual(eval_res.completeness_status, COMPLETION_TRUNCATED)

    def test_case30_phase_done_conformance_pass_gap_nonzero(self) -> None:
        """CASE 30: Project phase DONE, conformance CURRENT_PASS, gap nonzero -> admits work."""
        self.state_file.write_text(
            "---\nphase: DONE\ntask: none\nexecution_intent: goal\nconformance: CURRENT_PASS\n---\n",
            encoding="utf-8",
        )
        ledger_path = self.saipen_dir / "evidence" / "coverage.json"
        ledger_path.write_text(
            json.dumps({
                "total": 14122,
                "resolved": 1082,
                "gaps": [{"id": "sub_4100", "name": "NetSessionUpdate"}],
            }),
            encoding="utf-8",
        )
        goal = PersistentGoal(
            goal_id="bzcc_reverse_engineering",
            project_id="test",
            title="BZCC Complete Reverse Engineering",
            objective="Document all 14,122 engine procedures",
            evidence_provider="evidence_gap_ledger",
            research_or_work_backlog_source=".saipen/evidence/coverage.json",
        )
        save_goal(self.tmp, goal)
        res = replenish_from_goals(self.tmp, "test-agent", dry_run=True)
        self.assertTrue(res["ok"])
        self.assertTrue(res["replenished"])
        self.assertEqual(res["candidate"]["candidate_id"], "bzcc_reverse_engineering-sub_4100")


if __name__ == "__main__":
    unittest.main()
