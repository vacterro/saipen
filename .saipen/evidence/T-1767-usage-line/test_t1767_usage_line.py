"""T-1767: every top-level alternative of the usage line is a command.

The usage line separated top-level commands with `|` and used the same `|`
between the subcommands of one family, so `test suite [status]|declare --
<command>|run [T-###]|withdraw` presented declare, run and withdraw as
commands. An executor on SAI_WEBSITE T-31 read it that way, got `unknown
command` twice and reported the suite capability as missing (SRC-246).

The oracle reads the line the way such a reader does -- `|` at the outer
level separates commands -- and asks the dispatcher about each one.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402

import saipen as CLI  # noqa: E402

#: Commands with effects beyond a throwaway project, known to dispatch.
_NOT_PROBED = {"init", "launch", "push", "ship"}


def _call(*argv: str) -> dict:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        CLI.main(list(argv))
    raw = out.getvalue().strip()
    try:
        return json.loads(raw)
    except ValueError:
        return {"_raw": raw}


def _alternatives(usage: str) -> list[str]:
    """The top-level alternatives: `|` at depth 0 of the outer parenthesis."""
    body = usage[usage.index("(") + 1 :]
    depth, current, found = 0, "", []
    for char in body:
        if char in "([{<":
            depth += 1
        elif char in ")]}>":
            if depth == 0:
                break
            depth -= 1
        if char == "|" and depth == 0:
            found.append(current.strip())
            current = ""
        else:
            current += char
    found.append(current.strip())
    return found


def _probe(alternative: str) -> list[str]:
    """The literal words that invoke an alternative, plus a group's first member."""
    words: list[str] = []
    for token in alternative.split():
        if token.startswith("{"):
            words.append(token[1:].split("|")[0].rstrip("}"))
            break
        if token[0] in "<[-'":
            break
        words.append(token)
    return words


class UsageLineAlternatives(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._config = tempfile.mkdtemp(prefix="t1767-config-")
        cls._env = mock.patch.dict(os.environ, {"SAIPEN_USER_CONFIG_HOME": cls._config})
        cls._env.start()
        cls.root = Path(tempfile.mkdtemp(prefix="t1767-")) / "project"
        saipen = cls.root / ".saipen"
        saipen.mkdir(parents=True)
        (saipen / "STATE.md").write_text(
            "---\nphase: DONE\ntask: none\nnext_action: saipen continue\nblocker: none\n"
            "transition_from: SHIP\nsaipen_version: 8\nschema_version: 3\nlast_event: 1\n"
            f"style_contract: {CURRENT_STYLE_CONTRACT}\nagent: tester\nmode: full\n"
            "updated: 2026-10-14T00:00:00Z\n---\n",
            encoding="utf-8",
        )
        (saipen / "BOARD.md").write_text(
            "## DOING\n## TODO\n## DONE\n- [x] T-000 fixture | verify: PASS -- fixture\n"
            "## BLOCKED\n",
            encoding="utf-8",
        )
        (saipen / "LOG.md").write_text(
            "# Log\n- 01.01.20 00:00 [E-001] [agent: tester] DEC: fixture\n",
            encoding="utf-8",
        )
        cls.usage = _call("help", "--json")["usage"]
        cls.alternatives = _alternatives(cls.usage)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._env.stop()
        shutil.rmtree(cls.root.parent, ignore_errors=True)
        shutil.rmtree(cls._config, ignore_errors=True)

    def _unknown(self, *argv: str) -> bool:
        answer = _call(*argv, "--dry-run", "--json", "--project-root", str(self.root))
        return f"unknown command: {argv[0]}" in str(answer.get("detail", ""))

    def test_the_probe_sees_an_unknown_command(self) -> None:
        # Instrument control: the dispatcher's own answer for a word it lacks.
        self.assertTrue(self._unknown("frobnicate"))
        self.assertFalse(self._unknown("status"))

    def test_every_top_level_alternative_is_dispatched(self) -> None:
        unknown = []
        for alternative in self.alternatives:
            words = _probe(alternative)
            if not words or words[0] in _NOT_PROBED:
                continue
            if self._unknown(*words):
                unknown.append(alternative)
        self.assertEqual(unknown, [], self.usage)

    def test_the_suite_verbs_are_arguments_of_test_suite(self) -> None:
        suite = [alt for alt in self.alternatives if alt.startswith("test suite")]
        self.assertEqual(len(suite), 1, self.alternatives)
        for verb in ("status", "declare -- <command>", "run [T-###]", "withdraw"):
            self.assertIn(verb, suite[0])

    def test_run_and_declare_are_not_advertised_as_commands(self) -> None:
        firsts = {alt.split()[0] for alt in self.alternatives if alt.split()}
        for word in ("run", "declare", "withdraw"):
            self.assertNotIn(word, firsts)
            self.assertTrue(self._unknown(word))


if __name__ == "__main__":
    unittest.main()
