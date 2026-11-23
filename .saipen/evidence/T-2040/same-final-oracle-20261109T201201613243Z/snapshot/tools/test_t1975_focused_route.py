"""T-1975: a printed canonical route must be one the named tool can actually run.

`intake.set_disposition` derived its `--pattern` from whatever `.py` name
appeared in the verification text:

    test_target = Path(test_files[0]).name if test_files else ...

`focused_unit._patterns` accepts only a bare `test_*.py` filename. Handed
`verify_accounts_readiness.py` -- a real, runnable unittest module that simply
does not carry the prefix -- the engine printed

    python tools/core_unit.py focused T-1653 --pattern verify_accounts_readiness.py

and that command is refused by the very tool it names:

    patterns must select test_*.py filenames inside tools/

Measured 2026-10-31 on SRC-188:R009, whose owner T-1653 is DONE and whose
oracle is exactly that module. The refusal told the receiver to run a command
that can never succeed, which is the T-1640 failure the KNOWLEDGE card
`name-the-route-the-guard-admits` records: a named route is not a reachable
route until the surface that consumes it admits the spelling.

Controls:
1. A non-test oracle prints the full core-unit route, which the intake gate
   authenticates, and never a focused pattern that focused_unit refuses.
2. A genuine `test_*.py` oracle prints the focused route unchanged, and that
   printed pattern is one `focused_unit._patterns` admits.
3. Every focused command the engine emits is admissible by construction: the
   two emitters are checked against the tool's own grammar rather than a copy.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import debt, focused_unit, guard_events, intake  # noqa: E402

_PLACEHOLDER = re.compile(r"<[^<>]{1,40}>|\{[^{}]{0,60}\}|%[sd]")


def _typed(command: str) -> str:
    """What an operator actually types: placeholders stand for a value."""
    return _PLACEHOLDER.sub("T-1", command)

_FOCUSED_PATTERN = re.compile(r"core_unit\.py focused \S+ --pattern (\S+)")


class FocusedRouteTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="t1975-route-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / ".saipen").mkdir(parents=True, exist_ok=True)
        (self.root / ".saipen" / "STATE.md").write_text(
            "---\nphase: BUILD\ntask: T-100\n---\n", encoding="utf-8"
        )
        (self.root / ".saipen" / "BOARD.md").write_text(
            "# Board\n\n## DOING\n"
            "- [/] T-100 [P1] Live work | verify: test | owner: tester\n\n"
            "## DONE\n",
            encoding="utf-8",
        )
        (self.root / ".saipen" / "LOG.md").write_text("# Log\n", encoding="utf-8")
        (self.root / "tools").mkdir(parents=True, exist_ok=True)

    def _refusal(self, module: str) -> dict:
        (self.root / "tools" / module).write_text(
            "import unittest\n\n\nclass Probe(unittest.TestCase):\n"
            "    def test_placeholder(self):\n        pass\n",
            encoding="utf-8",
        )
        captured = intake.capture(
            self.root, f"request for {module}", source_kind="user_instruction",
            work="T-100",
        )
        receipt = captured["receipt"]
        intake.ensure_request_clause(self.root, receipt)
        return intake.set_disposition(
            self.root,
            receipt,
            "R001",
            "VERIFIED",
            work="T-100",
            evidence="probe ran",
            verification=f"python tools/{module} ran 3 tests OK",
        )

    def test_a_non_test_oracle_prints_a_route_that_can_run(self):
        res = self._refusal("verify_accounts_readiness.py")
        self.assertFalse(res.get("ok"))
        self.assertEqual(res.get("code"), "EVIDENCE_UNAUTHENTICATED")
        command = res.get("canonical_next_command") or ""
        self.assertTrue(command, res)
        self.assertNotIn(
            "core_unit.py focused", command,
            "a focused pattern was printed for a module focused_unit cannot "
            f"select: {command}",
        )
        # The family is discovered with `-p test_*.py`, so it never executes
        # this module; naming it would trade an unrunnable route for one that
        # falsely discharges the clause.
        self.assertNotIn(
            "core_unit.py evidence", command,
            f"the declared family cannot prove a non-test oracle: {command}",
        )
        self.assertTrue(
            command.startswith("saipen work reverify T-100 --contract"),
            command,
        )
        # The command itself must be one a guarded shell admits; the long-form
        # explanation lives in the refusal detail, not inside the argv.
        self.assertEqual(guard_events._saipen_cli_verb(_typed(command)), "work")
        self.assertIn("verify_accounts_readiness.py", res.get("detail", ""))

    def test_a_test_oracle_still_prints_the_focused_route(self):
        res = self._refusal("test_probe.py")
        self.assertFalse(res.get("ok"))
        self.assertEqual(res.get("code"), "EVIDENCE_UNAUTHENTICATED")
        command = res.get("canonical_next_command") or ""
        pattern = _FOCUSED_PATTERN.search(command)
        self.assertIsNotNone(pattern, command)
        self.assertEqual(pattern.group(1), "test_probe.py")
        self.assertEqual(
            focused_unit._patterns([pattern.group(1)]), ["test_probe.py"]
        )

    def test_every_emitted_focused_pattern_is_admissible(self):
        """The emitters are checked against the consuming tool's own grammar."""
        for module in (
            "verify_accounts_readiness.py",
            "test_probe.py",
            "saipen.py",
            "core_unit.py",
        ):
            with self.subTest(module=module):
                res = self._refusal(module)
                command = res.get("canonical_next_command") or ""
                pattern = _FOCUSED_PATTERN.search(command)
                if pattern is None:
                    continue
                # Must not raise: an inadmissible pattern is the defect.
                focused_unit._patterns([pattern.group(1)])

    def test_a_live_work_reverify_route_is_admissible(self):
        """The sibling emitter already prints `test_*.py`; keep it that way."""
        res = debt.reverify_work(
            self.root, "T-100", "tester",
            verification=[{"command": "python -m unittest tools/test_probe.py",
                           "result": "PASS"}],
        )
        self.assertFalse(res.get("ok"))
        self.assertEqual(res.get("code"), "REVERIFY_REFUSED")
        command = res.get("canonical_next_command") or ""
        pattern = _FOCUSED_PATTERN.search(command)
        self.assertIsNotNone(pattern, command)
        self.assertEqual(focused_unit._patterns([pattern.group(1)]), ["test_*.py"])
        json.dumps(res)


if __name__ == "__main__":
    unittest.main()
