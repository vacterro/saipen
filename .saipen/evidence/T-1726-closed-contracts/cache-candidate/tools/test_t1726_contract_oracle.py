"""Unchanged native CLI oracle for the SRC-225 before/after execution pair."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from saipen_engine.paths import unbound_environment
from test_work_reverify_cli import _make_project


class NativeClosedContractOracle(unittest.TestCase):
    def test_native_reverify_binds_current_behavior_and_detects_later_failure(self):
        with tempfile.TemporaryDirectory(prefix="closed-reverify-oracle-") as temporary:
            root = _make_project(Path(temporary))
            subject = root / "subject.py"
            subject.write_text("VALUE = 7\n", encoding="utf-8")
            (root / "test_probe.py").write_text(
                "import unittest\nfrom subject import VALUE\n"
                "class Test(unittest.TestCase):\n"
                "    def test_contract(self): self.assertEqual(VALUE, 7)\n", encoding="utf-8")
            contract = root / ".saipen/evidence/contract.json"
            contract.parent.mkdir(parents=True, exist_ok=True)
            contract.write_text(json.dumps({
                "schema": 1, "command": ["{python}", "-B", "-m", "unittest", "test_probe"],
                "format": "unittest", "context": ["subject.py", "test_probe.py"],
                "oracle_files": ["test_probe.py"], "subject_files": ["subject.py"], "timeout": 20,
            }), encoding="utf-8")
            argv = [sys.executable, "-B", str(Path(__file__).parent / "saipen.py"),
                    "--project-root", str(root), "--agent", "tester", "--json", "work", "reverify",
                    "T-001", "--contract", str(contract)]
            for expected, content in (("CURRENT_PASS", "VALUE = 7\n"),
                                      ("CURRENT_REGRESSION", "VALUE = 99\n")):
                subject.write_text(content, encoding="utf-8")
                result = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                                        env=unbound_environment(), timeout=90)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(json.loads(result.stdout)["closed_contract"]["status"], expected)
            generic = subprocess.run(argv[:-2], capture_output=True, text=True, encoding="utf-8",
                                     env=unbound_environment(), timeout=90)
            self.assertEqual(generic.returncode, 0, generic.stdout + generic.stderr)
            self.assertEqual(json.loads(generic.stdout)["verdict"], "FAIL")

    def test_closed_contract_diagnostic_is_reachable_and_read_only(self):
        with tempfile.TemporaryDirectory(prefix="closed-contract-oracle-") as temporary:
            root = _make_project(Path(temporary))
            before = {path.relative_to(root): path.read_bytes()
                      for path in root.rglob("*") if path.is_file()}
            result = subprocess.run(
                [sys.executable, "-B", str(Path(__file__).parent / "saipen.py"),
                 "--project-root", str(root), "--json", "work", "contracts", "T-001"],
                capture_output=True, text=True, encoding="utf-8",
                env=unbound_environment(), timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            body = json.loads(result.stdout)
            self.assertFalse(body["blocks_unrelated_work"])
            self.assertEqual(body["rows"][0]["status"], "UNVERIFIED")
            self.assertEqual(before, {path.relative_to(root): path.read_bytes()
                                     for path in root.rglob("*") if path.is_file()})


if __name__ == "__main__":
    unittest.main()
