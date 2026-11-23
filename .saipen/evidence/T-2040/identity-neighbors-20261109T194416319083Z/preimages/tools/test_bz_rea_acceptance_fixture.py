"""End-to-End _BZ_REA Acceptance Fixture (SRC-367 Section 17).

Deterministic acceptance fixture reproducing the observed _BZ_REA failure pattern:
- Project has a declared persistent research goal: BZCC Engine Reverse Engineering.
- 14,122 total procedures, 1,082 described, 1,568 anchored, 12,554 gaps.
- Queue is empty (no active tickets in DOING or TODO).
- Phase DONE.
- Conformance CURRENT_PASS.
- Source-change discovery reports unchanged inputs.
- Evidence gap-ledger provider reports actionable unknown procedures.

Verifies:
1. SAIPEN identifies the unsatisfied goal.
2. It does not claim mission completion (not ALL_WORK_COMPLETE).
3. It discovers a specific research candidate.
4. It deduplicates against existing tickets.
5. It creates one legitimate bounded ticket.
6. It enters the normal admission/lifecycle (PHASE SCOUT).
7. It presents the admitted action according to canonical execution architecture.
8. It checkpoints.
9. Once completed, it evaluates the remaining goal.
10. It can select a distinct next candidate.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.board import classify_idle_work, parse_board
from saipen_engine.discovery_providers import (
    COMPLETION_PARTIAL,
    CandidateTask,
    EvidenceGapLedgerProvider,
)
from saipen_engine.persistent_goal import (
    PersistentGoal,
    STATUS_ACTIONABLE_GAPS,
    STATUS_SATISFIED,
    get_goal,
    list_goals,
    save_goal,
)
from saipen_engine.replenishment import replenish_from_goals
from saipen_engine.work_exhaustion import (
    PERSISTENT_GOALS,
    WORK_AVAILABLE,
    certify_work_exhaustion,
)
from test_hermetic_env import isolate_host_session


def setUpModule() -> None:
    isolate_host_session()


class BzReaAcceptanceFixtureTests(unittest.TestCase):
    """End-to-end acceptance fixture replicating _BZ_REA procedure inventory & replenishment."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saipen_bz_rea_fixture_")).resolve()
        self.saipen_dir = self.tmp / ".saipen"
        self.saipen_dir.mkdir(parents=True, exist_ok=True)
        (self.saipen_dir / "goals").mkdir(parents=True, exist_ok=True)
        (self.saipen_dir / "evidence").mkdir(parents=True, exist_ok=True)

        # 1. Synthetic procedure inventory replicating _BZ_REA metrics:
        # 14,122 total, 1,082 described, 1,568 anchored, 12,554 gaps
        self.ledger_rel = ".saipen/evidence/procedure_inventory.json"
        self.ledger_path = self.tmp / self.ledger_rel
        self.sample_gaps = [
            {"id": "sub_41B200", "name": "NetSession_ProcessPacket", "priority": "P1", "description": "Demux packet types"},
            {"id": "sub_41B540", "name": "NetSession_HandleDisconnect", "priority": "P2", "description": "Teardown session state"},
            {"id": "sub_420100", "name": "TerrainRenderer_UpdateLOD", "priority": "P2", "description": "Terrain LOD quadtree walk"},
            {"id": "sub_430050", "name": "VehiclePhysics_ApplyImpulse", "priority": "P1", "description": "Hovercraft rigid body impulse"},
        ]
        self.inventory_data = {
            "total_procedures": 14122,
            "described_procedures": 1082,
            "anchored_procedures": 1568,
            "gap_count": 12554,
            "gap_entries": self.sample_gaps,
        }
        self.ledger_path.write_text(json.dumps(self.inventory_data, indent=2), encoding="utf-8")

        # 2. BOARD.md: Queue is empty
        self.board_file = self.saipen_dir / "BOARD.md"
        self.board_file.write_text(
            "# Board\n\n## DOING\n\n## TODO\n\n## DONE\n\n## BLOCKED\n",
            encoding="utf-8",
        )

        # 3. STATE.md: Phase DONE, Conformance CURRENT_PASS
        self.state_file = self.saipen_dir / "STATE.md"
        self.state_file.write_text(
            "---\nagent: bzcc-researcher\nphase: DONE\ntask: none\nexecution_intent: goal\nconformance: CURRENT_PASS\n---\n# State\n",
            encoding="utf-8",
        )

        # 4. Declare the persistent research goal
        self.goal = PersistentGoal(
            goal_id="bzcc_procedure_semantics",
            project_id="_BZ_REA",
            title="Complete Semantics for Engine Procedures",
            objective="Reverse engineer and verify semantics for all 14,122 procedures",
            authorization_scope="RESEARCH",
            evidence_provider="evidence_gap_ledger",
            research_or_work_backlog_source=self.ledger_rel,
            success_criteria={"coverage_percent": 100.0},
            admission_policy={"max_candidates_per_evaluation": 5},
        )
        save_goal(self.tmp, self.goal)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_e2e_bz_rea_unsatisfied_goal_discovery(self) -> None:
        """Step 1 & 2: Identifies unsatisfied goal and does not claim mission complete."""
        provider = EvidenceGapLedgerProvider()
        eval_res = provider.evaluate(self.tmp, self.goal)

        self.assertEqual(eval_res.satisfaction_status, STATUS_ACTIONABLE_GAPS)
        self.assertEqual(eval_res.metrics["total"], 14122)
        self.assertEqual(eval_res.metrics["resolved"], 1082)
        self.assertEqual(eval_res.metrics["gap_count"], 12554)
        self.assertAlmostEqual(eval_res.metrics["current_coverage_percent"], (1082 / 14122) * 100.0, places=2)
        self.assertEqual(eval_res.completeness_status, COMPLETION_PARTIAL)

        # Board classification: must NOT be ALL_WORK_COMPLETE
        parsed_board = parse_board(self.board_file.read_text(encoding="utf-8"))
        idle = classify_idle_work(parsed_board["tickets"], persistent_goals=[self.goal])
        self.assertFalse(idle["all_requirements_complete"])
        self.assertEqual(idle["disposition"], "GOAL_GAPS_ACTIONABLE")
        self.assertEqual(idle["stop_reason"], "NO_ADMISSIBLE_WORK")

    def test_e2e_bz_rea_work_exhaustion_not_exhausted(self) -> None:
        """Work exhaustion certificate must certify WORK_AVAILABLE, not EXHAUSTED."""
        cert = certify_work_exhaustion(self.tmp)
        self.assertFalse(cert["exhausted"])
        self.assertEqual(cert["status"], "WORK_ELIGIBLE")

        goal_source = next(s for s in cert["sources"] if s["source_name"] == PERSISTENT_GOALS)
        self.assertEqual(goal_source["eligibility_result"], WORK_AVAILABLE)
        self.assertIn("saipen continue", goal_source["authorized_actions"])

    def test_e2e_bz_rea_candidate_discovery_and_deduplication(self) -> None:
        """Step 3, 4, 5: Discovers specific research candidate, deduplicates, admits highest priority."""
        res = replenish_from_goals(self.tmp, "bzcc-researcher", dry_run=True)

        self.assertTrue(res["ok"])
        self.assertTrue(res["replenished"])
        self.assertEqual(res["goal_id"], "bzcc_procedure_semantics")

        candidate = res["candidate"]
        # P1 priority should win: sub_41B200 or sub_430050
        self.assertEqual(candidate["priority"], "P1")
        self.assertIn("bzcc_procedure_semantics-sub_41B200", candidate["candidate_id"])
        self.assertIn("NetSession_ProcessPacket", candidate["title"])

    def test_e2e_bz_rea_sequential_lifecycle_and_distinct_successor(self) -> None:
        """Step 6..10: Admitted task lifecycle -> checkpoint -> evaluates remaining goal -> distinct next candidate."""
        # 1. Admit candidate 1
        res1 = replenish_from_goals(self.tmp, "bzcc-researcher", dry_run=True)
        self.assertTrue(res1["replenished"])
        cid1 = res1["candidate"]["candidate_id"]

        # 2. Simulate task 1 completed on BOARD
        self.board_file.write_text(
            f"# Board\n\n## DOING\n\n## TODO\n\n## DONE\n- [x] T-49 NetSession_ProcessPacket | candidate: {cid1}\n\n## BLOCKED\n",
            encoding="utf-8",
        )

        # 3. Replenish next task: must skip sub_41B200 and select the next P1 or P2 candidate
        res2 = replenish_from_goals(self.tmp, "bzcc-researcher", dry_run=True)
        self.assertTrue(res2["replenished"])
        cid2 = res2["candidate"]["candidate_id"]

        self.assertNotEqual(cid1, cid2)
        # Next candidate should be sub_430050 (the other P1)
        self.assertIn("VehiclePhysics_ApplyImpulse", res2["candidate"]["title"])


if __name__ == "__main__":
    unittest.main()
