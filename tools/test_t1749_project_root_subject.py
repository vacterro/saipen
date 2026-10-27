"""T-1749: runtime-home scratch never decides a consumer's conformance."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from test_hermetic_env import isolate_host_session  # noqa: E402
from test_validator_layout_parity import (  # noqa: E402
    _build_home,
    _capture_findings,
    _neutral_project,
    _problem_keys,
)


def setUpModule():
    isolate_host_session()


class ValidatedProjectRoot(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="t1749-")
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.home = self.base / "home"
        self.home.mkdir()
        _build_home(self.home, flatten=False)
        self.consumer = _neutral_project(self.base / "consumer")

    def findings(self, project, label):
        output = self.base / (label + ".json")
        run = _capture_findings(self.home, project, output)
        self.assertTrue(output.is_file(), run.stdout + run.stderr)
        self.assertNotIn("Traceback", run.stderr)
        return json.loads(output.read_text(encoding="utf-8"))

    def root_findings(self, data):
        return [p for p in data.get("problems", []) if "[root-file-set]" in p.get("detail", "")]

    def test_runtime_spools_do_not_change_consumer_findings(self):
        clean = self.findings(self.consumer, "clean")
        for name in (".stdout", ".stderr", "stray-home-only.txt"):
            (self.home / name).write_bytes(b"")
        noisy = self.findings(self.consumer, "noisy")
        self.assertFalse(self.root_findings(noisy), noisy)
        self.assertEqual(_problem_keys(clean), _problem_keys(noisy))

    def test_the_same_runtime_home_still_reports_its_own_stray(self):
        _neutral_project(self.home)
        (self.home / "stray-home-only.txt").write_bytes(b"")
        findings = self.root_findings(self.findings(self.home, "self"))
        self.assertEqual(len(findings), 1, findings)
        self.assertIn("stray-home-only.txt", findings[0]["detail"])

    def test_another_source_project_is_judged_by_its_own_root(self):
        marker = self.consumer / "saipen/RFC.md"
        marker.parent.mkdir()
        marker.write_text("layout marker\n", encoding="utf-8")
        (self.consumer / "stray-project-only.txt").write_bytes(b"")
        (self.home / "stray-home-only.txt").write_bytes(b"")
        findings = self.root_findings(self.findings(self.consumer, "other-source"))
        self.assertEqual(len(findings), 1, findings)
        self.assertIn("stray-project-only.txt", findings[0]["detail"])
        self.assertNotIn("stray-home-only.txt", findings[0]["detail"])


if __name__ == "__main__":
    unittest.main()
