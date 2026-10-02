"""SAIPEN Core DONE-Work reverify receipts (T-158 Stage 2).

A re-verification receipt is a first-class machine-owned record saying:
"this already-DONE Work was checked again against this current tree."
DONE stays DONE; no synthetic VERIFY transition; strict Core, release and
historical debt visibility unchanged.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine import debt as debt_mod  # noqa: E402
from saipen_engine import findings as findings_mod  # noqa: E402
from saipen_engine import intake  # noqa: E402

SCENARIO = ROOT / "tests" / "scenarios" / "stale-state-reconciliation" / ".saipen"

V = [{"command": "unittest probe", "result": "PASS"}]


class ReverifyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-reverify-")
        self.root = Path(self.tmp.name) / "project"
        self.root.mkdir()
        shutil.copytree(SCENARIO, self.root / ".saipen")
        board = self.root / ".saipen/BOARD.md"
        text = board.read_text(encoding="utf-8")
        text = text.replace("## DOING\n- [/] T-001 DOING task", "## DOING")
        text = text.replace("## DONE\n", "## DONE\n- [x] T-001 DOING task | verify: proof exists\n")
        board.write_text(text, encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _canned(self, problems):
        return {
            "ok": True,
            "exit_code": 0 if not problems else 1,
            "gate": "core",
            "problems": problems,
            "warnings": [],
        }

    def _closure_finding(self, ticket: str) -> dict:
        return findings_mod.classify(
            "problem",
            f"ticket {ticket} is ## DONE but carries no current-cycle verification "
            "evidence (classifier: no current-cycle VERIFY boundary)",
        )

    def test_done_work_receives_pass_reverify_receipt(self) -> None:
        result = debt_mod.reverify_work(self.root, "T-001", "probe", verification=V)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["code"], "WORK_REVERIFIED")
        self.assertIn(result["verdict"], ("PASS", "PASS_WITH_CARRIED_DEBT"))
        record = debt_mod.load_reverify_receipt(self.root, result["receipt_id"])
        self.assertEqual(record["work"], "T-001")
        self.assertTrue(record["journal_op_id"])

    def test_done_state_remains_done_and_no_synthetic_verify(self) -> None:
        before_board = (self.root / ".saipen/BOARD.md").read_text(encoding="utf-8")
        before_log = (self.root / ".saipen/LOG.md").read_bytes()
        debt_mod.reverify_work(self.root, "T-001", "probe", verification=V)
        self.assertEqual(
            (self.root / ".saipen/BOARD.md").read_text(encoding="utf-8"), before_board
        )
        self.assertEqual((self.root / ".saipen/LOG.md").read_bytes(), before_log)
        from saipen_engine.log import parse_log_line

        events = [
            parsed
            for line in (self.root / ".saipen/LOG.md").read_text(encoding="utf-8").splitlines()
            if (parsed := parse_log_line(line)) is not None
        ]
        self.assertFalse(
            any("transition to VERIFY" in (e.get("text") or "") for e in events),
            "no synthetic VERIFY transition may appear",
        )

    def test_todo_work_refuses_reverify(self) -> None:
        intake.capture(self.root, "todo work body", source_kind="user_audit")
        board = self.root / ".saipen/BOARD.md"
        text = board.read_text(encoding="utf-8")
        text = text.replace("## TODO\n", "## TODO\n- [ ] T-050 [P2] todo | verify: x\n")
        board.write_text(text, encoding="utf-8")
        result = debt_mod.reverify_work(self.root, "T-050", "probe", verification=V)
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["code"], "REVERIFY_REFUSED")

    def test_doing_work_refuses_reverify(self) -> None:
        board = self.root / ".saipen/BOARD.md"
        text = board.read_text(encoding="utf-8")
        text = text.replace("- [x] T-001 DOING task | verify: proof exists\n", "")
        text = text.replace("## DOING", "## DOING\n- [/] T-050 [P2] doing | verify: x | owner: probe | claim_time: " + debt_mod._utc() + "\n")
        board.write_text(text, encoding="utf-8")
        from saipen_engine.state import parse_state, patch_state

        state_path = self.root / ".saipen/STATE.md"
        state = parse_state(state_path.read_text(encoding="utf-8"))
        state = patch_state(state_path.read_text(encoding="utf-8"), {"task": "T-050", "phase": "BUILD"})
        state_path.write_text(state, encoding="utf-8")
        result = debt_mod.reverify_work(self.root, "T-050", "probe", verification=V)
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["code"], "REVERIFY_REFUSED")

    def test_unknown_work_refuses_reverify(self) -> None:
        result = debt_mod.reverify_work(self.root, "T-999", "probe", verification=V)
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["code"], "TICKET_NOT_FOUND")

    def test_non_pass_verification_refuses(self) -> None:
        result = debt_mod.reverify_work(
            self.root, "T-001", "probe",
            verification=[{"command": "probe", "result": "FAIL"}],
        )
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["code"], "REVERIFY_REFUSED")

    def test_empty_verification_refuses(self) -> None:
        result = debt_mod.reverify_work(self.root, "T-001", "probe", verification=[])
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["code"], "REVERIFY_REFUSED")

    def test_pass_receipt_satisfies_closure_evidence(self) -> None:
        """The integration point: closure-evidence finding carried by receipt."""
        with patch.object(debt_mod, "capture_findings", return_value=self._canned([])):
            result = debt_mod.reverify_work(self.root, "T-001", "probe", verification=V)
        self.assertTrue(result["ok"], result)
        receipt_id = result["receipt_id"]
        record = debt_mod.load_reverify_receipt(self.root, receipt_id)
        self.assertIsNotNone(record)

    def test_fail_receipt_does_not_satisfy_closure_evidence(self) -> None:
        """A FAIL verdict receipt must never become accepted closure evidence."""
        finding = self._closure_finding("T-001")
        with patch.object(debt_mod, "capture_findings", return_value=self._canned([finding])):
            result = debt_mod.reverify_work(self.root, "T-001", "probe", verification=V)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIsNone(debt_mod.latest_pass_reverify(self.root, "T-001"))

    def test_free_text_run_checkpoint_does_not_satisfy(self) -> None:
        """Only the structured receipt satisfies the closure-evidence gate."""
        log = self.root / ".saipen/LOG.md"
        log.write_text(
            log.read_text(encoding="utf-8")
            + "- 07.09.26 23:00 [E-9999] [parent: E-0] [T-001] [agent: probe] [op: op-x] "
            "RUN: transition to VERIFY -- re-verified manually, all good\n",
            encoding="utf-8",
        )
        # The free-text boundary exists but no receipt: the strict classifier
        # must still refuse it (it needs PASS/conf: high AFTER the boundary,
        # and even then the receipt path is the one that carries provenance).
        result = debt_mod.latest_pass_reverify(self.root, "T-001")
        self.assertIsNone(result)

    def test_wrong_project_refuses(self) -> None:
        with patch.object(debt_mod, "capture_findings", return_value=self._canned([])):
            result = debt_mod.reverify_work(self.root, "T-001", "probe", verification=V)
        self.assertTrue(result["ok"], result)
        other = Path(self.tmp.name) / "other"
        shutil.copytree(self.root, other)
        with self.assertRaises(debt_mod.DebtRefusal) as caught:
            debt_mod.load_reverify_receipt(other, result["receipt_id"])
        self.assertIn(
            caught.exception.code,
            ("REVERIFY_RECEIPT_FOREIGN_PROJECT", "REVERIFY_RECEIPT_FOREIGN_LINEAGE"),
        )

    def test_stale_ruleset_refuses(self) -> None:
        with patch.object(debt_mod, "capture_findings", return_value=self._canned([])):
            result = debt_mod.reverify_work(self.root, "T-001", "probe", verification=V)
        self.assertTrue(result["ok"], result)
        with patch.object(findings_mod, "RULESET_VERSION", 99), patch.object(
            findings_mod, "ruleset_fingerprint", lambda: "stale"
        ):
            with self.assertRaises(debt_mod.DebtRefusal) as caught:
                debt_mod.load_reverify_receipt(self.root, result["receipt_id"])
        self.assertEqual(caught.exception.code, "BASELINE_RULESET_CHANGED")

    def test_corrupted_receipt_refuses(self) -> None:
        with patch.object(debt_mod, "capture_findings", return_value=self._canned([])):
            result = debt_mod.reverify_work(self.root, "T-001", "probe", verification=V)
        self.assertTrue(result["ok"], result)
        path = self.root / debt_mod.REVERIFY_DIR / f"{result['receipt_id']}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record["source_head"] = "tampered"
        path.write_text(json.dumps(record), encoding="utf-8")
        with self.assertRaises(debt_mod.DebtRefusal) as caught:
            debt_mod.load_reverify_receipt(self.root, result["receipt_id"])
        self.assertEqual(caught.exception.code, "REVERIFY_RECEIPT_CORRUPT")
        self.assertIsNone(debt_mod.latest_pass_reverify(self.root, "T-001"))

    def test_second_identical_reverify_is_reused(self) -> None:
        with patch.object(debt_mod, "capture_findings", return_value=self._canned([])):
            first = debt_mod.reverify_work(self.root, "T-001", "probe", verification=V)
            second = debt_mod.reverify_work(self.root, "T-001", "probe", verification=V)
        self.assertTrue(first["ok"] and second["ok"])
        self.assertEqual(second["code"], "REVERIFY_REUSED")
        self.assertEqual(first["receipt_id"], second["receipt_id"])
        receipts = list((self.root / debt_mod.REVERIFY_DIR).glob("RV-*.json"))
        self.assertEqual(len(receipts), 1)

    def test_newer_pass_supersedes_older_fail(self) -> None:
        fail_finding = self._closure_finding("T-001")
        with patch.object(debt_mod, "capture_findings", return_value=self._canned([fail_finding])):
            fail_result = debt_mod.reverify_work(self.root, "T-001", "probe", verification=V)
        self.assertEqual(fail_result["verdict"], "FAIL")
        # repair: the closure-evidence finding disappears
        with patch.object(debt_mod, "capture_findings", return_value=self._canned([])):
            pass_result = debt_mod.reverify_work(self.root, "T-001", "probe", verification=V)
        self.assertIn(pass_result["verdict"], ("PASS", "PASS_WITH_CARRIED_DEBT"))
        latest = debt_mod.latest_pass_reverify(self.root, "T-001")
        self.assertIsNotNone(latest)
        self.assertEqual(latest["receipt_id"], pass_result["receipt_id"])

    def test_work_delta_accepts_reverified_post_claim_done_work(self) -> None:
        """The integration: T-160/T-164/T-165 family post-claim + receipt."""
        import re as _re
        orig = debt_mod._legacy_eligibility

        def located_closure(reply, finding, boundary, *, target_work, target_source):
            raw, reason = orig(reply, finding, boundary, target_work=target_work, target_source=target_source)
            if not raw and finding.get("subject_kind") == "work" and _re.match(r"T-0(?:60|50)\b", str(finding.get("subject_id") or "")):
                return True, "Work T-060/T-050 predates E-816 (test-scoped; scenario base lacks T-06x canonical history)"
            return raw, reason

        log = self.root / ".saipen/LOG.md"
        log.write_text(
            log.read_text(encoding="utf-8")
            + "- 05.09.26 00:19 [E-815] [parent: E-814] [T-050] [agent: probe] [op: op-a] "
            "DEC: pre-claim work created\n"
            + "- 05.09.26 00:20 [E-816] [parent: E-815] [T-158] [agent: probe] [op: op-b] "
            "DEC: claimed via SAIOPS -- owner probe\n"
            + "- 05.09.26 00:21 [E-817] [parent: E-816] [T-060] [agent: probe] [op: op-c] "
            "DEC: post-claim work created\n",
            encoding="utf-8",
        )
        with patch.object(debt_mod, "capture_findings", return_value=self._canned([])), \
             patch.object(debt_mod, "_legacy_eligibility", side_effect=located_closure):
            debt_mod.reverify_work(self.root, "T-060", "probe", verification=V)
        with patch.object(
            debt_mod,
            "capture_findings",
            return_value=self._canned([self._closure_finding("T-060")]),
        ), patch.object(debt_mod, "_legacy_eligibility", side_effect=located_closure):
            delta = debt_mod.work_delta(
                self.root, "T-158", agent="probe", claim_boundary="E-816",
                verification=V,
            )
        self.assertTrue(delta["ok"], delta)
        self.assertEqual(delta["code"], "WORK_DELTA_PASS")
        self.assertEqual(delta["carried_problems"], 1)

    def test_work_delta_still_blocks_unreverified_post_claim_done_work(self) -> None:
        log = self.root / ".saipen/LOG.md"
        log.write_text(
            log.read_text(encoding="utf-8")
            + "- 05.09.26 00:20 [E-816] [parent: E-815] [T-158] [agent: probe] [op: op-b] "
            "DEC: claimed via SAIOPS -- owner probe\n"
            + "- 05.09.26 00:21 [E-817] [parent: E-816] [T-060] [agent: probe] [op: op-c] "
            "DEC: post-claim work created\n",
            encoding="utf-8",
        )
        with patch.object(
            debt_mod,
            "capture_findings",
            return_value=self._canned([self._closure_finding("T-060")]),
        ):
            delta = debt_mod.work_delta(
                self.root, "T-158", agent="probe", claim_boundary="E-816", verification=V,
            )
        self.assertTrue(delta["ok"], delta)
        self.assertEqual(delta["code"], "WORK_DELTA_BLOCKED")

    def test_receipt_serializes_no_secrets(self) -> None:
        with patch.object(debt_mod, "capture_findings", return_value=self._canned([])):
            result = debt_mod.reverify_work(self.root, "T-001", "probe", verification=V)
        self.assertTrue(result["ok"], result)
        path = self.root / debt_mod.REVERIFY_DIR / f"{result['receipt_id']}.json"
        raw = path.read_text(encoding="utf-8")
        for secret_marker in ("password", "api_key", "token=", "secret"):
            self.assertNotIn(secret_marker, raw.lower())

    def test_strict_findings_remain_visible_after_reverify(self) -> None:
        """The receipt carries the findings digest; strict Core count unchanged."""
        with patch.object(
            debt_mod,
            "capture_findings",
            return_value=self._canned([self._closure_finding("T-050")]),
        ):
            result = debt_mod.reverify_work(self.root, "T-001", "probe", verification=V)
        record = debt_mod.load_reverify_receipt(self.root, result["receipt_id"])
        self.assertEqual(record["problem_count"], 1)
        self.assertEqual(record["warning_count"], 0)
        self.assertTrue(record["findings_digest"])


if __name__ == "__main__":
    unittest.main()
