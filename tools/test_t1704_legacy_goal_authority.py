"""A prospective grant for an existing goal never rewrites its history.

All operator carriers and legacy records below are explicit fixture doubles.
No test grants authority to the maintainer's live project.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from saipen_engine import codec, goal_authority, intake, operations, state  # noqa: E402
from saipen_engine.journal import Journal, semantic_receipts_for_operation_safe  # noqa: E402
from saipen_engine.lock import project_writer_lock  # noqa: E402
from saipen_engine.log import read_history_snapshot  # noqa: E402
from saipen_engine.paths import project_lineage_identity  # noqa: E402
from saipen_engine.cold_recovery import goal_ingress_identity  # noqa: E402
from saipen_engine.iteration_verdict import project_iteration_verdict  # noqa: E402
from saipen_engine.reconcile import _derived_goal_counters  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_t1363_zero_manual_entry import _allocation_log, _stamp, cli, project  # noqa: E402

OBJECTIVE = "Maintain the protocol under its existing roadmap until completion"


def setUpModule():
    isolate_host_session()


class LegacyGoalAuthorityTests(unittest.TestCase):
    def current(self, root):
        return state.parse_state(codec.read_doc(root / ".saipen/STATE.md"))

    def snapshot(self, root):
        return tuple(
            (root / ".saipen" / name).read_bytes() for name in ("STATE.md", "BOARD.md", "LOG.md")
        )

    def patch_state(self, root, fields):
        p = root / ".saipen/STATE.md"
        p.write_text(state.patch_state(codec.read_doc(p), fields), encoding="utf-8")

    def legacy(self, *, tickets=0, waves=0):
        board = (
            "## DOING\n- [/] T-1703 [P2] interrupted evidence slice | verify: independent review "
            f"| owner: test-agent | claim_time: {_stamp(-1)}\n"
            "## TODO\n## DONE\n## BLOCKED\n"
        )
        root = project(
            self,
            board=board,
            log=_allocation_log("T-1703"),
            phase="REVIEW",
            transition_from="VERIFY",
            task="T-1703",
            next_action="PHASE REVIEW T-1703",
        )
        self.patch_state(root, {"saipen_home": str(TOOLS.parent)})
        entered = operations.set_goal_intent(root, "test-agent", OBJECTIVE)
        self.assertTrue(entered.ok, entered.to_dict())
        for key, desired in (("goal_waves", waves), ("goal_tickets", tickets)):
            for value in range(desired):
                counted = operations.checkpoint(
                    root, "test-agent", "DEC", None, f"{key} {value}->{value + 1}"
                )
                self.assertTrue(counted.ok, counted.to_dict())
        fields = {"goal_waves": waves, "goal_tickets": tickets}
        if tickets >= 20 or waves >= 3:
            fields["next_action"] = (
                f"WAIT: safety valve reached ({waves} waves / {tickets} tickets) "
                "-- run 'cc' to continue"
            )
        self.patch_state(root, fields)
        return root

    def capsule(self, root, **changes):
        history = read_history_snapshot(root).events
        pivot = [
            e for e in history if e["taxonomy"] == "DEC" and e["text"].startswith("goal pivot --")
        ][-1]
        identity = project_lineage_identity(root)
        event_bytes = json.dumps(
            {
                k: pivot.get(k)
                for k in ("date", "event", "parent", "ticket", "agent", "op_id", "taxonomy", "text")
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
        value = {
            "kind": "saipen-goal-continuation",
            "project_lineage": identity,
            **goal_authority.grant_fields(f"E-{pivot['event']}"),
            "goal_objective": pivot["text"][len("goal pivot -- ") :],
            "goal_event_sha256": hashlib.sha256(event_bytes).hexdigest(),
            "goal_ingress": goal_ingress_identity(
                hashlib.sha256(event_bytes).hexdigest(), identity
            ),
        }
        value.update(changes)
        return json.dumps(value, sort_keys=True, ensure_ascii=False)

    def upgrade(self, root, body=None, *, witnessed=True, dry_run=False):
        from test_operator_origin_support import native_operator, use_case_owner

        body = self.capsule(root) if body is None else body
        if not witnessed:
            return operations.authorize_goal_continuation(root, "test-agent", body, dry_run=dry_run)
        use_case_owner(self, root)
        with native_operator(root, body, action="authorize-goal"):
            return operations.authorize_goal_continuation(root, "test-agent", body, dry_run=dry_run)

    def test_fresh_grant_preserves_review_work_counters_board_and_original_journal(self):
        root = self.legacy(tickets=20)
        before = self.current(root)
        board = self.snapshot(root)[1]
        records, _ = semantic_receipts_for_operation_safe(root, "goal")
        old = Journal(root, records[-1]["op_id"]).manifest.read_bytes()
        result = self.upgrade(root)
        self.assertTrue(result.ok, result.to_dict())
        after = self.current(root)
        for key in (
            "phase",
            "task",
            "agent",
            "transition_from",
            "goal_waves",
            "goal_tickets",
            "next_action",
        ):
            self.assertEqual(after[key], before[key], key)
        self.assertEqual(self.snapshot(root)[1], board)
        self.assertEqual(Journal(root, records[-1]["op_id"]).manifest.read_bytes(), old)
        self.assertEqual(goal_authority.prove(root, after), [])
        self.assertEqual(after["continuation_authority"], "operator_persistent")

    def test_ticket_checkpoint_resumes_exact_active_review_after_restart(self):
        root = self.legacy(tickets=20)
        self.assertTrue(self.upgrade(root).ok)
        code, payload, output = cli(root, "continue", "--json")
        self.assertEqual(code, 0, output)
        current = self.current(root)
        self.assertEqual(
            (current["phase"], current["task"], current["goal_tickets"]), ("REVIEW", "T-1703", 0)
        )
        self.assertIn("goal checkpoint --", codec.read_doc(root / ".saipen/LOG.md"))
        self.assertNotEqual(payload.get("code"), "RECONCILE_REAUTH_REQUIRED")

    def test_wave_checkpoint_uses_the_same_grant(self):
        root = self.legacy(waves=3)
        self.assertTrue(self.upgrade(root).ok)
        code, _, output = cli(root, "continue", "--json")
        self.assertEqual(code, 0, output)
        self.assertEqual(
            (self.current(root)["goal_waves"], self.current(root)["phase"]), (0, "REVIEW")
        )

    def test_model_origin_is_refused_before_capture(self):
        root = self.legacy()
        before = self.snapshot(root)
        result = self.upgrade(root, witnessed=False)
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(self.snapshot(root), before)
        self.assertFalse((root / ".saipen/intake").exists())

    def test_wrong_carrier_digest_is_refused(self):
        root = self.legacy()
        before = self.snapshot(root)
        with patch.dict(os.environ, {"SAIPEN_TASK_SHA256": "f" * 64}):
            result = operations.authorize_goal_continuation(root, "test-agent", self.capsule(root))
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(self.snapshot(root), before)

    def test_capsule_must_name_exact_goal_objective_event_and_project(self):
        for changes in (
            {"project_lineage": "lineage-" + "f" * 32},
            {"authority_source": "E-9999"},
            {"goal_objective": "replace the roadmap"},
            {"goal_event_sha256": "0" * 64},
            {"authority_until": "forever"},
            {"goal_ingress": "goal-" + "0" * 16},
        ):
            root = self.legacy()
            before = self.snapshot(root)
            result = self.upgrade(root, self.capsule(root, **changes))
            self.assertFalse(result.ok, (changes, result.to_dict()))
            self.assertEqual(self.snapshot(root), before)

    def test_fresh_native_event_keeps_existing_model_source_unpromoted(self):
        root = self.legacy()
        body = self.capsule(root)
        captured = intake.capture(root, body, projection_policy=intake.PROJECTION_AUTHORITY_ONLY)
        self.assertTrue(captured["ok"], captured)
        before = self.snapshot(root)
        original = intake.read_body(root, captured["receipt"])["meta"]
        carrier = {"SAIPEN_TASK_SHA256": hashlib.sha256(body.encode()).hexdigest()}
        with patch.dict(os.environ, carrier):
            refused = self.upgrade(root, body, witnessed=False)
        self.assertFalse(refused.ok, refused.to_dict())
        self.assertEqual(self.snapshot(root), before)
        result = self.upgrade(root, body)
        self.assertTrue(result.ok, result.to_dict())
        self.assertNotEqual(result.data["authorization_receipt"], captured["receipt"])
        self.assertEqual(self.snapshot(root)[1], before[1])
        self.assertEqual(intake.read_body(root, captured["receipt"])["meta"], original)
        self.assertEqual(original["request_provenance"]["witness"], "model_supplied")

    def test_preview_writes_no_source_or_lifecycle_bytes(self):
        root = self.legacy()
        before = self.snapshot(root)
        result = self.upgrade(root, dry_run=True)
        self.assertTrue(result.ok, result.to_dict())
        self.assertEqual(self.snapshot(root), before)
        self.assertFalse((root / ".saipen/intake").exists())

    def test_identical_replay_reuses_grant_and_event_without_carrier(self):
        root = self.legacy()
        body = self.capsule(root)
        first = self.upgrade(root, body)
        self.assertTrue(first.ok, first.to_dict())
        before = self.snapshot(root)
        second = self.upgrade(root, body, witnessed=False)
        self.assertTrue(second.ok, second.to_dict())
        self.assertEqual(second.op_id, first.op_id)
        self.assertEqual(self.snapshot(root), before)

    def test_missing_original_goal_journal_refuses(self):
        root = self.legacy()
        body = self.capsule(root)
        records, _ = semantic_receipts_for_operation_safe(root, "goal")
        # Delete one exact fixture manifest, never a live project directory.
        manifest = Journal(root, records[-1]["op_id"]).manifest
        self.assertTrue(manifest.resolve().is_relative_to(root.resolve()))
        manifest.unlink()
        before = self.snapshot(root)
        self.assertFalse(self.upgrade(root, body).ok)
        self.assertEqual(self.snapshot(root), before)

    def test_missing_grant_journal_cannot_reset_checkpoint(self):
        root = self.legacy(tickets=20)
        result = self.upgrade(root)
        self.assertTrue(result.ok, result.to_dict())
        manifest = Journal(root, result.op_id).manifest
        self.assertTrue(manifest.resolve().is_relative_to(root.resolve()))
        manifest.unlink()
        before = self.snapshot(root)
        code, _, _ = cli(root, "continue", "--json")
        self.assertNotEqual(code, 0)
        self.assertEqual(self.snapshot(root), before)

    def test_concurrent_writer_cannot_create_a_grant(self):
        root = self.legacy()
        before = self.snapshot(root)
        with project_writer_lock(root):
            result = self.upgrade(root)
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(self.snapshot(root), before)

    def test_user_brake_survives_grant_and_continuation(self):
        root = self.legacy(tickets=20)
        self.patch_state(root, {"next_action": "WAIT: user brake -- explicit STOP"})
        self.assertTrue(self.upgrade(root).ok)
        before = self.snapshot(root)
        cli(root, "continue", "--json")
        self.assertEqual(self.snapshot(root), before)

    def test_native_event_keeps_imported_source_unpromoted(self):
        root = self.legacy()
        body = self.capsule(root)
        with patch.dict(
            os.environ, {"SAIPEN_TASK_SHA256": hashlib.sha256(body.encode()).hexdigest()}
        ):
            captured = intake.capture(
                root,
                body,
                source_kind="external_audit",
                request_provenance={"witness": "model_supplied"},
                projection_policy=intake.PROJECTION_AUTHORITY_ONLY,
            )
        self.assertTrue(captured["ok"], captured)
        before = self.snapshot(root)
        original = intake.read_body(root, captured["receipt"])["meta"]
        carrier = {"SAIPEN_TASK_SHA256": hashlib.sha256(body.encode()).hexdigest()}
        with patch.dict(os.environ, carrier):
            self.assertFalse(self.upgrade(root, body, witnessed=False).ok)
        self.assertEqual(self.snapshot(root), before)
        accepted = self.upgrade(root, body)
        self.assertTrue(accepted.ok, accepted.to_dict())
        self.assertNotEqual(accepted.data["authorization_receipt"], captured["receipt"])
        self.assertEqual(intake.read_body(root, captured["receipt"])["meta"], original)
        self.assertEqual(original["source_kind"], "external_audit")
        self.assertEqual(self.snapshot(root)[1], before[1])

    def test_replayed_capsule_cannot_authorize_another_project(self):
        first = self.legacy()
        body = self.capsule(first)
        self.assertTrue(self.upgrade(first, body).ok)
        other = self.legacy()
        before = self.snapshot(other)
        self.assertFalse(self.upgrade(other, body).ok)
        self.assertEqual(self.snapshot(other), before)
        self.assertNotIn("continuation_authority", self.current(other))

    def test_goal_replacement_does_not_inherit_a_previous_grant(self):
        root = self.legacy()
        old = self.capsule(root)
        self.assertTrue(self.upgrade(root, old).ok)
        replaced = operations.set_goal_intent(root, "test-agent", "A separate objective")
        self.assertTrue(replaced.ok, replaced.to_dict())
        before = self.snapshot(root)
        self.assertFalse(self.upgrade(root, old).ok)
        self.assertEqual(self.snapshot(root), before)
        self.assertNotIn("continuation_authority", self.current(root))

    def test_replacement_cannot_reuse_an_ingress_from_a_different_goal(self):
        root = self.legacy()
        self.assertTrue(self.upgrade(root).ok)
        previous = self.current(root)["goal_ingress"]
        self.assertTrue(operations.set_goal_intent(root, "test-agent", "Different objective").ok)
        self.assertEqual(self.current(root)["goal_ingress"], previous)
        before = self.snapshot(root)
        result = self.upgrade(root)
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(self.snapshot(root), before)

    def test_corrupted_or_revoked_source_refuses_continuation(self):
        for field, value in (
            ("request_provenance", {"witness": "model_supplied"}),
            ("status", "RETIRED"),
        ):
            root = self.legacy(tickets=20)
            result = self.upgrade(root)
            self.assertTrue(result.ok, result.to_dict())
            path = root / f".saipen/intake/active/{result['authorization_receipt']}.meta.json"
            meta = json.loads(path.read_text())
            meta[field] = value
            path.write_text(json.dumps(meta), encoding="utf-8")
            before = self.snapshot(root)
            self.assertTrue(goal_authority.prove(root, self.current(root)))
            code, _, text = cli(root, "continue", "--json")
            self.assertNotEqual(code, 0, text)
            self.assertEqual(self.snapshot(root), before)

    def test_corrupt_transition_manifest_refuses_continuation(self):
        root = self.legacy(tickets=20)
        result = self.upgrade(root)
        self.assertTrue(result.ok, result.to_dict())
        Journal(root, result.op_id).manifest.write_bytes(b"{not-json")
        before = self.snapshot(root)
        code, _, text = cli(root, "continue", "--json")
        self.assertNotEqual(code, 0, text)
        self.assertEqual(self.snapshot(root), before)

    def test_crashed_transition_recovers_exact_prepared_bytes_without_a_new_grant(self):
        for boundary in ("PREPARE", "LOG", "STATE", "VERIFIED"):
            root = self.legacy(tickets=20)
            body = self.capsule(root)
            crash_env = {f"NITRO_CRASH_AFTER_{boundary}": "1"}
            with patch.dict(os.environ, crash_env), self.assertRaises(SystemExit) as crash:
                self.upgrade(root, body)
            self.assertEqual(crash.exception.code, 87)
            code, _, text = cli(root, "recover", "--json")
            self.assertEqual(code, 0, (boundary, text))
            if boundary == "PREPARE":
                records, errors = semantic_receipts_for_operation_safe(root, "goal_authorize")
                self.assertFalse(errors, errors)
                self.assertEqual(records[-1]["status"], "ABORTED")
                self.assertNotIn("continuation_authority", self.current(root))
                self.assertFalse(self.upgrade(root, body, witnessed=False).ok)
                # The aborted attempt remains evidence. Only a fresh carrier
                # can authorize a new attempt after a zero-write rollback.
                self.assertTrue(self.upgrade(root, body).ok)
            self.assertEqual(goal_authority.prove(root, self.current(root)), [], (boundary, text))
            self.assertEqual(
                (self.current(root)["phase"], self.current(root)["goal_tickets"]), ("REVIEW", 20)
            )
            before = self.snapshot(root)
            replay = self.upgrade(root, body, witnessed=False)
            self.assertTrue(replay.ok, replay.to_dict())
            self.assertEqual(self.snapshot(root), before)
            log = codec.read_doc(root / ".saipen/LOG.md")
            self.assertEqual(log.count("DEC: goal authority transition --"), 1)

    def test_native_router_iteration_and_reconstructed_counts_agree(self):
        root = self.legacy(tickets=20)
        audit = root / "audit/1.md"
        audit.parent.mkdir()
        audit.write_text("# Independent audit\n\nKeep this queued.\n", encoding="utf-8")
        self.assertTrue(self.upgrade(root).ok)
        code, _, text = cli(root, "validate", "--json")
        self.assertEqual(code, 0, text)
        verdict = project_iteration_verdict(root)
        self.assertEqual(verdict["decision"], "AUTO_KICK", verdict)
        self.assertFalse(verdict["requires_human"], verdict)
        code, status, text = cli(root, "status", "--json")
        self.assertEqual(code, 0, text)
        self.assertEqual(status["goal_authority"]["state"], "persistent_verified", text)
        code, _, text = cli(root, "continue", "--json")
        self.assertEqual(code, 0, text)
        self.assertTrue(audit.exists())
        self.assertEqual(
            _derived_goal_counters(read_history_snapshot(root).events),
            {"goal_waves": 0, "goal_tickets": 0},
        )
        code, _, text = cli(root, "validate", "--json")
        self.assertEqual(code, 0, text)

    def test_foreign_claim_cannot_receive_a_grant(self):
        root = self.legacy()
        before = self.snapshot(root)
        body = self.capsule(root)
        with patch.dict(
            os.environ, {"SAIPEN_TASK_SHA256": hashlib.sha256(body.encode()).hexdigest()}
        ):
            result = operations.authorize_goal_continuation(root, "another-agent", body)
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(self.snapshot(root), before)

    def test_genuine_external_blocker_prevents_automatic_checkpoint(self):
        root = self.legacy(tickets=20)
        self.patch_state(root, {"blocker": "BLOCKED_EXTERNAL -- account login required"})
        self.assertTrue(self.upgrade(root).ok)
        before = self.snapshot(root)
        cli(root, "continue", "--json")
        self.assertEqual(self.snapshot(root), before)

    def test_cli_consumes_exact_capsule_and_does_not_replan(self):
        root = self.legacy()
        body = self.capsule(root)
        path = root / "operator-capsule.json"
        path.write_text(body, encoding="utf-8", newline="")
        board = self.snapshot(root)[1]
        code, payload, text = cli(
            root, "goal", "authorize", "--file", str(path), "--json", operator_text=body
        )
        self.assertEqual(code, 0, text)
        self.assertEqual(payload["code"], "GOAL_AUTHORIZED", text)
        self.assertEqual(self.snapshot(root)[1], board)

    def test_source_change_after_proof_is_rejected_by_apply_cas(self):
        root = self.legacy()
        before = self.snapshot(root)
        real_apply = operations.apply_plan

        def raced(subject, plan):
            grant = plan.receipt_metadata["goal_authority_transition"]
            path = root / f".saipen/intake/active/{grant['authorization_receipt']}.md"
            path.write_text("forged replacement", encoding="utf-8")
            return real_apply(subject, plan)

        with patch.object(operations, "apply_plan", side_effect=raced):
            result = self.upgrade(root)
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(result.code, "STALE_STATE", result.to_dict())
        self.assertEqual(self.snapshot(root), before)

    def test_committed_proof_pins_both_journals_project_and_source(self):
        root = self.legacy()
        result = self.upgrade(root)
        self.assertTrue(result.ok, result.to_dict())
        dependencies = {}
        self.assertEqual(
            goal_authority.prove(root, self.current(root), dependencies=dependencies), []
        )
        self.assertIn(".saipen/IDENTITY.md", dependencies)
        self.assertIn(f".saipen/intake/active/{result['authorization_receipt']}.md", dependencies)
        self.assertIn(
            f".saipen/intake/distribution/{result['authorization_receipt']}.json", dependencies
        )
        self.assertEqual(len([p for p in dependencies if p.endswith("operation.json")]), 2)

    def test_duplicate_capsule_keys_refuse_with_no_write(self):
        root = self.legacy()
        body = self.capsule(root)
        repeated = '{"kind":"saipen-goal-continuation",' + body[1:]
        before = self.snapshot(root)
        result = self.upgrade(root, repeated)
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(self.snapshot(root), before)

    def test_malformed_original_authority_metadata_refuses_without_traceback(self):
        root = self.legacy()
        body = self.capsule(root)
        records, _ = semantic_receipts_for_operation_safe(root, "goal")
        path = Journal(root, records[-1]["op_id"]).manifest
        record = json.loads(path.read_text())
        record["receipt_metadata"] = {"goal_authority": ["forged"]}
        path.write_text(json.dumps(record), encoding="utf-8")
        before = self.snapshot(root)
        result = self.upgrade(root, body)
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(self.snapshot(root), before)


if __name__ == "__main__":
    unittest.main()
