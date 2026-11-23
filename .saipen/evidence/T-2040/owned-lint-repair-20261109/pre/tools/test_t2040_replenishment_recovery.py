"""T-2040 residual recovery controls; disposable broker/project fixtures only.

Run: python -B tools/test_t2040_replenishment_recovery.py -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_hermetic_env import isolate_host_session
from test_operator_origin_support import use_case_owner
from test_t2040_maintenance_authority import (
    RestoredMaintenanceCandidate, current, rows, snapshot,
)
from test_t2023_goal_management_and_maintenance_binding import (
    MAINTENANCE_OBJECTIVE, _read_history, _witnessed_apply,
)
from saipen_engine import goal_authority, intake, operations, replenishment
from saipen_engine.discovery_providers import CandidateTask
from saipen_engine.journal import Journal, recover
from saipen_engine.plan import apply_plan
from saipen_engine.result import Result


def setUpModule():
    isolate_host_session()


class ReplenishmentRecovery(unittest.TestCase):
    def fixture(self, *, grant=True, native=False, long=False):
        fixture = RestoredMaintenanceCandidate.fixture(
            self, grant=grant and not native, long=long,
        )
        root, _goal, _candidate, _ticket, _receipt = fixture
        if native:
            host = use_case_owner(self, root)
            self.assertIsNotNone(host.offer(root, MAINTENANCE_OBJECTIVE, action="goal"))
            entered = operations.goal_entry(root, "fix", MAINTENANCE_OBJECTIVE)
            self.assertTrue(entered.ok, entered.to_dict())
            for ticket in rows(root).values():
                if ticket["section"] == "## DOING":
                    parked = operations.ticket_move(root, "block", ticket["id"], "fix",
                        payload="CONTINUATION_AUTHORITY_UNPROVEN -- fixture native goal checkpoint")
                    self.assertTrue(parked.ok, parked.to_dict())
            if grant:
                proposal = goal_authority.propose_capsule(root, current(root), _read_history(root))
                self.assertTrue(proposal["ok"], proposal)
                applied = _witnessed_apply(self, root, proposal["capsule_text"])
                self.assertTrue(applied.ok, applied.to_dict())
        return fixture

    def plan(self, root):
        captured = []

        def capture(_root, plan):
            captured.append(plan)
            return Result(ok=False, code="RECOVERY_REQUIRED", message="fixture interruption")

        with mock.patch("saipen_engine.plan.apply_plan", side_effect=capture):
            result = replenishment.replenish_from_goals(root, "fix")
        self.assertFalse(result.get("replenished"), result)
        self.assertEqual(len(captured), 1, result)
        return captured[0]

    def interrupted(self, root, plan):
        written = {target.path for target in plan.targets}
        journal = Journal(root, plan.op_id)
        journal.start(plan.operation, plan.agent, plan.project_identity,
            plan.semantic_payload_hash,
            [{"path": t.path, "role": t.role, "content": t.content,
              "before_hash": t.before_hash, "after_hash": t.after_hash} for t in plan.targets],
            preconditions={p: h for p, h in plan.preconditions.items() if p in written},
            read_preconditions={p: h for p, h in plan.preconditions.items() if p not in written},
            verification_policy="core_fast", receipt_metadata=plan.receipt_metadata)
        first = plan.targets[0]
        self.assertNotEqual(first.before_hash, first.after_hash)
        (root / first.path).write_bytes(first.content)
        journal.mark("APPLYING", progress_index=1, target_index=0)
        return journal

    def test_missing_board_is_invalid_not_an_empty_queue(self):
        with tempfile.TemporaryDirectory(prefix="t2040-missing-board-") as name:
            root = Path(name)
            with self.subTest(reader=True), self.assertRaises(ValueError):
                replenishment._parse_board_tickets(root)
            with self.subTest(entrypoint=True):
                result = replenishment.replenish_from_goals(root, "fix", dry_run=True)
                self.assertEqual(result.get("status"), "BOARD_INVALID", result)
                self.assertEqual(snapshot(root), {})

    def test_malformed_board_and_noncanonical_encoding_fail_closed(self):
        with tempfile.TemporaryDirectory(prefix="t2040-invalid-board-") as name:
            root = Path(name)
            board = root / ".saipen/BOARD.md"
            board.parent.mkdir()
            for data in (b"", b"## TODO\n", b"\xef\xbb\xbf## DOING\n## TODO\n## DONE\n## BLOCKED\n"):
                with self.subTest(data=data):
                    board.write_bytes(data)
                    before = snapshot(root)
                    result = replenishment.replenish_from_goals(root, "fix", dry_run=True)
                    self.assertEqual(result.get("status"), "BOARD_INVALID", result)
                    self.assertEqual(snapshot(root), before)

    def test_exact_legacy_candidate_is_scoped_not_foreign_or_prefix(self):
        candidate = CandidateTask("g-race-proc1", "g-race", "Proc 1")
        self.assertTrue(replenishment._matches_candidate(candidate,
            "Proc 1 candidate: g-race-proc1"))
        for text in ("Proc 1 candidate: g-race-proc10",
                     "Proc 1 | goal: foreign | candidate: g-race-proc1",
                     "Proc 1 [foreign] candidate: g-race-proc1"):
            with self.subTest(text=text):
                self.assertFalse(replenishment._matches_candidate(candidate, text))

    def test_prose_does_not_acquire_candidate_identity(self):
        candidate = CandidateTask("parser-gap-1", "maintenance", "Parser repair")
        for text in ("Memo about Parser repair | goal: maintenance",
                     "Discuss candidate: parser-gap-1 | goal: maintenance",
                     "Mention parser-gap-1 | goal: maintenance"):
            with self.subTest(text=text):
                self.assertFalse(replenishment._matches_candidate(candidate, text))
        self.assertTrue(replenishment._matches_candidate(candidate,
            "Parser repair | goal: maintenance | candidate: parser-gap-1"))

    def test_legacy_blocked_identity_deduplicates_but_never_restores(self):
        root, _goal, candidate, ticket, _receipt = self.fixture()
        board = root / ".saipen/BOARD.md"
        original = rows(root)[ticket]["raw"]
        from saipen_engine.board import escape_ticket_description
        description = f"Bounded local repair candidate: {candidate.candidate_id}"
        board.write_text(board.read_text(encoding="utf-8").replace(
            original, original.replace(escape_ticket_description(rows(root)[ticket]["description"]),
                                       escape_ticket_description(description))), encoding="utf-8")
        self.assertEqual(rows(root)[ticket]["description"], description)
        before = snapshot(root)
        result = replenishment.replenish_from_goals(root, "fix", dry_run=True)
        self.assertFalse(result.get("replenished"), result)
        self.assertEqual(snapshot(root), before)

    def test_native_restore_preserves_sources_origin_foreign_work_and_replay(self):
        root, _goal, _candidate, ticket, _receipt = self.fixture(native=True)
        foreign = rows(root)["T-1"]["raw"]
        before_sources = {p: h for p, h in snapshot(root).items() if p.startswith(".saipen/intake/")}
        plan = self.plan(root)
        result = apply_plan(root, plan)
        self.assertTrue(result.ok, result.to_dict())
        self.assertEqual(rows(root)[ticket]["section"], "## TODO")
        self.assertEqual(rows(root)["T-1"]["raw"], foreign)
        self.assertEqual({p: h for p, h in snapshot(root).items() if p.startswith(".saipen/intake/")}, before_sources)
        self.assertEqual(goal_authority.prove(root, current(root)), [])
        before = snapshot(root)
        replay = replenishment.replenish_from_goals(root, "fix")
        self.assertEqual(replay.get("status"), "TODO_AVAILABLE", replay)
        self.assertEqual(snapshot(root), before)

    def test_same_native_fixture_without_maintenance_grant_never_allocates(self):
        root, _goal, _candidate, _ticket, _receipt = self.fixture(native=True, grant=False)
        before = snapshot(root)
        for dry_run in (True, False):
            result = replenishment.replenish_from_goals(root, "fix", dry_run=dry_run)
            self.assertFalse(result.get("replenished"), result)
            self.assertEqual(snapshot(root), before)

    def test_source_metadata_and_index_must_name_same_exact_receipt(self):
        for change in ("receipt_id", "status", "index_digest", "index_membership"):
            with self.subTest(change=change):
                root, _goal, _candidate, _ticket, receipt = self.fixture()
                meta_path = root / f".saipen/intake/active/{receipt}.meta.json"
                index_path = root / ".saipen/intake/index.json"
                path = index_path if change.startswith("index_") else meta_path
                data = json.loads(path.read_text(encoding="utf-8"))
                if change == "index_digest":
                    data["active"][receipt]["source_sha256"] = "f" * 64
                elif change == "index_membership":
                    data["active"][receipt]["linked_work"] = "T-1"
                else:
                    data[change] = "SRC-999" if change == "receipt_id" else "CLOSED"
                path.write_text(json.dumps(data), encoding="utf-8")
                before = snapshot(root)
                result = replenishment.replenish_from_goals(root, "fix", dry_run=True)
                self.assertFalse(result.get("replenished"), result)
                self.assertEqual(snapshot(root), before)

    def test_source_drift_between_plan_apply_and_recovery_never_unblocks(self):
        for recovering in (False, True):
            with self.subTest(recovering=recovering):
                root, _goal, _candidate, ticket, receipt = self.fixture(native=True)
                plan = self.plan(root)
                if recovering:
                    self.interrupted(root, plan)
                body = root / f".saipen/intake/active/{receipt}.md"
                body.write_bytes(body.read_bytes() + b"\nfixture drift\n")
                result = recover(root, plan.op_id) if recovering else apply_plan(root, plan).to_dict()
                self.assertFalse(result["ok"], result)
                self.assertEqual(rows(root)[ticket]["section"], "## BLOCKED")

    def test_goal_policy_is_pinned_for_apply_and_recovery(self):
        for recovering in (False, True):
            with self.subTest(recovering=recovering):
                root, goal, _candidate, ticket, _receipt = self.fixture(native=True)
                plan = self.plan(root)
                if recovering:
                    self.interrupted(root, plan)
                path = root / f".saipen/goals/{goal.goal_id}.json"
                data = json.loads(path.read_text(encoding="utf-8"))
                data["success_criteria"]["new_policy"] = "fresh approval required"
                path.write_text(json.dumps(data), encoding="utf-8")
                result = recover(root, plan.op_id) if recovering else apply_plan(root, plan).to_dict()
                self.assertFalse(result["ok"], result)
                self.assertEqual(rows(root)[ticket]["section"], "## BLOCKED")

    def revoke(self, root, plan):
        for path in plan.preconditions:
            if path.startswith(".saipen/intake/active/") and path.endswith(".meta.json"):
                meta = json.loads((root / path).read_text(encoding="utf-8"))
                proof = (meta.get("request_provenance") or {}).get("operator_origin")
                if proof and proof.get("action") == "authorize-goal":
                    result = self._host.fixture.broker.handle(
                        {"op": "revoke-origin", "host": "claude", "proof": proof},
                        self._host.fixture.native_peer)
                    self.assertTrue(result.get("ok"), result)
                    return
        self.fail("native standing grant Source not pinned")

    def test_revoked_native_grant_never_restores_or_allocates(self):
        root, _goal, _candidate, ticket, _receipt = self.fixture(native=True)
        self.revoke(root, self.plan(root))
        before = snapshot(root)
        result = replenishment.replenish_from_goals(root, "fix")
        self.assertFalse(result.get("replenished"), result)
        self.assertEqual(rows(root)[ticket]["section"], "## BLOCKED")
        self.assertEqual(snapshot(root), before)

    def test_native_revocation_after_plan_refuses_before_work_write(self):
        root, _goal, _candidate, ticket, _receipt = self.fixture(native=True)
        original = operations._ticket_targets

        def revoke_after(*args, **kwargs):
            plan = original(*args, **kwargs)
            self.revoke(root, plan)
            return plan

        before = snapshot(root)
        with mock.patch.object(operations, "_ticket_targets", side_effect=revoke_after):
            result = replenishment.replenish_from_goals(root, "fix")
        self.assertFalse(result.get("replenished"), result)
        self.assertEqual(rows(root)[ticket]["section"], "## BLOCKED")
        self.assertEqual(snapshot(root), before)

    def test_recovery_rechecks_revoked_native_grant_before_unblock(self):
        root, _goal, _candidate, ticket, _receipt = self.fixture(native=True)
        plan = self.plan(root)
        self.interrupted(root, plan)
        self.revoke(root, plan)
        before_board = (root / ".saipen/BOARD.md").read_bytes()
        result = recover(root, plan.op_id)
        self.assertFalse(result.get("ok"), result)
        self.assertEqual(rows(root)[ticket]["section"], "## BLOCKED")
        self.assertEqual((root / ".saipen/BOARD.md").read_bytes(), before_board)

    def test_unchanged_interrupted_native_restore_recovers_once(self):
        root, _goal, _candidate, ticket, _receipt = self.fixture(native=True)
        plan = self.plan(root)
        self.interrupted(root, plan)
        result = recover(root, plan.op_id)
        self.assertTrue(result.get("ok"), result)
        self.assertEqual(rows(root)[ticket]["section"], "## TODO")
        before = snapshot(root)
        self.assertEqual(recover(root, plan.op_id).get("code"), "ALREADY_APPLIED")
        self.assertEqual(snapshot(root), before)


if __name__ == "__main__":
    unittest.main()
