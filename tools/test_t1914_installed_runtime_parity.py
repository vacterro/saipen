"""T-1914 (SRC-324 Gap E): installed-runtime parity verification.

Verify clause:
    a recorded parity report names each of E01-E10 with the observed value and
    the command that measured it, and any drift between source and installed
    runtime is reported as blocking rather than assumed equal.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from test_hermetic_env import isolate_host_session  # noqa: E402

ROOT = TOOLS.parent
REPORT_PATH = ROOT / ".saipen" / "evidence" / "T-1914-installed-runtime-parity" / "REPORT.md"
MANIFEST_PATH = ROOT / ".saipen" / "evidence" / "T-1914-installed-runtime-parity" / "parity.json"


def setUpModule() -> None:
    isolate_host_session()


class InstalledRuntimeParityTests(unittest.TestCase):
    def test_report_artifact_exists(self) -> None:
        self.assertTrue(REPORT_PATH.is_file(), f"Missing report at {REPORT_PATH}")
        self.assertTrue(MANIFEST_PATH.is_file(), f"Missing manifest at {MANIFEST_PATH}")

    def test_report_names_all_clauses_e01_through_e10(self) -> None:
        content = REPORT_PATH.read_text(encoding="utf-8")
        for i in range(1, 11):
            clause = f"E{i:02d}"
            self.assertIn(clause, content, f"Missing clause {clause} in parity report")

    def test_report_contains_measured_values_and_commands(self) -> None:
        content = REPORT_PATH.read_text(encoding="utf-8")
        self.assertIn("python -c", content)
        self.assertIn("hashlib.sha256", content)
        self.assertIn("fad31c4af85db4e9c7974efa0989ab39e334b414c147224755d4f4c2b1bd819e", content)
        self.assertIn("f99b50c60b9e64360d9a5d401cba8a5b1b4ffba63034b2caddfac3e48d41391e", content)
        self.assertIn("0f8d854d69fed1bf190e78b7c35ca04808fe9cc9f03418e93c6ae261e4077eb2", content)
        self.assertIn("svc-d86cd9f97afc8f881fab7843", content)
        self.assertIn("ZAICODE.exe", content)
        self.assertIn("UserPromptSubmit", content)
        self.assertIn("(None, 'absent')", content)

    def test_drift_reported_as_blocking(self) -> None:
        content = REPORT_PATH.read_text(encoding="utf-8")
        self.assertIn("BLOCKING", content)
        self.assertIn("DRIFT DETECTED", content)
        self.assertIn("source parity is not running-process parity", content.lower())

    def test_parity_json_manifest_structure(self) -> None:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertEqual(data.get("ticket"), "T-1914")
        self.assertEqual(data.get("source_receipt"), "SRC-324")
        self.assertEqual(data.get("disposition"), "BLOCKING")
        clauses = data.get("clauses", {})
        for i in range(1, 11):
            clause = f"E{i:02d}"
            self.assertIn(clause, clauses)


if __name__ == "__main__":
    unittest.main()
