"""Same oracle for request authorization; argv[1] selects the subject."""
from pathlib import Path
import json
import subprocess
import sys
import unittest

SUBJECT = Path(sys.argv.pop(1)).resolve()
sys.path.insert(0, str(SUBJECT / "tools"))
from saipen_engine import response_surface as RS, chat_style as CS

CONTRACT = CS.compile_style_contract((SUBJECT / "saipen/STYLE.md").read_text(encoding="utf-8"))
LONG_CHAT = "\n".join("Kontroll tehtud." for _ in range(CONTRACT.line_budget + 4))
SURFACE = (
    "STATUS\nDONE\nRESULT\nKontroll tehtud.\nBLOCKER\nNONE\n"
    "OPERATOR ACTION\nNONE\nNEXT EXACT ACTION\nNONE\nVALIDATION\nNOT_RUN\n"
    "DETAILS\nKontroll tehtud."
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
            ("please audit the accepted debt", RS.DETAIL_MODE_AUDIT),
            ("audit this project", RS.DETAIL_MODE_AUDIT),
            ("prepare the handoff", RS.DETAIL_MODE_HANDOFF),
            ("this is an exceptional boundary", RS.DETAIL_MODE_BOUNDARY),
        ):
            with self.subTest(request=request):
                mode = RS.detail_mode_for_request(request)
                self.assertEqual(mode, expected)
                self.assertEqual(RS.response_errors(SURFACE, detail_mode=mode), [])
                klass, errors = RS.classify_final_response(
                    LONG_CHAT, operational_turn=False, style_contract=CONTRACT, detail_mode=mode
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
        for request in UNAUTHORIZED[:5]:
            with self.subTest(request=request):
                run = subprocess.run(
                    [sys.executable, str(SUBJECT / "tools/saipen.py"), "response", "check",
                     "--stdin", "--classify", "--request", request, "--json"],
                    input=LONG_CHAT, encoding="utf-8", capture_output=True, timeout=60,
                    cwd=SUBJECT,
                )
                payload = json.loads(run.stdout)
                self.assertFalse(payload["ok"], payload)
                self.assertEqual(payload["detail_mode"], RS.DETAIL_MODE_NONE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
