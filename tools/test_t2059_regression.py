"""Regression controls for T-2059's GC production failures."""

from __future__ import annotations

import importlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


class T2059RegressionTests(unittest.TestCase):
    def _gc(self):
        try:
            return importlib.import_module("saipen_engine.gc")
        except ModuleNotFoundError as exc:
            self.fail(f"the production GC module is missing: {exc}")

    def test_git_guard_refusal_returns_complete_schema(self) -> None:
        gc = self._gc()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "not-a-repository"
            root.mkdir()
            cache = root / "work/__pycache__/module.pyc"
            cache.parent.mkdir(parents=True)
            cache.write_bytes(b"bytecode")

            report = gc.execute(root, "regression-agent")

        self.assertEqual(report["code"], "GIT_GUARD_FAILED")
        self.assertEqual(report["bytes_planned"], 0)
        self.assertEqual(report["bytes_reclaimed"], 0)
        self.assertFalse(report["git_guard"]["ok"])

    def test_zero_progress_budget_debt_is_durable_and_suppressed(self) -> None:
        gc = self._gc()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            root.mkdir()
            subprocess.run(["git", "-C", str(root), "init"], check=True, capture_output=True)
            log = root / ".saipen/LOG.md"
            log.parent.mkdir(parents=True)
            log.write_text(
                "".join(
                    f"- 1.1 [E-{index}] [T-{index}] [op: finish-{index}] DONE: measured\n"
                    for index in range(1, 21)
                ),
                encoding="utf-8",
            )
            state = gc.load_state(root)
            state["config"]["evidence_budget_gib"] = 1.0 / (1024**3)
            gc.save_state(root, state)
            evidence = root / ".saipen/evidence/canonical.json"
            evidence.parent.mkdir(parents=True)
            evidence.write_bytes(b'{"canonical": true}\n')

            first = gc.maintenance_checkpoint(root, "regression-agent")
            self.assertTrue(first["ok"], first)
            debt = gc.load_state(root)["maintenance"]
            self.assertEqual(debt["state"], gc.DEBT_BLOCKED_PROTECTED_BUDGET)
            self.assertTrue(gc.assess(root)["due"])

            retry = gc.maintenance_checkpoint(root, "regression-agent")
            self.assertEqual(retry["code"], "GC_RETRY_SUPPRESSED")
            self.assertTrue(retry["due"])
            self.assertEqual(
                gc.load_state(root)["maintenance"]["state"],
                gc.DEBT_BLOCKED_PROTECTED_BUDGET,
            )

    def test_finish_ticket_calls_the_post_commit_settlement_hook(self) -> None:
        from saipen_engine import operations
        from saipen_engine.result import Result

        hook = getattr(operations, "_t2049_settlement_checkpoint", None)
        self.assertTrue(callable(hook), "finish_ticket has no maintenance settlement hook")
        calls: list[tuple[str, str]] = []
        plan = SimpleNamespace(
            semantic_request={}, targets=[], preconditions={}, op_id="finish-regression"
        )

        def capture(_root, _agent, ticket, settlement_id):
            calls.append((ticket, settlement_id))

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with mock.patch.object(operations, "_plan_finish_ticket", return_value=plan), \
                 mock.patch.object(
                     operations, "apply_plan", return_value=Result(ok=True, code="FINISHED")
                 ), \
                 mock.patch.object(
                     operations, "_t2049_settlement_checkpoint", side_effect=capture
                 ):
                result = operations.finish_ticket(root, "T-2059", "regression-agent")

        self.assertTrue(result.ok, result)
        self.assertEqual(calls, [("T-2059", "finish-regression")])


if __name__ == "__main__":
    unittest.main()
