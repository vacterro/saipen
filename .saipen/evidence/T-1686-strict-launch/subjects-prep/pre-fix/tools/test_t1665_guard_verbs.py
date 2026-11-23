"""T-1665: the guard and COMMANDS.md give one answer for every documented verb.

Found in T-1640: typed in a guarded shell while no Work is active, `saipen
clean` and `saipen translate` answered NO_ACTIVE_WORK with "'clean' is not a
verb" -- while COMMANDS.md lists both, tools/saipen.py dispatches both and
`saipen transition CLEAN` was admitted in the same state. COMMAND_EFFECTS.json
`not_shell_canonical` carried them over from an older hand-written list.

* ADMIT  -- the two phase verbs are admitted exactly as `saipen transition
            PHASE` is, in both states the probe measured.
* TRUTH  -- every verb the CLI dispatches, walked through the guard: none is
            ever called "not a verb"; a verb a shell line does not run says
            what is true and, where one exists, names the admitted spelling.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from test_hermetic_env import isolate_host_session  # noqa: E402
from test_guard_hostile_matrix import (  # noqa: E402
    GuardEventHarness,
    active_project,
    fresh_project,
)

from saipen_engine import command_effects as CE  # noqa: E402
from saipen_engine import guard_events  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


def guard(root: Path, command: str) -> dict:
    _code, data = GuardEventHarness.run(
        GuardEventHarness.tool_event(root, "bash", {"command": command})
    )
    return data


class PhaseVerbTests(unittest.TestCase):
    def test_the_phase_verbs_are_admitted_as_their_transition_is(self):
        for label, root in (
            ("DONE, no Work", fresh_project()),
            ("BUILD, own Work", active_project()),
        ):
            for verb, phase in (("clean", "CLEAN"), ("translate", "TRANSLATE")):
                with self.subTest(state=label, verb=verb):
                    direct = guard(root, f"saipen {verb}")
                    transition = guard(root, f"saipen transition {phase}")
                    self.assertTrue(transition.get("admitted"), transition)
                    self.assertTrue(direct.get("admitted"), direct)
                    self.assertEqual(
                        (direct.get("event") or {}).get("action"),
                        (transition.get("event") or {}).get("action"),
                    )


class VerbTruthTests(unittest.TestCase):
    def test_no_verb_the_cli_dispatches_is_ever_called_not_a_verb(self):
        root = fresh_project()
        verbs = sorted(CE._VERBS)
        self.assertIn("clean", verbs)
        for verb in verbs:
            with self.subTest(verb=verb):
                problem = guard_events.saipen_line_problem(f"saipen {verb}")
                if problem is not None:
                    self.assertNotIn("is not a verb", problem[0], problem)
                answer = guard(root, f"saipen {verb}")
                self.assertNotIn("is not a verb", str(answer.get("detail") or ""), answer)
                self.assertNotIn("is not a verb", str(answer.get("reason") or ""), answer)

    def test_a_verb_a_shell_does_not_run_names_what_is_true(self):
        reason, spelling = guard_events.saipen_line_problem("saipen init")
        self.assertIn("is a SAIPEN verb", reason)
        self.assertEqual(spelling, "saipen set")
        self.assertTrue(CE.is_shell_canonical_verb("set"))
        for verb in ("launch", "first-publish-confirm"):
            with self.subTest(verb=verb):
                reason, spelling = guard_events.saipen_line_problem(f"saipen {verb}")
                self.assertIn("is a SAIPEN verb", reason)
                self.assertIsNone(spelling)

    def test_an_unknown_word_is_still_not_a_verb(self):
        reason, _spelling = guard_events.saipen_line_problem("saipen frobnicate")
        self.assertIn("is not a verb", reason)
        reason, spelling = guard_events.saipen_line_problem("saipen statuz")
        self.assertIn("did you mean `saipen status`", reason)
        self.assertEqual(spelling, "saipen status")


if __name__ == "__main__":
    unittest.main()
