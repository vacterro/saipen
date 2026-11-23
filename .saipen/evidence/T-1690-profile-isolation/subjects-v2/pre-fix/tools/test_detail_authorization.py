"""Report exceptions require an explicit request and a valid closed mode."""

from pathlib import Path
import json
import subprocess
import sys
import unittest

SUBJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SUBJECT / "tools"))
from saipen_engine import response_surface as RS, chat_style as CS  # noqa: E402
from saipen_engine.operator_task import witness  # noqa: E402
from test_fixture_support import operator_request_env  # noqa: E402

CONTRACT = CS.compile_style_contract((SUBJECT / "saipen/STYLE.md").read_text(encoding="utf-8"))
LONG_CHAT = "\n".join("Kontroll tehtud." for _ in range(CONTRACT.line_budget + 4))
SURFACE = (
    "STATUS: DONE\nRESULT: Kontroll tehtud.\n"
    "NEXT EXACT ACTION: NONE\nVALIDATION: NOT_RUN\n"
    "DETAILS: Kontroll tehtud."
)
UNAUTHORIZED = (
    "Fix audit logging",
    "Repair the handoff parser",
    "Do not write a detailed report; fix the bug",
    "Don't audit the change; fix the failing test",
    "Never prepare a handoff; continue",
    "The audit log is broken",
    "Audit logging is broken; fix it",
    "The phrase write a detailed report is an example",
    'The user previously said "write a detailed report"; now continue',
    '"write a detailed report"',
    "```\nwrite a detailed report\n```",
    "> write a detailed report",
    "continue",
    "give me a summary",
    "give me a brief",
    "give me a final report",
    "this is an exceptional boundary",
    "Write a detailed report? No, fix the bug.",
    "Write a detailed report is an example in this test",
    "Please audit this project? No audit; continue.",
    "Prepare a handoff is merely a quoted command name",
    "Write a report about the change but do not add details",
    "Write a report about the change; actually just continue",
    "Write a report about the change\nNo report; fix the bug",
    "Audit this project instead of returning a report",
    "Prepare a handoff for this project is an example",
    'Write a report about "do not write a report"',
)


class DetailAuthorizationRegression(unittest.TestCase):
    def test_incidental_negated_and_quoted_requests_never_grant(self):
        for request in UNAUTHORIZED:
            with self.subTest(request=request):
                self.assertEqual(RS.detail_mode_for_request(request), RS.DETAIL_MODE_NONE)

    def test_unauthorized_requests_preserve_both_response_budgets(self):
        for request in UNAUTHORIZED:
            with self.subTest(request=request):
                mode = RS.detail_mode_for_request(request)
                klass, errors = RS.classify_final_response(
                    LONG_CHAT, operational_turn=False, style_contract=CONTRACT, detail_mode=mode
                )
                self.assertEqual(klass, RS.CLASS_CHAT_STYLE_DRIFT, errors)
                self.assertTrue(RS.response_errors(SURFACE, detail_mode=mode))

    def test_explicit_requests_still_grant_their_own_mode(self):
        for request, expected in (
            ("write a detailed report of the change", RS.DETAIL_MODE_REPORT),
            ("Please produce a full report", RS.DETAIL_MODE_REPORT),
            ("please produce a full audit", RS.DETAIL_MODE_AUDIT),
            ("give me a full technical audit", RS.DETAIL_MODE_AUDIT),
            ("prepare a complete handoff", RS.DETAIL_MODE_HANDOFF),
            ("Could you please write a detailed report of the change?", RS.DETAIL_MODE_REPORT),
            ("Please prepare a full implementation handoff.", RS.DETAIL_MODE_HANDOFF),
        ):
            with self.subTest(request=request):
                mode = RS.detail_mode_for_request(request)
                self.assertEqual(mode, expected)
                self.assertEqual(RS.response_errors(SURFACE, detail_mode=mode), [])
                klass, errors = RS.classify_final_response(
                    LONG_CHAT,
                    operational_turn=False,
                    style_contract=CONTRACT,
                    detail_mode=mode,
                    human_request=request,
                    request_authority=witness(request, env=operator_request_env(request)),
                )
                self.assertEqual((klass, errors), (RS.CLASS_ORDINARY_CHAT, []))

    def test_unknown_context_cannot_authorize_chat_or_details(self):
        for mode in (None, "", "INVALID", 0, [], {}):
            with self.subTest(mode=mode):
                self.assertTrue(RS.response_errors(SURFACE, detail_mode=mode))
                for text in (LONG_CHAT, "Kontroll tehtud."):
                    klass, errors = RS.classify_final_response(
                        text, operational_turn=False, style_contract=CONTRACT, detail_mode=mode
                    )
                    self.assertNotIn(klass, (RS.CLASS_ORDINARY_CHAT, RS.CLASS_VALID_BOUNDARY))
                    self.assertTrue(errors)

    def test_public_cli_cannot_spend_incidental_or_negated_words(self):
        for request in UNAUTHORIZED:
            with self.subTest(request=request):
                run = subprocess.run(
                    [
                        sys.executable,
                        str(SUBJECT / "tools/saipen.py"),
                        "response",
                        "check",
                        "--stdin",
                        "--classify",
                        "--request",
                        request,
                        "--json",
                    ],
                    input=LONG_CHAT,
                    encoding="utf-8",
                    capture_output=True,
                    timeout=60,
                    cwd=SUBJECT,
                )
                payload = json.loads(run.stdout)
                self.assertFalse(payload["ok"], payload)
                self.assertEqual(payload["detail_mode"], RS.DETAIL_MODE_NONE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
