"""T-1287: a scoped audit_checks run that selects no control is an answer.

A change no CASE targets selects zero controls -- the ordinary result for an
engine module, measured while verifying T-1285. That run once died with
`ValueError: max_workers must be greater than 0`; 7e0d5a89 clamped the pool
without a regression, and the clamp still spawned one worker that copied the
whole tree and ran the validator twice to test nothing, then reported "the 0
selected control(s) each went red on their own condition".
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import audit_checks as A  # noqa: E402

CHANGED = frozenset({"tools/saipen_engine/fast_check.py"})


class _Context:
    """The four fields mutation_sweep_probe reads, over a tree that does not
    exist: any attempt to copy it is a worker that ran."""

    def __init__(self, sandbox: Path, cases: list, changed) -> None:
        self.pristine = sandbox / "no-such-pristine-tree"
        self.control = "validator control output\n"
        self.cases = cases
        self.sandbox = sandbox
        self.changed = changed
        self.extra: list[str] = []


class EmptyScopedSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="saipen-t1287-")
        self.addCleanup(tmp.cleanup)
        self.sandbox = Path(tmp.name)

    def test_the_measured_change_selects_no_control(self):
        self.assertEqual(A.select_cases(A.CASES, CHANGED), [])

    def test_zero_selected_controls_run_no_worker_and_pass(self):
        context = _Context(self.sandbox, [], CHANGED)
        self.assertIsNone(A.mutation_sweep_probe(context))
        self.assertEqual(list(self.sandbox.iterdir()), [])

    def test_zero_selected_controls_say_so_plainly(self):
        context = _Context(self.sandbox, [], CHANGED)
        A.mutation_sweep_probe(context)
        report = " ".join(context.extra)
        self.assertIn("no control declares any changed path as its target", report)
        self.assertNotIn("each went red", report)
        self.assertNotIn(A.FULL_SWEEP_PHRASE, report)
        self.assertIn(str(A.FULL_CASE_COUNT), report)
        for line in context.extra:
            self.assertTrue(line.lstrip().startswith("SCOPED:"), line)

    def test_a_real_worker_failure_is_still_a_gate_failure(self):
        case = A.CASES[0]
        label, rel, mutation, _expected, gate = A.case_parts(case)
        never_printed = (label, rel, mutation, "an expectation no control prints", gate)
        context = _Context(self.sandbox, [never_printed], CHANGED)
        verdict = A.mutation_sweep_probe(context)
        self.assertIsNotNone(verdict)
        self.assertIn("parallel mutation worker", verdict)

    def test_the_full_sweep_sentence_is_untouched(self):
        line = A.sweep_report(None, 229, 229, 0, 0)[0]
        self.assertTrue(line.startswith("PASS: 229 of 229 "))


if __name__ == "__main__":
    unittest.main()
