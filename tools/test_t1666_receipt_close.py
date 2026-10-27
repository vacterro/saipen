"""T-1666: a finished source receipt closes when its last gate is met.

`close_receipt` had one caller, `saipen source close`, and nothing said when to
run it: 97 of this project's 148 ACTIVE receipts had complete coverage and
every linked Work DONE, each re-proved on every validation and each keeping
its Work's closed row on the BOARD. Now:

* the command that meets the last gate closes the receipt -- `ticket done`
  when the last linked Work reaches DONE (its finish already demanded
  complete coverage), `source disp` when the last clause of a receipt bound
  to Work that is already DONE reaches its disposition;
* a receipt whose Work is still open, or that never produced Work, stays
  ACTIVE. Audit-bound receipts close through the same owner; the pending
  transport keeps its Work row until journaled ingestion consumes it (T-1752);
* entering CLEAN closes whatever an older engine left open, before the
  BOARD scrub, so the same entry can prune the rows they held.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import audit_inbox, intake  # noqa: E402
from saipen_engine.operations import apply_claim, checkpoint  # noqa: E402
from test_dependency_resume_liveness import AGENT, ResumeFixture  # noqa: E402

ENGINE = TOOLS / "saipen.py"
BODY = (
    "# User request\n\n"
    "priority: P1\n"
    "verify: the request is answered\n\n"
    "## Request\n\n"
    "one request answered by one piece of work\n"
)


class _Receipts(ResumeFixture):
    def cli(self, project: Path, *args: str) -> dict:
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
        env.update(PWD=str(project), SAIPEN_CAPABILITY="no-publish", PYTHONUTF8="1")
        proc = subprocess.run(
            [
                sys.executable,
                "-B",
                str(ENGINE),
                "--project-root",
                str(project),
                "--agent",
                AGENT,
                "--json",
                *args,
            ],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            env=env,
            cwd=str(project),
            timeout=300,
            check=False,
        )
        return json.loads(proc.stdout.decode("utf-8"))

    def receipt(self, project: Path, work: str, *, settle: bool = True) -> str:
        captured = intake.capture(project, BODY, source_kind="user_instruction", work=work)
        self.assertTrue(captured.get("ok"), captured)
        receipt = captured["receipt"]
        added = intake.add_requirement(project, receipt, rid="R1", text="the request clause")
        self.assertTrue(added.get("ok"), added)
        if settle:
            self.settle(project, receipt, work)
        return receipt

    def settle(self, project: Path, receipt: str, work: str) -> None:
        disposed = intake.set_disposition(
            project,
            receipt,
            f"{receipt}:R1",
            "VERIFIED",
            work=work,
            evidence="E-001",
            verification="focused test",
        )
        self.assertTrue(disposed.get("ok"), disposed)

    def status(self, project: Path, receipt: str) -> str:
        return str((intake._read_meta(project, receipt) or {}).get("status") or "CLOSED")

    def ready_to_finish(self, project: Path, work: str) -> None:
        self.assertTrue(apply_claim(project, work, AGENT, explicit=True).ok)
        self.to_ship(project, work)
        self.assertTrue(checkpoint(project, AGENT, "RUN", work, "acceptance -> PASS").ok)

    def finish(self, project: Path, work: str) -> dict:
        answer = self.cli(project, "ticket", "done", work, "--closure-mode", "own_patch")
        self.assertTrue(answer.get("ok"), answer)
        return answer

    def finished_work(self, project: Path) -> str:
        work = self.add(project, "answer the request")
        self.ready_to_finish(project, work)
        self.assertNotIn("source_closed", self.finish(project, work))
        return work


class LastGateTests(_Receipts):
    def test_the_last_work_reaching_done_closes_its_receipt(self):
        project = self.make_project()
        work = self.add(project, "answer the request")
        receipt = self.receipt(project, work)
        self.ready_to_finish(project, work)
        self.assertEqual(self.status(project, receipt), "ACTIVE")

        answer = self.finish(project, work)
        self.assertEqual(answer.get("source_closed", {}).get("closed"), [receipt], answer)
        self.assertEqual(self.status(project, receipt), "CLOSED")

    def test_the_last_clause_reaching_its_disposition_closes_its_receipt(self):
        project = self.make_project()
        work = self.finished_work(project)
        receipt = self.receipt(project, work, settle=False)
        self.assertEqual(self.status(project, receipt), "ACTIVE")

        answer = self.cli(
            project,
            "source",
            "disp",
            receipt,
            f"{receipt}:R1",
            "VERIFIED",
            "--work",
            work,
            "--evidence",
            "E-001",
            "--verification",
            "focused test",
        )
        self.assertTrue(answer.get("ok"), answer)
        self.assertEqual(answer.get("source_closed", {}).get("closed"), [receipt], answer)
        self.assertEqual(self.status(project, receipt), "CLOSED")


class StillOpenTests(_Receipts):
    def test_a_receipt_whose_work_is_still_open_stays_active(self):
        project = self.make_project()
        first, second = self.add(project, "first part"), self.add(project, "second part")
        receipt = self.receipt(project, first)
        self.assertTrue(intake.link_work_to(project, receipt, second).get("ok"))
        self.ready_to_finish(project, first)
        self.assertNotIn("source_closed", self.finish(project, first))
        self.assertEqual(self.status(project, receipt), "ACTIVE")
        self.assertEqual(intake.closable_receipts(project), [])

    def test_audit_state_cannot_hide_a_fully_covered_done_source(self):
        project = self.make_project()
        work = self.finished_work(project)
        receipt = self.receipt(project, work)
        self.assertEqual(intake.closable_receipts(project), [receipt])
        layer = {"layer": 1, "rel": "audit/1.md", "receipt_id": receipt, "state": "ACTIVE"}
        with mock.patch.object(
            audit_inbox, "classify", return_value={"layers": [layer], "orphans": []}
        ):
            self.assertEqual(intake.closable_receipts(project), [receipt])
        with mock.patch.object(audit_inbox, "classify", return_value={"ok": False}):
            closed = intake.close_finished(project)
        self.assertEqual(closed.get("closed"), [receipt], closed)
        self.assertEqual(self.status(project, receipt), "CLOSED")

    def test_a_receipt_that_never_produced_work_is_not_swept(self):
        project = self.make_project()
        captured = intake.capture(project, BODY, source_kind="user_instruction")
        self.assertTrue(captured.get("ok"), captured)
        self.assertEqual(intake.closable_receipts(project), [])


class CleanEntryTests(_Receipts):
    def test_entering_clean_closes_what_an_older_engine_left_open(self):
        project = self.make_project()
        work = self.finished_work(project)
        # What an engine before T-1666 left: complete, its Work DONE, and no
        # command that ever closed it.
        receipt = self.receipt(project, work)
        self.assertEqual(intake.closable_receipts(project), [receipt])

        answer = self.cli(project, "transition", "CLEAN")
        self.assertTrue(answer.get("ok"), answer)
        self.assertEqual(answer.get("source_closed", {}).get("closed"), [receipt], answer)
        self.assertEqual(self.status(project, receipt), "CLOSED")
        self.assertEqual(intake.closable_receipts(project), [])


if __name__ == "__main__":
    unittest.main()
