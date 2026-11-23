"""SRC-185: question tools cannot bypass canonical autonomous continuation.

Controlled status doubles exercise the closed disposition matrix. The cold
incident and both native transports also read real disposable project memory.
These are boundary fixtures, not a claim that FreeBuff has a blocking hook.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import saipen  # noqa: E402
from saipen_engine import guard_events, iteration, iteration_verdict  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_t1619_iteration_boundary import BUILD_BOARD, build_state, _seat  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


MENU = {
    "questions": [{
        "question": "What should I do for '/goal cc all'?",
        "header": "Next step",
        "options": [
            {"label": "Continue verification", "description": "Keeper says complete."},
            {"label": "Live acceptance guide", "description": "Session cache unreadable."},
            {"label": "Something else", "description": "Choose another phase."},
        ],
    }],
}
CANONICAL_ACTION = "manual-verify -- choose repository release visibility"


class QuestionAuthorityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="saipen-t1627-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "project"
        memory = self.root / ".saipen"
        memory.mkdir(parents=True)
        state = _seat(build_state(task="T-1624"), agent="test-agent", last_event=100)
        (memory / "STATE.md").write_text(state, encoding="utf-8")
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        board = BUILD_BOARD.replace("T-1618", "T-1624").replace("owner: test", "owner: test-agent")
        board = board.replace("2026-10-05T19:22:47Z", now)
        (memory / "BOARD.md").write_text(board, encoding="utf-8")
        (memory / "LOG.md").write_text(
            "- 09.10.26 00:00 [E-100] [agent: test-agent] RUN: question boundary fixture\n",
            encoding="utf-8",
        )
        self.status = {
            "ok": True, "phase": "BUILD", "task": "T-1624", "execution_intent": "goal",
            "next_action": "PHASE BUILD T-1624", "computed_next_action": "PHASE BUILD T-1624",
            "automation": {
                "schema_version": 1, "disposition": "CONTINUE", "next_command": "cc",
                "operator_action_due": False, "closure_complete": False,
            },
        }

    def _event(self, host="freebuff", tool="question", questions=None) -> dict:
        return {
            "event": "before_tool", "host": host, "tool_name": tool,
            "cwd": str(self.root), "session_id": "missing-transcript-session",
            "tool_input": questions if questions is not None else copy.deepcopy(MENU),
        }

    def _guard(self, *, status=None, host="freebuff", tool="question", questions=None) -> dict:
        output = io.StringIO()
        current = self.status if status is None else status

        def owned_status(_root, _json):
            print(json.dumps(current))
            return 0 if current.get("ok") else 1

        # Double only the existing canonical status projection, not the gate.
        with patch.object(saipen, "_status", side_effect=owned_status), \
                patch.object(sys, "stdin", io.StringIO(json.dumps(
                    self._event(host=host, tool=tool, questions=questions)
                ))), contextlib.redirect_stdout(output):
            saipen._guard_event(None, ["--event-json", "-"], True)
        return json.loads(output.getvalue())

    def _cli(self, *args, event=None):
        proc = subprocess.run(
            [sys.executable, "-B", str(TOOLS / "saipen.py"), *args,
             "--project-root", str(self.root), "--json"],
            input=json.dumps(event).encode("utf-8") if event is not None else None,
            capture_output=True, timeout=60, cwd=str(self.root), env=dict(os.environ),
        )
        return proc.returncode, json.loads(proc.stdout.decode("utf-8", errors="replace"))

    def test_continue_refuses_the_exact_incident_menu_and_preserves_build(self):
        before = (self.root / ".saipen/STATE.md").read_bytes()
        verdict = self._guard()
        self.assertFalse(verdict["admitted"])
        self.assertEqual(verdict["operator_question"]["class"], "AUTONOMOUS_HANDBACK")
        self.assertEqual(verdict["canonical_next_command"], "saipen continue --json")
        self.assertEqual(verdict["operator_question"]["next_action"], "PHASE BUILD T-1624")
        self.assertEqual((self.root / ".saipen/STATE.md").read_bytes(), before)

    def test_keeper_completion_and_session_cache_never_grant_question_authority(self):
        observations = ("keeper complete", "cache unreadable", "handoff absent", "model switched")
        for observation in observations:
            status = copy.deepcopy(self.status)
            status["model_observation"] = observation
            with self.subTest(observation=observation):
                self.assertFalse(self._guard(status=status)["admitted"])

    def test_complete_external_blocked_and_invalid_never_allow_a_lifecycle_menu(self):
        for disposition in ("COMPLETE", "WAIT_EXTERNAL", "BLOCKED", "INVALID"):
            status = copy.deepcopy(self.status)
            status["automation"].update(disposition=disposition, next_command=None)
            with self.subTest(disposition=disposition):
                self.assertFalse(self._guard(status=status)["admitted"])

    def test_unknown_or_missing_projection_is_a_diagnostic_not_a_question(self):
        projections = (
            {}, {"schema_version": 99, "disposition": "WAIT_USER"},
            {"schema_version": 1, "disposition": "IMPROVISED", "operator_action_due": True},
        )
        for auto in projections:
            status = {**self.status, "automation": auto}
            with self.subTest(automation=auto):
                self.assertFalse(self._guard(status=status)["admitted"])

    def _wait(self) -> dict:
        state_path = self.root / ".saipen/STATE.md"
        state_path.write_text(_seat(
            state_path.read_text(encoding="utf-8"),
            next_action=f'"WAIT: {CANONICAL_ACTION}"',
        ), encoding="utf-8")
        status = copy.deepcopy(self.status)
        status["automation"].update(
            disposition="WAIT_USER", next_command=None, operator_action_due=True,
        )
        return status

    def test_a_true_wait_allows_the_exact_canonical_operator_question(self):
        verdict = self._guard(status=self._wait(), questions={"questions": [{
            "question": CANONICAL_ACTION, "header": "SAIPEN", "options": [],
        }]})
        self.assertTrue(verdict["admitted"], verdict)

    def test_a_true_wait_cannot_smuggle_in_a_different_question_or_extra_choices(self):
        status = self._wait()
        self.assertFalse(self._guard(status=status)["admitted"])
        self.assertFalse(self._guard(status=status, questions={"questions": [{
            "question": CANONICAL_ACTION, "options": [{"label": "VERIFY"}],
        }]})["admitted"])

    def test_due_flag_must_be_machine_boolean_not_model_text(self):
        status = self._wait()
        status["automation"].update(disposition="CONTINUE", operator_action_due="true")
        self.assertFalse(self._guard(status=status)["admitted"])

    def test_incompatible_executor_uses_existing_failover_and_keeps_work(self):
        verdict = iteration_verdict.project_iteration_verdict(
            self.root, executor_caps={"read_tabular": True},
        )
        self.assertEqual(verdict["decision"], iteration.EXECUTOR_CAPABILITY_MISMATCH)
        self.assertFalse(verdict["requires_human"])
        self.assertEqual(verdict["canonical_task"], "T-1624")
        self.assertEqual(verdict["execution_intent"], "goal")
        self.assertFalse(self._guard()["admitted"])

    def test_claude_question_uses_the_same_canonical_semantics(self):
        verdict = self._guard(host="claude", tool="AskUserQuestion")
        self.assertFalse(verdict["admitted"])
        self.assertEqual(verdict["operator_question"]["class"], "AUTONOMOUS_HANDBACK")

    def test_real_claude_pretool_question_is_refused_before_ui_delivery(self):
        payload = {
            "hook_event_name": "PreToolUse", "tool_name": "AskUserQuestion",
            "tool_input": MENU, "cwd": str(self.root), "session_id": "claude-question",
        }
        proc = subprocess.run(
            [sys.executable, "-B", str(ROOT / "extensions/adapters/claude/saipen-guard.py"),
             "--host", "claude", "--saipen-root", str(ROOT)],
            input=json.dumps(payload).encode("utf-8"), capture_output=True,
            timeout=60, cwd=str(self.root), env=dict(os.environ),
        )
        answer = json.loads(proc.stdout.decode("utf-8", errors="replace") or "{}")
        self.assertEqual(answer.get("hookSpecificOutput", {}).get("permissionDecision"), "deny")
        self.assertIn("AUTONOMOUS_HANDBACK", str(answer))

    @unittest.skipUnless(shutil.which("node"), "node runtime unavailable")
    def test_real_opencode_question_hook_is_refused_before_ui_delivery(self):
        from test_opencode_adapter import PLUGIN, run_cases

        home = Path(self.temporary.name) / "profile"
        (home / ".saipen").mkdir(parents=True)
        (home / ".saipen/authority.json").write_text('{"mode":"degraded"}', encoding="utf-8")
        result = run_cases(PLUGIN, [{
            "id": "question", "project": str(self.root),
            "env": {"SAIPEN_SKILL_ROOT": str(ROOT), "SAIPEN_PYTHON": sys.executable,
                    "HOME": str(home), "USERPROFILE": str(home), "SAIPEN_AGENT": "test-agent"},
            "input": {"tool": "question", "sessionID": "opencode-question"},
            "output": {"args": copy.deepcopy(MENU)},
        }], Path(self.temporary.name) / "node-driver")[0]
        self.assertEqual(result["outcome"], "blocked", result)
        self.assertIn("AUTONOMOUS_HANDBACK", result["message"])

    def test_unbound_product_question_remains_non_interfering(self):
        ordinary = Path(self.temporary.name) / "ordinary"
        ordinary.mkdir()
        event = self._event()
        event["cwd"] = str(ordinary)
        self.assertTrue(guard_events.evaluate_event(event)["admitted"])

    def test_unregistered_question_name_never_gains_read_trust(self):
        for host in ("zaicode", "gemini", "generic"):
            with self.subTest(host=host):
                event = self._event(host=host)
                self.assertNotEqual(guard_events.map_event(event)["action"], "read")
                self.assertFalse(self._guard(host=host)["admitted"])

    def test_cold_real_project_route_wins_over_an_absent_provider_session(self):
        session = self.root / "unreadable-session.jsonl"
        session.mkdir()
        rc, status = self._cli("status")
        self.assertEqual(rc, 0, status)
        self.assertEqual(status["automation"]["disposition"], "CONTINUE")
        rc, continuation = self._cli("continue")
        self.assertEqual(rc, 0, continuation)
        self.assertEqual(continuation["action"], "PHASE BUILD T-1624")
        before = (self.root / ".saipen/STATE.md").read_bytes()
        rc, verdict = self._cli("guard", "--event-json", "-", event=self._event())
        self.assertNotEqual(rc, 0, verdict)
        self.assertFalse(verdict["admitted"])
        self.assertEqual((self.root / ".saipen/STATE.md").read_bytes(), before)

    def test_real_wait_projection_admits_only_its_owned_operator_action(self):
        self._wait()
        rc, status = self._cli("status")
        self.assertEqual(rc, 0, status)
        self.assertTrue(status["automation"]["operator_action_due"])
        event = self._event(questions={"questions": [{
            "question": CANONICAL_ACTION, "header": "SAIPEN", "options": [],
        }]})
        rc, verdict = self._cli("guard", "--event-json", "-", event=event)
        self.assertEqual(rc, 0, verdict)
        self.assertTrue(verdict["admitted"])
        self.assertIn(CANONICAL_ACTION, verdict["operator_question"]["canonical_surface"])

    def test_registry_records_advisory_freebuff_without_a_blocking_claim(self):
        registry = json.loads((ROOT / "extensions/adapters/registry.json").read_text("utf-8-sig"))
        hosts = {row["id"]: row for row in registry["adapters"]}
        self.assertEqual(hosts["freebuff"].get("question_enforcement"), "ADVISORY")
        self.assertFalse(hosts["freebuff"]["blocking_capability"])
        self.assertTrue(all(row.get("question_enforcement") in
                            {"MECHANICAL", "ADVISORY", "UNAVAILABLE"}
                            for row in hosts.values()))


if __name__ == "__main__":
    unittest.main()
