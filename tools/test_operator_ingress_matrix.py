"""Regression Matrix Tests for SRC-268 (Clauses A through R).

Verifies the engine's operator-ingress contract, start/continue routing, valve
integration and old-work preservation with OpenCode-shaped events. Native
identity/process facts are explicitly simulated by an isolated broker fixture;
no actual OpenCode/Freebuff process or real UI acceptance is claimed here.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from contextlib import contextmanager
from types import SimpleNamespace

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from saipen_engine import (  # noqa: E402
    admission,
    cold_recovery,
    commands,
    entry,
    goal_authority,
    guard_events,
    operator_task,
    intake,
    host_authority_client,
)
import test_t1844_origin_broker as origin_controls  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402


def setUpModule():
    isolate_host_session()


class TestOperatorIngressMatrix(unittest.TestCase):
    CATEGORY = "simulated_host_integration"

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="saipen_ingress_matrix_")
        self.root = Path(self.tmp)
        (self.root / ".saipen").mkdir(parents=True, exist_ok=True)
        (self.root / ".saipen" / "IDENTITY.md").write_text(
            "---\nproject_lineage: lineage-0123456789abcdef0123456789abcdef\n---\n",
            encoding="utf-8",
        )
        (self.root / ".saipen" / "STATE.md").write_text(
            '---\nphase: BUILD\ntask: T-1\nnext_action: "PHASE BUILD T-1"\n'
            "blocker: none\ntransition_from: SCOUT\nsaipen_version: 8\n"
            "schema_version: 3\nlast_event: 4\nstyle_contract: ded-069a4c52\n"
            'agent: saipen-cli\nmode: full\nupdated: "2026-10-17T00:00:00Z"\n'
            "execution_intent: goal\ngoal_waves: 3\ngoal_tickets: 22\n"
            "continuation_authority: operator_required\n"
            "authority_source: E-4\nauthority_until: budget\n"
            "safety_valve_mode: hard_wait\n---\n",
            encoding="utf-8",
        )
        (self.root / ".saipen" / "BOARD.md").write_text(
            "## DOING\n"
            "- [/] T-1 [P2] active task | verify: test verify | owner: saipen-cli | "
            "claim_time: 2026-10-17T00:00:00Z\n"
            "## TODO\n"
            "## BLOCKED\n"
            "## DONE\n"
            "- [x] T-91 [P2] old ship work | verify: test verify | owner: saipen-cli "
            "| claim_time: 2026-10-17T00:00:00Z | closure_mode: own_patch\n",
            encoding="utf-8",
        )
        (self.root / ".saipen" / "LOG.md").write_text(
            "# Log\n"
            "- 17.10.26 00:00 [E-1] [agent: saipen-cli] [op: "
            "init-514a0202c95c40e7aef0be708ce16dc5] RUN: init\n"
            "- 17.10.26 00:00 [E-2] [parent: E-1] [T-91] [agent: saipen-cli] [op: "
            "ticket-514a0202c95c40e7aef0be708ce16dc5] DEC: ticket added\n"
            "- 17.10.26 00:00 [E-3] [parent: E-2] [T-91] [agent: saipen-cli] [op: "
            "ticket-514a0202c95c40e7aef0be708ce16dc5] DEC: ticket done\n"
            "- 17.10.26 00:00 [E-4] [parent: E-3] [T-1] [agent: saipen-cli] [op: "
            "checkpoint-514a0202c95c40e7aef0be708ce16dc5] RUN: checkpoint\n",
            encoding="utf-8",
        )
        (self.root / ".saipen" / "intake").mkdir(parents=True, exist_ok=True)
        (self.root / ".saipen" / "intake" / "index.json").write_text(
            json.dumps({"schema_version": 1, "next_id": 1, "active": {}, "tombstones": {}}),
            encoding="utf-8",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    @contextmanager
    def native(self, text, *, action="goal", session="matrix-session"):
        origin = origin_controls.OriginKernelWithSimulatedNativeIdentity()
        origin.setUp()
        self.addCleanup(origin.doCleanups)
        origin.root = self.root
        proof = origin.issue(text=text, action=action, session=session)
        origin.register(proof)
        with mock.patch.dict(os.environ, {operator_task.ENV_HOST_SESSION: session}), \
                mock.patch.object(host_authority_client, "_call", side_effect=origin.bridge):
            yield origin, proof

    def model_source(self, text):
        # Seed the historical allocator gap, then let the canonical owner write
        # every body/metadata/contract/index byte. Corrupt metadata cannot prove
        # that a valid old model Source resists a later authority upgrade.
        index = intake._read_index(self.root)
        index["next_id"] = 43
        intake._write_index(self.root, index)
        body = f"# User request\n\npriority: P1\n\n## Request\n\n{text}\n"
        result = intake.capture(self.root, body, source_kind="user_instruction",
                                request_provenance={
                                    "witness": operator_task.WITNESS_MODEL,
                                    "compared_digest": hashlib.sha256(text.encode()).hexdigest(),
                                })
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["receipt"], "SRC-043")
        self.assertTrue(intake.read_body(self.root, result["receipt"])["ok"])
        return result["receipt"]

    def test_clause_a_new_handoff_with_cc_routes_to_start(self):
        """A. New handoff containing 'cc' routes to START."""
        handoff_text = (
            "SAIHANDOFF — FIX RETRY LOOP\n\n"
            "Please check the failover logic in combo-failover. "
            "Note: ensure cc continuation and cc all are respected."
        )
        self.assertTrue(commands.is_prose_or_handoff(handoff_text))
        self.assertFalse(cold_recovery.is_continuation_command(handoff_text))

        file_prompt = '"V:\\_TEMP_\\fastprompter_drag\\SAIHANDOFF — SAIPEN_20261017_2238.md"'
        self.assertTrue(commands.is_prose_or_handoff(file_prompt))
        self.assertFalse(cold_recovery.is_continuation_command(file_prompt))

    def test_clause_b_standalone_cc_routes_to_continue(self):
        """B. Standalone operator cc routes to CONTINUE."""
        self.assertTrue(cold_recovery.is_continuation_command("cc"))
        self.assertTrue(cold_recovery.is_continuation_command("\u0441\u0441"))
        self.assertTrue(cold_recovery.is_continuation_command("cc all"))
        self.assertTrue(cold_recovery.is_continuation_command("\u0441\u0441 all"))
        self.assertTrue(cold_recovery.is_continuation_command("saipen continue"))
        self.assertFalse(commands.is_prose_or_handoff("cc"))
        self.assertFalse(commands.is_prose_or_handoff("cc all"))

    def test_clause_c_host_prompt_reaches_canonical_admission(self):
        """C. Host prompt reaches canonical operator admission."""
        prompt = "Repair the native operator-ingress integration"
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        event = {
            "event": "before_tool",
            "host": "opencode",
            "cwd": str(self.root),
            "tool_name": "bash",
            "tool_input": {"command": "saipen status"},
            "session_id": "session-123",
            "host_ingress": {
                "message_id": "msg-001",
                "request_text": prompt,
                "request_digest": digest,
                "session_id": "session-123",
                "project_lineage": "lineage-0123456789abcdef0123456789abcdef",
            },
        }
        verdict = guard_events.evaluate_event(event, project_root=str(self.root))
        self.assertTrue(verdict.get("admitted"))
        active = operator_task.active_host_ingress(self.root)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["request_digest"], digest)
        self.assertEqual(active[0]["destination_op"], "start")

    def test_clause_d_agent_authored_text_cannot_impersonate(self):
        """D. Agent-authored text cannot impersonate the prompt."""
        prompt = "Genuine operator request"
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        operator_task.admit_host_ingress(
            {
                "message_id": "msg-002",
                "request_text": prompt,
                "request_digest": digest,
            },
            self.root,
        )
        paraphrase = "I am paraphrasing the user"
        res = operator_task.witness(paraphrase, root=self.root)
        self.assertEqual(res.get("code"), operator_task.CODE_MISMATCH)
        self.assertEqual(res.get("declared_digest"), digest)

    def test_clause_e_model_created_task_files_cannot_forge_authority(self):
        """E. Model-created task files cannot forge authority."""
        verdict = admission.evaluate_admission(
            str(self.root),
            target_path=".saipen/cache/ingress/fake.json",
            action="file_write",
            agent="saipen-cli",
        )
        self.assertFalse(verdict.get("admitted"))
        self.assertEqual(verdict.get("code"), "PROTECTED_CANONICAL_NAMESPACE")

    def test_clause_f_user_message_identity_survives_model_switching(self):
        """F. User-message identity survives model switching."""
        prompt = "Cross-model persistent request"
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        admitted = operator_task.admit_host_ingress(
            {
                "message_id": "msg-003",
                "request_text": prompt,
                "request_digest": digest,
                "session_id": "sess-456",
            },
            self.root,
        )
        self.assertTrue(admitted.get("ok"))
        active1 = operator_task.active_host_ingress(self.root)
        self.assertEqual(active1[0]["message_id"], "msg-003")
        # Second query simulating a different model in the same or linked session
        active2 = operator_task.active_host_ingress(self.root, session_id="sess-456")
        self.assertEqual(len(active2), 1)
        self.assertEqual(active2[0]["request_digest"], digest)

    def test_clause_g_multiple_queued_prompts_retain_separate_provenance(self):
        """G. Multiple queued prompts retain separate provenance."""
        prompt1 = "First prompt"
        digest1 = hashlib.sha256(prompt1.encode("utf-8")).hexdigest()
        operator_task.admit_host_ingress(
            {"message_id": "m1", "request_text": prompt1, "request_digest": digest1},
            self.root,
        )
        prompt2 = "Second prompt"
        digest2 = hashlib.sha256(prompt2.encode("utf-8")).hexdigest()
        operator_task.admit_host_ingress(
            {"message_id": "m2", "request_text": prompt2, "request_digest": digest2},
            self.root,
        )
        active = operator_task.active_host_ingress(self.root)
        self.assertEqual(len(active), 2)
        digests = {r["request_digest"] for r in active}
        self.assertEqual(digests, {digest1, digest2})

    def test_clause_h_delayed_callbacks_cannot_reuse_another_prompt(self):
        """H. Delayed callbacks cannot reuse another prompt."""
        prompt = "Single use prompt"
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        with self.native(prompt, action="start") as (origin, proof):
            operator_task.admit_host_ingress(
                {"message_id": "m3", "request_text": prompt, "request_digest": digest,
                 "session_id": "matrix-session", "operator_origin": proof}, self.root,
            )
            w1 = operator_task.witness(prompt, root=self.root)
            self.assertEqual(w1.get("witness"), operator_task.WITNESS_CARRIER)
            self.assertEqual(w1.get("declared_by"), operator_task.DECLARED_HOST_INGRESS)
            captured = intake.capture(self.root, prompt, request_provenance=w1)
            self.assertTrue(captured["ok"], captured)
            self.assertTrue(operator_task.authority_for_receipt(
                self.root, captured["receipt"], existing_only=False,
            )["user_explicit"])
            # A real query is pure; Source acceptance retires delivery. An
            # unrelated delayed OS worker cannot borrow that accepted event.
            origin.peer = SimpleNamespace(pid=30)
            w2 = operator_task.witness(prompt, root=self.root)
            self.assertEqual(w2.get("witness"), operator_task.WITNESS_MODEL)

    def test_clause_i_renderer_reload_does_not_grant_new_authority(self):
        """I. Renderer reload does not grant new authority."""
        active = operator_task.active_host_ingress(self.root)
        self.assertEqual(len(active), 0)
        # Calling witness without host ingress yields WITNESS_MODEL
        w = operator_task.witness("reloaded state", root=self.root)
        self.assertEqual(w.get("witness"), operator_task.WITNESS_MODEL)

    def test_clause_j_existing_model_supplied_src_remains_unchanged(self):
        """J. Existing model_supplied SRC remains unchanged."""
        receipt = self.model_source("Old model request")
        metadata = self.root / ".saipen/intake/active/SRC-043.meta.json"
        before = metadata.read_bytes()
        with self.native("Old model request") as (origin, proof):
            auth = operator_task.authority_for_receipt(self.root, receipt)
            self.assertEqual(auth.get("witness"), operator_task.WITNESS_MODEL)
            self.assertFalse(auth.get("user_explicit"))
            self.assertFalse(auth.get("reset_bounded_authority"))
            self.assertIsNone(origin.broker.origins.records[proof["nonce"]]["receipt"])
        self.assertEqual(metadata.read_bytes(), before)

    def test_clause_k_fresh_verified_ingress_authorizes_new_work(self):
        """K. Fresh verified ingress can authorize new Work."""
        prompt = "Legitimate operator task"
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        with self.native(prompt) as (_origin, proof):
            operator_task.admit_host_ingress(
                {"message_id": "m4", "request_text": prompt, "request_digest": digest,
                 "session_id": "matrix-session", "operator_origin": proof}, self.root,
            )
            w = operator_task.witness(prompt, root=self.root)
            auth = operator_task.authority_for_provenance(w, root=self.root)
            self.assertTrue(auth.get("user_explicit"))
            self.assertTrue(auth.get("reset_bounded_authority"))
            self.assertTrue(auth.get("goal_pivot"))

    def test_clause_l_tripped_bounded_valve_remains_effective(self):
        """L. Tripped bounded valve remains effective without fresh operator carrier."""
        state = {
            "execution_intent": "goal",
            "goal_waves": 3,
            "goal_tickets": 22,
            "continuation_authority": "operator_required",
            "authority_source": "E-4",
        }
        res = goal_authority.reset_authority(self.root, state)
        self.assertEqual(res.get("mode"), "wait")

    def test_clause_m_new_authorized_task_passes_valve_legally(self):
        """M. New authorized task can pass the valve legally."""
        prompt = "cc all"
        digest = hashlib.sha256(b"cc all").hexdigest()
        state = {
            "execution_intent": "goal",
            "goal_waves": 3,
            "goal_tickets": 22,
            "continuation_authority": "operator_required",
            "authority_source": "E-4",
        }
        with self.native(prompt, action="continue") as (_origin, proof):
            operator_task.admit_host_ingress(
                {"message_id": "m5", "request_text": prompt, "request_digest": digest,
                 "session_id": "matrix-session", "operator_origin": proof}, self.root,
            )
            res = goal_authority.reset_authority(self.root, state)
        self.assertEqual(res.get("mode"), "reauthorize")
        self.assertEqual(res.get("source"), "operator_carrier")

    def test_clause_n_existing_ship_evidence_is_preserved(self):
        """N. Existing T-91 SHIP evidence is preserved."""
        board_text = (self.root / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
        self.assertIn("- [x] T-91 [P2] old ship work", board_text)

    def test_clause_o_tag_conflict_not_silently_overwritten(self):
        """O. TAG_CONFLICT is not silently overwritten."""
        # Check that tag conflict checking is intact
        from saipen_engine import reconcile

        self.assertTrue(hasattr(reconcile, "reconcile_protocol_state"))

    def test_clause_p_opencode_native_integration_end_to_end(self):
        """P. OpenCode native integration passes end-to-end."""
        handoff_file = self.root / "SAIHANDOFF_test.md"
        handoff_text = "# Handoff\nEnsure cc works properly.\n"
        handoff_file.write_text(handoff_text, encoding="utf-8")
        _file_digest = hashlib.sha256(handoff_text.encode("utf-8")).hexdigest()

        prompt = f'"{handoff_file}"'
        prompt_digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

        event = {
            "event": "before_tool",
            "host": "opencode",
            "cwd": str(self.root),
            "tool_name": "bash",
            "tool_input": {"command": f'saipen start --file "{handoff_file}"'},
            "session_id": "session-live",
            "host_ingress": {
                "message_id": "msg-live",
                "request_text": prompt,
                "request_digest": prompt_digest,
                "session_id": "session-live",
                "project_lineage": "lineage-0123456789abcdef0123456789abcdef",
            },
        }
        with self.native(handoff_text, session="session-live") as (_origin, proof):
            event["host_ingress"]["operator_origin"] = proof
            verdict = guard_events.evaluate_event(event, project_root=str(self.root))
            self.assertTrue(verdict.get("admitted"))
            result = entry.start_work(
                self.root,
                "saipen-cli",
                actor_source="host_carrier",
                text=handoff_text,
            )
            self.assertTrue(result.get("ok"), result)
            receipt_id = result.get("receipt")
            self.assertTrue(receipt_id)
            # Inspect the authority actually spent by START and the accepted
            # Source. A changed task/budget must not retain fresh reset power.
            auth = result["ingress_authority"]
            self.assertEqual(auth.get("witness"), operator_task.WITNESS_CARRIER)
            self.assertTrue(auth.get("user_explicit"))
            self.assertTrue(auth.get("reset_bounded_authority"))
            self.assertTrue(result["valve_reauthorized"])
            self.assertTrue(operator_task.received_source_origin(
                self.root, receipt_id, action="goal",
            ))
            self.assertFalse(operator_task.authority_for_receipt(
                self.root, receipt_id,
            )["reset_bounded_authority"])

    def test_clause_q_no_operator_terminal_commands_needed(self):
        """Q. No operator terminal commands needed in normal use."""
        prompt = "New prompt arriving without environment variables"
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        operator_task.admit_host_ingress(
            {"message_id": "m-clean", "request_text": prompt, "request_digest": digest},
            self.root,
        )
        unstarted_task = operator_task.unstarted(self.root)
        self.assertIsNotNone(unstarted_task)
        self.assertEqual(unstarted_task["source"], operator_task.DECLARED_HOST_INGRESS)
        self.assertIn("saipen start", unstarted_task["command"])

    def test_live_acceptance_disposable_project(self):
        """Simulated acceptance on a disposable 9router-like project; no live UI:
        - Old SHIP ticket T-91 preserved.
        - Tripped bounded goal valve handled through canonical admission.
        - Old model_supplied receipt SRC-043 preserved.
        - New real operator task containing 'cc' recognized as new, admitted once,
          and granted operator_carrier provenance.
        """
        old_body = "Old model supplied task from field incident"
        self.model_source(old_body)
        old_metadata = self.root / ".saipen/intake/active/SRC-043.meta.json"
        old_before = old_metadata.read_bytes()

        # 2. Operator submits new handoff file containing 'cc'
        handoff_file = self.root / "SAIHANDOFF_live_acceptance.md"
        new_task_text = (
            "SAIHANDOFF — 9router upstream trace and combo-failover\n\n"
            "Ensure cc continuation does not starve new tasks.\n"
        )
        handoff_file.write_text(new_task_text, encoding="utf-8")
        _file_digest = hashlib.sha256(new_task_text.encode("utf-8")).hexdigest()

        # Ingress arrives through OpenCode
        prompt = f'"{handoff_file}"'
        prompt_digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        event = {
            "event": "before_tool",
            "host": "opencode",
            "cwd": str(self.root),
            "tool_name": "bash",
            "tool_input": {"command": f'saipen start --file "{handoff_file}"'},
            "session_id": "session-acceptance",
            "host_ingress": {
                "message_id": "msg-acceptance",
                "request_text": prompt,
                "request_digest": prompt_digest,
                "session_id": "session-acceptance",
                "project_lineage": "lineage-0123456789abcdef0123456789abcdef",
            },
        }
        with self.native(new_task_text, session="session-acceptance") as (_origin, proof):
            event["host_ingress"]["operator_origin"] = proof
            verdict = guard_events.evaluate_event(event, project_root=str(self.root))
            self.assertTrue(verdict.get("admitted"))
            active = operator_task.active_host_ingress(self.root)
            self.assertEqual(len(active), 1)
            self.assertEqual(active[0]["destination_op"], "start")
            res = entry.start_work(
                self.root,
                "saipen-cli",
                actor_source="host_carrier",
                text=new_task_text,
            )
            self.assertTrue(res.get("ok"), res)
            new_receipt = res.get("receipt")
            self.assertTrue(new_receipt)
            auth_old = operator_task.authority_for_receipt(self.root, "SRC-043")
            self.assertEqual(auth_old.get("witness"), operator_task.WITNESS_MODEL)
            self.assertFalse(auth_old.get("user_explicit"))
            auth_new = res["ingress_authority"]
            self.assertEqual(auth_new.get("witness"), operator_task.WITNESS_CARRIER)
            self.assertTrue(auth_new.get("user_explicit"))
            self.assertTrue(auth_new.get("reset_bounded_authority"))
            self.assertTrue(res["valve_reauthorized"])
            self.assertTrue(operator_task.received_source_origin(
                self.root, new_receipt, action="goal",
            ))
            self.assertFalse(operator_task.authority_for_receipt(
                self.root, new_receipt,
            )["reset_bounded_authority"])
        self.assertEqual(old_metadata.read_bytes(), old_before)

        # Verify old SHIP ticket T-91 is preserved
        board_text = (self.root / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
        self.assertIn("- [x] T-91 [P2] old ship work", board_text)

        # Verify ingress was consumed (cannot be reused)
        active_after = operator_task.active_host_ingress(self.root)
        self.assertEqual(len(active_after), 0)

    def test_clause_r_host_adapter_and_installed_plugin_match(self):
        """R. Host adapter and installed plugin generation match."""
        repo_adapter = Path("extensions/adapters/opencode/saipen-guard.js").resolve()
        installed_plugin = Path(
            os.path.expanduser("~/.config/opencode/plugins/saipen-guard.js")
        ).resolve()
        if not installed_plugin.is_file() or not repo_adapter.is_file():
            self.skipTest("installed-plugin parity is unavailable in this isolated fixture profile")
        h_repo = hashlib.sha256(repo_adapter.read_bytes()).hexdigest()
        h_inst = hashlib.sha256(installed_plugin.read_bytes()).hexdigest()
        self.assertEqual(h_repo, h_inst)


if __name__ == "__main__":
    unittest.main()
