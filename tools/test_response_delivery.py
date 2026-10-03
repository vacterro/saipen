"""Fresh-turn delivery, not model confession: actual completed-part transport."""

from pathlib import Path
import os
import shutil
import tempfile
import unittest
import json

from saipen_engine import response_surface as RS
from test_guard_hostile_matrix import fresh_project
from test_opencode_adapter import run_cases, REPO, NODE, PYTHON
from test_hermetic_env import isolate_host_session
from test_orchestration_repair import OrchestrationFixture


def setUpModule():
    isolate_host_session()


class RepeatedStateDigest(unittest.TestCase):
    def test_canonical_liveness_does_not_depend_on_an_adapter_diagnostic_flag(self):
        facts = {
            "phase": "BUILD",
            "task": "T-1510",
            "validation": "CURRENT_PASS",
            "automation": {"disposition": "CONTINUE", "next_command": "saipen continue"},
        }
        verdict = RS.gate_final_response(
            "Model retrospective",
            admission=None,
            admission_consulted=False,
            operational_turn=True,
            executable_action_remains=False,
            style_contract=None,
            facts=facts,
        )
        self.assertEqual(verdict["delivery"], "")
        self.assertEqual(verdict["delivery_validation"], "PASS")
        self.assertEqual(verdict["class"], RS.CLASS_AUTONOMOUS_HANDBACK)

    def test_delivery_candidate_itself_is_validated_and_fails_compactly(self):
        facts = {
            "phase": "BUILD",
            "task": "T-1510",
            "next_action": "NONE",
            "validation": "CURRENT_PASS",
        }
        verdict = RS.gate_final_response(
            "model retrospective" * 100,
            admission=None,
            admission_consulted=False,
            operational_turn=True,
            style_contract=None,
            facts=facts,
            current_phase="DONE",
            current_task="T-1510",
            current_validation="CURRENT_PASS",
        )
        self.assertFalse(verdict["ok"])
        self.assertEqual(verdict.get("delivery_validation"), "COMPACT_FAILURE")
        self.assertIn("RESPONSE_FACT_INVALID", verdict["delivery"])
        self.assertLessEqual(len(verdict["delivery"]), 900)
        self.assertEqual(RS.response_errors(verdict["delivery"]), [])

    def test_trusted_continue_does_not_authorize_a_caller_chosen_stop_reason(self):
        from saipen_engine.operator_task import witness, ENV_TASK_SHA256
        from saipen_engine.pending_ingress import ingress_digest

        request = "continue"
        authority = witness(request, env={ENV_TASK_SHA256: ingress_digest(request)})
        facts = {
            "phase": "BUILD",
            "task": "T-1510",
            "next_action": "PHASE BUILD T-1510",
            "validation": "CURRENT_PASS",
            "automation": {"disposition": "CONTINUE", "next_command": "saipen continue"},
        }
        verdict = RS.gate_final_response(
            "I chose to stop",
            admission=None,
            admission_consulted=False,
            operational_turn=True,
            executable_action_remains=True,
            style_contract=None,
            facts=facts,
            reason="stop",
            human_request=request,
            request_authority=authority,
        )
        self.assertFalse(verdict["ok"])
        self.assertEqual(verdict["delivery"], "")

    def test_malformed_facts_fail_compactly_without_dumping_input(self):
        for facts in (
            None,
            {"test_groups": [{"ran": "not a number"}]},
            {"automation": "not a mapping"},
            {"phase": "bad\n" * 1000},
        ):
            text = RS.digest_from_facts(facts, reason="stop")
            self.assertLessEqual(len(text.splitlines()), 6)
            self.assertLessEqual(len(text), 900)
            self.assertNotIn("not a number", text)

    def test_model_supplied_status_cannot_end_runnable_work(self):
        facts = {
            "phase": "BUILD",
            "task": "T-1510",
            "next_action": "PHASE BUILD T-1510",
            "blocker": "none",
            "validation": "CURRENT_PASS",
            "automation": {"disposition": "CONTINUE", "next_command": "saipen continue"},
        }
        verdict = RS.gate_final_response(
            "A report chosen by the model",
            admission=None,
            admission_consulted=False,
            operational_turn=True,
            executable_action_remains=True,
            style_contract=None,
            facts=facts,
            reason="summary",
            human_request="give me a summary",
            request_authority={"witness": "model_supplied"},
        )
        self.assertFalse(verdict["ok"])
        self.assertEqual(verdict["delivery"], "")

    def test_stop_checkpoint_has_canonical_delivery_and_durable_facts(self):
        from saipen_engine.operations import stop_checkpoint

        project = fresh_project()
        result = stop_checkpoint(project, "test-agent")
        self.assertTrue(result.ok, result.to_dict())
        self.assertIn("delivery", result.data)
        text = result.data["delivery"]
        self.assertLessEqual(len(text.splitlines()), 6)
        self.assertLessEqual(len(text), 900)
        report = json.loads((project / result.data["response_record"]).read_text(encoding="utf-8"))
        self.assertEqual(report["delivery"], text)
        self.assertEqual(report["reason"], RS.STOP_HANDBACK)
        self.assertEqual(report["facts"]["next_action"], result.data["next_action"])

    def test_three_fresh_turns_cannot_deliver_model_retrospective(self):
        facts = {
            "phase": "DONE",
            "task": "T-1598",
            "blocker": "none",
            "next_action": "NONE",
            "validation": "CURRENT_PASS",
        }
        for pressure in (10, 10, 1000):
            with self.subTest(pressure=pressure):
                facts["evidence"] = [f"E-{n}" for n in range(pressure)]
                verdict = RS.gate_final_response(
                    "The model deserves transparency.\n" * pressure,
                    admission=None,
                    admission_consulted=False,
                    operational_turn=True,
                    style_contract=None,
                    facts=facts,
                )
                self.assertFalse(verdict["ok"])
                self.assertLessEqual(len(verdict["delivery"].splitlines()), 6)
                self.assertLessEqual(len(verdict["delivery"]), 900)
                self.assertNotIn("transparency", verdict["delivery"])

    def test_all_default_classes_have_constant_inventory_weight(self):
        for reason in ("final", "stop", "summary", "safety"):
            for findings in (0, 1, 10, 100):
                for blockers in (0, 1, 54):
                    for groups in (1, 20):
                        facts = {
                            "phase": "DONE",
                            "task": "T-1598",
                            "blocker": "none",
                            "next_action": "NONE",
                            "validation": "CURRENT_PASS",
                            "findings": ["x"] * findings,
                            "blockers": [
                                {"ticket": f"T-{n}", "blocker": "BLOCKED_EXTERNAL"}
                                for n in range(blockers)
                            ],
                            "test_groups": [{"ran": 1, "red": 0} for _ in range(groups)],
                            "commits": ["a" * 40] * 20,
                            "evidence": ["evidence.json"] * 1000,
                        }
                        text = RS.digest_from_facts(facts, reason=reason)
                        self.assertLessEqual(len(text.splitlines()), 6)
                        self.assertLessEqual(len(text), 900)


@unittest.skipUnless(NODE and PYTHON, "node/python runtime unavailable")
class CompletedPartDelivery(unittest.TestCase):
    def test_host_prompt_grants_artifacts_but_quotes_and_fences_grant_nothing(self):
        project = fresh_project()
        directory = Path(tempfile.mkdtemp(prefix="saipen-artifact-delivery-"))
        self.addCleanup(shutil.rmtree, directory)
        plugin = Path(
            os.environ.get("SAIPEN_OPENCODE_PLUGIN")
            or REPO / "extensions/adapters/opencode/saipen-guard.js"
        )
        text = "Üleandmise tõendid ja jätkamise käsud.\n" * 80
        prompts = (
            ("write an implementation handoff", "allowed"),
            ("prepare the audit", "allowed"),
            ("write a specification", "allowed"),
            ('"write an implementation handoff"', "blocked"),
            ("The example says: write an implementation handoff", "blocked"),
            ("do not write an implementation handoff", "blocked"),
            ("give me a summary", "blocked"),
            ("", "blocked"),
        )
        cases = [
            {
                "id": f"artifact-{n}",
                "project": str(project),
                "session_id": f"artifact-fresh-{n}",
                "user_request": request,
                "text_complete": "```text\n" + text + "```",
                "env": {
                    "SAIPEN_SKILL_ROOT": str(REPO),
                    "SAIPEN_PYTHON": PYTHON,
                    "SAIPEN_AGENT": "test-agent",
                },
            }
            for n, (request, _outcome) in enumerate(prompts)
        ]
        records = run_cases(plugin, cases, directory)
        for record, (_request, outcome) in zip(records, prompts):
            self.assertEqual(record["outcome"], outcome, record)
            if outcome == "allowed":
                self.assertEqual(record["delivered"], "```text\n" + text + "```")

    def test_real_hook_replaces_three_fresh_oversized_turns(self):
        project = fresh_project()
        directory = Path(tempfile.mkdtemp(prefix="saipen-digest-delivery-"))
        self.addCleanup(shutil.rmtree, directory)
        plugin = Path(
            os.environ.get("SAIPEN_OPENCODE_PLUGIN")
            or REPO / "extensions/adapters/opencode/saipen-guard.js"
        )
        cases = [
            {
                "id": f"fresh-{n}",
                "project": str(project),
                "session_id": f"digest-fresh-{n}",
                "user_request": "saipen status",
                "operational_command": "saipen status",
                "text_complete": "Peatusin. Täiesti lõpetatud on T-1598.\n" * pressure,
                "env": {
                    "SAIPEN_SKILL_ROOT": str(REPO),
                    "SAIPEN_PYTHON": PYTHON,
                    "SAIPEN_AGENT": "test-agent",
                },
            }
            for n, pressure in enumerate((30, 30, 300))
        ]
        records = run_cases(plugin, cases, directory)
        for record in records:
            self.assertEqual(record["outcome"], "allowed", record)
            self.assertLessEqual(len(record["delivered"].splitlines()), 6, record)
            self.assertLessEqual(len(record["delivered"]), 900, record)
            self.assertNotIn("Peatusin.", record["delivered"])


class RecordedCompletion(OrchestrationFixture):
    def test_digest_reads_actual_finish_event_instead_of_inventing_completion(self):
        from saipen_engine.operations import finish_ticket

        project = self.make_project(active=True)
        (project / "main.py").write_text("shared = True\n", encoding="utf-8")
        self.to_ship(project, "T-7")
        result = finish_ticket(
            project,
            "T-7",
            "tester",
            closure_mode="cohort",
            closure_cohort="C-001",
            closure_paths=("main.py",),
        )
        self.assertTrue(result.ok, result.to_dict())
        facts = RS.canonical_facts(project)
        self.assertEqual(facts["completed"], ["T-7"])
        text = RS.digest_from_facts(facts, reason="stop")
        self.assertIn("T-7 lõpetatud", text)
        self.assertEqual(RS.response_errors(text), [])


if __name__ == "__main__":
    unittest.main()
