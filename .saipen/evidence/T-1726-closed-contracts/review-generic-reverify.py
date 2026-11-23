import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import closed_contracts, debt
from saipen_engine.paths import unbound_environment
from test_work_reverify_cli import _make_project

with tempfile.TemporaryDirectory(prefix="closed-negative-review-") as temporary:
    root = _make_project(Path(temporary))
    subject = root / "subject.py"
    subject.write_text("VALUE=7\n", encoding="utf-8")
    (root / "test_probe.py").write_text(
        "import unittest\nfrom subject import VALUE\nclass Test(unittest.TestCase):\n"
        "    def test_contract(self): self.assertEqual(VALUE, 7)\n", encoding="utf-8")
    contract = root / ".saipen/evidence/check.json"
    contract.parent.mkdir(parents=True, exist_ok=True)
    contract.write_text(json.dumps({
        "schema": 1, "command": ["{python}", "-B", "-m", "unittest", "test_probe"],
        "format": "unittest", "context": ["subject.py", "test_probe.py"],
        "oracle_files": ["test_probe.py"], "subject_files": ["subject.py"], "timeout": 20,
    }), encoding="utf-8")
    with patch.dict(os.environ, unbound_environment(), clear=True), patch.object(
        debt, "capture_findings", return_value={"ok": True, "exit_code": 0,
        "gate": "core", "problems": [], "warnings": []}
    ):
        first = debt.reverify_work(root, "T-001", "tester", contract_path=contract)
        subject.write_text("VALUE=99\n", encoding="utf-8")
        negative = debt.reverify_work(root, "T-001", "tester", contract_path=contract)
        generic = debt.reverify_work(root, "T-001", "tester", derive_default=True)
        observation = closed_contracts.inspect(root, "T-001")
        print(json.dumps({"baseline": first["closed_contract"]["status"],
                          "negative": negative["closed_contract"]["status"],
                          "generic_verdict": generic["verdict"], "observation": observation}, indent=2))
        assert generic["verdict"] == "FAIL", "generic strict PASS concealed a current focused failure"
