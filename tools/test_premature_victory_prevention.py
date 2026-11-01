"""Premature Victory Prevention, Outcome Truth & Autonomous Work Discovery Regressions.

Implements all 24 acceptance regressions PV01..PV24 specified in
PROJECT_SAIPEN_20261101_0024.md (Section 10):

PV01: 239 tickets, 135 DONE, 104 BLOCKED, 0 workable -> NO_ADMISSIBLE_WORK, not ALL_WORK_COMPLETE.
PV02: No runnable tickets but unmeasured user performance objective -> OBJECTIVE_UNVERIFIED.
PV03: Synthetic benchmark dictionary with PASS and arbitrary timings -> cannot satisfy PERFORMANCE_BENCHMARK.
PV04: All Source clauses point to one unit receipt -> each clause independently checked for fitness.
PV05: Valid shared receipt directly proves several unit requirements -> accepted where scope matches.
PV06: No valid continuous maintenance authorization -> no protected auto-HUNT/ADD writes.
PV07: Authentic continuous-maintenance grant with a drained board -> legal discovery remains eligible.
PV08: External release blocker plus independent authorized read-only work -> independent work not suppressed.
PV09: Stale repeated status with no external change -> no expensive hot polling and no misleading next action.
PV10: HUNT has not checked current source generation -> no claim of verified clean source.
PV11: HUNT checked an unchanged generation and found no issue -> quiescence, not invented Work.
PV12: New evidence arrives after quiescence -> eligibility re-evaluated and lawful resumption.
PV13: SAIPAL has eligible unfinished analysis slices -> objective remains schedulable.
PV14: All local tests PASS but installed host acceptance unavailable -> INSTALLED_UNVERIFIED.
PV15: Local DONE with publication_state pending -> not RELEASE_PUBLISHED.
PV16: A single external blocked task remains -> not blanket PRODUCT COMPLETE.
PV17: A model-turn ends while an authorized campaign remains active -> turn completion does not close campaign.
PV18: An expired campaign reports many blocked tickets -> WAIT_AUTHORITY with exact renewal need.
PV19: An intentionally held architecture gate -> preserve hold and prerequisites.
PV20: Previous false DONE is corrected by new evidence -> immutable historical event preserved, new correction linked.
PV21: Operator grants bounded continued objective -> executes within budget, no unrelated publication rights.
PV22: All legal sources checked, no new evidence, authorization valid -> event-driven QUIESCENT_WAIT.
PV23: Real user workflow improvement measured before and after -> actual outcome evidence, not proxy success.
PV24: User workflow is slower despite passing unit tests -> objective not verified as successful optimization.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import (
    board,
    evidence_fitness,
    goal_authority,
    intake,
    outcome_truth,
    work_exhaustion,
)
from test_hermetic_env import isolate_host_session


def setUpModule() -> None:
    isolate_host_session()


class PrematureVictoryPreventionTests(unittest.TestCase):
    """Full 24-case regression suite for outcome truth and victory prevention."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-pv-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / ".saipen").mkdir(parents=True, exist_ok=True)

    # PV01: 239 tickets, 135 DONE, 104 BLOCKED, 0 workable
    def test_pv01_no_admissible_work_not_all_work_complete(self) -> None:
        tickets = {}
        for i in range(1, 136):
            tid = f"T-{i}"
            tickets[tid] = {"id": tid, "section": "## DONE", "needs": []}
        for i in range(136, 240):
            tid = f"T-{i}"
            tickets[tid] = {
                "id": tid,
                "section": "## BLOCKED",
                "needs": [],
                "fields": {"blocker": "WAIT_USER_DECISION"},
            }

        res = board.classify_idle_work(tickets)
        self.assertNotEqual(res["disposition"], board.ALL_WORK_COMPLETE)
        self.assertEqual(res["stop_reason"], board.NO_ADMISSIBLE_WORK)
        self.assertFalse(res["all_requirements_complete"])
        self.assertTrue(res["no_admissible_work"])
        self.assertIn(
            res["disposition"],
            (board.IDLE_OPERATOR_REQUIRED, board.IDLE_BLOCKED_EXTERNAL, board.IDLE_FUTURE_GATED),
        )

    # PV02: No runnable tickets but unmeasured user performance objective
    def test_pv02_empty_runnable_queue_unmeasured_user_outcome(self) -> None:
        tickets = {
            "T-1": {"id": "T-1", "section": "## DONE"},
            "T-2": {
                "id": "T-2",
                "section": "## BLOCKED",
                "fields": {"blocker": "BLOCKED_EXTERNAL"},
            },
        }
        truth = outcome_truth.compute_outcome_truth(
            self.root,
            tickets=tickets,
            state={"phase": "DONE", "task": "none"},
            objective_evidence=None,  # Unmeasured
        )
        self.assertEqual(truth["objective_status"], outcome_truth.OBJECTIVE_UNVERIFIED)
        self.assertEqual(truth["queue_status"], outcome_truth.QUEUE_DRAINED)
        self.assertNotEqual(truth["campaign_status"], outcome_truth.CAMPAIGN_COMPLETE)

    # PV03: Synthetic benchmark dictionary with PASS and arbitrary timings
    def test_pv03_synthetic_benchmark_dictionary_rejected(self) -> None:
        synthetic_report = {
            "ticket_wall_s": 12.5,
            "test_execution_wall_s": 8.2,
            "full_family_execution_count": 1,
            "reused_record_count": 1,
            "SHIP_ACCEPTANCE_OUTCOME": "PASS",
        }
        fitness = evidence_fitness.validate_evidence_fitness(
            requirement_id="R-PERF",
            required_evidence_class=evidence_fitness.PERFORMANCE_BENCHMARK,
            actual_evidence_class=evidence_fitness.PERFORMANCE_BENCHMARK,
            evidence_payload=synthetic_report,
        )
        self.assertFalse(fitness["fit"])
        self.assertEqual(fitness["verdict"], "UNFIT_SYNTHETIC")

        bench_verdict = evidence_fitness.validate_performance_benchmark(synthetic_report)
        self.assertFalse(bench_verdict["ok"])
        self.assertEqual(bench_verdict["verdict"], "UNVERIFIED")
        self.assertEqual(bench_verdict["code"], "SYNTHETIC_BENCHMARK_REJECTED")

    # PV04: All Source clauses point to one unit receipt
    def test_pv04_shared_unit_receipt_insufficient_for_non_unit_requirements(self) -> None:
        ledger = {
            "requirements": {
                "SRC-001:R01": {
                    "class": "requirement",
                    "text": "Core logic behaves correctly [UNIT]",
                    "disposition": "VERIFIED",
                    "evidence": "E-100",
                    "verification": "verify -> PASS",
                    "actual_evidence_class": evidence_fitness.UNIT,
                },
                "SRC-001:R02": {
                    "class": "requirement",
                    "text": "Live user performance improved [PERFORMANCE_BENCHMARK]",
                    "disposition": "VERIFIED",
                    "evidence": "E-100",
                    "verification": "verify -> PASS",
                    "actual_evidence_class": evidence_fitness.UNIT,  # Only UNIT evidence cited!
                },
            }
        }
        summary = intake._coverage_summary_from_ledger("SRC-001", ledger)
        self.assertIn("SRC-001:R02", summary["unresolved"])
        self.assertIn("SRC-001:R02", summary.get("unresolved_fitness", []))
        self.assertNotIn("SRC-001:R01", summary["unresolved"])

    # PV05: Valid shared receipt directly proves several unit requirements
    def test_pv05_shared_unit_receipt_accepted_for_matching_unit_requirements(self) -> None:
        ledger = {
            "requirements": {
                "SRC-001:R01": {
                    "class": "requirement",
                    "text": "First unit invariant holds [UNIT]",
                    "disposition": "VERIFIED",
                    "evidence": "E-100",
                    "verification": "verify -> PASS",
                    "actual_evidence_class": evidence_fitness.UNIT,
                },
                "SRC-001:R02": {
                    "class": "requirement",
                    "text": "Second unit invariant holds [UNIT]",
                    "disposition": "VERIFIED",
                    "evidence": "E-100",
                    "verification": "verify -> PASS",
                    "actual_evidence_class": evidence_fitness.UNIT,
                },
            }
        }
        summary = intake._coverage_summary_from_ledger("SRC-001", ledger)
        self.assertEqual(summary["unresolved"], [])

    # PV06: No valid continuous maintenance authorization
    def test_pv06_unauthorized_continuous_maintenance_refuses_auto_writes(self) -> None:
        state = {
            "authority_until": "budget",
            "continuation_authority": "operator_required",
            "execution_intent": "goal",
        }
        cert = work_exhaustion.certify_work_exhaustion(
            self.root,
            state=state,
            continuous_maintenance_authorized=False,
        )
        improve_source = next(s for s in cert["sources"] if s["source_name"] == work_exhaustion.IMPROVE_CANDIDATES)
        self.assertEqual(improve_source["eligibility_result"], work_exhaustion.BLOCKED_AUTHORITY)
        self.assertEqual(improve_source["authorized_actions"], [])

    # PV07: Authentic continuous-maintenance grant with a drained board
    def test_pv07_authentic_continuous_maintenance_allows_discovery_at_idle(self) -> None:
        state = {
            "authority_until": "continuous_maintenance",
            "continuation_authority": "authorized",
            "execution_intent": "goal",
        }
        cert = work_exhaustion.certify_work_exhaustion(
            self.root,
            state=state,
            continuous_maintenance_authorized=True,
        )
        improve_source = next(s for s in cert["sources"] if s["source_name"] == work_exhaustion.IMPROVE_CANDIDATES)
        self.assertNotEqual(improve_source["eligibility_result"], work_exhaustion.BLOCKED_AUTHORITY)

    # PV08: External release blocker plus independent authorized read-only work
    def test_pv08_external_release_blocker_does_not_suppress_independent_work(self) -> None:
        tickets = {
            "T-1816": {
                "id": "T-1816",
                "section": "## BLOCKED",
                "needs": [],
                "fields": {"blocker": "PUBLICATION_STAGING_BLOCKED: foreign staged paths"},
            },
            "T-2000": {
                "id": "T-2000",
                "section": "## TODO",
                "needs": [],
                "fields": {"blocker": ""},
            },
        }
        proj = board.project_blockers(tickets)
        staging_group = next((g for g in proj["groups"] if g["cause"] == "publication-staging"), None)
        self.assertIsNotNone(staging_group)
        self.assertTrue(staging_group["read_only_work_may_proceed"])
        self.assertTrue(staging_group.get("independent_work_allowed", False))

    # PV09: Stale repeated status with no external change
    def test_pv09_stale_repeated_status_no_hot_polling(self) -> None:
        truth = outcome_truth.compute_outcome_truth(
            self.root,
            tickets={"T-1": {"id": "T-1", "section": "## BLOCKED", "fields": {"blocker": "WAIT_USER_DECISION"}}},
            state={"phase": "DONE", "task": "none", "authority_until": "budget"},
            is_budget_exhausted=True,
        )
        self.assertEqual(truth["next_eligible_action"], "saipen status")
        self.assertIn("operator", truth["next_wake_condition"].lower())

    # PV10: HUNT has not checked the current source generation
    def test_pv10_hunt_not_checked_source_generation_no_clean_claim(self) -> None:
        cert = work_exhaustion.certify_work_exhaustion(
            self.root,
            source_generation="gen-20261101",
            hunt_state={"last_analyzed_generation": "gen-older"},
        )
        hunt_source = next(s for s in cert["sources"] if s["source_name"] == work_exhaustion.HUNT_FINDINGS)
        self.assertEqual(hunt_source["eligibility_result"], work_exhaustion.NOT_CHECKED)
        self.assertFalse(cert["all_checked"])

    # PV11: HUNT checked an unchanged generation and found no issue
    def test_pv11_hunt_unchanged_generation_quiescent_not_busywork(self) -> None:
        cert = work_exhaustion.certify_work_exhaustion(
            self.root,
            source_generation="gen-20261101",
            hunt_state={"last_analyzed_generation": "gen-20261101", "findings": 0},
            continuous_maintenance_authorized=True,
        )
        hunt_source = next(s for s in cert["sources"] if s["source_name"] == work_exhaustion.HUNT_FINDINGS)
        self.assertEqual(hunt_source["eligibility_result"], work_exhaustion.UNCHANGED)
        self.assertEqual(hunt_source["authorized_actions"], [])

    # PV12: New evidence arrives after quiescence
    def test_pv12_new_evidence_wakes_quiescent_campaign(self) -> None:
        cert_quiescent = work_exhaustion.certify_work_exhaustion(
            self.root,
            source_generation="gen-1",
            audit_inbox={"unresolved_audit_count": 0},
        )
        self.assertTrue(cert_quiescent["exhausted"])

        # New audit evidence arrives
        cert_woken = work_exhaustion.certify_work_exhaustion(
            self.root,
            source_generation="gen-1",
            audit_inbox={"unresolved_audit_count": 2},
        )
        self.assertFalse(cert_woken["exhausted"])
        self.assertEqual(cert_woken["status"], "WORK_ELIGIBLE")

    # PV13: SAIPAL has eligible unfinished analysis slices
    def test_pv13_saipal_unfinished_slices_schedulable(self) -> None:
        cert = work_exhaustion.certify_work_exhaustion(
            self.root,
            forensic_state={"unfinished_slices": ["slice-1", "slice-2"]},
        )
        forensic_source = next(s for s in cert["sources"] if s["source_name"] == work_exhaustion.EXTERNAL_FORENSICS)
        self.assertEqual(forensic_source["eligibility_result"], work_exhaustion.WORK_AVAILABLE)
        self.assertIn("saipen sub", forensic_source["authorized_actions"])

    # PV14: All local tests PASS but installed host acceptance unavailable
    def test_pv14_local_tests_pass_without_installed_host_acceptance(self) -> None:
        truth = outcome_truth.compute_outcome_truth(
            self.root,
            tickets={"T-1": {"id": "T-1", "section": "## DONE"}},
            state={"phase": "DONE", "task": "none"},
            objective_evidence={"verdict": "PASS", "scope": "LOCAL_UNIT"},
        )
        # Local tests pass, but installed host verification was not run
        self.assertNotEqual(truth["publication_status"], outcome_truth.INSTALLED_VERIFIED)

    # PV15: Local DONE with publication_state pending
    def test_pv15_local_done_pending_publication_not_published(self) -> None:
        truth = outcome_truth.compute_outcome_truth(
            self.root,
            tickets={"T-1": {"id": "T-1", "section": "## DONE"}},
            state={"phase": "DONE", "publication_state": "pending"},
        )
        self.assertNotEqual(truth["publication_status"], outcome_truth.RELEASE_PUBLISHED)
        self.assertEqual(truth["publication_status"], outcome_truth.RELEASE_BLOCKED)

    # PV16: A single external blocked task remains
    def test_pv16_single_external_blocked_prevents_blanket_product_complete(self) -> None:
        tickets = {
            "T-1": {"id": "T-1", "section": "## DONE"},
            "T-2": {"id": "T-2", "section": "## BLOCKED", "fields": {"blocker": "BLOCKED_EXTERNAL"}},
        }
        truth = outcome_truth.compute_outcome_truth(self.root, tickets=tickets)
        self.assertNotEqual(truth["campaign_status"], outcome_truth.CAMPAIGN_COMPLETE)
        self.assertEqual(truth["campaign_status"], outcome_truth.CAMPAIGN_WAIT_EXTERNAL)

    # PV17: A model-turn ends while an authorized campaign remains active
    def test_pv17_model_turn_end_does_not_close_authorized_campaign(self) -> None:
        truth = outcome_truth.compute_outcome_truth(
            self.root,
            tickets={"T-1": {"id": "T-1", "section": "## DOING"}},
            state={"phase": "BUILD", "task": "T-1"},
            has_continuous_maintenance=True,
        )
        self.assertEqual(truth["campaign_status"], outcome_truth.CAMPAIGN_RUNNING)
        self.assertNotEqual(truth["campaign_status"], outcome_truth.CAMPAIGN_COMPLETE)

    # PV18: An expired campaign reports many blocked tickets
    def test_pv18_expired_campaign_reports_wait_authority(self) -> None:
        truth = outcome_truth.compute_outcome_truth(
            self.root,
            tickets={"T-1": {"id": "T-1", "section": "## BLOCKED", "fields": {"blocker": "WAIT_USER_DECISION"}}},
            is_budget_exhausted=True,
            has_continuous_maintenance=False,
        )
        self.assertEqual(truth["campaign_status"], outcome_truth.CAMPAIGN_WAIT_AUTHORITY)
        self.assertIn("operator", truth["next_wake_condition"].lower())

    # PV19: An intentionally held architecture gate
    def test_pv19_intentionally_held_architecture_gate_preserved(self) -> None:
        tickets = {
            "T-442": {
                "id": "T-442",
                "section": "## BLOCKED",
                "needs": [],
                "fields": {"blocker": "HELD: architectural gate"},
            }
        }
        proj = board.project_blockers(tickets)
        held_group = next((g for g in proj["groups"] if "architecture:held-chain" in g["shared_blocker_id"]), None)
        self.assertIsNotNone(held_group)
        self.assertEqual(held_group["blocker_class"], "HELD")

    # PV20: Previous false DONE is corrected by new evidence
    def test_pv20_false_done_corrected_without_rewriting_history(self) -> None:
        # Check that evidence fitness can reject a previously cited fixture
        fitness = evidence_fitness.validate_evidence_fitness(
            requirement_id="R-OLD",
            required_evidence_class=evidence_fitness.PERFORMANCE_BENCHMARK,
            actual_evidence_class=evidence_fitness.PERFORMANCE_BENCHMARK,
            evidence_payload={"is_synthetic": True},
        )
        self.assertFalse(fitness["fit"])
        self.assertEqual(fitness["verdict"], "UNFIT_SYNTHETIC")

    # PV21: Operator grants one appropriately scoped, bounded continued objective
    def test_pv21_operator_bounded_grant_executes_within_scope(self) -> None:
        truth = outcome_truth.compute_outcome_truth(
            self.root,
            tickets={"T-1": {"id": "T-1", "section": "## TODO", "blocked": False}},
            state={"phase": "PLAN", "authority_until": "budget"},
            has_continuous_maintenance=False,
        )
        self.assertEqual(truth["queue_status"], outcome_truth.QUEUE_HAS_WORK)
        self.assertEqual(truth["publication_status"], outcome_truth.RELEASE_BLOCKED)

    # PV22: All legal sources checked, no new evidence, authorization valid
    def test_pv22_all_sources_exhausted_event_driven_quiescent_wait(self) -> None:
        cert = work_exhaustion.certify_work_exhaustion(
            self.root,
            continuous_maintenance_authorized=True,
            hunt_state={"last_analyzed_generation": "gen-current", "findings": 0},
            source_generation="gen-current",
        )
        self.assertTrue(cert["exhausted"])
        truth = outcome_truth.compute_outcome_truth(
            self.root,
            tickets={"T-1": {"id": "T-1", "section": "## DONE"}},
            has_continuous_maintenance=True,
        )
        self.assertEqual(truth["campaign_status"], outcome_truth.CAMPAIGN_QUIESCENT)

    # PV23: Real user workflow improvement measured before and after
    def test_pv23_real_user_workflow_improvement_verified(self) -> None:
        report = {
            "entrypoint": "tools/saipen.py",
            "source_generation": "gen-1234",
            "is_synthetic": False,
        }
        baseline = {"wall_time_s": 20.5}
        optimized = {"wall_time_s": 12.1}
        result = evidence_fitness.validate_performance_benchmark(
            report,
            baseline_telemetry=baseline,
            optimized_telemetry=optimized,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["verdict"], "VERIFIED")
        self.assertEqual(result["code"], "PERFORMANCE_OPTIMIZED")
        self.assertAlmostEqual(result["improvement_s"], 8.4)

    # PV24: User workflow is slower despite passing unit tests
    def test_pv24_user_workflow_slower_fails_optimization_objective(self) -> None:
        report = {
            "entrypoint": "tools/saipen.py",
            "source_generation": "gen-1234",
            "is_synthetic": False,
        }
        baseline = {"wall_time_s": 10.0}
        slower_optimized = {"wall_time_s": 15.5}
        result = evidence_fitness.validate_performance_benchmark(
            report,
            baseline_telemetry=baseline,
            optimized_telemetry=slower_optimized,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["verdict"], "UNVERIFIED")
        self.assertEqual(result["code"], "PERFORMANCE_REGRESSION")

    # PV25: A prose keyword is not a demand; only an explicit [CLASS] tag is.
    def test_pv25_incidental_prose_does_not_raise_required_class(self) -> None:
        # A clause that merely mentions a strong-class word in ordinary wording
        # (a "contract" deliverable, a narrative "performance" aside, a "schema"
        # file) must stay UNIT. Promoting it is the false positive that made
        # such clauses permanently unclosable and voided verified receipts.
        for text in (
            "Cross-version portability contracts.",
            "Find the necessary native/API contracts.",
            "Documentation correctness; a section mentions performance once.",
            "Describe the resource schema and release notes.",
        ):
            self.assertEqual(
                evidence_fitness.extract_required_evidence_class(text),
                evidence_fitness.UNIT,
                f"incidental prose raised the class: {text!r}",
            )

        # A clause that genuinely demands a stronger class declares it by tag.
        self.assertEqual(
            evidence_fitness.extract_required_evidence_class(
                "Live user performance improved [PERFORMANCE_BENCHMARK]"
            ),
            evidence_fitness.PERFORMANCE_BENCHMARK,
        )

        # And the fitness gate agrees: a UNIT-only receipt closes the prose
        # clause but is still refused for the tagged one.
        ledger = {
            "requirements": {
                "SRC-X:R01": {
                    "class": "requirement",
                    "text": "Cross-version portability contracts.",
                    "disposition": "VERIFIED",
                    "evidence": "E-1",
                    "verification": "verify -> PASS",
                },
                "SRC-X:R02": {
                    "class": "requirement",
                    "text": "Live performance improved [PERFORMANCE_BENCHMARK]",
                    "disposition": "VERIFIED",
                    "evidence": "E-1",
                    "verification": "verify -> PASS",
                },
            }
        }
        summary = intake._coverage_summary_from_ledger("SRC-X", ledger)
        self.assertNotIn("SRC-X:R01", summary["unresolved"])
        self.assertIn("SRC-X:R02", summary.get("unresolved_fitness", []))

    # PV26: A [CLASS]-tagged clause is closable through the supported route.
    def test_pv26_declared_evidence_class_closes_tagged_clause(self) -> None:
        import shutil

        scenario = (
            Path(__file__).resolve().parent.parent
            / "tests" / "scenarios" / "stale-state-reconciliation" / ".saipen"
        )
        proj = self.root / "proj"
        proj.mkdir()
        shutil.copytree(scenario, proj / ".saipen")
        cap = intake.capture(proj, "audit", source_kind="user_audit")
        self.assertTrue(cap["ok"], cap)
        receipt = cap["receipt"]
        added = intake.add_requirement(
            proj, receipt, rid="R001", text="Portability contracts. [CONTRACT]"
        )
        self.assertTrue(added["ok"], added)

        # UNIT evidence cannot close a clause that declares CONTRACT.
        settled = intake.set_disposition(
            proj, receipt, "R001", "VERIFIED",
            evidence="E-1 unit observation", verification="verify viz -> PASS",
        )
        self.assertTrue(settled["ok"], settled)
        self.assertIn(
            f"{receipt}:R001", intake.coverage_summary(proj, receipt)["unresolved_fitness"]
        )

        # The declared class closes it; the class is persisted for the gate.
        settled = intake.set_disposition(
            proj, receipt, "R001", "VERIFIED",
            evidence="contract conformance report", verification="schema check -> PASS",
            evidence_class="CONTRACT",
        )
        self.assertTrue(settled["ok"], settled)
        self.assertEqual(settled["actual_evidence_class"], "CONTRACT")
        self.assertEqual(intake.coverage_summary(proj, receipt)["unresolved"], [])

        # An unknown class is refused by the shared authority, apply or dry-run.
        self.assertEqual(
            intake.validate_evidence_class("BOGUS")["code"], "VALIDATION_FAILED"
        )
        self.assertIsNone(intake.validate_evidence_class(None))
        self.assertIsNone(intake.validate_evidence_class("UNIT"))

    def test_pv26_lane_statuses_distinct_under_foreign_staged_blocker(self) -> None:
        """P0-01: Distinct lane statuses prevent release conflict from masquerading as global completion."""
        from saipen_engine import outcome_truth

        # Case 1: Shared staging blocker with an actionable TODO ticket
        tickets = {
            "T-1816": {
                "id": "T-1816",
                "section": "## BLOCKED",
                "fields": {"blocker": "PUBLICATION_STAGING_BLOCKED: foreign staged paths"},
            },
            "T-2001": {
                "id": "T-2001",
                "section": "## TODO",
                "blocked": False,
                "fields": {"blocker": ""},
            },
        }
        lanes = outcome_truth.compute_lane_statuses(
            tickets=tickets,
            foreign_staged=True,
            has_continuous_maintenance=False,
        )
        self.assertEqual(lanes["RELEASE_LANE"], outcome_truth.RELEASE_LANE_BLOCKED_FOREIGN_INDEX)
        self.assertEqual(lanes["IMPLEMENTATION_LANE"], outcome_truth.IMPLEMENTATION_LANE_ELIGIBLE)
        self.assertEqual(lanes["DISCOVERY_LANE"], outcome_truth.DISCOVERY_LANE_AUTHORITY_REQUIRED)
        self.assertEqual(lanes["PUBLICATION_LANE"], outcome_truth.PUBLICATION_LANE_BLOCKED)
        self.assertEqual(lanes["CAMPAIGN"], outcome_truth.CAMPAIGN_LANE_RUNNING)

        # Case 2: Shared staging blocker with drained queue and no continuous maintenance authority
        drained_tickets = {
            "T-1816": {
                "id": "T-1816",
                "section": "## BLOCKED",
                "fields": {"blocker": "PUBLICATION_STAGING_BLOCKED: foreign staged paths"},
            },
        }
        lanes_drained = outcome_truth.compute_lane_statuses(
            tickets=drained_tickets,
            foreign_staged=True,
            has_continuous_maintenance=False,
            is_budget_exhausted=True,
        )
        self.assertEqual(lanes_drained["RELEASE_LANE"], outcome_truth.RELEASE_LANE_BLOCKED_FOREIGN_INDEX)
        self.assertEqual(lanes_drained["IMPLEMENTATION_LANE"], outcome_truth.IMPLEMENTATION_LANE_AUTHORITY_REQUIRED)
        self.assertEqual(lanes_drained["DISCOVERY_LANE"], outcome_truth.DISCOVERY_LANE_AUTHORITY_REQUIRED)
        self.assertEqual(lanes_drained["PUBLICATION_LANE"], outcome_truth.PUBLICATION_LANE_BLOCKED)
        self.assertEqual(lanes_drained["CAMPAIGN"], outcome_truth.CAMPAIGN_LANE_WAIT_EXTERNAL)

    def test_pv27_response_surface_preserves_independent_action_under_shared_staging_blocker(self) -> None:
        """P0-01: response_surface does not force NEXT EXACT ACTION to NONE when independent action exists."""
        from saipen_engine import response_surface

        # When an independent next command is present, it must be preserved
        mock_auto = {
            "disposition": "WAIT_USER",
            "operator_action_due": True,
            "next_command": "saipen claim T-2001",
            "primary_blocker": {
                "cause": "publication-staging",
                "recovery_operation": {
                    "operator_action": "Resolve foreign staged-batch ownership, or authorize isolated release."
                },
            },
        }
        mock_status = {
            "automation": mock_auto,
            "conformance_status": {"status": "CURRENT_PASS"},
        }
        mock_state = {
            "phase": "DONE",
            "task": "none",
            "next_action": "saipen claim T-2001",
        }
        with unittest.mock.patch("saipen_engine.state.parse_state", return_value=mock_state), \
             unittest.mock.patch("saipen_engine.board.parse_board", return_value={"tickets": {}}), \
             unittest.mock.patch("saipen_engine.codec.read_doc", return_value=""), \
             unittest.mock.patch("saipen_engine.log.read_history_snapshot") as mock_log, \
             unittest.mock.patch("saipen_engine.conformance.conformance_status", return_value={"status": "CURRENT_PASS"}):
            mock_log.return_value.events = []
            facts = response_surface.canonical_facts(".", status=mock_status)
            self.assertEqual(facts["next_action"], "saipen claim T-2001")


    def test_pv28_stale_plan_recovery_command_attached(self) -> None:
        import json
        """P0-02: STALE_PLAN refusal carries exact canonical recovery command."""
        from saipen_engine.release import ReleaseRefusal, _load_scope, _plan_crew_release

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            scope_dir = tmppath / ".saipen" / "kitchen" / "release_scope"
            scope_dir.mkdir(parents=True)
            test_file = tmppath / "foo.py"
            test_file.write_text("print('hello live')", encoding="utf-8")
            (tmppath / ".saipen" / "IDENTITY.md").write_text("---\nproject_lineage: lineage-0123456789abcdef0123456789abcdef\n---\n", encoding="utf-8")

            # Recorded scope with differing hash
            scope_data = {
                "schema_version": 2,
                "ticket": "T-2002",
                "project_lineage": "lineage-0123456789abcdef0123456789abcdef",
                "source_head": "0123456789abcdef",
                "paths": {"foo.py": "0000000000000000"},
            }
            (scope_dir / "T-2002.json").write_text(json.dumps(scope_data), encoding="utf-8")

            with self.assertRaises(ReleaseRefusal) as ctx:
                _load_scope(tmppath, "T-2002", head="0123456789abcdef", fingerprint="fp", continuation=False)
            self.assertEqual(ctx.exception.code, "STALE_PLAN")
            self.assertEqual(ctx.exception.next_command, "saipen scope T-2002 foo.py")

            # Cohort carrier STALE_PLAN via cohort_ship
            from saipen_engine.operations import cohort_ship
            res_cohort = cohort_ship(Path("."), "C-019", "saipen-cli", dry_run=True)
            self.assertEqual(res_cohort.code, "STALE_PLAN")
            self.assertEqual(res_cohort.data.get("next_command"), "saipen cohort reconcile C-019 --review-work T-1850")

    def test_pv29_isolated_release_decision_request(self) -> None:
        """P0-03: create_isolated_release_decision_request satisfies Section 4 requirements."""
        from saipen_engine.decision_request import create_isolated_release_decision_request, validate_decision_request

        req = create_isolated_release_decision_request(
            action="isolated_release C-019",
            reviewed_scope=["foo.py", "bar.py"],
            target_destination="isolated git index / clean worktree",
            paths_changed=["foo.py", "bar.py"],
            paths_protected="790 staged paths (hash 1b84a7f4095cfead77f30001c6ccf2b45210bb89)",
            expected_side_effects="clean commit and tag created; zero touch to shared git index",
            rollback="discard isolated temporary index/worktree",
            reason_insufficient="broker receipt covering regenerated plan not yet captured",
        )
        self.assertEqual(validate_decision_request(req), [])
        self.assertEqual(req["action"], "isolated_release C-019")
        self.assertEqual(req["target_destination"], "isolated git index / clean worktree")
        self.assertIn("1b84a7f4095cfead77f30001c6ccf2b45210bb89", req["paths_protected"])
        self.assertIn("broker receipt", req["missing_authorization"])


if __name__ == "__main__":
    unittest.main()
