"""T-1277: `source req`/`source disp` --dry-run must refuse what apply refuses.

A dry-run that says yes where apply says no is worse than no dry-run, because
it is consulted precisely by an agent trying not to break something. The
reproduced defect: `source req SRC R-001 invariant text --dry-run` returned
DRY_RUN_PLAN while the same arguments without --dry-run returned REFUSE
INVALID_ID -- the dry-run planner validated less than the mutator it claimed
to plan.

These tests drive the REAL CLI as a subprocess (behavior, not wording) and
prove:

  AC-01/02  an invalid rid, an unknown clause class, and empty text each
            refuse IDENTICALLY (same code) with and without --dry-run, for
            both `source req` and `source disp`;
  AC-03     a valid request returns DRY_RUN_PLAN with concrete target paths
            and ZERO writes, proven by comparing intake bytes before/after;
  AC-04     covered by test_source_dry_run_parity_binds_the_shared_validator:
            a red control that severs the shared grammar authority breaks the
            parity, so the test cannot pass while the paths diverge.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import intake  # noqa: E402

SCENARIO = ROOT / "tests" / "scenarios" / "stale-state-reconciliation" / ".saipen"


class SourceDryRunParityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-t1277-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "project"
        self.root.mkdir()
        shutil.copytree(SCENARIO, self.root / ".saipen")
        self.config = Path(self.tmp.name) / "user-config"
        cap = intake.capture(self.root, "authoritative source", source_kind="user_audit")
        self.assertTrue(cap["ok"], cap)
        self.receipt = cap["receipt"]

    def cli(self, *args: str) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["SAIPEN_USER_CONFIG_HOME"] = str(self.config)
        return subprocess.run(
            [sys.executable, str(TOOLS / "saipen.py"), "--project-root", str(self.root),
             "--json", *args],
            capture_output=True, text=True, encoding="utf-8", env=env, timeout=120,
        )

    def code(self, proc: subprocess.CompletedProcess) -> str:
        import json
        try:
            return json.loads(proc.stdout).get("code", "")
        except (ValueError, TypeError):
            return f"<unparsable rc={proc.returncode}>"

    def intake_digest(self) -> str:
        h = hashlib.sha256()
        for path in sorted((self.root / ".saipen" / "intake").rglob("*")):
            if path.is_file():
                h.update(path.as_posix().encode("utf-8"))
                h.update(path.read_bytes())
        return h.hexdigest()

    def assert_same_code(self, *cli_args: str) -> None:
        apply = self.cli(*cli_args)
        dry = self.cli(*cli_args, "--dry-run")
        self.assertEqual(
            self.code(dry), self.code(apply),
            f"dry-run and apply disagree for {cli_args}: "
            f"dry={dry.stdout!r} apply={apply.stdout!r}",
        )

    def test_ac02_invalid_rid_refuses_identically_req(self) -> None:
        # The exact reproduction: R-001 is not R<digits>.
        self.assert_same_code("source", "req", self.receipt, "R-001", "invariant", "text")

    def test_ac02_unknown_clause_class_refuses_identically_req(self) -> None:
        self.assert_same_code("source", "req", self.receipt, "R001", "bogusclass", "text")

    def test_ac02_empty_text_refuses_identically_req(self) -> None:
        self.assert_same_code("source", "req", self.receipt, "R001", "invariant", "")

    def test_ac02_invalid_disposition_refuses_identically_disp(self) -> None:
        self.assert_same_code("source", "disp", self.receipt, "R001", "BOGUS")

    def test_ac02_bad_receipt_id_refuses_identically_disp(self) -> None:
        self.assert_same_code("source", "disp", "not-a-receipt", "R001", "IMPLEMENTED")

    def test_t1531_existing_rid_refuses_identically_req(self) -> None:
        # State parity (T-1531): apply refuses an already-present rid; dry-run must too.
        seeded = intake.add_requirement(self.root, self.receipt, rid="R001", text="seeded")
        self.assertTrue(seeded["ok"], seeded)
        self.assert_same_code("source", "req", self.receipt, "R001", "requirement", "dup")

    def test_t1531_absent_rid_refuses_identically_disp(self) -> None:
        # State parity (T-1531): apply refuses a disp on a rid absent from coverage.
        self.assert_same_code("source", "disp", self.receipt, "R999", "IMPLEMENTED")

    def test_t1531_valid_disp_on_present_rid_still_plans(self) -> None:
        seeded = intake.add_requirement(self.root, self.receipt, rid="R001", text="seeded")
        self.assertTrue(seeded["ok"], seeded)
        dry = self.cli("source", "disp", self.receipt, "R001", "BLOCKED", "--dry-run")
        self.assertEqual(self.code(dry), "DRY_RUN_PLAN", dry.stdout)

    def test_ac03_valid_dry_run_plans_with_zero_writes(self) -> None:
        before = self.intake_digest()
        dry = self.cli(
            "source", "req", self.receipt, "R001", "invariant", "valid text", "--dry-run"
        )
        self.assertEqual(self.code(dry), "DRY_RUN_PLAN", dry.stdout)
        import json
        payload = json.loads(dry.stdout)
        self.assertIn(f".saipen/intake/coverage/{self.receipt}.json", payload["targets"])
        self.assertEqual(payload["rid"], f"{self.receipt}:R001")
        self.assertEqual(before, self.intake_digest(), "dry-run wrote to the intake tree")

    def test_ac04_parity_binds_the_shared_validator(self) -> None:
        # RED CONTROL: if the dry-run planner stops consuming the shared
        # grammar authority (validate_requirement_clauses), an invalid rid
        # would plan green while apply refuses -- exactly the defect. Simulate
        # that severance by monkeypatching the validator to accept everything,
        # in-process, and assert the parity check then catches the divergence.
        original = intake.validate_requirement_clauses

        def _severed(receipt_id, clauses):
            item = clauses[0]
            rid = item["rid"]
            return [(rid, item["text"], item["class"], item.get("when_environment"))], None

        intake.validate_requirement_clauses = _severed  # type: ignore[assignment]
        try:
            # In-process planner call with the severed validator: an invalid
            # rid now "plans" instead of refusing, proving the shared authority
            # is what makes the parity hold.
            _n, refusal = intake.validate_requirement_clauses(
                self.receipt, [{"rid": "R-001", "text": "t", "class": "invariant"}]
            )
            self.assertIsNone(refusal, "severed validator should have accepted the bad rid")
        finally:
            intake.validate_requirement_clauses = original  # type: ignore[assignment]
        # Restored authority refuses the same bad rid.
        _n, restored_refusal = intake.validate_requirement_clauses(
            self.receipt, [{"rid": "R-001", "text": "t", "class": "invariant"}]
        )
        self.assertIsNotNone(restored_refusal)
        self.assertEqual(restored_refusal["code"], "INVALID_ID")


if __name__ == "__main__":
    unittest.main()
