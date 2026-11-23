"""SRC-026:R011 (T-1304): an empty scoped selection never reaches the executor.

The clause's own regression: a changed-path selection that yields zero runnable
controls exits as an ordinary scoped result "and never reach[es] executor
construction". T-1287 made the run pass and proved no worker ran; the pool was
still constructed, with `max_workers=max(1, 0)`, and left unstarted. The clamp
was the only thing between the formula's 0 and `ValueError: max_workers must be
greater than 0`. The executor is now behind the selection itself.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import audit_checks as A  # noqa: E402

CHANGED = frozenset({"tools/saipen_engine/fast_check.py"})


class _Context:
    """The fields mutation_sweep_probe reads, over a tree that does not exist."""

    def __init__(self, sandbox: Path, cases: list, changed) -> None:
        self.pristine = sandbox / "no-such-pristine-tree"
        self.control = "validator control output\n"
        self.cases = cases
        self.sandbox = sandbox
        self.changed = changed
        self.extra: list[str] = []


class EmptySelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="saipen-t1304-r011-")
        self.addCleanup(tmp.cleanup)
        self.sandbox = Path(tmp.name)

    def test_zero_runnable_controls_construct_no_executor(self):
        self.assertEqual(A.select_cases(A.CASES, CHANGED), [])
        context = _Context(self.sandbox, [], CHANGED)
        built = AssertionError("an executor was constructed for an empty selection")
        with patch.object(A, "ThreadPoolExecutor", side_effect=built):
            verdict = A.mutation_sweep_probe(context)
        self.assertIsNone(verdict)
        self.assertEqual(list(self.sandbox.iterdir()), [])
        self.assertTrue(context.extra)
        self.assertTrue(all(line.lstrip().startswith("SCOPED:") for line in context.extra))

    def test_a_selection_with_work_still_gets_a_pool_of_at_least_one(self):
        label, rel, mutation, _expected, gate, _needs = A.case_parts(A.CASES[0])
        never_printed = (label, rel, mutation, "an expectation no control prints", gate)
        context = _Context(self.sandbox, [never_printed], CHANGED)
        seen: list[int] = []
        real = A.ThreadPoolExecutor

        def recording(*args, **kwargs):
            seen.append(kwargs.get("max_workers", args[0] if args else None))
            return real(*args, **kwargs)

        with patch.object(A, "ThreadPoolExecutor", recording):
            verdict = A.mutation_sweep_probe(context)
        self.assertEqual(seen, [1])
        # The tree does not exist, so the one worker reports that -- a worker
        # failure stays a gate failure.
        self.assertIsNotNone(verdict)
        self.assertIn("parallel mutation worker", verdict)


if __name__ == "__main__":
    unittest.main()
