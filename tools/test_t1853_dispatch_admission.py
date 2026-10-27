"""SRC-274:R003 -- a fresh handoff is admitted, queued or refused. Never dropped.

F-02 measured the defect in the AUDAPACK session (2026-10-16 01:27 UTC). The
operator's message named a different objective, its executor root and an
end-to-end repair. The session ran `continue`, was handed `PHASE REVIEW T-1745`,
verified and closed T-1745, and then reported the newly requested mechanism as
already present. Nothing refused that request and nothing admitted it: routing
read the queued operator Source only under `if not active`, so a fresh receipt
was invisible for as long as a ticket held the seat.

These controls hold the repaired contract:

  1. a receipt with a FREE seat is ADMITTED and its action is the canonical
     ingress;
  2. a receipt behind a live ticket is QUEUED with that holder named -- the
     deferral is a stated decision, not an absence;
  3. the queued receipt's `holder` is never a Work membership of the receipt
     itself, which is what makes a DONE for the holder unable to answer it;
  4. an unreadable receipt is REFUSED, never read as "nothing waiting";
  5. a project with no fresh receipt carries NO verdict, so the absence of the
     field means exactly one thing.

Control 3 is the negative half of the clause and the F-02 failure mode: closing
T-1745 cannot close the new objective, and the record must show that.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from test_dependency_resume_liveness import AGENT, ResumeFixture  # noqa: E402

from saipen_engine import dispatch_admission, intake  # noqa: E402
from saipen_engine.board import parse_board  # noqa: E402
from saipen_engine.router import queued_source_projection  # noqa: E402
from saipen_engine.state import parse_state  # noqa: E402


def _request(text: str) -> str:
    return (
        "# User request\n\n"
        "priority: P1\n"
        "verify: the requested change is present\n\n"
        "## Request\n\n"
        f"{text}\n"
    )


class FreshHandoffTests(ResumeFixture):
    def _capture(self, project: Path, text: str) -> str:
        captured = intake.capture(project, _request(text), source_kind="user_instruction")
        self.assertTrue(captured.get("ok"), captured)
        return captured["receipt"]

    def _verdict(self, project: Path) -> dict | None:
        board = parse_board((project / ".saipen" / "BOARD.md").read_text(encoding="utf-8"))
        return dispatch_admission.decision(
            project,
            state=parse_state((project / ".saipen" / "STATE.md").read_text(encoding="utf-8")),
            board=board,
            queued_source=queued_source_projection(project),
        )

    def test_a_receipt_with_a_free_seat_is_admitted(self) -> None:
        project = self.make_project()
        receipt = self._capture(project, "ship the new objective end to end")
        verdict = self._verdict(project)
        self.assertIsNotNone(verdict, "a fresh receipt must never read as no input")
        self.assertEqual(verdict["verdict"], dispatch_admission.ADMITTED, verdict)
        self.assertEqual(verdict["reason"], dispatch_admission.ADMITTED_FREE_SEAT, verdict)
        self.assertEqual(verdict["receipt"], receipt)
        self.assertIsNone(verdict["holder"])
        self.assertIn(f"--receipt {receipt}", verdict["action"])
        self.assertIsNone(dispatch_admission.problem(verdict), verdict)

    def test_a_receipt_behind_a_live_ticket_is_queued_and_names_the_holder(self) -> None:
        """The measured F-02 shape: T-1745 in flight, a new objective arrives."""
        project = self.make_project()
        holder = self.add(project, "the ticket already in flight")
        self.assertTrue(
            __import__(
                "saipen_engine.operations", fromlist=["apply_claim"]
            ).apply_claim(project, holder, AGENT, explicit=True).ok
        )
        receipt = self._capture(project, "repair the archived cycle end to end")
        verdict = self._verdict(project)
        self.assertEqual(verdict["verdict"], dispatch_admission.QUEUED, verdict)
        self.assertEqual(verdict["receipt"], receipt)
        self.assertEqual(verdict["queued_behind"], holder)
        self.assertEqual(verdict["holder"], holder)
        self.assertEqual(verdict["reason"], dispatch_admission.QUEUED_BEHIND_LIVE_WORK, verdict)
        self.assertIn(holder, verdict["detail"])
        self.assertIn(receipt, verdict["detail"])
        self.assertIsNone(dispatch_admission.problem(verdict), verdict)

    def test_the_holder_is_never_work_that_answers_the_receipt(self) -> None:
        """Control 3: closing the holder must not close the new objective."""
        project = self.make_project()
        holder = self.add(project, "the ticket already in flight")
        self.assertTrue(
            __import__(
                "saipen_engine.operations", fromlist=["apply_claim"]
            ).apply_claim(project, holder, AGENT, explicit=True).ok
        )
        receipt = self._capture(project, "a different objective entirely")
        verdict = self._verdict(project)
        self.assertFalse(verdict["holder_is_linked_work"], verdict)
        self.assertFalse(
            intake.is_linked_to(intake._read_meta(project, receipt) or {}, holder),
            "the receipt must remain unprojected: no Work membership names it",
        )
        # The queue is still there to be started, which is what makes a DONE
        # for `holder` unable to answer it.
        queued = queued_source_projection(project)
        self.assertEqual(queued and queued.get("receipt"), receipt, queued)

    def test_an_unreadable_receipt_is_refused_not_dropped(self) -> None:
        project = self.make_project()
        verdict = dispatch_admission.decision(
            project,
            state=parse_state((project / ".saipen" / "STATE.md").read_text(encoding="utf-8")),
            board=parse_board((project / ".saipen" / "BOARD.md").read_text(encoding="utf-8")),
            queued_source={
                "invalid": True,
                "action": "saipen source status",
                "detail": "the intake index is unreadable",
            },
        )
        self.assertEqual(verdict["verdict"], dispatch_admission.REFUSED, verdict)
        self.assertEqual(verdict["reason"], dispatch_admission.REFUSED_UNREADABLE, verdict)
        self.assertIn("unreadable", verdict["detail"])
        self.assertIsNone(dispatch_admission.problem(verdict), verdict)

    def test_a_project_with_no_fresh_receipt_carries_no_verdict(self) -> None:
        project = self.make_project()
        self.assertIsNone(self._verdict(project))
        self.assertEqual(
            dispatch_admission.summary(None), "no fresh handoff"
        )

    def test_a_foreign_shape_is_not_silence(self) -> None:
        for shape in ({}, {"schema": 1}, {"schema": 1, "family": "dispatch-admission"},
                      {"schema": 1, "family": "dispatch-admission", "verdict": "MAYBE"},
                      {"schema": 1, "family": "dispatch-admission", "verdict": "QUEUED"},
                      {"schema": 1, "family": "dispatch-admission",
                       "verdict": "ADMITTED"}, "ADMITTED", 3, []):
            self.assertIsNotNone(dispatch_admission.problem(shape), shape)

    def test_the_verdict_is_closed_and_machine_readable(self) -> None:
        project = self.make_project()
        receipt = self._capture(project, "ship the new objective end to end")
        verdict = self._verdict(project)
        self.assertEqual(verdict["schema"], dispatch_admission.SCHEMA)
        self.assertEqual(verdict["family"], dispatch_admission.FAMILY)
        self.assertIn(verdict["verdict"], dispatch_admission.VERDICTS)
        self.assertEqual(verdict["receipt"], receipt)
        self.assertEqual(
            set(verdict) - {"action"},
            {
                "schema", "family", "verdict", "reason", "detail",
                "receipt", "holder", "holder_is_linked_work",
            },
            "every key a consumer may read is declared, and no prose is load-bearing",
        )


class TheDecisionIsShownTests(ResumeFixture):
    """The clause says the decision is SHOWN, so the answer must carry it.

    A verdict that only a unit test can reach is not an admission decision: the
    operator reads `continue`. These controls run the real CLI path and read
    the field out of its JSON.
    """

    def _continue(self, project: Path) -> dict:
        import json
        import os
        import subprocess
        import sys as _sys

        env = dict(os.environ)
        env["SAIPEN_PROJECT_ROOT"] = str(project)
        env["SAIPEN_SKILL_ROOT"] = str(TOOLS.parent)
        proc = subprocess.run(
            [_sys.executable, "-B", str(TOOLS / "saipen.py"), "continue", "--json",
             "--project-root", str(project)],
            capture_output=True, text=True, env=env, timeout=240,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr[-800:])
        return json.loads(proc.stdout)

    def _receipt(self, project: Path, text: str) -> str:
        captured = intake.capture(
            project,
            _request(text),
            source_kind="user_instruction",
        )
        self.assertTrue(captured.get("ok"), captured)
        return captured["receipt"]

    def test_a_free_seat_route_shows_an_admitted_handoff(self) -> None:
        project = self.make_project()
        receipt = self._receipt(project, "fresh objective with the seat free")
        answer = self._continue(project)
        self.assertEqual(answer.get("action"), f"saipen start --receipt {receipt}", answer)
        shown = answer.get("dispatch_admission") or {}
        self.assertEqual(shown.get("verdict"), "ADMITTED", answer)
        self.assertEqual(shown.get("receipt"), receipt, answer)

    def test_a_live_ticket_route_shows_the_deferred_handoff(self) -> None:
        """E-18734's F-02 shape, end to end: the old route closes nothing about it."""
        from saipen_engine.operations import apply_claim

        project = self.make_project()
        holder = self.add(project, "the ticket already in flight")
        self.assertTrue(apply_claim(project, holder, AGENT, explicit=True).ok)
        receipt = self._receipt(project, "SAIHANDOFF: a different objective, end to end")
        answer = self._continue(project)
        self.assertEqual(answer.get("action"), f"PHASE SCOUT {holder}",
                         "a live ticket still owns the turn", )
        shown = answer.get("dispatch_admission") or {}
        self.assertEqual(shown.get("verdict"), "QUEUED", answer)
        self.assertEqual(shown.get("queued_behind"), holder, answer)
        self.assertEqual(shown.get("receipt"), receipt, answer)

    def test_no_fresh_receipt_means_no_field_at_all(self) -> None:
        project = self.make_project()
        self.add(project, "ordinary work only")
        answer = self._continue(project)
        self.assertNotIn("dispatch_admission", answer, answer)


if __name__ == "__main__":
    unittest.main()