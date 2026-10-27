"""T-1446 field soak defect: a repeated request must never mint duplicate Work.

Measured 2026-09-22 (.saipen/evidence/T-1446-field-soak-20260922): one minute
after a cold successor finished T-2, it ran `saipen start` with T-2's exact
text. START captured SRC-001 and projected T-4 -- a second Work for a request
the project had already completed -- because it deduplicated identical
receipt BODIES only, never an existing BOARD Work carrying the same request.

Controls:

  1. the same request over DONE Work refuses TICKET_ALREADY_DONE, projects no
     Work, and leaves its receipt CONSUMED (bound, request clause VERIFIED by
     that Work) so it never re-queues and DONE Work has no unresolved source;
  2. the same request over OPEN Work projects no Work and binds to it;
  3. whitespace/case differences are the same request;
  4. a genuinely different request still projects new Work.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from test_dependency_resume_liveness import AGENT, ResumeFixture  # noqa: E402

from saipen_engine import intake  # noqa: E402
from saipen_engine.entry import start_work  # noqa: E402
from saipen_engine.operations import apply_claim, finish_ticket  # noqa: E402
from saipen_engine.router import queued_source_projection  # noqa: E402

REQUEST = (
    "create src/mathx.py defining add(a, b) that returns a + b, and "
    "tests/test_mathx.py with a unittest asserting add(2, 3) == 5"
)


class DuplicateIngressTests(ResumeFixture):
    def _done(self, project: Path, request: str = REQUEST) -> str:
        work = self.add(project, request)
        self.assertTrue(apply_claim(project, work, AGENT, explicit=True).ok)
        self.to_ship(project, work)
        finished = finish_ticket(project, work, AGENT)
        self.assertTrue(finished.ok, finished.to_dict())
        self.assertEqual(self.tickets(project)[work]["section"], "## DONE")
        return work

    def test_a_repeat_of_done_work_mints_nothing_and_is_consumed(self):
        project = self.make_project()
        work = self._done(project)
        before = set(self.tickets(project))
        with mock.patch(
            "saipen_engine.debt.current_tree_reverify",
            return_value={"receipt_id": "RV-CURRENT"},
        ):
            started = start_work(project, AGENT, actor_source="explicit", text=REQUEST)
        self.assertEqual(started.get("code"), "TICKET_ALREADY_DONE", started)
        self.assertEqual(started.get("ticket"), work, started)
        self.assertEqual(set(self.tickets(project)), before, "no duplicate Work")
        receipt = started["receipt"]
        meta = intake._read_meta(project, receipt)
        self.assertIn(work, intake.linked_works(meta))
        self.assertTrue(intake.coverage_complete(project, receipt))
        self.assertIsNone(queued_source_projection(project), "consumed ingress never re-queues")

    def test_done_description_without_current_proof_remains_actionable(self):
        project = self.make_project()
        old = self._done(project)
        started = start_work(project, AGENT, actor_source="explicit", text=REQUEST)
        self.assertEqual(started.get("code"), "STARTED", started)
        self.assertNotEqual(started.get("ticket"), old)
        receipt = started["receipt"]
        self.assertTrue(intake.ensure_request_clause(project, receipt)["ok"])
        self.assertEqual(
            intake.coverage_summary(project, receipt)["unresolved"], [f"{receipt}:R001"]
        )

    def test_a_repeat_of_open_work_binds_to_it(self):
        project = self.make_project()
        work = self.add(project, REQUEST)
        before = set(self.tickets(project))
        started = start_work(
            project, AGENT, actor_source="explicit", text="  " + REQUEST.upper() + "  "
        )
        self.assertEqual(set(self.tickets(project)), before, started)
        self.assertEqual(started.get("ticket"), work, started)
        self.assertIn(work, intake.linked_works(intake._read_meta(project, started["receipt"])))

    def test_a_different_request_still_projects_new_work(self):
        project = self.make_project()
        self._done(project)
        before = set(self.tickets(project))
        started = start_work(
            project, AGENT, actor_source="explicit", text="create src/mathx.py with sub(a, b)"
        )
        self.assertEqual(started.get("code"), "STARTED", started)
        self.assertEqual(len(set(self.tickets(project)) - before), 1, started)

    def test_matching_done_description_does_not_settle_new_compound_clauses(self):
        project = self.make_project()
        request = (
            "Deliver the audit: 1. Publish the canonical audit artifact; "
            "2. Bind the producer operation identity"
        )
        old = self._done(project, request)
        started = start_work(project, AGENT, actor_source="explicit", text=request)
        self.assertEqual(started.get("code"), "STARTED", started)
        self.assertNotEqual(started.get("ticket"), old)
        summary = intake.coverage_summary(project, started["receipt"])
        self.assertEqual(
            len(summary["unresolved"]), 2,
            (summary, intake.read_body(project, started["receipt"])),
        )
        ledger = intake._read_coverage(project, started["receipt"])
        self.assertTrue(
            all(item["disposition"] == "UNKNOWN" for item in ledger["requirements"].values()),
            ledger,
        )
        self.assertIn(
            started["ticket"], intake.linked_works(intake._read_meta(project, started["receipt"]))
        )


if __name__ == "__main__":
    unittest.main()
