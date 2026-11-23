"""T-2087 focused check: DRIFT_MATRIX anchors re-derive from live fixtures.

Reads the durable fixtures captured for this ticket and asserts the exact
anchor facts the drift matrix cites, so the VERIFIED disposition of
SRC-421:R001 has an authentic, repeatable execution receipt instead of a
hand-typed claim.
"""

from __future__ import annotations

import json
import sqlite3
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB = Path(r"C:/Users/vac34/.zcode/cli/db/db.sqlite")
SESSION = "sess_a3345396-c502-4aa7-8536-eff7baf6d8cb"
BZ = Path(r"V:/___VAC/__K/__CODE/_MISC/_BZDECOMP/.saipen")


def _part_texts(cur, message_id):
    cur.execute(
        "SELECT data FROM part WHERE message_id=? ORDER BY sequence", (message_id,)
    )
    out = []
    for (blob,) in cur.fetchall():
        p = json.loads(blob)
        if p.get("type") == "text" and p.get("text"):
            out.append(p["text"])
    return out


class E1IngressChain(unittest.TestCase):
    def test_real_user_message_precedes_model_supplied_receipt(self):
        cur = sqlite3.connect(str(DB)).cursor()
        cur.execute(
            "SELECT data FROM message WHERE id=?",
            ("msg_mwl79i9a_6ed7c258-a680-4bd1-8446-06159c4cf77b",),
        )
        msg = json.loads(cur.fetchone()[0])
        prov = msg["metadata"]["inputProvenance"]
        self.assertEqual(prov["origin"], "real_user")
        self.assertTrue(prov["humanAuthored"])
        self.assertEqual(prov["source"], "queue_promotion")
        self.assertIn(
            "killfeed", " ".join(_part_texts(cur, "msg_mwl79i9a_6ed7c258-a680-4bd1-8446-06159c4cf77b")).lower()
        )

        meta = json.loads(
            (BZ / "archive" / "source" / "SRC-801.meta.json").read_text(encoding="utf-8")
        )
        self.assertEqual(meta["request_provenance"]["witness"], "model_supplied")
        self.assertEqual(meta["linked_work"], "T-919")
        body = (BZ / "archive" / "source" / "SRC-801.md").read_text(encoding="utf-8")
        self.assertIn("killfeed again renders empty black boxes", body)
        # the operator's Russian bytes never crossed the seam verbatim
        self.assertNotIn("чёрные", body)


class E2AdmissionLatency(unittest.TestCase):
    def test_user_messages_admitted_only_as_late_paraphrase(self):
        cur = sqlite3.connect(str(DB)).cursor()
        for mid in (
            "msg_mwl7qcgg_88b8ef3c-0024-4d4c-a4a1-cbbd6c4f1ba1",
            "msg_mwl7r40x_f5d12f3f-0773-4af6-935e-8d22b289592b",
        ):
            cur.execute("SELECT data FROM message WHERE id=?", (mid,))
            msg = json.loads(cur.fetchone()[0])
            self.assertEqual(msg["metadata"]["inputProvenance"]["origin"], "real_user")
        for sid, rel in (
            ("SRC-802", "archive/source/SRC-802.meta.json"),
            ("SRC-803", "intake/active/SRC-803.meta.json"),
            ("SRC-804", "intake/active/SRC-804.meta.json"),
            ("SRC-805", "intake/active/SRC-805.meta.json"),
        ):
            meta = json.loads((BZ / rel).read_text(encoding="utf-8"))
            self.assertEqual(meta["request_provenance"]["witness"], "model_supplied")
            received = meta["received_at"]
            self.assertTrue(
                received >= "2026-11-17T22:24:16Z", f"{sid} admitted too early: {received}"
            )


class E4ResponseContractMeasured(unittest.TestCase):
    def test_first_command_contract_admits_no_enforcement(self):
        cur = sqlite3.connect(str(DB)).cursor()
        cur.execute(
            "SELECT data FROM message WHERE id=?",
            ("msg_mw9tuskk_adf732c1-ca21-49f3-9cd9-e0fc720edc13",),
        )
        msg = json.loads(cur.fetchone()[0])
        rc = msg["metadata"]["inputIntent"]["responseContract"]
        self.assertIsNone(rc["replyLanguage"])
        self.assertEqual(rc["enforcement"]["language"], "none")
        self.assertEqual(rc["enforcement"]["structure"], "none")
        self.assertEqual(rc["admissionMode"], "observed")
        self.assertIn("observed, not enforced", rc["limitation"])
        # no pinned language => every later language decision is advisory only
        self.assertEqual(rc["replyLanguageDeclarations"], [])


class E5TruncatedAuthorityPopulation(unittest.TestCase):
    def test_measured_command_shapes_exist(self):
        cur = sqlite3.connect(str(DB)).cursor()
        cur.execute(
            "SELECT data FROM part WHERE session_id=? AND data LIKE '%saipen%'",
            (SESSION,),
        )
        continue_head = grep_board = 0
        for (blob,) in cur.fetchall():
            try:
                p = json.loads(blob)
            except json.JSONDecodeError:
                continue
            cmd = (p.get("state") or {}).get("input", {}).get("command", "")
            if "saipen continue" in cmd and "head" in cmd:
                continue_head += 1
            if "grep" in cmd and "BOARD.md" in cmd:
                grep_board += 1
        self.assertGreaterEqual(continue_head, 25)
        self.assertGreaterEqual(grep_board, 100)


class E7DeclinedHumanQuestion(unittest.TestCase):
    def test_askuserquestion_part_is_host_error(self):
        cur = sqlite3.connect(str(DB)).cursor()
        cur.execute(
            "SELECT data FROM part WHERE id=?",
            ("part_mwhap9pe_96bc3dc0-3c18-4774-977f-8c265ca3d41d",),
        )
        p = json.loads(cur.fetchone()[0])
        self.assertEqual(p["state"]["status"], "error")


if __name__ == "__main__":
    unittest.main()
