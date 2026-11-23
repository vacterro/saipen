"""Keep unavailable shell startup distinct from pipeline exit-code behavior."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


TOOLS = Path(__file__).resolve().parent
CASE = (
    "test_t1736_tool_safety_and_evidence.ToolSafetyAndEvidenceTests."
    "test_pipelined_validator_exit_status_preservation"
)


class PipelineShellProfiles(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="saipen-t1742-")
        self.root = Path(self.temporary.name).resolve()
        self.temp_root = Path(tempfile.gettempdir()).resolve()
        self.assertTrue(self.root.is_relative_to(self.temp_root))
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.assertTrue(self.root.resolve().is_relative_to(self.temp_root))
        self.temporary.cleanup()

    def run_subject(self, search_path):
        env = os.environ.copy()
        env["PATH"] = search_path
        env["PYTHONPATH"] = os.pathsep.join(
            part for part in (str(TOOLS), env.get("PYTHONPATH", "")) if part
        )
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [sys.executable, "-B", "-m", "unittest", CASE],
            cwd=TOOLS, env=env, capture_output=True, text=True, encoding="utf-8",
            timeout=30, check=False,
            stdin=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        failure = next(
            (line for line in result.stderr.splitlines() if line.startswith("AssertionError:")),
            "subject subprocess failed; no assertion diagnostic",
        )
        self.assertEqual(result.returncode, 0, f"Subject exit {result.returncode}: {failure}")
        self.assertIn("Ran 1 test", result.stderr)
        self.assertRegex(result.stderr, r"(?m)^OK$")

    def test_missing_shell_preserves_the_real_python_exit_pair(self):
        empty = self.root / "empty"
        empty.mkdir()
        self.run_subject(str(empty))

    def test_unusable_shell_is_not_mistaken_for_a_pipeline_failure(self):
        bad = self.root / "unusable"
        bad.mkdir()
        if os.name == "nt":
            (bad / "bash.cmd").write_text("@echo off\nexit /b 75\n", encoding="ascii")
        else:
            proxy = bad / "bash"
            proxy.write_text("#!/bin/sh\nexit 75\n", encoding="ascii")
            proxy.chmod(0o700)
        self.run_subject(str(bad))

    def test_runnable_native_shell_preserves_pipeline_and_direct_failures(self):
        if os.name == "nt":
            candidate = (
                Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Git/bin/bash.exe"
            )
        else:
            found = shutil.which("bash")
            candidate = Path(found) if found else None
        if candidate is None or not candidate.is_file():
            self.skipTest("native Bash positive control is not installed on this host")
        paths = [str(candidate.parent)]
        if os.name == "nt":
            paths.append(str(candidate.parent.parent / "usr/bin"))
        paths.append(os.environ.get("PATH", ""))
        self.run_subject(os.pathsep.join(paths))


if __name__ == "__main__":
    unittest.main()
