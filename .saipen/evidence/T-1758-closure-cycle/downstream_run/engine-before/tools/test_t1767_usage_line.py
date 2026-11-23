"""T-1767: the usage line presents only commands the dispatcher dispatches.

The line rendered `...|test suite [status]|declare -- <command>|run [T-###]|
withdraw|...`, so `declare`, `run` and `withdraw` read as top-level commands.
They are actions of `test suite` (T-1658): `saipen run` and `saipen declare`
answered "unknown command", and an executor on SAI_WEBSITE T-31 reported the
capability as missing (SRC-246). The same flat spelling covered `context`,
`knowledge`, `future`, `host`, `storage`, `response`, `fleet` and `userperson`.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import test_t1614_future_gate as H  # noqa: E402
from saipen_engine.commands import load_shortcut_table  # noqa: E402
from test_hermetic_env import hermetic_env, isolate_host_session  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


def _cli(*args: str, cwd: Path = ROOT) -> dict:
    proc = subprocess.run(
        [sys.executable, "-B", str(TOOLS / "saipen.py"), *args],
        cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
        env=hermetic_env(), timeout=300,
    )
    return json.loads(proc.stdout)


def _top_level(usage: str) -> list[str]:
    """Alternatives of the outer `saipen ( ... )` group; (), [] and <> nest."""
    body = usage[usage.index("(") + 1:]
    parts, depth, current = [], 0, []
    for char in body:
        if char in "([<":
            depth += 1
        elif char in ")]>":
            if depth == 0:
                break
            depth -= 1
        if char == "|" and depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    parts.append("".join(current).strip())
    return [part for part in parts if part]


def _dispatched_verbs() -> set[str]:
    """The verbs the dispatcher in tools/saipen.py compares its argument with."""
    source = (TOOLS / "saipen.py").read_text(encoding="utf-8")
    verbs = set(re.findall(r'\b(?:command|args\[0\]) == "([a-z][a-z0-9-]*)"', source))
    for group in re.findall(r"\b(?:command|args\[0\]) in \(([^)]*)\)", source):
        verbs.update(re.findall(r'"([a-z][a-z0-9-]*)"', group))
    return verbs | set(load_shortcut_table())


class UsageLineTests(unittest.TestCase):
    def test_every_top_level_alternative_is_a_dispatched_verb(self):
        usage = _cli("help", "--json")["usage"]
        verbs = _dispatched_verbs()
        self.assertIn("test", verbs)
        stray = [alt for alt in _top_level(usage) if alt.split()[0] not in verbs]
        self.assertEqual(stray, [], "advertised as top-level but not dispatched")

    def test_suite_verbs_are_arguments_of_test_suite(self):
        usage = _cli("help", "--json")["usage"]
        self.assertIn("test suite [status|declare -- <command>|run [T-###]|withdraw]", usage)
        firsts = {alt.split()[0] for alt in _top_level(usage)}
        self.assertFalse(firsts & {"declare", "run", "withdraw"}, firsts)


class UnknownCommandRouteTests(unittest.TestCase):
    def setUp(self):
        self.base, self.project = H._project(intent="goal")
        self.addCleanup(shutil.rmtree, self.base, True)

    def test_a_nested_action_names_its_real_route(self):
        payload = _cli("run", "--json", "--project-root", str(self.project), cwd=self.project)
        self.assertEqual(payload.get("code"), "VALIDATION_FAILED", payload)
        self.assertEqual(payload.get("dispatched_as"), ["saipen test suite run"], payload)
        self.assertIn("saipen test suite run", payload.get("detail", ""))

    def test_a_word_no_verb_owns_stays_a_bare_refusal(self):
        payload = _cli("frobnicate", "--json", "--project-root", str(self.project),
                       cwd=self.project)
        self.assertEqual(payload.get("detail"), "unknown command: frobnicate", payload)
        self.assertNotIn("dispatched_as", payload)


if __name__ == "__main__":
    unittest.main()
