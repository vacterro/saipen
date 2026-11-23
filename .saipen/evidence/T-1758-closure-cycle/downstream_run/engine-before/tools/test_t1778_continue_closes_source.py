"""T-1778: a Work finished by `continue` closes its fully covered Source.

`ticket done` closes a receipt the moment its last linked Work reaches DONE
(T-1666), but `continue`'s finish-at-ship step called `finish_ticket` directly
and skipped that closure: on 2026-10-14 T-1776 finished through continue
(E-15388) and SRC-249 stayed ACTIVE with its only clause VERIFIED until a hand
`source close` (SRC-250 section 6: completion that needs a second
administrative pass). The two finishing paths now close alike.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import intake  # noqa: E402
from test_t1666_receipt_close import _Receipts  # noqa: E402


class ContinueClosesTheReceipt(_Receipts):
    def _finish_step(self, answer: dict) -> dict:
        steps = [
            s for s in answer.get("continue_trace") or [] if s.get("operation") == "ticket_done"
        ]
        self.assertEqual(len(steps), 1, answer)
        self.assertTrue(steps[0].get("ok"), answer)
        return steps[0]

    def test_continue_finishing_the_last_work_closes_its_receipt(self):
        project = self.make_project()
        work = self.add(project, "answer the request")
        receipt = self.receipt(project, work)
        self.ready_to_finish(project, work)
        step = self._finish_step(self.cli(project, "continue"))
        self.assertEqual(step.get("source_closed", {}).get("closed"), [receipt], step)
        self.assertEqual(self.status(project, receipt), "CLOSED")

    def test_continue_leaves_a_receipt_with_open_work_active(self):
        project = self.make_project()
        first, second = self.add(project, "first part"), self.add(project, "second part")
        receipt = self.receipt(project, first)
        self.assertTrue(intake.link_work_to(project, receipt, second).get("ok"))
        self.ready_to_finish(project, first)
        step = self._finish_step(self.cli(project, "continue"))
        self.assertNotIn("source_closed", step)
        self.assertEqual(self.status(project, receipt), "ACTIVE")


if __name__ == "__main__":
    unittest.main()
