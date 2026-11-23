"""T-2040 Wave C: fixture-only authority recovery and zero-write finish planning.

Real canonical writers, Sources, journals and broker; native process facts are
explicitly simulated. No production host/UI admission or live state is exercised.
Run: python -B tools/test_t2040_maintenance_authority.py -v
"""
from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from test_hermetic_env import isolate_host_session
from test_operator_origin_support import use_case_owner
from test_request_clause_closure import TASK, drive
from test_t1363_zero_manual_entry import cli, healthy, receipts_of
from test_t2023_goal_management_and_maintenance_binding import (
    MAINTENANCE_OBJECTIVE, _project, _read_history, _register_maintenance,
    _witnessed_apply,
)
from saipen_engine import codec, goal_authority, intake, operations, replenishment, state
from saipen_engine.board import parse_board
from saipen_engine.discovery_providers import CandidateTask, get_provider
from saipen_engine.journal import Journal
from saipen_engine.persistent_goal import save_goal


def setUpModule():
    isolate_host_session()


def snapshot(root):
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*") if p.is_file()
    }


def current(root):
    return state.parse_state(codec.read_doc(root / ".saipen/STATE.md"))


def rows(root):
    return parse_board(codec.read_doc(root / ".saipen/BOARD.md"))["tickets"]


def source(case, root, text, work):
    captured = intake.capture(root, operations._user_request_body(
        text, "P1", "The exact local regression oracle passes", []
    ), source_kind="user_instruction", request_provenance={"witness": "model_supplied"})
    case.assertTrue(captured.get("ok"), captured)
    receipt = captured["receipt"]
    linked = intake.link_work_to(root, receipt, work)
    case.assertTrue(linked.get("ok"), linked)
    return receipt


def block(case, root, ticket, payload):
    result = operations.ticket_move(root, "block", ticket, "fix", payload=payload)
    case.assertTrue(result.ok, result.to_dict())


class FinishPlanPurity(unittest.TestCase):
    def fixture(self):
        root = healthy(self)
        drive(self, root)
        return root

    def test_done_dry_run_preserves_every_source_and_journal_byte(self):
        root = self.fixture()
        before = snapshot(root)
        code, result, text = cli(root, "ticket", "done", "T-1", "--closure-mode",
                                 "own_patch", "--dry-run", "--json")
        self.assertEqual(code, 0, text)
        self.assertTrue(result["dry_run"], result)
        self.assertEqual(snapshot(root), before)

    def test_late_refusal_does_not_discharge_or_seed_source(self):
        root = self.fixture()
        before = snapshot(root)
        result = operations.finish_ticket(root, "T-1", "test-agent",
            closure_mode="inherited_verified", implementation_source="T-999")
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(snapshot(root), before)

    def test_missing_verification_refuses_without_seeding(self):
        root = healthy(self)
        drive(self, root, verified=False)
        before = snapshot(root)
        result = operations.finish_ticket(root, "T-1", "test-agent", dry_run=True)
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(snapshot(root), before)

    def test_derived_clause_refusal_keeps_all_coverage_bytes(self):
        root = self.fixture()
        receipt = receipts_of(root)[0]
        self.assertTrue(intake.ensure_request_clause(root, receipt).get("ok"))
        self.assertTrue(intake.add_requirement(root, receipt, rid="R002",
            text="Never touch packaging metadata", clause_class="requirement").get("ok"))
        before = snapshot(root)
        result = operations.finish_ticket(root, "T-1", "test-agent")
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(result.code, "SOURCE_UNRESOLVED")
        self.assertEqual(snapshot(root), before)

    def test_compound_source_refusal_is_also_byte_pure(self):
        root = self.fixture()
        source(self, root, "1. Repair the parser regression\n2. Preserve packaging metadata", "T-1")
        before = snapshot(root)
        result = operations.finish_ticket(root, "T-1", "test-agent", dry_run=True)
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(snapshot(root), before)

    def test_applied_finish_owns_request_targets_in_its_single_journal(self):
        root = self.fixture()
        receipt = receipts_of(root)[0]
        result = operations.finish_ticket(root, "T-1", "test-agent")
        self.assertTrue(result.ok, result.to_dict())
        record = Journal(root, result.op_id).read()
        paths = {target["path"] for target in record["targets"]}
        self.assertTrue({f".saipen/intake/contracts/{receipt}.json",
                         f".saipen/intake/contracts/{receipt}.r001.json",
                         f".saipen/intake/coverage/{receipt}.json"} <= paths, paths)
        self.assertEqual(intake.coverage_summary(root, receipt)["unresolved"], [])
        clause = intake._read_contract(root, receipt)["clauses"][f"{receipt}:R001"]
        self.assertEqual(clause["text"], TASK)
        self.assertEqual(rows(root)["T-1"]["section"], "## DONE")


class ExactProtectedGoalIdentity(unittest.TestCase):
    def fixture(self, *, matching=True, description="Authority repair fixture"):
        root = _project(self, objective=MAINTENANCE_OBJECTIVE)
        _register_maintenance(root)
        block(self, root, "T-1", "BLOCKED_EXTERNAL -- publication owned elsewhere")
        added = operations.ticket_add(root, "fix", "P1", description, needs=[],
            verify="The exact local regression oracle passes")
        self.assertTrue(added.ok, added.to_dict())
        ticket = added.data["ticket"]
        receipt = source(self, root,
            MAINTENANCE_OBJECTIVE if matching else "Discuss maintenance documentation only",
            ticket)
        block(self, root, ticket,
              "CONTINUATION_AUTHORITY_UNPROVEN -- self-maintenance-core grant absent")
        return root, ticket, receipt

    def request(self, root):
        return operations.user_request(root, "fix",
            "Please authorize the current self-maintenance goal self-maintenance-core")

    def test_nested_blocker_reuses_exact_durable_goal_membership(self):
        root, ticket, _receipt = self.fixture()
        result = self.request(root)
        self.assertEqual(result.code, "PROTECTED_OPERATION_BLOCKED", result.to_dict())
        self.assertEqual(result.data["ticket"], ticket)
        self.assertTrue(result.data["duplicate"])
        meta = intake.read_body(root, result.data["receipt"])["meta"]
        self.assertTrue(intake.is_linked_to(meta, ticket))
        self.assertEqual(meta["request_provenance"]["witness"], "model_supplied")

    def test_unrelated_self_maintenance_prose_cannot_acquire_source(self):
        root, ticket, _receipt = self.fixture(matching=False,
            description="Discuss self-maintenance documentation")
        result = self.request(root)
        self.assertEqual(result.code, "PROTECTED_OPERATION_BLOCKED", result.to_dict())
        self.assertIsNone(result.data["ticket"])
        self.assertFalse(result.data["duplicate"])
        self.assertFalse(intake.is_linked_to(
            intake.read_body(root, result.data["receipt"])["meta"], ticket))

    def test_link_refusal_is_not_reported_as_a_duplicate(self):
        root, _ticket, _receipt = self.fixture()
        with mock.patch.object(intake, "link_work_to", return_value={
            "ok": False, "code": "WRITER_BUSY", "detail": "fixture writer busy"
        }):
            result = self.request(root)
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(result.code, "WRITER_BUSY")
        self.assertFalse(result.data.get("duplicate", False))

    def test_identical_linked_replay_has_same_source_work_and_bytes(self):
        root, ticket, _receipt = self.fixture()
        first = self.request(root)
        self.assertEqual(first.data["ticket"], ticket)
        before = snapshot(root)
        replay = self.request(root)
        self.assertEqual(replay.data["receipt"], first.data["receipt"])
        self.assertEqual(replay.data["ticket"], ticket)
        self.assertEqual(snapshot(root), before)


class NativeGrantAndIdentity(unittest.TestCase):
    def native(self, *, active=False):
        root = _project(self, objective="previous fixture objective")
        _register_maintenance(root)
        if not active:
            block(self, root, "T-1", "BLOCKED_EXTERNAL -- unrelated publication")
        host = use_case_owner(self, root)
        proof = host.offer(root, MAINTENANCE_OBJECTIVE, action="goal")
        self.assertIsNotNone(proof)
        entered = operations.goal_entry(root, "fix", MAINTENANCE_OBJECTIVE)
        self.assertTrue(entered.ok, entered.to_dict())
        self.assertEqual(goal_authority.prove(root, current(root)), [])
        return root, host, proof

    def test_active_native_entry_keeps_exact_pivot_objective(self):
        root, _host, _proof = self.native(active=True)
        binding = goal_authority.current_binding(root, current(root),
            _read_history(root), {}, until="continuous_maintenance")
        self.assertEqual(binding["goal_objective"], MAINTENANCE_OBJECTIVE)
        self.assertEqual(rows(root)["T-1"]["section"], "## TODO")
        self.assertTrue(any("active T-1 checkpointed to TODO" in e["text"]
                            for e in _read_history(root)))

    def test_native_same_goal_upgrade_preserves_ingress_budget_and_replay(self):
        root, _host, _proof = self.native()
        before = current(root)
        capsule = goal_authority.propose_capsule(root, before, _read_history(root))
        self.assertTrue(capsule["ok"], capsule)
        upgraded = _witnessed_apply(self, root, capsule["capsule_text"])
        self.assertTrue(upgraded.ok, upgraded.to_dict())
        after = current(root)
        for key in ("goal_ingress", "authority_source", "goal_waves", "goal_tickets",
                    "blocker", "phase", "task", "next_action"):
            self.assertEqual(after.get(key), before.get(key), key)
        self.assertEqual(after["authority_until"], "continuous_maintenance")
        self.assertEqual(goal_authority.prove(root, after), [])
        frozen = snapshot(root)
        replay = operations.authorize_goal_continuation(root, "fix", capsule["capsule_text"])
        self.assertTrue(replay.ok, replay.to_dict())
        self.assertEqual(replay.code, "GOAL_AUTHORITY_ALREADY_SET")
        self.assertEqual(replay.op_id, upgraded.op_id)
        self.assertEqual(snapshot(root), frozen)

    def test_revoked_old_native_grant_cannot_be_upgraded(self):
        root, host, proof = self.native()
        capsule = goal_authority.propose_capsule(root, current(root), _read_history(root))
        self.assertTrue(capsule["ok"], capsule)
        host.fixture.broker.handle({"op": "revoke-origin", "host": "claude", "proof": proof},
                                  host.fixture.native_peer)
        before = snapshot(root)
        refused = operations.authorize_goal_continuation(root, "fix", capsule["capsule_text"])
        self.assertFalse(refused.ok, refused.to_dict())
        self.assertEqual(snapshot(root), before)

    def test_revocation_preview_names_only_existing_native_owner(self):
        root = _project(self, objective=MAINTENANCE_OBJECTIVE)
        _register_maintenance(root)
        proposal = goal_authority.propose_capsule(root, current(root), _read_history(root))
        self.assertTrue(proposal["ok"], proposal)
        route = proposal["preview"]["revocation_path"]
        self.assertIn("revoke-origin", route)
        self.assertNotIn("reset_authority", route)
        self.assertNotIn("authorize with a new capsule", route)
        self.assertIn("no public", route.lower())


class RestoredMaintenanceCandidate(unittest.TestCase):
    def fixture(self, *, blocker=None, long=False, grant=True):
        root = _project(self, objective=MAINTENANCE_OBJECTIVE)
        goal = _register_maintenance(root, evidence_provider="evidence_gap_ledger")
        goal.research_or_work_backlog_source = ".saipen/evidence/coverage_gap.json"
        save_goal(root, goal)
        path = root / goal.research_or_work_backlog_source
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"total": 1, "resolved": 0,
            "gaps": [{"id": "repair-1", "name": "Local parser",
                      "verify": "The exact local regression oracle passes"}]}), encoding="utf-8")
        block(self, root, "T-1", "BLOCKED_EXTERNAL -- publication owned elsewhere")
        candidate = get_provider(goal.evidence_provider).evaluate(root, goal).actionable_candidates[0]
        description = ("Bounded local repair " + "detail " * 220 if long else candidate.title)
        description += (f" | goal: {goal.goal_id} | candidate: {candidate.candidate_id}"
                        f" | evidence_fp: {candidate.evidence_fingerprint}")
        added = operations.ticket_add(root, "fix", "P1", description,
            needs=[], verify=candidate.verification)
        self.assertTrue(added.ok, added.to_dict())
        ticket = added.data["ticket"]
        receipt = source(self, root,
            f"Repair local candidate {candidate.candidate_id} | goal: {goal.goal_id}", ticket)
        block(self, root, ticket, blocker or
              "CONTINUATION_AUTHORITY_UNPROVEN -- standing maintenance grant missing")
        if grant:
            proposal = goal_authority.propose_capsule(root, current(root), _read_history(root))
            self.assertTrue(proposal["ok"], proposal)
            result = _witnessed_apply(self, root, proposal["capsule_text"])
            self.assertTrue(result.ok, result.to_dict())
            self.assertEqual(goal_authority.prove(root, current(root)), [])
        return root, goal, candidate, ticket, receipt

    def test_provider_does_not_suppress_verified_authority_only_work(self):
        root, goal, candidate, _ticket, _receipt = self.fixture()
        before = snapshot(root)
        evaluation = get_provider(goal.evidence_provider).evaluate(root, goal)
        self.assertEqual(evaluation.candidate_ids, [candidate.candidate_id])
        self.assertEqual(snapshot(root), before)

    def test_dry_run_reuses_work_without_any_source_or_canonical_write(self):
        root, _goal, _candidate, ticket, _receipt = self.fixture()
        before = snapshot(root)
        result = replenishment.replenish_from_goals(root, "fix", dry_run=True)
        self.assertTrue(result.get("replenished"), result)
        self.assertEqual(result.get("admitted_ticket"), ticket)
        self.assertTrue(result.get("reused_work"), result)
        self.assertEqual(snapshot(root), before)

    def test_apply_reuses_work_preserving_source_origin_and_external_blocker(self):
        root, _goal, _candidate, ticket, receipt = self.fixture()
        external = rows(root)["T-1"]["raw"]
        before_source = intake.read_body(root, receipt)["meta"]
        result = replenishment.replenish_from_goals(root, "fix")
        self.assertTrue(result.get("replenished"), result)
        self.assertEqual(result.get("admitted_ticket"), ticket)
        self.assertTrue(result.get("reused_work"), result)
        self.assertEqual(set(rows(root)), {"T-1", ticket})
        self.assertEqual(rows(root)[ticket]["section"], "## TODO")
        self.assertEqual(rows(root)["T-1"]["raw"], external)
        self.assertEqual(intake.read_body(root, receipt)["meta"], before_source)
        self.assertEqual(before_source["request_provenance"]["witness"], "model_supplied")

    def test_compacted_identity_is_read_from_validated_detail(self):
        root, _goal, candidate, ticket, _receipt = self.fixture(long=True)
        self.assertTrue(rows(root)[ticket]["fields"].get("detail_ref"))
        projected = replenishment._parse_board_tickets(root)["blocked"]
        row = next(row for row in projected if row["id"] == ticket)
        self.assertIn(f"candidate: {candidate.candidate_id}", row["text"])
        result = replenishment.replenish_from_goals(root, "fix", dry_run=True)
        self.assertEqual(result.get("admitted_ticket"), ticket, result)

    def test_unverified_or_revoked_grant_cannot_restore_or_allocate(self):
        root, _goal, _candidate, _ticket, _receipt = self.fixture(grant=False)
        before = snapshot(root)
        result = replenishment.replenish_from_goals(root, "fix", dry_run=True)
        self.assertFalse(result.get("replenished"), result)
        self.assertEqual(snapshot(root), before)

    def test_mixed_external_blocker_stays_blocked_with_valid_grant(self):
        root, _goal, _candidate, ticket, _receipt = self.fixture(blocker=
            "CONTINUATION_AUTHORITY_UNPROVEN -- BLOCKED_EXTERNAL publication owned elsewhere")
        before = snapshot(root)
        result = replenishment.replenish_from_goals(root, "fix", dry_run=True)
        self.assertFalse(result.get("replenished"), result)
        self.assertEqual(rows(root)[ticket]["section"], "## BLOCKED")
        self.assertEqual(snapshot(root), before)

    def test_corrupt_linked_source_never_restores_work(self):
        root, _goal, _candidate, _ticket, receipt = self.fixture()
        body = root / f".saipen/intake/active/{receipt}.md"
        body.write_bytes(body.read_bytes() + b"\nchanged fixture bytes\n")
        before = snapshot(root)
        result = replenishment.replenish_from_goals(root, "fix", dry_run=True)
        self.assertFalse(result.get("replenished"), result)
        self.assertEqual(snapshot(root), before)

    def test_candidate_marker_has_exact_identity_not_prefix_or_foreign_goal(self):
        candidate = CandidateTask("parser-gap-1", "maintenance", "Parser repair")
        self.assertFalse(replenishment._matches_candidate(candidate,
            "Parser repair | goal: maintenance | candidate: parser-gap-10"))
        self.assertFalse(replenishment._matches_candidate(candidate,
            "Parser repair | goal: foreign-maintenance | candidate: parser-gap-1"))
        self.assertTrue(replenishment._matches_candidate(candidate,
            "Parser repair | goal: maintenance | candidate: parser-gap-1"))

    def test_candidate_text_in_verify_is_not_description_identity(self):
        root = _project(self, objective=MAINTENANCE_OBJECTIVE)
        added = operations.ticket_add(root, "fix", "P1", "Unrelated fixture work",
            needs=[], verify="Discuss candidate: parser-gap-1 in this oracle")
        self.assertTrue(added.ok, added.to_dict())
        candidate = CandidateTask("parser-gap-1", "maintenance", "Parser repair")
        duplicate, _reason = replenishment._is_candidate_duplicate(candidate,
            replenishment._parse_board_tickets(root))
        self.assertFalse(duplicate)


if __name__ == "__main__":
    unittest.main()
