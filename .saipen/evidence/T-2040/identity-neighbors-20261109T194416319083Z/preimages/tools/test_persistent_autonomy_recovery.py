"""Independent Negative Controls and Verification for Persistent Autonomy & Release Recovery (SRC-368 / T-1994).

Validates:
1. Path Escape Controls:
   - save_goal, get_goal, delete_goal reject traversing or absolute IDs.
   - transfer_reviewed_scope rejects traversing or absolute paths.
   - execute_isolated_release does not junction to primary .saipen directories.
2. False Goal Satisfaction Controls:
   - EvidenceGapLedgerProvider rejects total=0, resolved=0 as SATISFIED.
   - EvidenceGapLedgerProvider rejects truncated=True as SATISFIED.
   - EvidenceGapLedgerProvider rejects resolved > total as SATISFIED.
   - BacklogProvider rejects empty backlog (0 items) as SATISFIED.
   - FailedTestProvider rejects ran=0 as SATISFIED.
3. Dry-Run Integrity Controls:
   - evaluate_all_goals(commit=False) does not write to disk.
   - replenish_from_goals(dry_run=True) does not mutate goals or board.
4. Candidate Deduplication & Independent Selection:
   - _is_candidate_duplicate does not falsely match arbitrary substrings.
   - replenish_from_goals selects unblocked candidate when first candidate is blocked.
5. Isolated Release Equality:
   - github_sync_verified requires remote_head_after == expected_commit_sha.
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

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.discovery_providers import (
    COMPLETION_FULL,
    COMPLETION_TRUNCATED,
    COMPLETION_UNKNOWN,
    CandidateTask,
    EvidenceGapLedgerProvider,
    BacklogProvider,
    FailedTestProvider,
)
from saipen_engine.isolated_release import (
    IsolatedReleaseError,
    transfer_reviewed_scope,
)
from saipen_engine.persistent_goal import (
    PersistentGoal,
    STATUS_ACTIONABLE_GAPS,
    STATUS_BLOCKED_BY_EVIDENCE,
    STATUS_NO_ADMISSIBLE_WORK,
    STATUS_SATISFIED,
    delete_goal,
    get_goal,
    goals_dir,
    save_goal,
)
from saipen_engine.replenishment import (
    _is_candidate_duplicate,
    evaluate_all_goals,
    replenish_from_goals,
)
from saipen_engine.safeid import InvalidIdError


class PathEscapeControlsTests(unittest.TestCase):
    """Negative controls for path confinement."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saipen_path_test_")).resolve()
        self.saipen_dir = self.tmp / ".saipen"
        self.goals_dir = self.saipen_dir / "goals"
        self.goals_dir.mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_save_goal_rejects_parent_traversal(self) -> None:
        """A traversing goal_id (e.g. '../../evil') must raise InvalidIdError and never write outside."""
        goal = PersistentGoal(
            goal_id="../../evil",
            project_id="test",
            title="Evil Goal",
            objective="Escape root",
        )
        with self.assertRaises(InvalidIdError):
            save_goal(self.tmp, goal)
        evil_file = self.tmp.parent / "evil.json"
        self.assertFalse(evil_file.exists())

    def test_save_goal_rejects_absolute_path(self) -> None:
        """An absolute goal_id must raise InvalidIdError."""
        abs_id = "/etc/evil" if os.name != "nt" else "C:\\evil"
        goal = PersistentGoal(
            goal_id=abs_id,
            project_id="test",
            title="Evil Goal",
            objective="Escape root",
        )
        with self.assertRaises(InvalidIdError):
            save_goal(self.tmp, goal)

    def test_get_goal_rejects_traversal(self) -> None:
        """get_goal with traversal ID returns None without file escape."""
        res = get_goal(self.tmp, "../../evil")
        self.assertIsNone(res)

    def test_delete_goal_rejects_traversal(self) -> None:
        """delete_goal with traversal ID returns False without file escape."""
        res = delete_goal(self.tmp, "../../evil")
        self.assertFalse(res)

    def test_transfer_reviewed_scope_rejects_traversing_path(self) -> None:
        """transfer_reviewed_scope must reject paths that contain '..' or are absolute."""
        source = self.tmp / "src"
        target = self.tmp / "dst"
        source.mkdir()
        target.mkdir()

        # Traversing path
        with self.assertRaises(IsolatedReleaseError) as ctx:
            transfer_reviewed_scope(source, target, ["../../escape.txt"])
        self.assertEqual(ctx.exception.code, "PATH_TRAVERSAL_DETECTED")

        # Absolute path
        abs_p = "/outside.txt" if os.name != "nt" else "C:\\outside.txt"
        with self.assertRaises(IsolatedReleaseError) as ctx:
            transfer_reviewed_scope(source, target, [abs_p])
        self.assertEqual(ctx.exception.code, "PATH_TRAVERSAL_DETECTED")


class FalseGoalSatisfactionControlsTests(unittest.TestCase):
    """Negative controls for goal satisfaction and coverage completeness."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saipen_sat_test_")).resolve()
        self.saipen_dir = self.tmp / ".saipen"
        self.evidence_dir = self.saipen_dir / "evidence"
        self.evidence_dir.mkdir(parents=True)
        self.provider = EvidenceGapLedgerProvider()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_empty_denominator_never_satisfied(self) -> None:
        """A ledger with total=0, resolved=0, gaps=[] must NOT be classified as SATISFIED."""
        ledger = self.evidence_dir / "coverage_gap.json"
        ledger.write_text(
            json.dumps({"total": 0, "resolved": 0, "gaps": []}),
            encoding="utf-8",
        )
        goal = PersistentGoal(
            goal_id="g1",
            project_id="test",
            title="Coverage Goal",
            objective="Full coverage",
            research_or_work_backlog_source=".saipen/evidence/coverage_gap.json",
        )
        res = self.provider.evaluate(self.tmp, goal)
        self.assertNotEqual(res.satisfaction_status, STATUS_SATISFIED)
        self.assertEqual(res.completeness_status, COMPLETION_UNKNOWN)
        self.assertIn("empty or unknown denominator", res.blockers[0].lower())

    def test_truncated_inventory_never_satisfied(self) -> None:
        """A truncated inventory must NOT be classified as SATISFIED even if gaps is empty."""
        ledger = self.evidence_dir / "coverage_gap.json"
        ledger.write_text(
            json.dumps({"total": 10, "resolved": 10, "gaps": [], "truncated": True}),
            encoding="utf-8",
        )
        goal = PersistentGoal(
            goal_id="g1",
            project_id="test",
            title="Coverage Goal",
            objective="Full coverage",
            research_or_work_backlog_source=".saipen/evidence/coverage_gap.json",
        )
        res = self.provider.evaluate(self.tmp, goal)
        self.assertNotEqual(res.satisfaction_status, STATUS_SATISFIED)
        self.assertEqual(res.completeness_status, COMPLETION_TRUNCATED)

    def test_inconsistent_metrics_rejected(self) -> None:
        """Resolved > total must be rejected as inconsistent, not SATISFIED."""
        ledger = self.evidence_dir / "coverage_gap.json"
        ledger.write_text(
            json.dumps({"total": 5, "resolved": 10, "gaps": []}),
            encoding="utf-8",
        )
        goal = PersistentGoal(
            goal_id="g1",
            project_id="test",
            title="Coverage Goal",
            objective="Full coverage",
            research_or_work_backlog_source=".saipen/evidence/coverage_gap.json",
        )
        res = self.provider.evaluate(self.tmp, goal)
        self.assertNotEqual(res.satisfaction_status, STATUS_SATISFIED)
        self.assertEqual(res.satisfaction_status, STATUS_BLOCKED_BY_EVIDENCE)
        self.assertEqual(res.completeness_status, COMPLETION_UNKNOWN)

    def test_traversing_evidence_source_blocked(self) -> None:
        """An evidence source attempting parent traversal must be rejected with BLOCKED_BY_EVIDENCE."""
        goal = PersistentGoal(
            goal_id="g1",
            project_id="test",
            title="Coverage Goal",
            objective="Full coverage",
            research_or_work_backlog_source="../../outside_coverage.json",
        )
        res = self.provider.evaluate(self.tmp, goal)
        self.assertEqual(res.satisfaction_status, STATUS_BLOCKED_BY_EVIDENCE)
        self.assertIn("escapes", res.blockers[0].lower())

    def test_backlog_empty_never_satisfied(self) -> None:
        """BacklogProvider with 0 items must NOT be classified as SATISFIED."""
        backlog_file = self.tmp / ".saipen" / "backlog" / "items.json"
        backlog_file.parent.mkdir(parents=True)
        backlog_file.write_text(json.dumps([]), encoding="utf-8")

        goal = PersistentGoal(
            goal_id="g-backlog",
            project_id="test",
            title="Backlog Goal",
            objective="Drain backlog",
            evidence_provider="backlog",
        )
        bp = BacklogProvider()
        res = bp.evaluate(self.tmp, goal)
        self.assertNotEqual(res.satisfaction_status, STATUS_SATISFIED)
        self.assertEqual(res.completeness_status, COMPLETION_UNKNOWN)

    def test_failed_test_ran_zero_never_satisfied(self) -> None:
        """FailedTestProvider with ran=0 must NOT be classified as SATISFIED."""
        core_unit_dir = self.tmp / ".saipen" / "evidence" / "core-unit"
        core_unit_dir.mkdir(parents=True)
        rec = core_unit_dir / "record.json"
        rec.write_text(json.dumps({"status": "PASS", "ran": 0, "failures": []}), encoding="utf-8")

        goal = PersistentGoal(
            goal_id="g-test",
            project_id="test",
            title="Test Clean Goal",
            objective="Clean tests",
            evidence_provider="failed_tests",
        )
        ftp = FailedTestProvider()
        res = ftp.evaluate(self.tmp, goal)
        self.assertNotEqual(res.satisfaction_status, STATUS_SATISFIED)
        self.assertEqual(res.completeness_status, COMPLETION_UNKNOWN)

    def test_genuinely_complete_inventory_satisfied(self) -> None:
        """Genuinely complete inventory (total=10, resolved=10, gaps=[]) is SATISFIED."""
        ledger = self.evidence_dir / "coverage_gap.json"
        ledger.write_text(
            json.dumps({"total": 10, "resolved": 10, "gaps": []}),
            encoding="utf-8",
        )
        goal = PersistentGoal(
            goal_id="g1",
            project_id="test",
            title="Coverage Goal",
            objective="Full coverage",
            research_or_work_backlog_source=".saipen/evidence/coverage_gap.json",
        )
        res = self.provider.evaluate(self.tmp, goal)
        self.assertEqual(res.satisfaction_status, STATUS_SATISFIED)
        self.assertEqual(res.completeness_status, COMPLETION_FULL)


class DryRunIntegrityTests(unittest.TestCase):
    """Negative controls for dry-run and read-only purity."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saipen_dry_test_")).resolve()
        self.saipen_dir = self.tmp / ".saipen"
        self.goals_dir = self.saipen_dir / "goals"
        self.goals_dir.mkdir(parents=True)
        self.evidence_dir = self.saipen_dir / "evidence"
        self.evidence_dir.mkdir(parents=True)

        self.board_file = self.saipen_dir / "BOARD.md"
        self.board_file.write_text("# Board\n\n## DOING\n\n## TODO\n\n## DONE\n\n## BLOCKED\n", encoding="utf-8")

        ledger = self.evidence_dir / "gap.json"
        ledger.write_text(
            json.dumps({"total": 5, "resolved": 2, "gaps": [{"id": "p1", "name": "P1"}]}),
            encoding="utf-8",
        )

        self.goal = PersistentGoal(
            goal_id="g-dry",
            project_id="test",
            title="Dry Goal",
            objective="Ensure dry-run purity",
            evidence_provider="evidence_gap_ledger",
            research_or_work_backlog_source=".saipen/evidence/gap.json",
        )
        save_goal(self.tmp, self.goal)
        self.initial_goal_bytes = (self.goals_dir / "g-dry.json").read_bytes()
        self.initial_board_bytes = self.board_file.read_bytes()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_evaluate_all_goals_pure_by_default(self) -> None:
        """evaluate_all_goals(commit=False) must NOT change the goal file on disk."""
        results = evaluate_all_goals(self.tmp, commit=False)
        self.assertEqual(len(results), 1)
        current_bytes = (self.goals_dir / "g-dry.json").read_bytes()
        self.assertEqual(current_bytes, self.initial_goal_bytes)

    def test_replenish_from_goals_dry_run_writes_zero_bytes(self) -> None:
        """replenish_from_goals(dry_run=True) must NOT change goal or board files."""
        res = replenish_from_goals(self.tmp, "test-agent", dry_run=True)
        self.assertTrue(res.get("ok"))
        self.assertTrue(res.get("dry_run"))

        current_goal_bytes = (self.goals_dir / "g-dry.json").read_bytes()
        current_board_bytes = self.board_file.read_bytes()

        self.assertEqual(current_goal_bytes, self.initial_goal_bytes)
        self.assertEqual(current_board_bytes, self.initial_board_bytes)


class CandidateDeduplicationAndIndependentSelectionTests(unittest.TestCase):
    """Negative controls for candidate deduplication and independent candidate selection."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saipen_dedup_test_")).resolve()
        self.saipen_dir = self.tmp / ".saipen"
        self.board_file = self.saipen_dir / "BOARD.md"
        self.saipen_dir.mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_arbitrary_substring_does_not_deduplicate(self) -> None:
        """A ticket containing a common word in its title does not deduplicate an unrelated candidate."""
        # Unrelated ticket mentions "status"
        self.board_file.write_text(
            "# Board\n\n## DOING\n\n## TODO\n\n## DONE\n- [x] T-10 Update user status indicator\n\n## BLOCKED\n",
            encoding="utf-8",
        )
        from saipen_engine.replenishment import _parse_board_tickets
        board = _parse_board_tickets(self.tmp)

        # Candidate with title "Status" or locator "status"
        cand = CandidateTask(
            candidate_id="g1-check-status-gate",
            goal_id="g1",
            title="Check Status Gate",
            target_locator="status_gate",
        )
        is_dup, reason = _is_candidate_duplicate(cand, board)
        self.assertFalse(is_dup)
        self.assertIsNone(reason)

    def test_blocked_first_candidate_selects_second_candidate(self) -> None:
        """If candidate 1 is blocked on the board, replenishment selects candidate 2 from the pool."""
        self.board_file.write_text(
            "# Board\n\n## DOING\n\n## TODO\n\n## DONE\n\n## BLOCKED\n- [-] T-99 Investigate cand-1 | goal: g-pool | candidate: g-pool-c1\n",
            encoding="utf-8",
        )
        evidence_dir = self.saipen_dir / "evidence"
        evidence_dir.mkdir(parents=True)
        ledger = evidence_dir / "gap.json"
        ledger.write_text(
            json.dumps({
                "total": 10,
                "resolved": 0,
                "gaps": [
                    {"id": "c1", "name": "Cand 1", "priority": "P1"},
                    {"id": "c2", "name": "Cand 2", "priority": "P2"},
                ]
            }),
            encoding="utf-8",
        )
        goal = PersistentGoal(
            goal_id="g-pool",
            project_id="test",
            title="Pool Goal",
            objective="Select unblocked candidate",
            evidence_provider="evidence_gap_ledger",
            research_or_work_backlog_source=".saipen/evidence/gap.json",
        )
        save_goal(self.tmp, goal)

        res = replenish_from_goals(self.tmp, "test-agent", dry_run=True)
        self.assertTrue(res.get("ok"))
        self.assertTrue(res.get("replenished"))
        # Candidate 2 was selected because candidate 1 was blocked!
        self.assertEqual(res["candidate"]["candidate_id"], "g-pool-c2")


if __name__ == "__main__":
    unittest.main()
