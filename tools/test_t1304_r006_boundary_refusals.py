"""SRC-026:R006 (T-1304): a source-boundary diagnostic becomes a closed refusal.

A phase transition into BUILD, REVIEW or SHIP re-reads the source receipts of
its Work (`intake.boundary_gate`). The clause: whatever that gate finds must
reach the caller as an operation refusal in the closed vocabulary, with zero
mutation, "rather than crashing" -- and it names the regression: every intake
boundary diagnostic driven through a transition.

Held here twice over. Five diagnostics are produced for real, by damaging the
receipt the way the field does (changed body, drifted linkage, missing
metadata, changed contract, unreadable index). Then every code the gate can
forward -- including one intake does not have yet -- is driven through the
same transition, and each answers with a registered code, the original
diagnostic in its text, and not one byte written.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import intake  # noqa: E402
from saipen_engine.errors import CODES  # noqa: E402
from saipen_engine.journal import scan_pending  # noqa: E402
from saipen_engine.operations import (  # noqa: E402
    _source_refusal_code,
    apply_claim,
    transition_phase,
)
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_orchestration_repair import OrchestrationFixture  # noqa: E402

#: Every code `boundary_gate` can forward: its own, `verify_integrity`'s,
#: `_contract_integrity`'s and the receipt-id refusal's.
BOUNDARY_CODES = (
    "VALIDATION_FAILED",
    "INVALID_ID",
    "INVALID",
    "SOURCE_RECEIPT_MISSING",
    "SOURCE_LINKAGE_DRIFT",
    "SOURCE_CORRUPTION",
    "SOURCE_BODY_NOT_DISTRIBUTED",
    "CONTRACT_DRIFT",
)


def setUpModule() -> None:
    isolate_host_session()


class _Boundary(OrchestrationFixture):
    def scouting(self) -> tuple[Path, str, str]:
        """A project whose active Work sits in SCOUT and owns one receipt."""
        project = self.make_project()
        ticket = self.add(project, "work with a source receipt")
        captured = intake.capture(project, "the request this work answers", work=ticket)
        self.assertTrue(captured["ok"], captured)
        self.assertTrue(apply_claim(project, ticket, "tester").ok)
        self.assertEqual(self.state(project)["phase"], "SCOUT")
        gate = intake.boundary_gate(project, ticket, "BUILD")
        self.assertTrue(gate["ok"], gate)
        self.assertEqual(gate["receipts"], [captured["receipt"]])
        return project, ticket, captured["receipt"]

    def canonical(self, project: Path) -> dict[str, bytes]:
        return {
            name: (project / ".saipen" / name).read_bytes()
            for name in ("STATE.md", "BOARD.md", "LOG.md")
        }

    def assert_closed_refusal(self, project: Path, ticket: str, before: dict, expected: str):
        result = transition_phase(project, "BUILD", "tester", ticket, "SCOUT: measured")
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(result.code, expected)
        self.assertIn(result.code, CODES)
        self.assertNotIn("unregistered_code", result.to_dict())
        self.assertIn("source reread gate at BUILD", result.message)
        self.assertEqual(self.canonical(project), before, "a refused transition wrote bytes")
        self.assertEqual(scan_pending(project), ([], []))
        self.assertEqual(self.state(project)["phase"], "SCOUT")
        return result


class RealDiagnosticTests(_Boundary):
    def test_a_changed_source_body_refuses_the_transition(self):
        project, ticket, receipt = self.scouting()
        body = next((project / ".saipen" / "intake" / "active").glob(f"{receipt}.*md"))
        body.write_bytes(body.read_bytes() + b"one more sentence the operator never wrote\n")
        before = self.canonical(project)
        self.assert_closed_refusal(project, ticket, before, "SOURCE_CORRUPTION")

    def test_a_drifted_linkage_refuses_the_transition(self):
        project, ticket, receipt = self.scouting()
        meta = project / ".saipen" / "intake" / "active" / f"{receipt}.meta.json"
        document = json.loads(meta.read_text(encoding="utf-8"))
        document["linked_work"] = "T-999"
        document.pop("linked_works", None)
        meta.write_text(json.dumps(document), encoding="utf-8")
        before = self.canonical(project)
        self.assert_closed_refusal(project, ticket, before, "SOURCE_LINKAGE_DRIFT")

    def test_missing_receipt_metadata_refuses_the_transition(self):
        project, ticket, receipt = self.scouting()
        (project / ".saipen" / "intake" / "active" / f"{receipt}.meta.json").unlink()
        before = self.canonical(project)
        self.assert_closed_refusal(project, ticket, before, "SOURCE_RECEIPT_MISSING")

    def test_an_unreadable_intake_index_refuses_the_transition(self):
        project, ticket, _ = self.scouting()
        (project / ".saipen" / "intake" / "index.json").write_text("{not json", encoding="utf-8")
        before = self.canonical(project)
        self.assert_closed_refusal(project, ticket, before, "VALIDATION_FAILED")

    def test_the_undamaged_receipt_lets_the_same_transition_through(self):
        # The control: the refusals above are the damage, not the fixture.
        project, ticket, _ = self.scouting()
        result = transition_phase(project, "BUILD", "tester", ticket, "SCOUT: measured")
        self.assertTrue(result.ok, result.to_dict())
        self.assertEqual(self.state(project)["phase"], "BUILD")


class EveryDiagnosticTests(_Boundary):
    def test_every_boundary_code_is_a_registered_refusal_with_zero_mutation(self):
        project, ticket, receipt = self.scouting()
        before = self.canonical(project)
        for code in BOUNDARY_CODES:
            with self.subTest(code=code):
                self.assertIn(code, CODES)
                answer = {"ok": False, "code": code, "receipt": receipt, "boundary": "BUILD"}
                with patch.object(intake, "boundary_gate", return_value=answer):
                    result = self.assert_closed_refusal(project, ticket, before, code)
                self.assertIn(code, result.message)
                self.assertEqual(result.to_dict().get("receipt"), receipt)

    def test_a_diagnostic_intake_does_not_have_yet_still_answers_in_the_closed_vocabulary(self):
        project, ticket, receipt = self.scouting()
        before = self.canonical(project)
        for answer in (
            {"ok": False, "code": "SOURCE_SOMETHING_NEW", "receipt": receipt},
            {"ok": False, "receipt": receipt},
            {"ok": False, "code": None},
            {"ok": False, "code": 17},
        ):
            with self.subTest(answer=answer), patch.object(
                intake, "boundary_gate", return_value=answer
            ):
                result = self.assert_closed_refusal(project, ticket, before, "SOURCE_CORRUPTION")
                # The original diagnostic is carried, not replaced.
                carried = repr(answer["code"]) if "code" in answer else "receipt"
                self.assertIn(carried, result.message)

    def test_the_adapter_keeps_what_is_registered_and_closes_what_is_not(self):
        for code in BOUNDARY_CODES:
            self.assertEqual(_source_refusal_code({"code": code}, "SOURCE_CORRUPTION"), code)
        for unknown in ("SOURCE_SOMETHING_NEW", "", None, 17, ["SOURCE_CORRUPTION"]):
            self.assertEqual(
                _source_refusal_code({"code": unknown}, "SOURCE_CORRUPTION"), "SOURCE_CORRUPTION"
            )
        self.assertEqual(_source_refusal_code({}, "SOURCE_UNRESOLVED"), "SOURCE_UNRESOLVED")

    def test_review_and_ship_ask_the_same_gate(self):
        project, ticket, receipt = self.scouting()
        asked: list[str] = []
        real = intake.boundary_gate

        def recording(root, work, boundary):
            asked.append(boundary)
            return real(root, work, boundary)

        with patch.object(intake, "boundary_gate", recording):
            self.to_ship(project, ticket)
        self.assertEqual(asked, ["BUILD", "REVIEW", "SHIP"])
        self.assertEqual(self.state(project)["phase"], "SHIP")
        del receipt
