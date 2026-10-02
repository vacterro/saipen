"""T-1583 same-incident RED control: the 2026-10-01 11:28:57Z FastPrompter reply.

The regression carrier is the REAL incident, not a toy: the exact Russian
human ingress (190 chars) and the exact emitted Estonian reply (2643 chars,
7 non-empty prose lines) captured byte-exact from the producing host session
(ZCode CLI rollout model-io sess_d9be29f2, turn_ebdb9065, model SAIFREN).

The control must fail for the SAME reason the user observed: the reply is
ordinary chat (turn_decision ORDINARY), detail authorization is NONE for this
exact ingress, and the prose is over the machine char ceiling -- while the
STYLE line budget alone would have passed it (7 <= 8 lines). If a future
change makes the canonical authority accept these exact bytes again (as every
installed home except opencode's still does at capture time), this control
goes red.

Usage: python incident.py [subject-root]   (default: this repository)
"""
from pathlib import Path
import hashlib
import sys
import unittest

SUBJECT = Path(sys.argv.pop(1)).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(SUBJECT / "tools"))
from saipen_engine import chat_style as CS, response_surface as RS  # noqa: E402

HERE = Path(__file__).resolve().parent
INGRESS_BYTES = (HERE / "ingress.txt").read_bytes()
REPLY_BYTES = (HERE / "reply.txt").read_bytes()
#: Byte-binding of the captured incident (UTF-8). Guards the carrier itself.
INGRESS_SHA256 = "fd7bed0eef4f1bb2338817eaba94ceadb5dd2e37d869470c74d1b720404b73d2"
REPLY_SHA256 = "d6c2c592a71631666a19ad1d0fc89ff90300572025ae2b74f1fc7e27c7c6c9f0"
INGRESS = INGRESS_BYTES.decode("utf-8")
REPLY = REPLY_BYTES.decode("utf-8")


class T1583IncidentRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = CS.compile_style_contract(
            (SUBJECT / "saipen" / "STYLE.md").read_text(encoding="utf-8")
        )

    def test_carrier_bytes_are_the_incident(self):
        self.assertEqual(hashlib.sha256(INGRESS_BYTES).hexdigest(), INGRESS_SHA256)
        self.assertEqual(hashlib.sha256(REPLY_BYTES).hexdigest(), REPLY_SHA256)
        self.assertEqual(len(INGRESS), 190)
        self.assertEqual(len(REPLY), 2643)

    def test_exact_human_ingress_earns_no_detail_authorization(self):
        self.assertEqual(RS.detail_mode_for_request(INGRESS), RS.DETAIL_MODE_NONE)

    def test_the_line_budget_alone_cannot_catch_this_incident(self):
        nonempty = [line for line in REPLY.splitlines() if line.strip()]
        self.assertEqual(len(nonempty), 7)
        self.assertLessEqual(len(nonempty), self.contract.line_budget)

    def test_canonical_authority_refuses_the_exact_reply(self):
        klass, errors = RS.classify_final_response(
            REPLY,
            operational_turn=False,
            style_contract=self.contract,
            detail_mode=RS.DETAIL_MODE_NONE,
        )
        self.assertEqual(klass, RS.CLASS_CHAT_STYLE_DRIFT)
        self.assertTrue(
            any("2631" in e and "2000" in e for e in errors),
            f"expected the char-ceiling refusal, got {errors!r}",
        )

    def test_a_compact_reply_on_the_same_ingress_stays_ordinary_chat(self):
        klass, errors = RS.classify_final_response(
            "Põhjus: mudel leiutas ise detaili-loa; masina detail_mode jäi NONE,"
            " klausel keeldus (2631 > 2000). Korrastus omanik: T-1558.",
            operational_turn=False,
            style_contract=self.contract,
            detail_mode=RS.DETAIL_MODE_NONE,
        )
        self.assertEqual(klass, RS.CLASS_ORDINARY_CHAT)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
