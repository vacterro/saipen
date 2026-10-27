"""T-1916 Continuation Discipline Test Suite.

Verify clause:
    a turn whose NEXT EXACT ACTION is an executable command the engine could run
    continues tool-to-tool; only a real WAIT/operator gate, a true WAIT_EXTERNAL
    or a terminal result ends the turn, and the same rule is stated where the
    agent reads its response contract.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from test_hermetic_env import isolate_host_session  # noqa: E402
from saipen_engine.response_surface import (  # noqa: E402
    CLASS_AUTONOMOUS_HANDBACK,
    CLASS_VALID_BOUNDARY,
    classify_final_response,
    is_executable_command,
    response_errors,
)


def setUpModule() -> None:
    isolate_host_session()


class ContinuationDisciplineTests(unittest.TestCase):
    def test_rule_is_stated_in_execution_response_contract(self) -> None:
        execution_md = (TOOLS.parent / "saipen" / "EXECUTION.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Continuation discipline", execution_md)
        self.assertIn("NEXT EXACT ACTION is an", execution_md)
        self.assertIn("executable command", execution_md)
        self.assertIn("tool-to-tool", execution_md)

    def test_executable_command_detection(self) -> None:
        self.assertTrue(is_executable_command("saipen transition VERIFY T-1916"))
        self.assertTrue(is_executable_command("python tools/saipen.py ticket done T-1916"))
        self.assertTrue(is_executable_command("cc"))
        self.assertTrue(is_executable_command("ccc"))
        self.assertTrue(is_executable_command("./tools/verify.sh"))
        self.assertTrue(is_executable_command("git status"))
        self.assertTrue(is_executable_command("pytest tools/"))

        self.assertFalse(is_executable_command("NONE"))
        self.assertFalse(is_executable_command(""))
        self.assertFalse(is_executable_command(None))
        self.assertFalse(is_executable_command("await core-unit PID 1234 completion"))
        self.assertFalse(is_executable_command("NONE -- ticket completed"))

    def test_compact_final_naming_executable_action_on_inflight_phase_refuses(self) -> None:
        for phase in ("SCOUT", "BUILD", "VERIFY", "REVIEW", "SHIP"):
            for cmd in (
                "saipen transition VERIFY T-1916",
                "python tools/saipen.py ticket done T-1916",
                "cc",
                "ccc",
            ):
                with self.subTest(phase=phase, cmd=cmd):
                    text = (
                        f"STATUS: {phase} T-1916\n"
                        "RESULT: in progress\n"
                        f"NEXT EXACT ACTION: {cmd}\n"
                        "VALIDATION: PASS"
                    )
                    errors = response_errors(text)
                    self.assertIn(
                        "eligible autonomous action remains; returning control is invalid",
                        errors,
                    )
                    klass, _ = classify_final_response(text, operational_turn=True)
                    self.assertEqual(klass, CLASS_AUTONOMOUS_HANDBACK)

    def test_terminal_state_allows_ending_the_turn(self) -> None:
        text = (
            "STATUS: DONE\n"
            "RESULT: completed successfully\n"
            "NEXT EXACT ACTION: NONE\n"
            "VALIDATION: PASS"
        )
        errors = response_errors(text)
        self.assertEqual(errors, [])
        klass, _ = classify_final_response(text, operational_turn=True)
        self.assertEqual(klass, CLASS_VALID_BOUNDARY)

    def test_real_operator_gate_allows_ending_the_turn(self) -> None:
        text = (
            "STATUS: WAIT\n"
            "RESULT: operator input required\n"
            "OPERATOR ACTION: Confirm database schema migration (yes/no)\n"
            "NEXT EXACT ACTION: saipen continue\n"
            "VALIDATION: PASS"
        )
        errors = response_errors(text)
        self.assertEqual(errors, [])
        klass, _ = classify_final_response(text, operational_turn=True)
        self.assertEqual(klass, CLASS_VALID_BOUNDARY)

    def test_real_blocker_allows_ending_the_turn(self) -> None:
        text = (
            "STATUS: BLOCKED\n"
            "RESULT: execution blocked on external dependency\n"
            "BLOCKER: BLOCKED_EXTERNAL -- upstream API unreachable\n"
            "NEXT EXACT ACTION: saipen status\n"
            "VALIDATION: PASS"
        )
        errors = response_errors(text)
        self.assertEqual(errors, [])
        klass, _ = classify_final_response(text, operational_turn=True)
        self.assertEqual(klass, CLASS_VALID_BOUNDARY)

    def test_non_executable_inflight_action_allows_awaiting_gate(self) -> None:
        text = (
            "STATUS: BUILD T-1916\n"
            "RESULT: awaiting background test run\n"
            "NEXT EXACT ACTION: await core-unit PID 5678 completion\n"
            "VALIDATION: PASS"
        )
        errors = response_errors(text)
        self.assertNotIn(
            "eligible autonomous action remains; returning control is invalid",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
