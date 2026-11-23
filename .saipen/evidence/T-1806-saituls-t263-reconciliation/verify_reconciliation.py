"""Deterministic verification for T-1806 / SRC-265 (SAITULS T-263 reconciliation)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import unittest

SAIPEN_ROOT = Path(__file__).resolve().parents[3]
if str(SAIPEN_ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(SAIPEN_ROOT / "tools"))

from saipen_engine.board import parse_board, ticket_is_workable  # noqa: E402
from saipen_engine.operator_task import authority_for_receipt  # noqa: E402

SAITULS_ROOT = Path(r"V:\___VAC\__K\__CODE\__SAITULS")
EVIDENCE_DIR = Path(__file__).resolve().parent
RECONCILIATION_MD = EVIDENCE_DIR / "RECONCILIATION.md"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class T1806SaitulsReconciliationTests(unittest.TestCase):
    def test_r001_r002_r003_e3221_provenance_and_later_restrictions(self) -> None:
        index_data = json.loads(
            (SAITULS_ROOT / ".saipen" / "intake" / "index.json").read_text(encoding="utf-8")
        )
        self.assertEqual(index_data["next_id"], 106)
        src105_meta = json.loads(
            (SAITULS_ROOT / ".saipen" / "archive" / "source" / "SRC-105.meta.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(src105_meta["received_at"], "2026-10-13T11:10:27Z")
        self.assertEqual(
            src105_meta["request_provenance"]["witness"],
            "model_supplied",
        )
        # Deliberate red control: model_supplied receipt SRC-100 cannot grant operator_explicit or preemptive authority
        auth_src100 = authority_for_receipt(SAITULS_ROOT, "SRC-100")
        self.assertFalse(auth_src100["user_explicit"])
        self.assertFalse(auth_src100["preempt_active_work"])

        op_e3221 = json.loads(
            (
                SAITULS_ROOT
                / ".saipen"
                / "recovery"
                / "settled"
                / "ticket-f7a679dfef284a1f86e94d4d2744be6e"
                / "operation.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(op_e3221["operation"], "ticket_move")
        self.assertEqual(op_e3221["created_at"], "2026-10-14T04:53:21Z")
        self.assertEqual(
            op_e3221["project_lineage"],
            "lineage-ded945ae8243480ab1bfee73baeb29c6",
        )

        state_text = (SAITULS_ROOT / ".saipen" / "STATE.md").read_text(encoding="utf-8")
        self.assertIn("continuation_authority: operator_required", state_text)
        self.assertIn("authority_source: E-3128", state_text)
        self.assertIn("authority_until: budget", state_text)
        self.assertIn("safety_valve_mode: hard_wait", state_text)
        self.assertIn("T-261, T-262, T-263 remain paused.", state_text)

    def test_r004_r005_r007_r012_canonical_dependency_and_blockers(self) -> None:
        board = parse_board((SAITULS_ROOT / ".saipen" / "BOARD.md").read_text(encoding="utf-8"))
        tickets = board["tickets"]
        self.assertIn("T-263", tickets)
        self.assertIn("T-261", tickets)
        t263 = tickets["T-263"]
        t261 = tickets["T-261"]
        self.assertEqual(t263["section"], "## TODO")
        self.assertEqual(t263["fields"].get("needs"), "T-261")
        self.assertEqual(t261["section"], "## BLOCKED")
        self.assertIn("PAUSED_BY_OPERATOR 2026-10-08", t261["fields"].get("blocker", ""))

        # Canonical Pick Rule: T-263 is NOT workable while T-261 is BLOCKED
        self.assertFalse(ticket_is_workable(t263, tickets))

        # Deliberate red/counterfactual control: if T-261 were in ## DONE, T-263 would become workable
        counterfactual = json.loads(json.dumps(tickets))
        counterfactual["T-261"]["section"] = "## DONE"
        self.assertTrue(ticket_is_workable(counterfactual["T-263"], counterfactual))

        # Verify all 6 BLOCKED tickets and ownership preserved
        expected_blocked = {"T-220", "T-262", "T-261", "T-143", "T-144", "T-167"}
        actual_blocked = {
            tid for tid, rec in tickets.items() if rec.get("section") == "## BLOCKED"
        }
        self.assertEqual(actual_blocked, expected_blocked)

    def test_r008_r011_saituls_non_mutation_and_artifact_preservation(self) -> None:
        self.assertEqual(
            _sha256(SAITULS_ROOT / ".saipen" / "STATE.md"),
            "aa2e750be6eaed6b7bc7a002d97c1cf0b71fa3af0e356cdec97495b49279315b",
        )
        self.assertEqual(
            _sha256(SAITULS_ROOT / ".saipen" / "BOARD.md"),
            "80594b2dc76ba3dabd551a426cb257d4fd5a3d1d685b4646a6155f023db06b71",
        )
        self.assertEqual(
            _sha256(SAITULS_ROOT / ".saipen" / "LOG.md"),
            "3dc0734d2b8623a074b546fffa06160ad5fcf749b749fac44940a568dddf3cc2",
        )
        self.assertEqual(
            _sha256(SAITULS_ROOT / "Scripts" / "secure_apps" / "sa_future_gates.py"),
            "343fc0c2432d680a678b25b670350bbf8c027ba05f229ac32287b9d20bfd454c",
        )
        self.assertEqual(
            _sha256(SAITULS_ROOT / "Wiki" / "SECURE-APPS-FUTURE-GATES.md"),
            "00723cea1df8ec099cf1ca09857e76e7b380c40bf04e0866477946ac373c3bfa",
        )
        self.assertEqual(
            _sha256(SAITULS_ROOT / "tests" / "secure_apps_future_gates.py"),
            "3939c275a75520346fedeafee5da19bd625b036d0a9f0e650c86ce3e9e7785ee",
        )
        self.assertEqual(
            _sha256(SAITULS_ROOT / ".saipen" / "evidence" / "SRC-100-admission-and-readiness.md"),
            "b3648f02951173217f5df082cadab2e049774b9d5139ef966d866101157bb135",
        )

    def test_r006_r009_r010_reconciliation_report_completeness(self) -> None:
        text = RECONCILIATION_MD.read_text(encoding="utf-8")
        for rid in [f"R{i:03d}" for i in range(1, 13)]:
            self.assertIn(rid, text)
        for heading in (
            "### STATUS",
            "### AUTHORITY",
            "### E-3221 PROVENANCE VERDICT",
            "### T-261/T-263 DEPENDENCY VERDICT",
            "### CANONICAL TRANSITIONS",
            "### CONFORMANCE",
            "### NEXT EXACT ACTION",
            "### NEED USER",
        ):
            self.assertIn(heading, text)


if __name__ == "__main__":
    unittest.main()
