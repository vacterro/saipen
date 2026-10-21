"""Proportional local verification; the complete family still gates publication."""

from __future__ import annotations

import hashlib
import io
import json
import sys
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import core_unit  # noqa: E402
from test_core_unit_gate import CoreUnitFixture, _run  # noqa: E402

POLICY_REL = "tools/verification_policy.json"
POLICY = {"schema": 1, "ticket": "focused", "publication": "full"}
RECORD_REL = ".saipen/evidence/focused-unit/run.json"


class FocusedPolicyTests(CoreUnitFixture):
    def setUp(self):
        super().setUp()
        (self.project / POLICY_REL).write_text(json.dumps(POLICY), encoding="utf-8")
        (self.project / "tools/test_focus.py").write_text(
            "import unittest\nclass Focus(unittest.TestCase):\n"
            "    def test_ok(self):\n        self.assertEqual(2 + 2, 4)\n",
            encoding="utf-8",
        )

    def focused_record(self, **changes):
        from saipen_engine.verification_cache import capture

        data = {
            "schema": 1,
            "family": "focused-unit",
            "fingerprint": core_unit.tree_fingerprint(self.project),
            "patterns": ["test_focus.py"],
            "runs": [{"pattern": "test_focus.py", **_run([])}],
            "ran": 10,
            "verdict": "PASS",
            "verification_identity": capture(self.project, {
                "family": "focused-unit", "patterns": ["test_focus.py"], "timeout": 300,
            }),
            **changes,
        }
        path = self.project / RECORD_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.record(
            f"FOCUSED-UNIT-EVIDENCE PASS conf: high ran:{data['ran']} "
            f"record:{RECORD_REL} sha256:{digest}"
        )
        return path

    def test_focused_current_tree_enters_ship_without_a_full_family_run(self):
        self.assertTrue(self.to("VERIFY").ok)
        self.focused_record()
        self.assertTrue(self.to("REVIEW").ok)
        result = self.to("SHIP")
        self.assertTrue(result.ok, result.to_dict())

    def test_ordinary_pass_still_cannot_replace_executed_evidence(self):
        self.reach_review()
        self.assertFalse(self.to("SHIP").ok)

    def test_changed_tree_refuses_focused_evidence(self):
        self.assertTrue(self.to("VERIFY").ok)
        self.focused_record()
        self.assertTrue(self.to("REVIEW").ok)
        (self.project / "tools/test_focus.py").write_text("# changed\n", encoding="utf-8")
        result = self.to("SHIP")
        self.assertFalse(result.ok)
        self.assertIn("different tree", result.message)

    def test_tampered_record_refuses(self):
        self.assertTrue(self.to("VERIFY").ok)
        path = self.focused_record()
        self.assertTrue(self.to("REVIEW").ok)
        path.write_text("{}", encoding="utf-8")
        self.assertIn("sha256", self.to("SHIP").message)

    def test_zero_tests_or_red_or_timeout_refuses(self):
        from saipen_engine.focused_unit import record_problem

        for run in (_run([], ran=0), _run(["test_focus.Focus.test_ok"]),
                    _run([], status="TIMEOUT", exit_code=None)):
            with self.subTest(run=run):
                path = self.focused_record(runs=[{"pattern": "test_focus.py", **run}])
                self.assertIsNotNone(record_problem(self.project, json.loads(path.read_text())))

    def test_full_evidence_is_still_accepted_for_a_focused_project(self):
        self.reach_review()
        self.cite(_run([]))
        self.assertTrue(self.to("SHIP").ok)

    def test_invalid_policy_does_not_disable_a_gate(self):
        self.reach_review()
        for policy in ({}, {**POLICY, "publication": "focused"}, {**POLICY, "extra": True}):
            with self.subTest(policy=policy):
                (self.project / POLICY_REL).write_text(json.dumps(policy), encoding="utf-8")
                result = self.to("SHIP")
                self.assertFalse(result.ok)
                self.assertIn("verification policy", result.message)

    def test_publication_requires_a_full_run_of_current_bytes(self):
        from saipen_engine.focused_unit import publication_gate

        self.focused_record()
        self.assertIsNotNone(publication_gate(self.project))
        self.cite(_run([]))
        self.assertIsNone(publication_gate(self.project))
        (self.project / "tools/test_focus.py").write_text("# next change\n", encoding="utf-8")
        self.assertIsNotNone(publication_gate(self.project))

    def test_new_red_in_full_record_blocks_publication(self):
        from saipen_engine.focused_unit import publication_gate

        self.cite(_run(["test_new.New.test_red"]))
        self.assertIsNotNone(publication_gate(self.project))

    def test_real_cli_records_then_reuses_unchanged_evidence(self):
        from saipen_engine import focused_unit

        self.assertTrue(self.to("VERIFY").ok)
        args = Namespace(pattern=["test_focus.py"], timeout=30,
                         ticket="T-7", agent="tester", fresh=False)
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(focused_unit.evidence(self.project, args), 0)
        self.assertFalse(json.loads(output.getvalue())["reused"])
        output = io.StringIO()
        with redirect_stdout(output), mock.patch.object(focused_unit, "run_focused") as runner:
            self.assertEqual(focused_unit.evidence(self.project, args), 0)
        runner.assert_not_called()
        self.assertTrue(json.loads(output.getvalue())["reused"])
        self.assertTrue(self.to("REVIEW").ok)
        self.assertTrue(self.to("SHIP").ok)

    def test_focused_execution_receipt_satisfies_source_coverage(self):
        from saipen_engine import focused_unit, intake

        captured = intake.capture(self.project, "Proportional verification",
                                  work="T-7", force=True)
        self.assertTrue(captured["ok"], captured)
        receipt = captured["receipt"]
        added = intake.add_requirement(self.project, receipt, rid="R001",
                                       text="Proportional verification")
        self.assertTrue(added["ok"], added)
        self.assertTrue(self.to("VERIFY").ok)
        args = Namespace(pattern=["test_focus.py"], timeout=30,
                         ticket="T-7", agent="tester", fresh=False)
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(focused_unit.evidence(self.project, args), 0)
        reference = json.loads(output.getvalue())["record"]
        result = intake.set_disposition(
            self.project, receipt, "R001", "IMPLEMENTED", work="T-7",
            evidence=reference, verification=f"record:{reference}",
        )
        self.assertTrue(result["ok"], result)

    def test_real_focused_runner_executes_only_selected_tests_and_detects_red(self):
        from saipen_engine.focused_unit import run_focused

        # An unrelated broken module must not run in this local check.
        (self.project / "tools/test_other.py").write_text("raise RuntimeError('unrelated')\n")
        clean = run_focused(self.project, ["test_focus.py"], timeout=30)
        self.assertEqual(clean["ran"], 1)
        self.assertEqual(clean["verdict"], "PASS")
        self.assertEqual(clean["fingerprint"], core_unit.tree_fingerprint(self.project))
        target = self.project / "tools/test_focus.py"
        target.write_text(target.read_text().replace("2 + 2, 4", "2 + 2, 5"))
        broken = run_focused(self.project, ["test_focus.py"], timeout=30)
        self.assertEqual(broken["verdict"], "FAIL")
        self.assertIn("test_focus.Focus.test_ok", broken["runs"][0]["red"])

    def test_missing_pattern_and_empty_selection_refuse(self):
        from saipen_engine.focused_unit import run_focused

        for patterns in ([], ["missing.py"], ["../test_focus.py"]):
            with self.subTest(patterns=patterns), self.assertRaises(ValueError):
                run_focused(self.project, patterns, timeout=30)


class PublicationWiringTests(unittest.TestCase):
    def test_release_executor_refuses_before_external_validator(self):
        from saipen_engine import focused_unit, release

        with mock.patch.object(focused_unit, "publication_gate", return_value="full run missing"), \
                mock.patch.object(release.subprocess, "run") as external:
            result = release._run_gate(Path("."), "ship")
        self.assertFalse(result["ok"])
        self.assertIn("full run missing", result["detail"])
        external.assert_not_called()


if __name__ == "__main__":
    unittest.main()
