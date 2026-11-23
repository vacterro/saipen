"""Long-suite preflight and a replay of the stub-mismatch failure loop."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from saipen_engine import suite_record as SR
from saipen_engine import test_runner as TR
from saipen_engine.command_effects import classify_tokens
from saipen_engine.suite_preflight import affected


class SuitePreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="saipen-preflight-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / ".saipen").mkdir()

    def write(self, path, text):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def git(self, *words):
        subprocess.run(
            ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid", *words],
            cwd=self.root, stdin=subprocess.DEVNULL, capture_output=True, check=True, timeout=30,
        )

    def declare(self, text):
        self.write("suite.py", text)
        SR.declare(self.root, [sys.executable, "-B", "suite.py"])

    def test_stub_mismatch_stops_before_sibling_and_reaps_descendants(self):
        # The sentinel lives outside the subject; cleanup must reap the child
        # before it can start the next slow fixture.
        sentinel = self.root.parent / (self.root.name + "-sibling")
        self.addCleanup(sentinel.unlink, missing_ok=True)
        child = f"import time,pathlib;time.sleep(3);pathlib.Path({str(sentinel)!r}).touch()"
        self.declare(
            "import sys,subprocess,time\n"
            f"subprocess.Popen([sys.executable, '-c', {child!r}])\n"
            "print(\"FAIL: NativeMissionRouterTests: stub DllBase.cpp lacks vrv::satmap\", "
            "file=sys.stderr, flush=True)\n"
            "time.sleep(4)\n"
        )
        started = time.monotonic()
        written = SR.write_record(self.root, SR.run(self.root, fail_fast=True))
        self.assertLess(time.monotonic() - started, 3)
        record = written["record"]
        self.assertEqual(record["verdict"], "FAIL")
        self.assertTrue(record["stopped_on_failure"])
        self.assertIn("NativeMissionRouterTests", record["first_failure_line"])
        time.sleep(3.1)
        self.assertFalse(sentinel.exists(), "a surviving descendant started the next fixture")
        self.assertIsNone(SR.reusable_record(self.root)[0])

    def test_fail_line_with_exit_zero_is_partial_fail(self):
        self.declare("print('FAIL: fixture stub mismatch', flush=True)\n")
        record = SR.write_record(self.root, SR.run(self.root, fail_fast=True))["record"]
        self.assertEqual(record["verdict"], "FAIL")

    def test_timings_survive_output_tail_and_overhead_is_separate(self):
        self.declare(
            "print('SAIPEN-SCRIPT {\"script\":\"Test-GamePrefs.ps1\",\"duration_s\":1.25}')\n"
            "print('DURATION: Test-NativeMissionRouter.ps1 2.50s')\n"
            "print('SAIPEN-SCRIPT {\"script\":\"bad\",\"duration_s\":NaN}')\n"
            "print('x' * 100000)\n"
            "print('2 passed in 3.75s')\n"
        )
        written = SR.write_record(self.root, SR.run(self.root))
        record = json.loads((self.root / written["path"]).read_text(encoding="utf-8"))
        self.assertEqual(record["scripts"], [
            {"script": "Test-GamePrefs.ps1", "duration_s": 1.25},
            {"script": "Test-NativeMissionRouter.ps1", "duration_s": 2.5},
        ])
        self.assertTrue(record["script_timings_available"])
        self.assertGreaterEqual(record["process_s"], 0)
        self.assertEqual(set(record["overhead_s"]), {"pre_hash", "post_hash", "parsing", "total"})
        self.assertEqual(SR._summary(written)["duration_s"], record["duration_s"])

    def test_opaque_runner_has_no_invented_script_timings(self):
        self.declare("print('PASS: no timing reports')\n")
        record = SR.run(self.root, fail_fast=True)
        self.assertEqual(record["status"], "PASS")
        self.assertEqual(record["scripts"], [])
        self.assertFalse(record["script_timings_available"])

    def test_affected_covers_staged_unstaged_untracked_and_sibling_fixtures(self):
        self.declare("print('PASS')\n")
        self.write("src/DllBase.cpp", "void load() {}\n")
        self.write("src/Table.cpp", "const int kLINE_COUNT = 132;\n")
        self.write("tests/NativeFixture.cpp", '// cuts DllBase.cpp\n')
        self.write("tests/Test-Native.ps1", "# NativeFixture.cpp\n")
        self.write("tests/Test-Classic.ps1", "# copies DllBase.cpp\n")
        self.write("tests/Test-Prefs.ps1", "# kLINE_COUNT asserted against 132\n")
        self.write("tests/Test-NewSymbol.ps1", "# vrv::satmap\n")
        self.write("tests/Test-Other.ps1", "# unrelated\n")
        self.git("init", "-q")
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")
        self.write("src/DllBase.cpp", "void load() { vrv::satmap(); }\n")
        self.git("add", "src/DllBase.cpp")
        self.write("src/Table.cpp", "const int kLINE_COUNT = 133;\n")
        self.write("src/New.cpp", "void f() { vrv::satmap(); }\n")
        result = affected(self.root)
        self.assertEqual(set(result["scripts"]), {
            "tests/Test-Native.ps1", "tests/Test-Classic.ps1",
            "tests/Test-Prefs.ps1", "tests/Test-NewSymbol.ps1",
        })
        self.assertEqual(set(result["changed_paths"]), {
            "src/DllBase.cpp", "src/Table.cpp", "src/New.cpp",
        })
        self.assertFalse(result["executed"])
        self.assertTrue(result["limitations"])

    def test_cli_dry_run_and_read_only_classification(self):
        self.declare("raise RuntimeError('must not execute')\n")
        result, code = SR.cli(
            self.root, ["run", "T-2019", "--fail-fast"], agent="tester", dry_run=True
        )
        self.assertEqual(code, 0)
        self.assertTrue(result["fail_fast"])
        self.assertEqual(classify_tokens("saipen test suite affected T-2019".split()), "DIAGNOSTIC")
        result, code = SR.cli(self.root, ["affected", "oops"], agent="tester")
        self.assertEqual(code, 2)

    def test_affected_does_not_propose_the_full_entrypoint_as_a_subset(self):
        self.write("tests/Run-All.ps1", "# Test-Native.ps1\n")
        self.write("tests/Test-Native.ps1", "# DllBase.cpp\n")
        self.write("tests/New-Settings.ps1", "# generator reading DllBase.cpp\n")
        self.write("DllBase.cpp", "void load() {}\n")
        SR.declare(self.root, ["pwsh", "-File", "tests/Run-All.ps1"])
        self.git("init", "-q")
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")
        self.write("DllBase.cpp", "void load() { vrv::satmap(); }\n")
        result = affected(self.root)
        self.assertEqual(result["scripts"], ["tests/Test-Native.ps1"])
        entry = next(item for item in result["candidates"] if item["suite_entrypoint"])
        self.assertEqual(entry["path"], "tests/Run-All.ps1")

    def test_fail_fast_preserves_timeout_when_no_fail_is_printed(self):
        self.declare("import time; time.sleep(30)\n")
        record = SR.write_record(self.root, SR.run(self.root, fail_fast=True, timeout=1))["record"]
        self.assertEqual((record["status"], record["verdict"]), ("TIMEOUT", "FAIL"))
        self.assertFalse(record["stopped_on_failure"])

    def test_failure_grammar_accepts_powershell_errors_but_not_source_excerpts(self):
        for line in (
            b"FAIL: stub mismatch", b"Exception: FAIL: stub mismatch",
            b"Write-Error: FAIL: stub mismatch", b"    | FAIL: stub mismatch",
            b"\x1b[31mFAIL: stub mismatch\x1b[0m",
        ):
            with self.subTest(line=line):
                self.assertTrue(TR._failure_line(line))
        for line in (b'11 | throw "FAIL: $Text"', b"# FAIL example", b"FAILURE count: 0"):
            with self.subTest(line=line):
                self.assertFalse(TR._failure_line(line))

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 unavailable")
    def test_powershell_stub_error_stops_before_next_fixture(self):
        self.write("suite.ps1", "Write-Error 'FAIL: stub DllBase.cpp lacks vrv::satmap' "
                   "-ErrorAction Continue\nStart-Sleep -Seconds 30\n")
        SR.declare(self.root, ["pwsh", "-NoProfile", "-File", "suite.ps1"])
        started = time.monotonic()
        record = SR.write_record(self.root, SR.run(self.root, fail_fast=True))["record"]
        self.assertLess(time.monotonic() - started, 10)
        self.assertEqual(record["verdict"], "FAIL")
        self.assertTrue(record["stopped_on_failure"])
        self.assertIn("FAIL:", record["first_failure_line"])

    def test_ignored_nested_suite_repository_is_included(self):
        self.write(".gitignore", "/vrv/\n")
        self.write("vrv/tools/Run-All.ps1", "# Test-Native.ps1\n")
        self.write("vrv/tools/Test-Native.ps1", "# DllBase.cpp\n")
        self.write("vrv/DllBase.cpp", "void load() {}\n")
        self.git("init", "-q")
        self.git("add", ".")
        self.git("commit", "-qm", "outer")
        self.git("-C", "vrv", "init", "-q")
        self.git("-C", "vrv", "add", ".")
        self.git("-C", "vrv", "commit", "-qm", "nested")
        SR.declare(self.root, ["pwsh", "-File", "vrv/tools/Run-All.ps1"])
        self.write("vrv/DllBase.cpp", "void load() { vrv::satmap(); }\n")
        result = affected(self.root)
        self.assertEqual(result["scripts"], ["vrv/tools/Test-Native.ps1"])
        self.assertIn("vrv/DllBase.cpp", result["changed_paths"])
        self.assertEqual(set(result["repositories"]), {".", "vrv"})

    def test_rule_owner_requires_subset_and_failed_script_before_full_run(self):
        home = Path(__file__).resolve().parent.parent
        text = (home / "saipen/phases/verify.md").read_text(encoding="utf-8")
        registry = json.loads((home / "saipen/REGISTRY.json").read_text(encoding="utf-8"))
        self.assertEqual(registry["rule_owners"]["SUITE-PREFLIGHT-01"], "saipen/phases/verify.md")
        section = text.split("<!-- RULE-OWNER: SUITE-PREFLIGHT-01 -->", 1)[1].split("\n### ", 1)[0]
        expected_text = (
            "300 seconds", "subset passes", "only the failing script", "sibling fixtures"
        )
        for expected in expected_text:
            self.assertIn(expected, section)


if __name__ == "__main__":
    unittest.main()
