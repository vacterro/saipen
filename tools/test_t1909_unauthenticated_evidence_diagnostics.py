"""T-1909 / IMP-002: EVIDENCE_UNAUTHENTICATED and reverify live work diagnostics.

Controls:
1. `debt.reverify_work` on live Work under ## DOING refuses with REVERIFY_REFUSED
   and names the exact canonical command to produce the receipt for live Work
   (`python tools/core_unit.py focused <work> --pattern test_*.py`), including
   `canonical_next_command`.
2. `intake.set_disposition` when no authentic execution receipt exists refuses with
   EVIDENCE_UNAUTHENTICATED, names the exact focused unit command for live Work,
   and returns `canonical_next_command`.
3. `intake.set_disposition` when an unauthenticated/uncommitted PASS JSON is presented
   refuses with EVIDENCE_UNAUTHENTICATED, names the exact focused unit command for
   live Work, and returns `canonical_next_command`.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import debt, intake  # noqa: E402


class UnauthenticatedEvidenceDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="t1909-diagnostics-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / ".saipen").mkdir(parents=True, exist_ok=True)
        (self.root / ".saipen" / "STATE.md").write_text(
            "---\nphase: BUILD\ntask: T-100\n---\n", encoding="utf-8"
        )
        (self.root / ".saipen" / "BOARD.md").write_text(
            "# Board\n\n## DOING\n- [/] T-100 [P1] Live test work | verify: test | owner: tester\n\n## DONE\n- [x] T-99 [P1] Old work | verify: pass\n",
            encoding="utf-8",
        )
        (self.root / ".saipen" / "LOG.md").write_text("# Log\n", encoding="utf-8")

    def test_reverify_refuses_doing_work_and_names_focused_command(self):
        res = debt.reverify_work(
            self.root,
            "T-100",
            "tester",
            verification=[{"command": "python -m unittest tools/test_sample.py", "result": "PASS"}],
        )
        self.assertFalse(res.get("ok"))
        self.assertEqual(res.get("code"), "REVERIFY_REFUSED")
        self.assertIn("T-100 is under ## DOING", res.get("detail", ""))
        expected_cmd = "python tools/core_unit.py focused T-100 --pattern test_*.py"
        self.assertIn(expected_cmd, res.get("detail", ""))
        self.assertEqual(res.get("canonical_next_command"), expected_cmd)

    def test_intake_evidence_unauthenticated_names_focused_command(self):
        # Create an intake source receipt with requirement R001
        cap = intake.capture(
            self.root,
            "Test request",
            source_kind="user_instruction",
            work="T-100",
        )
        rcpt = cap["receipt"]
        intake.ensure_request_clause(self.root, rcpt)

        test_file = self.root / "tools" / "test_unauthenticated.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("import unittest\n", encoding="utf-8")

        res = intake.set_disposition(
            self.root,
            rcpt,
            "R001",
            "VERIFIED",
            work="T-100",
            evidence="tools/test_unauthenticated.py verified",
            verification="python -m unittest tools/test_unauthenticated.py -> PASS",
        )
        self.assertFalse(res.get("ok"))
        self.assertEqual(res.get("code"), "EVIDENCE_UNAUTHENTICATED")
        self.assertIn("no authentic execution receipt found", res.get("detail", ""))
        expected_cmd = "python tools/core_unit.py focused T-100 --pattern test_unauthenticated.py"
        self.assertIn(expected_cmd, res.get("detail", ""))
        self.assertEqual(res.get("canonical_next_command"), expected_cmd)

    def test_intake_uncommitted_json_receipt_names_focused_command(self):
        cap = intake.capture(
            self.root,
            "Test request 2",
            source_kind="user_instruction",
            work="T-100",
        )
        rcpt = cap["receipt"]
        intake.ensure_request_clause(self.root, rcpt)

        test_file = self.root / "tools" / "test_dummy.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("import unittest\n", encoding="utf-8")

        fake_receipt = (
            self.root / ".saipen" / "evidence" / "regression" / "fake-pass.json"
        )
        fake_receipt.parent.mkdir(parents=True, exist_ok=True)
        fake_receipt.write_text(
            json.dumps({"status": "PASS", "oracle_files": ["tools/test_dummy.py"]}),
            encoding="utf-8",
        )

        res = intake.set_disposition(
            self.root,
            rcpt,
            "R001",
            "VERIFIED",
            work="T-100",
            evidence=str(fake_receipt.relative_to(self.root)),
            verification=f"python tools/test_dummy.py -> PASS record: {fake_receipt.relative_to(self.root)}",
        )
        self.assertFalse(res.get("ok"))
        self.assertEqual(res.get("code"), "EVIDENCE_UNAUTHENTICATED")
        expected_cmd = "python tools/core_unit.py focused T-100 --pattern test_dummy.py"
        self.assertIn(expected_cmd, res.get("detail", ""))
        self.assertEqual(res.get("canonical_next_command"), expected_cmd)


if __name__ == "__main__":
    unittest.main()
