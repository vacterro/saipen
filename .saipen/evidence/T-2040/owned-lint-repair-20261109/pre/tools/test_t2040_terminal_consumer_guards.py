"""T-2040 terminal consumers: identical red/green oracle, disposable native fixtures.

Run: python -B tools/test_t2040_terminal_consumer_guards.py -v
"""
from __future__ import annotations

import copy
import datetime as dt
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from campaign_test_support import inspect_fixture_campaign, write_scoped_fixture_grant
from test_campaign_continuation_assessment import _format_state
from test_fixture_support import checked_discovery_evidence
from test_hermetic_env import isolate_host_session
from test_t2023_goal_management_and_maintenance_binding import (
    MAINTENANCE_OBJECTIVE, _project, _read_history, _register_maintenance, _witnessed_apply,
)
from saipen_engine import (
    automation, backend_protocol, board, campaign, continuation_assessment as CA,
    goal_authority, iteration_verdict as IV, operations, outcome_truth, persistent_goal,
    router, state as state_owner, supervisor, watchdog, worker, work_exhaustion as W,
)

BOARD = "## DOING\n## TODO\n## DONE\n## BLOCKED\n"
T0 = dt.datetime(2026, 10, 25, 12, 0, tzinfo=dt.timezone.utc)


def setUpModule():
    isolate_host_session()


def certificate(*, generation="100", source=None, action="saipen improve"):
    rows = [
        {"source_name": name, "source_generation": generation,
         "last_checked_generation": generation, "checked": True,
         "eligibility_result": W.CLEAN_VERIFIED, "authorized_actions": []}
        for name in W.ALL_WORK_SOURCES
    ]
    result = {
        "schema_version": 2, "status": W.VERIFIED_QUIESCENT,
        "source_generation": generation, "sources": rows, "all_checked": True,
        "exhausted": True, "certificate_errors": [], "blocked_obligations": [],
    }
    if source:
        row = next(row for row in rows if row["source_name"] == source)
        row.update(checked=False, last_checked_generation=None,
                   eligibility_result=W.NOT_CHECKED, authorized_actions=[action])
        result.update(status=W.INCOMPLETE_DISCOVERY, all_checked=False, exhausted=False)
        result["discovery_dispatch"] = {
            "source_name": source, "source_generation": generation,
            "action": action, "bounded": True,
        }
    return result


def idle_route(cert):
    routed = {
        "ok": True, "reason": "maintain", "action": "saipen status",
        "terminal_classification": cert["status"], "stop_reason": cert["status"],
        "work_exhaustion": cert, "detail": "current terminal evidence",
        "all_requirements_complete": False,
    }
    if "discovery_dispatch" in cert:
        routed["discovery_dispatch"] = cert["discovery_dispatch"]
    return routed


class TerminalConsumerGuards(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="saipen-terminal-guards-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / ".saipen").mkdir()
        (self.root / ".saipen/IDENTITY.md").write_text(
            "---\nproject_lineage: lineage-0123456789abcdef0123456789abcdef\n---\n",
            encoding="utf-8",
        )
        self.write_state()
        (self.root / ".saipen/BOARD.md").write_text(BOARD, encoding="utf-8")
        (self.root / ".saipen/LOG.md").write_text("# LOG\n", encoding="utf-8")
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)

    def write_state(self, **kwargs):
        text = _format_state(**kwargs)
        (self.root / ".saipen/STATE.md").write_text(text, encoding="utf-8")
        self.state, error = state_owner.parse_state_or_error(text)
        self.assertIsNone(error, error)
        return text

    def route(self, **kwargs):
        return router.route_next(
            _format_state(), BOARD, _state=self.state, _board=board.parse_board(BOARD),
            pending_ops=[], conflict_ops=[], **kwargs,
        )

    def owners(self):
        for name in ("audit_inbox_projection", "queued_source_projection", "pending_append_projection"):
            self.stack.enter_context(mock.patch.object(CA, name, return_value=None))
        self.stack.enter_context(mock.patch.object(CA, "future_gate_projection", return_value=None))
        for name in ("goal_checkpoint_gate", "continuous_maintenance_gate", "conformance_crew_gate",
                     "closure_finish_gate", "conformance_idle_gate"):
            self.stack.enter_context(mock.patch.object(router, name, return_value=None))

    def native_grant(self):
        root = _project(self, objective=MAINTENANCE_OBJECTIVE)
        _register_maintenance(root)
        blocked = operations.ticket_move(root, "block", "T-1", "fix",
                                         payload="BLOCKED_EXTERNAL -- unrelated publication")
        self.assertTrue(blocked.ok, blocked.to_dict())
        current, error = state_owner.parse_state_or_error(
            (root / ".saipen/STATE.md").read_text(encoding="utf-8"))
        self.assertIsNone(error)
        proposal = goal_authority.propose_capsule(root, current, _read_history(root))
        self.assertTrue(proposal["ok"], proposal)
        applied = _witnessed_apply(self, root, proposal["capsule_text"])
        self.assertTrue(applied.ok, applied.to_dict())
        current, error = state_owner.parse_state_or_error(
            (root / ".saipen/STATE.md").read_text(encoding="utf-8"))
        self.assertIsNone(error)
        self.assertTrue(goal_authority.continuous_maintenance_proven(root, current))
        return root, current

    def assessment(self, cert, *, proven=False):
        routed = idle_route(cert)
        result = CA._make_assessment(
            CA.INCOMPLETE_DISCOVERY, action=cert.get("discovery_dispatch", {}).get("action"),
            reason="maintain", detail="current terminal evidence", effective_route=routed,
            raw_route=routed, continuous_maintenance_proven=proven,
        )
        if "discovery_dispatch" in cert:
            result["discovery_dispatch"] = cert["discovery_dispatch"]
        return result

    def admit(self, root=None, backend=None):
        root = root or self.root
        write_scoped_fixture_grant(root)
        self.stack.enter_context(mock.patch(
            "saipen_engine.host_authority_client.inspect_operator_campaign",
            side_effect=inspect_fixture_campaign,
        ))
        controller = campaign.CampaignController(root, backend=backend)
        result = controller.admit_campaign(
            campaign_id="CAMP-T2040-TERMINAL", authority_proof_reference=".saipen/authority/grant.json",
        )
        self.assertTrue(result["admitted"], result)
        return controller

    def automation(self, routed, *, root=None, state=None):
        return automation.automation_block(
            root or self.root, state=self.state if state is None else state,
            board=board.parse_board(BOARD), routed=routed,
            audit_status={"ok": True, "clean": True, "pending": [], "orphans": [], "residue": []},
            convergence={"ok": False, "stages": []},
            source_identity=mock.Mock(source_head="head", source_tree_fingerprint="tree"),
        )

    def test_external_wait_supervisor_never_becomes_idle(self):
        self.write_state(blocker="BLOCKED_EXTERNAL -- current external boundary")
        for lease in (None, watchdog.EXPIRED, watchdog.TERMINAL):
            with self.subTest(lease=lease):
                path = self.root / watchdog.CACHE_REL
                path.unlink(missing_ok=True)
                if lease is not None:
                    watchdog.acquire_lease(self.root, "previous", now=T0)
                    if lease == watchdog.TERMINAL:
                        watchdog.fence(self.root, "previous", 1, now=T0)
                result = supervisor.decide(self.root, now=T0 + dt.timedelta(seconds=200))
                self.assertEqual(result["verdict"], CA.WAIT_EXTERNAL, result)
                self.assertFalse(result["may_mutate"])
                self.assertFalse(result["requires_human"])

    def test_external_wait_worker_never_reports_success_or_takes_authority(self):
        self.write_state(blocker="BLOCKED_EXTERNAL -- current external boundary")
        with mock.patch.object(worker, "take_authority") as take, mock.patch.object(
            worker, "_run_generation",
        ) as execute:
            result = worker._supervise(self.root, ["fixture-agent"], max_cycles=3)
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["stop"], CA.WAIT_EXTERNAL)
        self.assertIsNone(result["operator_action"])
        self.assertEqual(result["counters"]["worker_generation_count"], 0)
        take.assert_not_called()
        execute.assert_not_called()

    def test_live_or_ambiguous_lease_is_never_stolen_during_external_wait(self):
        self.write_state(blocker="BLOCKED_EXTERNAL -- current external boundary")
        watchdog.acquire_lease(self.root, "live", now=T0)
        for seconds in (5, 45):
            result = supervisor.decide(self.root, now=T0 + dt.timedelta(seconds=seconds), worker_id="other")
            self.assertEqual(result["verdict"], supervisor.AWAIT_WORKER)
            self.assertFalse(result["may_mutate"])
        (self.root / watchdog.CACHE_REL).write_text("{broken", encoding="utf-8")
        result = supervisor.decide(self.root, now=T0, worker_id="other")
        self.assertEqual(result["verdict"], supervisor.AMBIGUOUS_AUTHORITY)

    def test_authoritative_external_stop_outranks_stale_workable_board(self):
        self.write_state(blocker="BLOCKED_EXTERNAL -- current external boundary")
        (self.root / ".saipen/BOARD.md").write_text(
            "## DOING\n## TODO\n- [ ] T-1 [P1] stale work | verify: local test\n## DONE\n## BLOCKED\n",
            encoding="utf-8",
        )
        picture = supervisor.observe(self.root, now=T0)
        self.assertEqual(picture["continuation_classification"], CA.WAIT_EXTERNAL)
        self.assertIsNone(picture["executable_work"], picture)
        result = supervisor.decide(self.root, now=T0)
        self.assertEqual(result["verdict"], CA.WAIT_EXTERNAL)

    def test_stored_actionable_goals_cannot_override_current_blocked_assessment(self):
        goal = persistent_goal.PersistentGoal(
            goal_id="stale-goal", project_id=self.root.name, title="Stale observation",
            objective="Current proof required", current_status=persistent_goal.STATUS_ACTIONABLE_GAPS,
        )
        persistent_goal.save_goal(self.root, goal)
        for kwargs, classification in (
            ({"blocker": "BLOCKED_EXTERNAL -- current boundary"}, CA.WAIT_EXTERNAL),
            ({"next_action": '"WAIT: user brake -- operator stopped work"'}, CA.WAIT_OPERATOR),
        ):
            with self.subTest(classification=classification):
                self.write_state(**kwargs)
                with mock.patch.object(IV, "_recall_decision", return_value=None):
                    result = IV.project_iteration_verdict(self.root)
                self.assertEqual(result["continuation_classification"], classification, result)
                self.assertFalse(result["executable_action_remains"], result)
                self.assertFalse(result["goal_complete"])

    def test_iteration_refuses_malformed_goal_inventory_without_throwing(self):
        for inventory in (42, {"goals": [42], "complete": True}, {"goals": 42}):
            with self.subTest(inventory=inventory), mock.patch.object(
                persistent_goal, "list_goals_report", return_value=inventory,
            ), mock.patch.object(IV, "_recall_decision", return_value=None):
                result = IV.project_iteration_verdict(self.root)
                self.assertFalse(result["goal_complete"], result)
                self.assertFalse(result["executable_action_remains"], result)

    def test_board_validates_typed_envelopes_before_consuming_them(self):
        for payload in (
            {"tickets": 42}, {"tickets": {"T-1": 42}},
            {"tickets": {"T-1": {"section": "## TODO", "fields": 42}}},
            {"tickets": {"T-1": {"section": "## TODO", "needs": 42}}},
            {"state": 42}, {"state": ["truthy"]},
            {"future_gate": 42}, {"audit_inbox": 42}, {"source_evidence": 42},
        ):
            with self.subTest(payload=payload):
                args = {"tickets": {}, "state": self.state, "persistent_goals": [],
                        "source_evidence": checked_discovery_evidence("100"), **payload}
                result = board.classify_idle_work(**args)
                self.assertFalse(result["all_requirements_complete"], result)
                self.assertIsInstance(result["work_exhaustion"], dict)
                self.assertFalse(W.verified_quiescence(result["work_exhaustion"]))

    def test_board_rejects_malformed_certificate_owner_envelopes(self):
        for cert in (42, ["truthy"], {"status": W.VERIFIED_QUIESCENT, "sources": 42}):
            with self.subTest(certificate=cert), mock.patch.object(
                W, "certify_work_exhaustion", return_value=cert,
            ):
                result = board.classify_idle_work({}, state=self.state, persistent_goals=[])
                self.assertFalse(result["all_requirements_complete"], result)
                self.assertTrue(result["no_admissible_work"])
                self.assertEqual(result["work_exhaustion"]["status"], W.INCOMPLETE_DISCOVERY)

    def test_router_validates_preparsed_state_and_board_envelopes(self):
        for state, parsed in (
            (42, board.parse_board(BOARD)), (self.state, 42),
            ({**self.state, "next_action": 42}, board.parse_board(BOARD)),
            (self.state, {"tickets": 42, "errors": []}),
            (self.state, {"tickets": {"T-1": 42}, "errors": []}),
            (self.state, {"tickets": {}, "errors": 42}),
        ):
            with self.subTest(state=state, board=parsed):
                result = router.route_next(_format_state(), BOARD, _state=state, _board=parsed)
                self.assertFalse(result["ok"], result)
                self.assertIsInstance(result["action"], str)

    def test_router_rejects_malformed_truthy_projection_envelopes(self):
        for kwargs in (
            {"queued_source": 42}, {"pending_append": 42}, {"audit_inbox": 42},
            {"future_gate": 42}, {"future_gate": {"eligible": 42}},
            {"audit_inbox": {"pending": 42}}, {"queued_source": {"action": 42}},
            {"pending_append": {"action": 42}},
            {"audit_inbox": {"invalid": True}}, {"audit_inbox": {"residue": 42}},
            {"audit_inbox": {"closed_pending_delete": True}},
            {"audit_inbox": {"invalid_only": 42}}, {"audit_inbox": {"residue_only": "yes"}},
            {"audit_inbox": {"binding_corrupt": 1}},
        ):
            with self.subTest(projection=kwargs):
                result = self.route(**kwargs)
                self.assertFalse(result["ok"], result)
                self.assertIsInstance(result["action"], str)

    def test_router_accepts_the_real_audit_inbox_projection_shape(self):
        # The live producer emits `invalid`/`residue`/`pending`/`closed_pending_delete`
        # as LISTS of layer keys and only the `*_only`/`binding_corrupt` verdicts as
        # booleans. A validator demanding booleans everywhere rejects the honest
        # projection and bricks `saipen continue` with "invalid must be a boolean".
        live = {
            "rule_id": "SOURCE-AUDIT-INBOX-01",
            "action": "saipen audit status",
            "pending": ["a#1"],
            "closed_pending_delete": ["b#2"],
            "invalid": [{"layer": "c", "rel": "audit/c.md", "state": "INVALID"}],
            "residue": ["audit/stray.txt"],
            "residue_count": 1,
            "unresolved_audit_count": 1,
            "invalid_only": False,
            "residue_only": False,
            "binding_corrupt": False,
        }
        result = self.route(audit_inbox=live)
        self.assertTrue(result.get("ok"), result)

    def test_assessment_refuses_malformed_board_or_discovery_envelope(self):
        self.owners()
        for parsed in (42, {"tickets": 42, "errors": []}, {"tickets": {}, "errors": 42}):
            with self.subTest(board=parsed):
                result = CA.assess_continuation(self.root, parsed_board=parsed)
                self.assertEqual(result["classification"], CA.INVALID_RUNTIME)
                self.assertFalse(result["actionable"])
        for evidence in (42, {"source_evidence": 42}, {"source_evidence": []}):
            with self.subTest(evidence=evidence), mock.patch.object(
                W, "discovery_evidence", return_value=evidence,
            ):
                result = CA.assess_continuation(self.root, source_evidence={"hunt_findings": {}})
                self.assertIn(result["classification"], (CA.INVALID_RUNTIME, CA.INCOMPLETE_DISCOVERY))
                self.assertFalse(result["actionable"])

    def test_assessment_refuses_malformed_effective_route(self):
        for routed in (42, ["truthy"], {"ok": True, "reason": "maintain", "primary_blocker": 42}):
            with self.subTest(route=routed):
                result = CA._classify_effective_route(self.root, routed, {}, self.state, board.parse_board(BOARD))
                self.assertIn(result["classification"], (CA.INVALID_RUNTIME, CA.INCOMPLETE_DISCOVERY))
                self.assertFalse(result["actionable"])

    def test_completion_requires_verified_quiescence_and_all_goals_satisfied(self):
        for goals, expected in (
            ([], True), ([{"goal_id": "g", "current_status": "SATISFIED"}], True),
            ([{"goal_id": "g", "current_status": "ACTIVE", "paused": True}], False),
            ({"goals": [], "complete": False}, False),
        ):
            with self.subTest(goals=goals), mock.patch.object(
                W, "certify_work_exhaustion", return_value=certificate(),
            ):
                result = board.classify_idle_work({}, state=self.state, persistent_goals=goals)
                self.assertEqual(result["all_requirements_complete"], expected, result)
                routed = self.route(persistent_goals=goals)
                self.assertEqual(routed.get("stop_reason") == "ALL_REQUIREMENTS_COMPLETE", expected, routed)
        with mock.patch.object(W, "certify_work_exhaustion", return_value=certificate(source=W.IMPROVE_CANDIDATES)):
            result = board.classify_idle_work({}, state=self.state, persistent_goals=[])
            self.assertFalse(result["all_requirements_complete"])

    def test_outcome_failure_cannot_leak_router_completion(self):
        with mock.patch.object(W, "certify_work_exhaustion", return_value=certificate()), mock.patch.object(
            outcome_truth, "compute_outcome_truth", side_effect=ValueError("owner proof unreadable"),
        ):
            result = self.route(persistent_goals=[])
        self.assertNotEqual(result.get("stop_reason"), "ALL_REQUIREMENTS_COMPLETE", result)
        self.assertIn("outcome_truth_error", result)

    def test_automation_helpers_fail_closed_on_malformed_envelopes(self):
        for status in (42, {"ok": True, "clean": True, "orphans": [42]}):
            with self.subTest(status=status):
                self.assertFalse(automation.audit_quiescent(status))
                self.assertIsNone(automation.audit_epoch(status))
        for kwargs in ({"board": 42}, {"state": 42}, {"convergence": 42}, {"history_events": 42}):
            with self.subTest(envelope=kwargs):
                args = {"status_out": {}, "convergence": {}, "history_events": [],
                        "board": board.parse_board(BOARD), "state": self.state, **kwargs}
                result = automation.closure_gate(**args)
                self.assertFalse(result["complete"])
                self.assertTrue(all(type(value) is bool for value in result["conditions"].values()))

    def test_automation_unknown_route_or_missing_certificate_cannot_continue(self):
        for routed in (
            {"ok": True, "reason": "unknown-success", "action": "saipen status"},
            {"ok": True, "reason": "maintain", "action": "saipen continue"},
            {"ok": True, "reason": "maintain", "action": "saipen continue", "work_exhaustion": 42},
        ):
            with self.subTest(route=routed):
                result = self.automation(routed)
                self.assertNotIn(result["disposition"], (automation.CONTINUE, automation.COMPLETE), result)
                self.assertIsNone(result["next_command"])

    def test_automation_certificate_cannot_complete_unsatisfied_objectives(self):
        routed = idle_route(certificate())
        routed["terminal_classification"] = "ALL_WORK_COMPLETE"
        with mock.patch.object(automation, "closure_gate", return_value={
            "complete": True, "convergence_current": True, "conditions": {},
        }):
            result = self.automation(routed)
        self.assertNotEqual(result["disposition"], automation.COMPLETE, result)
        self.assertFalse(result["closure_complete"])

    def test_same_issued_publication_carrier_reaches_pure_board_and_router(self):
        carrier = outcome_truth.read_publication_evidence(self.root, tickets={})
        for consumer in ("board", "router"):
            with self.subTest(consumer=consumer), mock.patch.object(
                outcome_truth, "compute_outcome_truth", wraps=outcome_truth.compute_outcome_truth,
            ) as compute, mock.patch.object(outcome_truth, "read_publication_evidence",
                                           side_effect=AssertionError("pure owner IO")):
                if consumer == "board":
                    board.classify_idle_work({}, state=self.state, persistent_goals=[], publication_evidence=carrier)
                else:
                    self.route(persistent_goals=[], publication_evidence=carrier)
                self.assertIsNone(compute.call_args.args[0])
                self.assertIs(compute.call_args.kwargs["publication_evidence"], carrier)

    def test_assessment_forwards_same_issued_publication_carrier(self):
        carrier = outcome_truth.read_publication_evidence(self.root, tickets={})
        self.owners()
        with mock.patch.object(W, "discovery_evidence", return_value={
            "persistent_goals": [], "source_evidence": checked_discovery_evidence("100"),
            "continuous_maintenance_authorized": False,
        }), mock.patch.object(CA, "route_next", wraps=CA.route_next) as route:
            result = CA.assess_continuation(self.root, publication_evidence=carrier)
        self.assertNotEqual(result["classification"], CA.INVALID_RUNTIME, result)
        self.assertIs(route.call_args.kwargs["publication_evidence"], carrier)

    def test_native_grant_and_valid_hint_enable_bounded_incomplete_assessment(self):
        root, current = self.native_grant()
        cert = certificate(generation=str(current["last_event"]), source=W.IMPROVE_CANDIDATES)
        routed = idle_route(cert)
        result = CA._classify_effective_route(root, routed, routed, current, board.parse_board(BOARD))
        self.assertEqual(result["classification"], CA.INCOMPLETE_DISCOVERY, result)
        self.assertFalse(result["actionable"])
        self.assertFalse(result["quiescent"])
        self.assertTrue(result["continuous_maintenance_proven"])
        self.assertIs(result["discovery_dispatch"], cert["discovery_dispatch"])
        self.assertEqual(result["action"], cert["discovery_dispatch"]["action"])
        self.assertEqual(result["raw_route"]["stop_reason"], W.INCOMPLETE_DISCOVERY)

    def test_native_grant_valid_hint_automation_continues_without_promotion(self):
        root, current = self.native_grant()
        cert = certificate(generation=str(current["last_event"]), source=W.IMPROVE_CANDIDATES)
        result = self.automation(idle_route(cert), root=root, state=current)
        self.assertEqual(result["disposition"], automation.CONTINUE, result)
        self.assertEqual(result["next_command"], "cc")
        self.assertFalse(result["closure_complete"])
        self.assertFalse(result["operator_action_due"])
        self.assertIs(result["discovery_dispatch"], cert["discovery_dispatch"])
        self.assertEqual(cert["status"], W.INCOMPLETE_DISCOVERY)

    def test_native_grant_valid_hint_supervisor_uses_existing_execution_seam(self):
        root, current = self.native_grant()
        cert = certificate(generation=str(current["last_event"]), source=W.IMPROVE_CANDIDATES)
        with mock.patch.object(supervisor, "assess_continuation", return_value=self.assessment(cert, proven=True)):
            result = supervisor.decide(root)
        self.assertEqual(result["verdict"], supervisor.RUN_WORK, result)
        self.assertEqual(result["work"], cert["discovery_dispatch"]["action"])
        self.assertEqual(result["observation"]["continuation_classification"], CA.INCOMPLETE_DISCOVERY)
        self.assertFalse(result["observation"]["continuation_actionable"])

    def test_unproven_or_stale_hint_never_creates_authority(self):
        self.write_state(continuation_authority="operator_persistent", authority_until="continuous_maintenance",
                         goal_ingress="goal-0123456789abcdef")
        cert = certificate(source=W.IMPROVE_CANDIDATES)
        routed = idle_route(cert)
        result = CA._classify_effective_route(self.root, routed, routed, self.state, board.parse_board(BOARD))
        self.assertEqual(result["classification"], CA.WAIT_AUTHORITY, result)
        self.assertFalse(result["actionable"])
        self.assertFalse(result.get("discovery_dispatch"))
        result = self.automation(routed)
        self.assertNotEqual(result["disposition"], automation.CONTINUE, result)
        for change in ({"source_generation": "stale"}, {"bounded": 1}, {"action": "saipen release"}):
            broken = copy.deepcopy(cert)
            broken["discovery_dispatch"].update(change)
            with self.subTest(hint=change), mock.patch.object(
                supervisor, "assess_continuation", return_value=self.assessment(broken, proven=True),
            ):
                result = supervisor.decide(self.root)
                self.assertFalse(result["may_mutate"], result)
                self.assertEqual(result["verdict"], supervisor.INCOMPLETE_DISCOVERY)

    def test_campaign_valid_hint_reuses_one_bounded_worker_attempt(self):
        root, current = self.native_grant()
        controller = self.admit(root)
        cert = certificate(generation=str(current["last_event"]), source=W.IMPROVE_CANDIDATES)
        with mock.patch.object(CA, "assess_continuation", return_value=self.assessment(cert, proven=True)), mock.patch.object(
            controller, "_execute_canonical_worker", return_value={"ok": True, "route_only": True},
        ) as execute:
            result = controller.step()
        self.assertTrue(result["ok"], result)
        execute.assert_called_once()
        intent = result["state"]["worker_attempt"]["execution_intent"]
        self.assertEqual(intent["classification"], CA.INCOMPLETE_DISCOVERY)
        self.assertEqual(intent["action"], cert["discovery_dispatch"]["action"])
        self.assertFalse(intent["actionable"])
        self.assertEqual(result["state"]["worker_generation"], 1)
        self.assertNotEqual(result["state"]["campaign_state"], campaign.QUIESCENT_WAIT)

    def test_campaign_no_new_forensic_evidence_is_not_whole_campaign_quiescence(self):
        backend = mock.Mock()
        controller = self.admit(backend=backend)
        assessment = CA._make_assessment(CA.MAINTENANCE_AVAILABLE, action="saipen continue",
                                         reason="maintain", detail="bounded forensic source")
        for status in (backend_protocol.NO_NEW_EVIDENCE, "UNKNOWN_SUCCESS"):
            with self.subTest(status=status), mock.patch.object(CA, "assess_continuation", return_value=assessment):
                backend.discover.return_value = {"ok": True, "status": status}
                result = controller.step()
                self.assertNotEqual(result["state"]["campaign_state"], campaign.QUIESCENT_WAIT, result)
                self.assertFalse(result["ok"], result)
        self.assertEqual(backend.discover.call_count, 2)

    def test_campaign_refuses_malformed_assessment_and_delivery_without_throwing(self):
        backend = mock.Mock()
        controller = self.admit(backend=backend)
        with mock.patch.object(CA, "assess_continuation", return_value=42):
            result = controller.step()
        self.assertFalse(result["ok"], result)
        backend.discover.assert_not_called()
        assessment = CA._make_assessment(CA.MAINTENANCE_AVAILABLE, action="saipen continue",
                                         reason="maintain", detail="bounded forensic source")
        backend.discover.return_value = {"ok": True, "status": backend_protocol.NEW_QUALIFIED_FINDINGS,
                                         "findings": [{"finding_id": "f"}]}
        backend.deliver_finding_to_audit_inbox.return_value = 42
        with mock.patch.object(CA, "assess_continuation", return_value=assessment):
            result = controller.step()
        self.assertFalse(result["ok"], result)
        backend.acknowledge_delivery.assert_not_called()


if __name__ == "__main__":
    unittest.main()
