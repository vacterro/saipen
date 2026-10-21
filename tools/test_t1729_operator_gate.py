"""SRC-228: an authenticated, scoped decision owns its exact gate.

Carrier values below are explicit TEST HARNESS witnesses in disposable
projects. They are never installed into the real project or SAITULS and
do not claim a real operator or production host acceptance.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from saipen_engine import intake, journal, operator_task  # noqa: E402
from saipen_engine.journal import ensure_project_lineage  # noqa: E402
from saipen_engine.pending_ingress import ingress_digest  # noqa: E402
from saipen_engine.reconcile import reconcile_protocol_state  # noqa: E402
from saipen_engine.router import route_next  # noqa: E402
from saipen_engine.state import binding_brake, parse_state_or_error, patch_state  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_recovery_reachability import _project  # noqa: E402

WAIT = (
    "WAIT: blocked -- operator must accept-or-extend the Flush(true) "
    "power-loss durability ceiling before any further work"
)


def setUpModule():
    isolate_host_session()


def capsule(root, *, resolve=None, expires=None):
    """The test harness independently describes the fixture's exact scope."""
    state, error = parse_state_or_error((root / ".saipen/STATE.md").read_text(encoding="utf-8"))
    if error:
        raise AssertionError(error)
    gate = {key: state[key] for key in ("phase", "task", "last_event", "blocker", "next_action")}
    lineage = ensure_project_lineage(root)
    binding = {"project_lineage": lineage, "gate": gate}
    gate_id = hashlib.sha256(json.dumps(
        binding, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")).hexdigest()
    return {
        "kind": "saipen-gate-decision",
        "schema": 1,
        **binding,
        "gate_id": gate_id,
        "resolve": ["blocker", "next_action"] if resolve is None else resolve,
        "decision": "ACCEPT_LIMITATION",
        "statement": "TEST HARNESS operator accepts this fixture limitation only.",
        "expires_at": expires or (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=2))
        .replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def capture(root, value, *, witnessed=True, statement=None):
    value = dict(value)
    if statement is not None:
        value["statement"] = statement
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if witnessed:
        from test_operator_origin_support import native_operator

        with native_operator(root, text, action="resolve-gate"):
            provenance = operator_task.witness(text, root=root)
            result = intake.capture(
                root, text, source_kind="user_instruction", request_provenance=provenance,
                projection_policy=intake.PROJECTION_AUTHORITY_ONLY,
            )
            if result.get("ok"):
                operator_task.authority_for_receipt(root, result["receipt"], existing_only=False)
    else:
        provenance = operator_task.witness(text, env={})
        result = intake.capture(
            root, text, source_kind="user_instruction", request_provenance=provenance,
            projection_policy=intake.PROJECTION_AUTHORITY_ONLY,
        )
    if not result.get("ok"):
        raise AssertionError(result)
    return result["receipt"]


def fixture_authority(root, *, resolve=("blocker",), statement=None, next_action=None):
    """Reusable TEST HARNESS authority; never evidence of real human ingress."""
    ensure_project_lineage(root)
    value = capsule(root, resolve=list(resolve))
    if next_action is not None:
        value["next_action"] = next_action
    return capture(root, value, statement=statement)


class ScopedOperatorDecision(unittest.TestCase):
    def make(self, *, wait=WAIT, blocker="WAIT_USER_CONFIRMATION -- fixture limitation"):
        root = _project(blocker=blocker, next_action=wait, board_blocked=True)
        # Only the exact newly-created fixture is eligible for cleanup.
        self.assertEqual(root.resolve().parent, Path(tempfile.gettempdir()).resolve())
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        ensure_project_lineage(root)
        # Both fixture tickets have explicit allocation evidence. A gate
        # transition must not accidentally introduce unrelated adoption debt.
        log = root / ".saipen/LOG.md"
        log.write_text(
            "# Log\n"
            "- 14.09.26 00:00 [E-1] [T-001] [agent: tester] "
            f"[op: transition-{'a' * 32}] RUN: transition to SCOUT\n"
            "- 14.09.26 00:01 [E-2] [parent: E-1] [T-002] [agent: tester] "
            f"[op: ticket-{'b' * 32}] DEC: ticket added via SAIOPS\n",
            encoding="utf-8",
        )
        path = root / ".saipen/STATE.md"
        path.write_text(patch_state(path.read_text(encoding="utf-8"), {"last_event": 2}),
                        encoding="utf-8")
        return root

    def canonical(self, root):
        return {name: (root / ".saipen" / name).read_bytes()
                for name in ("STATE.md", "BOARD.md", "LOG.md")}

    def state(self, root):
        value, error = parse_state_or_error((root / ".saipen/STATE.md").read_text(encoding="utf-8"))
        self.assertIsNone(error)
        return value

    def resolve(self, root, receipt, *, dry_run=False):
        return reconcile_protocol_state(root, "tester", resolve_blocker=receipt, dry_run=dry_run)

    def with_computed_budget_stop(self, root):
        log = root / ".saipen/LOG.md"
        text = log.read_text(encoding="utf-8")
        text += ("- 14.09.26 00:02 [E-3] [parent: E-2] [agent: tester] "
                 "DEC: goal pivot -- fixture\n")
        for index in range(20):
            text += (f"- 14.09.26 00:02 [E-{index + 4}] [parent: E-{index + 3}] "
                     f"[agent: tester] DEC: goal_tickets {index}->{index + 1}\n")
        log.write_text(text, encoding="utf-8")
        state = root / ".saipen/STATE.md"
        state.write_text(patch_state(state.read_text(encoding="utf-8"), {
            "last_event": 23, "execution_intent": "goal", "goal_tickets": 20,
            "goal_waves": 0, "continuation_authority": "operator_required",
            "authority_source": "E-3", "authority_until": "budget",
            "safety_valve_mode": "hard_wait",
        }), encoding="utf-8")
        return "WAIT: safety valve reached (0 waves / 20 tickets) -- run 'cc' to continue"

    def assert_refused_unchanged(self, root, receipt):
        before = self.canonical(root)
        result = self.resolve(root, receipt)
        self.assertFalse(result["ok"], result)
        self.assertEqual(self.canonical(root), before)
        self.assertIsNotNone(binding_brake(self.state(root)))
        return result

    def test_plain_model_decision_does_not_authorize_a_gate(self):
        root = self.make()
        self.assert_refused_unchanged(root, "OPERATOR_ACCEPTED_LIMITATION vendor renewed")

    def test_model_supplied_source_is_not_promoted_by_a_later_carrier(self):
        root = self.make()
        value = capsule(root)
        receipt = capture(root, value, witnessed=False)
        with mock.patch.dict(os.environ, {
            operator_task.ENV_TASK_SHA256: ingress_digest(json.dumps(value, sort_keys=True))
        }):
            self.assert_refused_unchanged(root, receipt)

    def test_valid_witness_resolves_only_the_matching_gate(self):
        root = self.make()
        before = self.canonical(root)
        receipt = capture(root, capsule(root))
        result = self.resolve(root, receipt)
        self.assertTrue(result["ok"], result)
        state = self.state(root)
        self.assertEqual(state["next_action"], "PHASE SCOUT T-001")
        self.assertEqual(state["blocker"], "none")
        self.assertEqual(state["phase"], "SCOUT")
        self.assertEqual(state["task"], "T-001")
        self.assertIsNone(binding_brake(state))
        self.assertEqual((root / ".saipen/BOARD.md").read_bytes(), before["BOARD.md"])
        route = route_next(
            (root / ".saipen/STATE.md").read_text(encoding="utf-8"),
            before["BOARD.md"].decode("utf-8"), current_agent="tester",
        )
        self.assertEqual(route["action"], "PHASE SCOUT T-001")
        self.assertIn(receipt, (root / ".saipen/LOG.md").read_text(encoding="utf-8"))
        original = list((root / ".saipen/recovery").rglob("*.STATE.md"))
        self.assertTrue(any(path.read_bytes() == before["STATE.md"] for path in original))

    def test_limitation_acceptance_preserves_a_computed_budget_stop(self):
        root = self.make()
        budget_wait = self.with_computed_budget_stop(root)
        receipt = capture(root, capsule(root))
        result = self.resolve(root, receipt)
        self.assertTrue(result["ok"], result)
        state = self.state(root)
        self.assertEqual(state["blocker"], "none")
        self.assertEqual(state["next_action"], budget_wait)
        self.assertEqual(state["goal_tickets"], 20)
        self.assertEqual(state["safety_valve_mode"], "hard_wait")
        self.assertIsNotNone(binding_brake(state))
        route = route_next((root / ".saipen/STATE.md").read_text(encoding="utf-8"),
                           (root / ".saipen/BOARD.md").read_text(encoding="utf-8"),
                           current_agent="tester")
        self.assertEqual(route["action"], budget_wait, route)
        self.assertEqual(route["executable_behavior"], "RESTATE_AND_STOP", route)
        before = self.canonical(root)
        self.assertTrue(self.resolve(root, receipt)["ok"])
        self.assertEqual(self.canonical(root), before)

    def test_requested_resume_cannot_override_a_computed_budget_stop(self):
        root = self.make()
        self.with_computed_budget_stop(root)
        value = capsule(root)
        value["next_action"] = "saipen continue"
        receipt = capture(root, value)
        result = self.assert_refused_unchanged(root, receipt)
        self.assertEqual(result["cause"], "GATE_OWNER_MISMATCH", result)
        self.assertEqual(self.state(root)["goal_tickets"], 20)

    def test_missing_or_wrong_source_digest_cannot_grant_authority(self):
        root = self.make()
        self.assert_refused_unchanged(root, "SRC-999999")
        receipt = capture(root, capsule(root))
        body = root / ".saipen/intake/active" / (receipt + ".md")
        body.write_bytes(body.read_bytes() + b" ")
        self.assert_refused_unchanged(root, receipt)

    def test_project_gate_version_and_digest_mismatch_are_refused(self):
        for field, changed in (
            ("project_lineage", "lineage-foreign"),
            ("gate_id", "0" * 64),
            ("gate", {"phase": "SCOUT", "task": "T-002", "last_event": 0,
                      "blocker": "none", "next_action": WAIT}),
        ):
            with self.subTest(field=field):
                root = self.make()
                value = capsule(root)
                value[field] = changed
                self.assert_refused_unchanged(root, capture(root, value))

    def test_expired_authority_is_not_used(self):
        root = self.make()
        expired = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1))
        value = capsule(root, expires=expired.isoformat().replace("+00:00", "Z"))
        self.assert_refused_unchanged(root, capture(root, value))

    def test_quarantined_authority_is_not_reused(self):
        root = self.make()
        receipt = capture(root, capsule(root))
        result = intake.quarantine_receipt(root, receipt, reason="TEST_REVOKED")
        self.assertTrue(result["ok"], result)
        self.assert_refused_unchanged(root, receipt)

    def test_unrelated_wait_remains_binding_when_only_blocker_is_authorized(self):
        root = self.make(wait="WAIT: user brake -- unrelated operator pause")
        receipt = capture(root, capsule(root, resolve=["blocker"]))
        result = self.resolve(root, receipt)
        self.assertTrue(result["ok"], result)
        state = self.state(root)
        self.assertEqual(state["blocker"], "none")
        self.assertEqual(state["next_action"], "WAIT: user brake -- unrelated operator pause")
        self.assertIsNotNone(binding_brake(state))

    def test_matching_capsule_cannot_waive_a_different_wait_owner(self):
        for category in ("user brake", "manual-verify", "destructive-op", "first-publish"):
            with self.subTest(category=category):
                root = self.make(wait=f"WAIT: {category} -- separate owner")
                self.assert_refused_unchanged(root, capture(root, capsule(root)))

    def test_dry_run_is_pure_and_repeated_acceptance_is_idempotent(self):
        root = self.make()
        receipt = capture(root, capsule(root))
        before = self.canonical(root)
        planned = self.resolve(root, receipt, dry_run=True)
        self.assertTrue(planned["ok"], planned)
        self.assertEqual(self.canonical(root), before)
        first = self.resolve(root, receipt)
        self.assertTrue(first["ok"], first)
        after = self.canonical(root)
        again = self.resolve(root, receipt)
        self.assertTrue(again["ok"], again)
        self.assertEqual(self.canonical(root), after)

    def test_repeated_acceptance_cannot_discharge_a_later_gate(self):
        root = self.make()
        receipt = capture(root, capsule(root))
        self.assertTrue(self.resolve(root, receipt)["ok"])
        path = root / ".saipen/STATE.md"
        path.write_text(patch_state(path.read_text(encoding="utf-8"), {
            "blocker": "WAIT_USER_CONFIRMATION -- a later distinct limitation",
            "next_action": "WAIT: blocked -- a later distinct limitation",
        }), encoding="utf-8")
        before = self.canonical(root)
        result = self.resolve(root, receipt)
        self.assertEqual(result["code"], "ALREADY_APPLIED", result)
        self.assertEqual(self.canonical(root), before)
        self.assertIsNotNone(binding_brake(self.state(root)))

    def test_a_new_checkpoint_invalidates_an_unconsumed_gate_decision(self):
        root = self.make()
        receipt = capture(root, capsule(root))
        from saipen_engine import operations
        result = operations.checkpoint(root, "tester", "DEC", "T-001", "fixture observation")
        self.assertTrue(result.ok, result.to_dict())
        self.assertEqual(self.assert_refused_unchanged(root, receipt)["cause"],
                         "GATE_SCOPE_MISMATCH")

    def test_the_historical_committed_decision_is_not_an_operator_witness(self):
        root = self.make()
        log = root / ".saipen/LOG.md"
        log.write_text(
            log.read_text(encoding="utf-8").replace("[E-1]", "[E-3001]")
            .replace("[E-2]", "[E-3002]").replace("[parent: E-1]", "[parent: E-3001]")
            + "- 14.09.26 00:02 [E-3003] [parent: E-3002] [T-001] [agent: tester] "
            "DEC: operator gate requires Flush(true) acceptance\n"
            + "".join(f"- 14.09.26 00:02 [E-{event}] [parent: E-{event - 1}] "
                      "[agent: tester] RUN: fixture observation\n" for event in range(3004, 3009))
            + "- 14.09.26 00:03 [E-3009] [parent: E-3008] [T-002] [agent: tester] "
            f"[op: ticket-{'c' * 32}] DEC: ticket_move OPERATOR_ACCEPTED_LIMITATION\n"
            + "- 14.09.26 00:04 [E-3010] [parent: E-3009] [agent: tester] "
            "DEC: operator gate satisfied\n"
            + "- 14.09.26 00:05 [E-3011] [parent: E-3010] [agent: tester] "
            "DEC: operator gate satisfied\n", encoding="utf-8",
        )
        path = root / ".saipen/STATE.md"
        path.write_text(patch_state(path.read_text(encoding="utf-8"), {"last_event": 3011}),
                        encoding="utf-8")
        before = self.canonical(root)
        route = route_next(path.read_text(encoding="utf-8"),
                           before["BOARD.md"].decode("utf-8"), current_agent="tester")
        self.assertEqual(route["executable_behavior"], "RESTATE_AND_STOP", route)
        result = reconcile_protocol_state(root, "tester")
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["code"], "RECONCILE_REAUTH_REQUIRED", result)
        self.assertEqual(self.canonical(root), before)
        receipt = capture(root, capsule(root), witnessed=False)
        self.assert_refused_unchanged(root, receipt)

    def test_interrupted_publication_recovers_the_same_authorized_transition(self):
        for stage in ("PREPARED", "log", "state", "generic", "VERIFIED"):
            with self.subTest(stage=stage):
                root = self.make()
                receipt = capture(root, capsule(root))

                def crash(key):
                    if key == stage:
                        raise SystemExit(87)

                interruption = self.assertRaises(SystemExit)
                with mock.patch.object(journal, "_crash_after", side_effect=crash), interruption:
                    self.resolve(root, receipt)
                pending = journal.pending_ops(root)
                self.assertEqual(len(pending), 1, pending)
                result = journal.recovery_preflight(root)
                self.assertTrue(result["ok"], result)
                self.assertFalse(journal.pending_ops(root))
                if stage == "PREPARED":
                    # The journal aborts a zero-write prepared transaction.
                    # Reapplying the still-valid witnessed Source is safe.
                    self.assertIsNotNone(binding_brake(self.state(root)))
                    self.assertTrue(self.resolve(root, receipt)["ok"])
                self.assertIsNone(binding_brake(self.state(root)))
                self.assertEqual(self.state(root)["next_action"], "PHASE SCOUT T-001")
                before = self.canonical(root)
                self.assertTrue(self.resolve(root, receipt)["ok"])
                self.assertEqual(self.canonical(root), before)

    def test_changed_authority_during_apply_refuses_without_state_writes(self):
        from saipen_engine import gate_decision
        root = self.make()
        receipt = capture(root, capsule(root))
        before = self.canonical(root)
        real_apply = gate_decision.apply_plan

        def race(project_root, plan):
            path = root / ".saipen/intake/active" / (receipt + ".md")
            path.write_bytes(path.read_bytes() + b" ")
            return real_apply(project_root, plan)

        with mock.patch.object(gate_decision, "apply_plan", side_effect=race):
            result = self.resolve(root, receipt)
        self.assertFalse(result["ok"], result)
        self.assertEqual(self.canonical(root), before)

    def test_wrong_external_carrier_is_rejected_before_source_capture(self):
        root = self.make()
        from saipen_engine.operations import authority_capture
        text = json.dumps(capsule(root), sort_keys=True)
        before = self.canonical(root)
        with mock.patch.dict(os.environ, {operator_task.ENV_TASK_SHA256: "0" * 64}):
            result = authority_capture(root, "tester", text=text)
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(result.code, operator_task.CODE_MISMATCH)
        self.assertEqual(self.canonical(root), before)

    def test_a_canonical_ticket_move_without_a_witness_grants_no_gate_authority(self):
        from saipen_engine import operations
        root = self.make(wait="PHASE SCOUT T-001", blocker="none")
        moved = operations.ticket_move(
            root, "unblock", "T-002", "tester", "OPERATOR_ACCEPTED_LIMITATION test only"
        )
        self.assertTrue(moved.ok, moved.to_dict())
        records, errors = journal.semantic_receipts_for_operation_safe(root, "ticket_move")
        self.assertFalse(errors, errors)
        self.assertTrue(any(record["status"] == "COMMITTED" for record in records), records)
        path = root / ".saipen/STATE.md"
        path.write_text(patch_state(path.read_text(encoding="utf-8"), {
            "blocker": "WAIT_USER_CONFIRMATION -- fixture limitation", "next_action": WAIT,
        }), encoding="utf-8")
        self.assert_refused_unchanged(root, "OPERATOR_ACCEPTED_LIMITATION test only")
        self.assert_refused_unchanged(root, capture(root, capsule(root), witnessed=False))

    def test_revoked_authority_blocks_recovery_of_an_interrupted_decision(self):
        root = self.make()
        receipt = capture(root, capsule(root))

        def crash(key):
            if key == "log":
                raise SystemExit(87)

        interruption = self.assertRaises(SystemExit)
        with mock.patch.object(journal, "_crash_after", side_effect=crash), interruption:
            self.resolve(root, receipt)
        path = root / ".saipen/intake/active" / (receipt + ".md")
        path.write_bytes(path.read_bytes() + b" ")
        result = journal.recovery_preflight(root)
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["code"], "CONFLICT", result)
        route = route_next(
            (root / ".saipen/STATE.md").read_text(encoding="utf-8"),
            (root / ".saipen/BOARD.md").read_text(encoding="utf-8"),
            current_agent="tester",
            pending_ops=[op["op_id"] for op in journal.pending_ops(root)],
            conflict_ops=[op["op_id"] for op in journal.pending_conflicts(root)],
        )
        self.assertEqual(route["reason"], "recovery-conflict", route)
        self.assertIsNotNone(binding_brake(self.state(root)))

    def test_changed_project_identity_before_apply_refuses(self):
        from saipen_engine import gate_decision
        from saipen_engine.paths import identity_file_content, new_project_lineage
        root = self.make()
        receipt = capture(root, capsule(root))
        before = self.canonical(root)
        real_apply = gate_decision.apply_plan

        def race(project_root, plan):
            (root / ".saipen/IDENTITY.md").write_text(
                identity_file_content(new_project_lineage()), encoding="utf-8"
            )
            return real_apply(project_root, plan)

        with mock.patch.object(gate_decision, "apply_plan", side_effect=race):
            result = self.resolve(root, receipt)
        self.assertFalse(result["ok"], result)
        self.assertEqual(self.canonical(root), before)

    def test_original_operator_text_is_preserved_by_native_capture_and_restart(self):
        root = self.make()
        value = capsule(root)
        text = json.dumps(value, sort_keys=True, ensure_ascii=False)
        path = root / ".saipen/evidence/operator-capsule.json"
        path.parent.mkdir()
        path.write_text(text, encoding="utf-8")
        env = {key: val for key, val in os.environ.items()
               if not key.startswith("SAIPEN_")}
        env[operator_task.ENV_TASK_SHA256] = ingress_digest(text)

        def native(args, environment):
            from test_operator_origin_support import cold_command

            command = cold_command(
                root, [sys.executable, "-B", str(TOOLS / "saipen.py"), *args, "--json"],
                environment, operator_text=text if args[:2] == ["authority", "capture"] else None,
                action="resolve-gate",
            )
            run = subprocess.run(
                command,
                cwd=root, env=environment, capture_output=True, text=True,
                encoding="utf-8", timeout=60, check=False,
            )
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            return json.loads(run.stdout)

        captured = native(["authority", "capture", "--file", str(path)], env)
        clean = {key: val for key, val in env.items()
                 if key not in (operator_task.ENV_TASK_SHA256, operator_task.ENV_TASK_FILE)}
        native(["recover", "resolve-blocker", captured["receipt"]], clean)
        self.assertIsNone(binding_brake(self.state(root)))
        snapshot = self.canonical(root)
        native(["recover"], clean)
        self.assertEqual(self.state(root)["next_action"], "PHASE SCOUT T-001")
        # Restart/reconcile may maintain projections, but never restore the WAIT.
        self.assertEqual((root / ".saipen/BOARD.md").read_bytes(), snapshot["BOARD.md"])


if __name__ == "__main__":
    unittest.main()
