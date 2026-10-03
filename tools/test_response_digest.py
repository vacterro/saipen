"""Visible-surface regression oracles, recorded before changing its owner."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from saipen_engine import response_surface as RS  # noqa: E402

INCIDENTS = json.loads(
    (TOOLS.parent / "tests/fixtures/response-authority/incidents.json").read_text(encoding="utf-8")
)


class DetailIntentTests(unittest.TestCase):
    def test_typed_artifact_carrier_requires_a_whole_human_request(self):
        request = "write an implementation handoff"
        self.assertEqual(RS.artifact_for_request(request), "HANDOFF")
        self.assertEqual(RS.detail_mode_for_request(request), RS.DETAIL_MODE_NONE)
        for untrusted in (f'"{request}"', f"example: {request}", f"do not {request}"):
            self.assertIsNone(RS.artifact_for_request(untrusted))
        provenance = {"witness": "model_supplied"}
        verdict = RS.gate_final_response(
            "```text\n" + "x" * 4000 + "\n```",
            admission=None,
            admission_consulted=False,
            operational_turn=True,
            style_contract=None,
            human_request=request,
            request_authority=provenance,
        )
        self.assertFalse(verdict["ok"])

    def test_explicit_artifact_is_bounded_even_when_the_request_is_witnessed(self):
        from saipen_engine import operator_task, pending_ingress

        request = "write a specification"
        authority = operator_task.witness(
            request,
            env={operator_task.ENV_TASK_SHA256: pending_ingress.ingress_digest(request)},
        )
        klass, errors = RS.classify_final_response(
            "x" * (RS.ARTIFACT_CHAR_BUDGET + 1),
            operational_turn=False,
            human_request=request,
            request_authority=authority,
        )
        self.assertEqual(klass, RS.CLASS_CHAT_STYLE_DRIFT)
        self.assertTrue(errors)

    def test_summary_brief_and_normal_final_report_remain_compact(self):
        for request in (
            "give me a summary",
            "give me a brief",
            "give me a final report",
            "brief update",
            "what happened?",
            "where are we?",
            "status",
            "tell me the result",
            "дай сводку",
            "дай краткий отчёт",
            "что там?",
            "что сделал?",
            "где мы?",
            "статус",
            "что получилось?",
            "anna kokkuvõte",
            "lühike raport",
            "mis juhtus?",
            "kus me oleme?",
            "staatus",
            "continue",
            "keep going until done",
            "stop",
        ):
            with self.subTest(request=request):
                self.assertEqual(RS.detail_mode_for_request(request), RS.DETAIL_MODE_NONE)

    def test_explicit_depth_works_in_each_supported_ingress_language(self):
        for request in (
            "give me a detailed forensic report with all evidence",
            "produce a full technical audit",
            "write a complete implementation handoff",
            "explain everything in full detail including evidence and root cause",
            "дай подробный форензик-отчёт \u0441\u043e всеми доказательствами",
            "сделай полный технический аудит",
            "дай полный детальный хендофф",
            "дай полный подробный технический отчёт \u0441\u043e всеми доказательствами",
            "anna täielik detailne tehniline aruanne koos tõenditega",
            "tee täielik audit",
            "anna detailne täielik handoff",
        ):
            with self.subTest(request=request):
                self.assertNotEqual(RS.detail_mode_for_request(request), RS.DETAIL_MODE_NONE)

    def test_model_cannot_authorize_detail_by_claiming_an_exception(self):
        for reasoning in (
            "this is an exceptional boundary",
            "this is important",
            "the user deserves transparency",
            "the root cause needs explanation",
            "there were many changes",
            "this deserves a detailed answer",
            "I should be complete",
        ):
            with self.subTest(reasoning=reasoning):
                self.assertEqual(RS.detail_mode_for_request(reasoning), RS.DETAIL_MODE_NONE)

    def test_negations_and_quotes_do_not_authorize_depth(self):
        for request in (
            "do not give me a detailed report, just fix it",
            'The bug is that "give me a detailed report" triggers something.',
            '"give me a detailed forensic report with all evidence"',
            "не давай подробный отчёт, просто исправь",
            "ära anna detailset aruannet, paranda viga",
        ):
            with self.subTest(request=request):
                self.assertEqual(RS.detail_mode_for_request(request), RS.DETAIL_MODE_NONE)


class SurfacePressureTests(unittest.TestCase):
    def boundary(self, result="T-1598 fixed; T-1510 resumed", **kwargs):
        return RS.OperationalBoundary(
            "DONE",
            result,
            "NONE",
            "NONE",
            "NONE",
            "CURRENT_PASS | full core 4728 | red 0 | new_red 0",
            **kwargs,
        )

    def test_actual_rendered_default_fits_six_visible_lines(self):
        text = RS.render_boundary(self.boundary())
        self.assertLessEqual(len(text.splitlines()), 6, text)
        self.assertLessEqual(len(text), 900)

    def test_real_blocker_inventory_is_not_a_default_result(self):
        identifiers = [row["ticket"] for row in INCIDENTS["blocker_rows"][:54]]
        self.assertEqual(len(identifiers), 54)
        raw = "\n".join(
            f"{key}\n{value}"
            for key, value in self.boundary("Remaining blockers: " + ", ".join(identifiers))
            .fields()
            .items()
        )
        self.assertTrue(
            RS.response_errors(raw),
            "54 complete ticket identities were accepted in the default human surface",
        )

    def test_a_model_supplied_detail_mode_does_not_authorize_host_output(self):
        raw = "\n".join(
            f"{key}\n{value}"
            for key, value in self.boundary(details="Full retrospective chosen by the model.")
            .fields()
            .items()
        )
        verdict = RS.gate_final_response(
            raw,
            admission=None,
            admission_consulted=False,
            operational_turn=True,
            style_contract=None,
            detail_mode=RS.DETAIL_MODE_REPORT,
        )
        self.assertFalse(verdict["ok"], verdict)

    def test_stop_report_uses_machine_facts_not_the_model_retrospective(self):
        # The real supplied STOP excerpt names the completed ticket. The full
        # report is preserved separately when its host transcript is available.
        self.assertIn("T-1598", INCIDENTS["stop_excerpt"])
        builder = getattr(RS, "digest_from_facts", None)
        self.assertIsNotNone(builder, "there is no canonical state-to-human digest owner")
        facts = {
            "phase": "SCOUT",
            "task": "T-1510",
            "next_action": "PHASE SCOUT T-1510",
            "blocker": "none",
            "validation": "CURRENT_PASS",
            "completed": ["T-1598"],
            "blockers": INCIDENTS["blocker_rows"][:54],
            "evidence": [f"E-{n}" for n in range(100)],
            "commits": [str(n) * 40 for n in range(20)],
            "test_groups": [{"ran": 236, "red": 0} for _ in range(20)],
        }
        text = builder(facts, reason="stop")
        self.assertLessEqual(len(text.splitlines()), 6, text)
        self.assertLessEqual(len(text), 900, text)
        self.assertNotIn("E-99", text)
        self.assertNotIn("T-1450", text)


if __name__ == "__main__":
    unittest.main()
