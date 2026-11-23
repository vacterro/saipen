"""T-1752: a finished audit layer is closed by the protocol, not by hand.

`intake.closable_receipts` skipped every receipt an audit inbox layer is bound
to and said `saipen audit ingest` closes it, but ingest only consumes a layer
whose receipt is ALREADY closed, and the router moved on to the next NEW
generation. Measured after T-1746 reached DONE with all thirteen clauses of
SRC-240 VERIFIED: the layer audit/SAIPEN_20261013_1409.md stayed ACTIVE through
an ingest until `saipen source close SRC-240` was typed by hand.

The skip guarded one real hazard: once the receipt closes, a CLEAN scrub may
prune the Work row, and the delete gate read DONE from that row alone. A
receipt closes only after `close_receipt` proved every linked Work DONE under
the writer lock, and the scrub prunes a row only with its closing event in the
LOG, so a CLOSED receipt whose Work row is gone is that proof, not a hole.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import audit_inbox, intake  # noqa: E402
from saipen_engine.operations import apply_claim, checkpoint  # noqa: E402
from test_dependency_resume_liveness import AGENT, ResumeFixture  # noqa: E402

ENGINE = TOOLS / "saipen.py"
LAYER = "audit/1.md"
BODY = "# audit\n\nfindings: one clause the Work answers\n"


class AuditLayerClosureTests(ResumeFixture):
    def cli(self, project: Path, *args: str) -> dict:
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
        env.update(PWD=str(project), SAIPEN_CAPABILITY="no-publish", PYTHONUTF8="1")
        proc = subprocess.run(
            [sys.executable, "-B", str(ENGINE), "--project-root", str(project),
             "--agent", AGENT, "--json", *args],
            stdin=subprocess.DEVNULL, capture_output=True, env=env, cwd=str(project),
            timeout=300, check=False,
        )
        return json.loads(proc.stdout.decode("utf-8"))

    def bound_work(self, project: Path) -> tuple[str, str]:
        """A captured layer, its Work, one clause settled: ready to finish."""
        work = self.add(project, "execute the audit layer")
        path = project / LAYER
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(BODY, encoding="utf-8")
        captured = audit_inbox.capture_layer(project, LAYER, work=work)
        self.assertTrue(captured.get("ok"), captured)
        receipt = captured["receipt"]
        bound = audit_inbox.bind_layer(
            project, LAYER, layer=1, generation=1,
            file_sha256=captured["file_sha256"], size_bytes=len(BODY.encode("utf-8")),
            receipt_id=receipt, receipt_sha256=captured["file_sha256"], binding="exact",
            linked_work=work, state=audit_inbox.ACTIVE,
        )
        self.assertIsNotNone(bound)
        self.assertTrue(intake.add_requirement(project, receipt, rid="R1", text="the clause")["ok"])
        self.assertTrue(
            intake.set_disposition(
                project, receipt, f"{receipt}:R1", "VERIFIED", work=work,
                evidence="E-001", verification="focused test",
            )["ok"]
        )
        self.assertTrue(apply_claim(project, work, AGENT, explicit=True).ok)
        self.to_ship(project, work)
        self.assertTrue(checkpoint(project, AGENT, "RUN", work, "acceptance -> PASS").ok)
        return work, receipt

    def layer_state(self, project: Path) -> str:
        layers = audit_inbox.classify(project)["layers"]
        return next(item["state"] for item in layers if item["rel"] == LAYER)

    def test_finishing_the_work_closes_its_audit_receipt(self):
        project = self.make_project()
        work, receipt = self.bound_work(project)
        answer = self.cli(project, "ticket", "done", work, "--closure-mode", "own_patch")
        self.assertTrue(answer.get("ok"), answer)
        self.assertIn(receipt, (answer.get("source_closed") or {}).get("closed") or [], answer)
        self.assertEqual(intake.status(project, receipt)["status"], intake.CLOSED_STATUS)
        self.assertEqual(self.layer_state(project), audit_inbox.CLOSED_PENDING_DELETE)

    def test_the_next_ingest_consumes_it_even_after_the_row_was_pruned(self):
        project = self.make_project()
        work, receipt = self.bound_work(project)
        self.assertTrue(self.cli(project, "ticket", "done", work, "--closure-mode", "own_patch")["ok"])
        board = project / ".saipen" / "BOARD.md"
        board.write_text(
            "".join(
                line for line in board.read_text(encoding="utf-8").splitlines(keepends=True)
                if f" {work} " not in line
            ),
            encoding="utf-8",
        )
        gate = audit_inbox.delete_gate(project, LAYER)
        self.assertTrue(gate.get("ok"), gate)
        consumed = self.cli(project, "audit", "ingest")
        self.assertEqual(consumed.get("code"), "AUDIT_CONSUMED", consumed)
        self.assertFalse((project / LAYER).exists())

    def test_a_reopened_work_still_keeps_its_layer(self):
        """A row that is present and not DONE still refuses, CLOSED receipt or not."""
        project = self.make_project()
        work, _receipt = self.bound_work(project)
        self.assertTrue(self.cli(project, "ticket", "done", work, "--closure-mode", "own_patch")["ok"])
        board = project / ".saipen" / "BOARD.md"
        text = board.read_text(encoding="utf-8")
        row = next(line for line in text.splitlines() if f" {work} " in line)
        board.write_text(
            text.replace(row + "\n", "").replace("## TODO\n", "## TODO\n" + row.replace("[x]", "[ ]", 1) + "\n"),
            encoding="utf-8",
        )
        gate = audit_inbox.delete_gate(project, LAYER)
        self.assertFalse(gate.get("ok"), gate)
        self.assertTrue((project / LAYER).is_file())

    def test_an_open_audit_receipt_stays_open(self):
        project = self.make_project()
        work, receipt = self.bound_work(project)
        self.assertEqual(intake.closable_receipts(project), [])
        self.assertEqual(intake.status(project, receipt)["status"], intake.ACTIVE_STATUS)
        self.assertEqual(self.layer_state(project), audit_inbox.ACTIVE)


if __name__ == "__main__":
    unittest.main()
