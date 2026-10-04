#!/usr/bin/env python
"""The CI failure roster must name every red test AND say why.

A green run needs nothing here. A red run needs the one thing a CI log
truncation cannot take away: which tests failed, and the line each ended on.
``test_runner.py`` prints the roster last so it survives any truncation of the
job log, and the cause rides with the name because a bare name is a count, not
a diagnosis.
"""

from __future__ import annotations

import importlib
import tempfile
import unittest
from pathlib import Path

R = importlib.import_module("saipen_engine.test_runner")

# The exact shape unittest prints: a rule, the header, the header's own rule,
# the traceback, the exception, then the closing rule.
TWO_FAILURES = """\
======================================================================
FAIL: test_alpha (m.C.test_alpha)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "x.py", line 1, in test_alpha
    self.assertEqual(1, 2)
AssertionError: 1 != 2 : the cause line

======================================================================
ERROR: test_beta (m.C.test_beta)
----------------------------------------------------------------------
RuntimeError: boom
----------------------------------------------------------------------

"""


class FailureRosterTests(unittest.TestCase):
    def spool(self, text: str) -> Path:
        directory = Path(tempfile.mkdtemp(prefix="saipen-roster-"))
        path = directory / "stderr"
        path.write_text(text, encoding="utf-8")
        return path

    def test_the_roster_names_every_failing_test(self):
        self.assertEqual(
            R._read_failure_roster_from_path(self.spool(TWO_FAILURES)),
            ["test_alpha", "test_beta"],
        )

    def test_each_name_carries_the_line_its_block_ended_on(self):
        self.assertEqual(
            R._read_failure_causes_from_path(self.spool(TWO_FAILURES)),
            {
                "test_alpha": "AssertionError: 1 != 2 : the cause line",
                "test_beta": "RuntimeError: boom",
            },
        )

    def test_a_separator_is_not_mistaken_for_the_cause(self):
        """The rule unittest prints BETWEEN blocks must not become the cause."""
        text = TWO_FAILURES + (
            "======================================================================\n"
            "FAIL: test_gamma (m.C.test_gamma)\n"
            "----------------------------------------------------------------------\n"
            "AssertionError: the last one\n"
        )
        causes = R._read_failure_causes_from_path(self.spool(text))
        self.assertEqual(causes["test_gamma"], "AssertionError: the last one")

    def test_a_block_with_no_body_has_no_cause_rather_than_a_guess(self):
        causes = R._read_failure_causes_from_path(
            self.spool("FAIL: test_delta (m.C.test_delta)\n" + "-" * 70 + "\n")
        )
        self.assertEqual(causes, {})

    def test_a_missing_spool_reads_as_empty_rather_than_raising(self):
        absent = Path(tempfile.mkdtemp(prefix="saipen-roster-")) / "never-written"
        self.assertEqual(R._read_failure_roster_from_path(absent), [])
        self.assertEqual(R._read_failure_causes_from_path(absent), {})


if __name__ == "__main__":
    unittest.main()