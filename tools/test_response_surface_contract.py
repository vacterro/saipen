"""Focused owner test for EXEC-RESPONSE-01 (T-1419).

Proves both the mechanically-checked shape (registry rule, owner, BOOT/placement,
cold profile, HUSH parity, validator surface) and at least one BEHAVIOURAL
projection (the surface contract and the autonomy continuation), so this is not
a string-presence test.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
for _entry in (str(TOOLS), str(ROOT)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from saipen_engine import response_surface as RS  # noqa: E402
from saipen_engine.hush import HUSHED, MANDATORY as HUSH_MANDATORY  # noqa: E402

PROTOCOL = ROOT / "saipen"
REGISTRY = json.loads((PROTOCOL / "REGISTRY.json").read_text(encoding="utf-8-sig"))


class RegistrationTests(unittest.TestCase):
    def test_rule_is_registered_with_the_execution_owner(self):
        facts = REGISTRY["semantic_baseline"]["facts"]
        self.assertIn("EXEC-RESPONSE-01", facts)
        self.assertEqual(facts["EXEC-RESPONSE-01"]["owner"], "saipen/EXECUTION.md")
        self.assertEqual(REGISTRY["rule_owners"]["EXEC-RESPONSE-01"], "saipen/EXECUTION.md")

    def test_exact_owner_file_is_execution_not_style(self):
        # It is NOT a STYLE rule: the owner is EXECUTION.md.
        self.assertEqual(RS.RULE_ID, "EXEC-RESPONSE-01")
        text = (PROTOCOL / "EXECUTION.md").read_text(encoding="utf-8-sig")
        self.assertIn("RULE-OWNER: EXEC-RESPONSE-01", text)
        style = (PROTOCOL / "STYLE.md").read_text(encoding="utf-8-sig")
        self.assertNotIn("RULE-OWNER: EXEC-RESPONSE-01", style)


class PlacementTests(unittest.TestCase):
    def test_boot_loads_style_and_execution_before_first_output(self):
        boot = (PROTOCOL / "BOOT.md").read_text(encoding="utf-8-sig")
        self.assertIn("STYLE.md", boot)
        self.assertIn("EXECUTION.md", boot)
        self.assertIn("before any", boot)
        # The reference to the canonical rule, not a duplicate schema.
        self.assertIn("EXEC-RESPONSE-01", boot)

    def test_activation_block_references_execution_without_duplicating_schema(self):
        block = (PROTOCOL / "ACTIVATION_BLOCK.md").read_text(encoding="utf-8-sig")
        self.assertIn("EXECUTION.md", block)
        self.assertIn("EXEC-RESPONSE-01", block)
        # No duplicate schema: the field list lives only in its owner.
        for field in RS.MANDATORY_FIELDS:
            self.assertNotIn(field, block, field)

    def test_execution_is_in_the_cold_first_response_profile(self):
        cold = REGISTRY["load_profiles"]["profiles"]["cold"]["routes"][0]
        self.assertIn("EXECUTION.md", cold["must"])


class FieldOrderTests(unittest.TestCase):
    def test_mandatory_order_is_fixed(self):
        doc = (PROTOCOL / "EXECUTION.md").read_text(encoding="utf-8-sig")
        positions = [doc.index(field) for field in RS.MANDATORY_FIELDS]
        self.assertEqual(positions, sorted(positions), "owner field order drifted")
        self.assertEqual(
            RS.MANDATORY_FIELDS,
            (
                "STATUS",
                "RESULT",
                "BLOCKER",
                "OPERATOR ACTION",
                "NEXT EXACT ACTION",
                "VALIDATION",
            ),
        )

    def test_details_is_optional_and_last(self):
        self.assertNotIn("DETAILS", RS.MANDATORY_FIELDS)
        self.assertEqual(RS.FIELD_ORDER[-1], "DETAILS")

    def test_a_wellformed_block_has_no_errors(self):
        block = {field: "x" for field in RS.MANDATORY_FIELDS}
        self.assertEqual(RS.surface_errors(block, status="DONE"), [])


class SurfaceBehaviourTests(unittest.TestCase):
    def test_missing_mandatory_field_refuses(self):
        block = {field: "x" for field in RS.MANDATORY_FIELDS if field != "BLOCKER"}
        errors = RS.surface_errors(block)
        self.assertTrue(any("BLOCKER" in error for error in errors), errors)

    def test_out_of_order_fields_refuse(self):
        block = {field: "x" for field in reversed(RS.MANDATORY_FIELDS)}
        self.assertTrue(any("canonical order" in error for error in RS.surface_errors(block)))

    def test_details_before_a_mandatory_field_refuses(self):
        block = {field: "x" for field in RS.MANDATORY_FIELDS}
        block["DETAILS"] = "x"
        # Reinsert DETAILS in the middle: dicts preserve insertion order.
        block = {
            k: block[k] for k in (*RS.MANDATORY_FIELDS[:3], "DETAILS", *RS.MANDATORY_FIELDS[3:])
        }
        self.assertTrue(
            any("DETAILS must render last" in error for error in RS.surface_errors(block))
        )

    def test_wait_without_operator_action_refuses(self):
        block = {field: "x" for field in RS.MANDATORY_FIELDS}
        block["OPERATOR ACTION"] = "NONE"
        errors = RS.surface_errors(block, status="WAIT -- manual-verify")
        self.assertTrue(any("OPERATOR ACTION" in error for error in errors), errors)

    def test_rendered_boundary_is_checked_after_assembly(self):
        boundary = RS.OperationalBoundary(
            status="CLEAN completed; current conformance is failing",
            result="Scratch cleanup completed; closure evidence remains unresolved",
            blocker="CONFORMANCE_UNHEALTHY -- 46 work_closure_evidence findings",
            operator_action="Decide whether to retain the ignored scripts",
            next_exact_action="saipen validate",
            validation="CURRENT_FAIL",
        )
        rendered = RS.render_boundary(boundary)
        self.assertEqual(rendered.splitlines()[0], "STATUS: " + boundary.status)
        self.assertEqual(RS.response_errors(rendered), [])

    def test_actual_text_refuses_prose_duplicates_missing_and_vague_action(self):
        valid = RS.render_boundary(
            RS.OperationalBoundary("DONE", "Work completed", "NONE", "NONE", "NONE", "CURRENT_PASS")
        )
        cases = (
            "An explanation before the card\n" + valid,
            valid.replace("RESULT: Work completed", "RESULT: Work completed\nRESULT: duplicated"),
            valid.replace("RESULT: Work completed\n", ""),
            valid.replace("NEXT EXACT ACTION: NONE", "NEXT EXACT ACTION: investigate further"),
            valid.replace(
                "RESULT: Work completed",
                "RESULT: Work completed\nBLOCKER: There is still a problem",
            ),
        )
        for text in cases:
            with self.subTest(text=text[:70]):
                self.assertTrue(RS.response_errors(text))

    def test_operator_action_rejects_agent_commands_but_accepts_human_decisions(self):
        for action in (
            "saipen validate",
            "Run `saipen validate`",
            "python tools/saipen.py validate",
            "Run the next internal phase",
            "Continue processing",
            "Execute a command the agent can execute itself",
        ):
            with self.subTest(action=action):
                boundary = RS.OperationalBoundary(
                    "BLOCKED",
                    "Work is paused",
                    "HUMAN_DECISION -- choose disposition",
                    action,
                    "saipen continue",
                    "CURRENT_FAIL",
                )
                rendered = "\n".join(f"{key}\n{value}" for key, value in boundary.fields().items())
                errors = RS.response_errors(rendered)
                self.assertTrue(any("agent command" in error for error in errors), errors)
        boundary = RS.OperationalBoundary(
            "BLOCKED",
            "Work is paused",
            "HUMAN_DECISION -- choose disposition",
            "Approve deletion of the retained ignored scripts",
            "saipen continue",
            "CURRENT_FAIL",
        )
        rendered = "\n".join(f"{key}: {value}" for key, value in boundary.fields().items())
        self.assertEqual(RS.response_errors(rendered), [])

    def test_autonomous_repair_is_not_a_response_boundary(self):
        rendered = RS.render_boundary(
            RS.OperationalBoundary(
                "VERIFY failure",
                "Repairable debt found",
                "NONE",
                "NONE",
                "saipen continue",
                "CURRENT_FAIL",
            )
        )
        self.assertIn(
            "eligible autonomous action remains; returning control is invalid",
            RS.response_errors(rendered, executable_action_remains=True, response_boundary=False),
        )
        invented = RS.render_boundary(
            RS.OperationalBoundary(
                "VERIFY failure",
                "Repairable debt found",
                "NONE",
                "Decide whether I should repair this",
                "saipen continue",
                "CURRENT_FAIL",
            )
        )
        self.assertIn(
            "OPERATOR ACTION is not due on the current route",
            RS.response_errors(invented, executable_action_remains=True, response_boundary=False),
        )

    def test_fresh_conformance_truth_supersedes_a_cached_pass(self):
        stale = RS.render_boundary(
            RS.OperationalBoundary(
                "VERIFY", "Validator ran", "NONE", "NONE", "NONE", "CURRENT_PASS"
            )
        )
        self.assertIn(
            "VALIDATION must start with current CURRENT_FAIL",
            RS.response_errors(stale, current_validation="CURRENT_FAIL"),
        )

    def test_canonical_phase_task_and_operator_gate_cannot_be_hidden(self):
        stale = RS.render_boundary(
            RS.OperationalBoundary("DONE", "No work changed", "NONE", "NONE", "NONE", "NOT_RUN")
        )
        errors = RS.response_errors(
            stale,
            current_phase="BUILD",
            current_task="T-1548",
            current_blocker="HUMAN_DECISION -- retained files",
            operator_due=True,
        )
        for required in (
            "current phase BUILD",
            "current task T-1548",
            "current HUMAN_DECISION",
            "OPERATOR ACTION is required",
        ):
            self.assertTrue(any(required in error for error in errors), errors)

    def test_pinned_languages_change_values_but_never_field_labels(self):
        for result in ("Töö valmis", "Работа завершена", "Work complete"):
            with self.subTest(result=result):
                rendered = RS.render_boundary(
                    RS.OperationalBoundary("DONE", result, "NONE", "NONE", "NONE", "CURRENT_PASS")
                )
                self.assertEqual(RS.response_errors(rendered), [])
                values, errors = RS.parse_surface(rendered)
                self.assertFalse(errors)
                self.assertTrue(set(RS.MANDATORY_FIELDS).issubset(values))

    def test_public_runtime_renderer_and_checker_share_the_same_contract(self):
        fields = {
            "status": "DONE",
            "result": "Work completed",
            "blocker": "NONE",
            "operator_action": "NONE",
            "next_exact_action": "NONE",
            "validation": "CURRENT_PASS",
        }
        rendered = subprocess.run(
            [sys.executable, str(TOOLS / "saipen.py"), "response", "render", "--stdin", "--json"],
            input=json.dumps(fields),
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(rendered.returncode, 0, rendered.stdout + rendered.stderr)
        text = json.loads(rendered.stdout)["text"]
        checked = subprocess.run(
            [sys.executable, str(TOOLS / "saipen.py"), "response", "check", "--stdin", "--json"],
            input=text,
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
        self.assertEqual(json.loads(checked.stdout)["code"], "RESPONSE_VALID")

    def test_public_autonomy_gate_reads_current_route(self):
        from test_guard_hostile_matrix import active_project
        from saipen_engine.conformance import conformance_decision

        project = active_project()
        validation = conformance_decision(project, gate="core")["status"]
        rendered = RS.render_boundary(
            RS.OperationalBoundary(
                "BUILD T-9001",
                "Work remains",
                "NONE",
                "NONE",
                "saipen continue",
                validation,
            )
        )
        proc = subprocess.run(
            [
                sys.executable,
                str(TOOLS / "saipen.py"),
                "response",
                "check",
                "--stdin",
                "--auto-eligibility",
                "--project-root",
                str(project),
                "--json",
            ],
            input=rendered,
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("eligible autonomous action remains", proc.stdout)

    @unittest.skipUnless(shutil.which("node"), "Node runtime unavailable")
    def test_opencode_output_hook_rejects_operational_prose(self):
        from test_guard_hostile_matrix import fresh_project
        from saipen_engine.conformance import conformance_decision

        project = fresh_project()
        before = {
            name: (project / ".saipen" / name).read_bytes()
            for name in ("STATE.md", "BOARD.md", "LOG.md")
        }
        validation = conformance_decision(project, gate="core")["status"]
        valid = RS.render_boundary(
            RS.OperationalBoundary("DONE", "No work changed", "NONE", "NONE", "NONE", validation)
        )
        plugin = ROOT / "extensions" / "adapters" / "opencode" / "saipen-guard.js"
        script = """
import { pathToFileURL } from 'node:url';
        const [pluginPath, project, valid] = process.argv.slice(1);
        const factory = (await import(pathToFileURL(pluginPath).href)).default;
        const hooks = await factory({ worktree: project, directory: project });
        const system = { system: [] };
        await hooks['experimental.chat.system.transform'](
          { sessionID: 'response-test', model: {} }, system,
        );
        await hooks['chat.message'](
  { sessionID: 'ordinary', messageID: 'q' },
  { message: { id: 'q' }, parts: [{ type: 'text', text: 'Explain this concept' }] },
);
await hooks['experimental.text.complete'](
  { sessionID: 'ordinary', messageID: 'a', partID: 'part' },
  { text: 'An ordinary explanation.' },
);
await hooks['chat.message'](
  { sessionID: 'response-test', messageID: 'request' },
  { message: { id: 'request' }, parts: [{ type: 'text', text: 'saipen status' }] },
);
await hooks['tool.execute.before'](
  { tool: 'bash', sessionID: 'response-test' }, { args: { command: 'saipen status' } },
);
let rejected = false;
const attempted = { text: 'Everything is fine.' };
try {
  await hooks['experimental.text.complete'](
    { sessionID: 'response-test', messageID: 'reply', partID: 'part' },
    attempted,
  );
  rejected = attempted.text !== 'Everything is fine.' && attempted.text.startsWith('STATUS:');
} catch (error) {
  rejected = String(error.message).includes('EXEC_RESPONSE_INVALID');
}
await hooks['experimental.text.complete'](
  { sessionID: 'response-test', messageID: 'reply2', partID: 'part2' },
  { text: valid },
);
process.stdout.write(JSON.stringify({ rejected, prompt: system.system.join('\\n') }));
"""
        env = {**os.environ, "SAIPEN_SKILL_ROOT": str(ROOT), "SAIPEN_PYTHON": sys.executable}
        proc = subprocess.run(
            [
                shutil.which("node") or "node",
                "--input-type=module",
                "-e",
                script,
                str(plugin),
                str(project),
                valid,
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        result = json.loads(proc.stdout)
        self.assertTrue(result["rejected"])
        self.assertIn("EXECUTION", result["prompt"])
        self.assertIn("EXEC-RESPONSE-01", result["prompt"])
        self.assertIn("saipen response render --stdin", result["prompt"])
        self.assertIn("--auto-eligibility", result["prompt"])
        for name, expected in before.items():
            self.assertEqual((project / ".saipen" / name).read_bytes(), expected)

    @unittest.skipUnless(shutil.which("node"), "Node runtime unavailable")
    def test_opencode_command_enforces_autonomy_on_its_followup_response(self):
        from test_guard_hostile_matrix import active_project
        from saipen_engine.conformance import conformance_decision

        project = active_project()
        validation = conformance_decision(project, gate="core")["status"]
        valid = RS.render_boundary(
            RS.OperationalBoundary(
                "BUILD T-9001",
                "Work remains",
                "NONE",
                "NONE",
                "saipen continue --json",
                validation,
            )
        )
        plugin = ROOT / "extensions" / "adapters" / "opencode" / "saipen-guard.js"
        script = """
import { pathToFileURL } from 'node:url';
const [pluginPath, project, valid] = process.argv.slice(1);
const factory = (await import(pathToFileURL(pluginPath).href)).default;
const hooks = await factory({ worktree: project, directory: project });
await hooks['chat.message'](
  { sessionID: 'autonomy-test', messageID: 'request' },
  { message: { id: 'request' }, parts: [{ type: 'text', text: 'saipen continue' }] },
);
await hooks['tool.execute.before'](
  { tool: 'bash', sessionID: 'autonomy-test' }, { args: { command: 'saipen continue' } },
);
let blocked = false;
let errorText = '';
try {
  await hooks['experimental.text.complete'](
    { sessionID: 'autonomy-test', messageID: 'reply', partID: 'part' },
    { text: valid },
  );
} catch (error) {
  errorText = String(error.message);
  blocked = errorText.includes('eligible autonomous action remains');
}
process.stdout.write(JSON.stringify({ blocked, errorText }));
"""
        env = {**os.environ, "SAIPEN_SKILL_ROOT": str(ROOT), "SAIPEN_PYTHON": sys.executable}
        proc = subprocess.run(
            [
                shutil.which("node") or "node",
                "--input-type=module",
                "-e",
                script,
                str(plugin),
                str(project),
                valid,
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(json.loads(proc.stdout)["blocked"], proc.stdout)

    @unittest.skipUnless(shutil.which("node"), "Node runtime unavailable")
    def test_opencode_explicit_status_request_keeps_the_control_surface(self):
        from test_guard_hostile_matrix import active_project
        from saipen_engine.conformance import conformance_decision

        project = active_project()
        validation = conformance_decision(project, gate="core")["status"]
        valid = RS.render_boundary(
            RS.OperationalBoundary(
                "BUILD T-9001",
                "Current status requested",
                "NONE",
                "NONE",
                "saipen continue --json",
                validation,
            )
        )
        plugin = ROOT / "extensions" / "adapters" / "opencode" / "saipen-guard.js"
        script = """
import { pathToFileURL } from 'node:url';
const [pluginPath, project, valid] = process.argv.slice(1);
const factory = (await import(pathToFileURL(pluginPath).href)).default;
const hooks = await factory({ worktree: project, directory: project });
await hooks['chat.message'](
  { sessionID: 'status-test', messageID: 'request' },
  { message: { id: 'request' }, parts: [{ type: 'text', text: 'saipen status' }] },
);
await hooks['tool.execute.before'](
  { tool: 'bash', sessionID: 'status-test' }, { args: { command: 'saipen status' } },
);
await hooks['experimental.text.complete'](
  { sessionID: 'status-test', messageID: 'reply', partID: 'part' },
  { text: valid },
);
process.stdout.write(JSON.stringify({ accepted: true }));
"""
        env = {**os.environ, "SAIPEN_SKILL_ROOT": str(ROOT), "SAIPEN_PYTHON": sys.executable}
        proc = subprocess.run(
            [
                shutil.which("node") or "node",
                "--input-type=module",
                "-e",
                script,
                str(plugin),
                str(project),
                valid,
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(json.loads(proc.stdout)["accepted"])


class AutonomyTests(unittest.TestCase):
    def test_deterministic_continuation_does_not_return_to_the_user(self):
        self.assertTrue(
            RS.should_continue(
                operator_action="NONE",
                executable_action_remains=True,
                response_boundary=False,
            )
        )

    def test_required_human_action_returns_the_surface(self):
        self.assertFalse(
            RS.should_continue(
                operator_action="Run the manual test and reply PASS/FAIL",
                executable_action_remains=True,
                response_boundary=False,
            )
        )

    def test_a_true_boundary_returns_the_surface(self):
        self.assertFalse(
            RS.should_continue(
                operator_action="NONE",
                executable_action_remains=True,
                response_boundary=True,
            )
        )

    def test_exhausted_route_returns_the_surface(self):
        self.assertFalse(
            RS.should_continue(
                operator_action="NONE",
                executable_action_remains=False,
                response_boundary=False,
            )
        )


class HushParityTests(unittest.TestCase):
    def test_hush_preserves_every_mandatory_field(self):
        # No mandatory control-surface field may be suppressed by HUSH.
        surface = set(RS.MANDATORY_FIELDS)
        suppressed = {kind for kind in HUSH_MANDATORY}
        self.assertEqual(surface & suppressed, set())
        for field in RS.MANDATORY_FIELDS:
            self.assertFalse(HUSHED.suppresses(field.lower()), field)

    def test_hush_may_suppress_details_only(self):
        self.assertTrue(HUSHED.suppresses("details"))
        # And every one of the six mandatory fields stays printed.
        for field in RS.MANDATORY_FIELDS:
            self.assertFalse(HUSHED.suppresses(field), field)

    def test_mandatory_kinds_are_never_discretionary(self):
        discretionary = set(HUSHED.describe()["suppressed"])
        mandatory = set(HUSHED.describe()["mandatory"])
        self.assertEqual(discretionary & mandatory, set())


class BudgetTests(unittest.TestCase):
    def test_context_budget_remains_green_with_execution_in_cold(self):
        import protocol_budget

        errors = protocol_budget.check(PROTOCOL)
        self.assertEqual(errors, [], errors)


if __name__ == "__main__":
    unittest.main()
