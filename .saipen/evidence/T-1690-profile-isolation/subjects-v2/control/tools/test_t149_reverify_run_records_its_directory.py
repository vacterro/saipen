"""T-149: an executed re-verification receipt must say WHERE it ran.

RED CONTROL. `_run_verification_command` executes the operator's command with
`cwd` set to the project root, and neither the command surface, nor any
refusal, nor the minted entry ever said so. A module-form command resolves
against that root rather than the directory the tests live in, so it dies
before touching the code under test and is recorded as an honest FAIL -- which
is indistinguishable, in the receipt, from the capability being broken.

Measured on this project: eighteen consecutive tickets were re-verified with
`python -B -m unittest test_wave_next1.TermisaiAdapter`, all eighteen minted
verdict FAIL, while the identical module passes from `tools/` and the identical
coverage as discovery rooted at tools passes from the root. The evidence class
is correctly fail-closed, but the only lever the operator holds is a string
carrying an undocumented invariant, and violating it scores like a regression.

Recording `cwd` makes the failure legible without guessing from stderr whether
a non-zero exit was a launch problem or a genuine break.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = str(Path(__file__).resolve().parent)
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

from saipen_engine.debt import _run_verification_command  # noqa: E402


class ReverifyRunRecordsItsDirectory(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="t149-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def _run(self, command: str) -> dict:
        entry = _run_verification_command(self.root, command, 60)
        # Round-trip through JSON: the receipt is serialised, so a field that
        # does not survive the wire was never in the evidence.
        return json.loads(json.dumps(entry))

    def test_a_passing_command_records_the_directory_it_ran_in(self):
        entry = self._run("python -c \"import os;print(os.getcwd())\"")
        self.assertEqual(entry["result"], "PASS", entry)
        self.assertEqual(entry["cwd"], str(self.root))

    def test_a_failing_command_still_records_the_directory(self):
        """The whole point: the FAIL that reads as a regression is legible."""
        entry = self._run("python -c \"raise SystemExit(3)\"")
        self.assertEqual(entry["result"], "FAIL", entry)
        self.assertEqual(entry["exit_code"], 3, entry)
        self.assertEqual(entry["cwd"], str(self.root))

    def test_a_module_that_does_not_resolve_from_the_root_is_honest_about_it(self):
        """The measured case, and the reason the field exists.

        The command is recorded honestly as a FAIL; what it must NOT do is
        leave the operator with no way to tell a wrong directory from a broken
        capability. `cwd` is what tells them.
        """
        entry = self._run("python -c \"import no_such_module_xyz\"")
        self.assertEqual(entry["result"], "FAIL", entry)
        self.assertEqual(entry["cwd"], str(self.root))
        self.assertEqual(entry["executed"], True, entry)

    def test_a_timeout_still_records_the_directory(self):
        entry = _run_verification_command(self.root, "python -c \"import time;"
                                          "time.sleep(20)\"", 1)
        self.assertTrue(entry.get("timed_out"), entry)
        self.assertEqual(entry["cwd"], str(self.root))

    def test_an_unlaunchable_command_still_records_the_directory(self):
        """`shell=True` means the shell reports this as exit 1, not an OSError.

        Either way it is an honest FAIL; `cwd` is what tells the operator it
        never reached the code under test.
        """
        entry = self._run("this-command-does-not-exist-anywhere")
        self.assertEqual(entry["result"], "FAIL", entry)
        self.assertNotEqual(entry["exit_code"], 0, entry)
        self.assertEqual(entry["cwd"], str(self.root))


if __name__ == "__main__":
    unittest.main()