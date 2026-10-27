"""T-1659: "completed" in the operator checkpoint means what THIS run completed.

The machine digest counted every ticket finished since the last stop
operation. A project that is never stopped never resets that window: measured
on 2026-10-07, one project answered `133 completed` after a run that finished
one ticket (it has no stop operation in its whole history), and this
repository answered 22. The count is the first thing the checkpoint says about
the outcome, so it has to be about the run the operator is looking at.

A run starts over at a stop and at every operator ingress: a user request, a
goal. The stop REASON of the digest keeps reading the last stop alone.
"""

from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import test_t1614_future_gate as H  # noqa: E402
from saipen_engine import response_surface as RS  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

FINISHED = "ticket finished via SAIOPS -- completion (from SHIP)"


def setUpModule() -> None:
    isolate_host_session()


class _Log(unittest.TestCase):
    def setUp(self) -> None:
        base, self.project = H._project()
        self.addCleanup(shutil.rmtree, base, True)
        self.lines: list[str] = []

    def event(self, text: str, *, ticket: str = "", op: str = "", taxonomy: str = "DEC") -> int:
        number = len(self.lines) + 1
        parts = [f"- 01.09.26 00:{number % 60:02d} [E-{number:03d}]"]
        if number > 1:
            parts.append(f"[parent: E-{number - 1:03d}]")
        if ticket:
            parts.append(f"[{ticket}]")
        parts.append("[agent: tester]")
        if op:
            parts.append(f"[op: {op}-{number:032x}]")
        self.lines.append(" ".join(parts) + f" {taxonomy}: {text}")
        return number

    def finish(self, ticket: str) -> int:
        return self.event(FINISHED, ticket=ticket, op="finish")

    def facts(self, *, last_event: int | None = None) -> dict:
        (self.project / ".saipen" / "LOG.md").write_text(
            "\n".join(self.lines) + "\n", encoding="utf-8"
        )
        state = self.project / ".saipen" / "STATE.md"
        number = len(self.lines) if last_event is None else last_event
        state.write_text(
            "\n".join(
                f"last_event: {number}" if line.startswith("last_event:") else line
                for line in state.read_text(encoding="utf-8").splitlines()
            )
            + "\n",
            encoding="utf-8",
        )
        return RS.canonical_facts(self.project)


class RunWindowTests(_Log):
    def test_without_a_boundary_every_finish_counts(self):
        self.finish("T-1")
        self.finish("T-2")
        self.assertEqual(self.facts()["completed"], ["T-1", "T-2"])

    def test_a_stop_starts_the_run_over(self):
        self.finish("T-1")
        self.event("stopped via SAIOPS checkpoint", op="stop")
        self.finish("T-2")
        self.assertEqual(self.facts()["completed"], ["T-2"])

    def test_an_operator_request_starts_the_run_over(self):
        self.finish("T-1")
        self.event("user request SRC-002 projected as T-2", ticket="T-2", op="userreq")
        self.finish("T-2")
        self.assertEqual(self.facts()["completed"], ["T-2"])

    def test_a_goal_starts_the_run_over(self):
        for op in ("goal", "goal-entry"):
            with self.subTest(op):
                self.lines = []
                self.finish("T-1")
                self.event("goal entered", op=op)
                self.finish("T-2")
                self.assertEqual(self.facts()["completed"], ["T-2"])

    def test_a_machine_operation_is_not_a_boundary(self):
        self.finish("T-1")
        for op in ("claim", "checkpoint", "transition", "scope", "reconcile", "ticket"):
            self.event(f"{op} recorded", ticket="T-2", op=op, taxonomy="RUN")
        self.finish("T-2")
        self.assertEqual(self.facts()["completed"], ["T-1", "T-2"])

    def test_the_pointer_follows_the_same_window(self):
        self.event("verify -> PASS [target: T-1] conf: high", ticket="T-1", op="checkpoint",
                   taxonomy="RUN")
        self.finish("T-1")
        self.event("user request SRC-002 projected as T-2", ticket="T-2", op="userreq")
        verified = self.event("verify -> PASS [target: T-2] conf: high", ticket="T-2",
                              op="checkpoint", taxonomy="RUN")
        finished = self.finish("T-2")
        refs = self.facts()["detail_refs"]
        self.assertEqual(refs, [f"E-{verified:03d}", f"E-{finished:03d}"])

    def test_the_stop_reason_still_reads_the_last_stop_alone(self):
        self.finish("T-1")
        stopped = self.event("stopped via SAIOPS checkpoint", op="stop")
        self.assertEqual(self.facts(last_event=stopped)["response_reason"], "stop")
        self.event("user request SRC-002 projected as T-2", ticket="T-2", op="userreq")
        self.assertEqual(self.facts()["response_reason"], "final", "an ingress is not a stop")

    def test_the_checkpoint_names_the_one_ticket_of_this_run(self):
        """The measured shape: a long history that was never stopped, one
        operator request, one ticket finished after it."""
        for number in range(1, 41):
            self.finish(f"T-{number}")
        self.event("user request SRC-009 projected as T-41", ticket="T-41", op="userreq")
        self.finish("T-41")
        facts = self.facts()
        self.assertEqual(facts["completed"], ["T-41"])
        text = RS.digest_from_facts({**facts, "phase": "DONE"}, reason="status", language="et")
        result = RS.parse_surface(text)[0]["RESULT"]
        self.assertIn("T-41 lõpetatud", result)
        self.assertNotIn("41 lõpetatud;", result.replace("T-41 lõpetatud", ""))


if __name__ == "__main__":
    unittest.main()
