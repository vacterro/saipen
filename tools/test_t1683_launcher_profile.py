"""T-1683: an injector's Python child cannot escape its selected user home."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from saipen_engine import path_launcher as PL
from test_hermetic_env import isolate_host_session

ROOT = Path(__file__).resolve().parent.parent
WINDOWS = os.name == "nt"
BASH = (str(Path("C:/Program Files/Git/bin/bash.exe"))
        if WINDOWS and Path("C:/Program Files/Git/bin/bash.exe").is_file()
        else shutil.which("bash"))
POWERSHELL = shutil.which("powershell") if WINDOWS else shutil.which("pwsh")


def setUpModule():
    isolate_host_session()


class InjectorProfileOwnership(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="t1683-profile-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.target, self.protected = self.base / "selected home", self.base / "protected home"
        self.target.mkdir()
        self.protected.mkdir()
        self.target_bin = PL.declared_dirs(self.target)[0]
        self.protected_bin = PL.declared_dirs(self.protected)[0]
        self.path = os.pathsep.join((str(self.target_bin), str(self.protected_bin),
                                    os.environ.get("PATH", "")))
        old_engine = self.base / "old engine" / "tools" / "saipen.py"
        old_engine.parent.mkdir(parents=True)
        old_engine.write_text("print('old fixture engine')\n", encoding="utf-8")
        answer = PL.install(old_engine, self.protected, {"PATH": self.path})
        self.assertTrue(answer["ok"], answer)
        self.before = self.protected_bytes()

    def protected_bytes(self):
        return {path.relative_to(self.protected).as_posix(): path.read_bytes()
                for path in self.protected.rglob("*") if path.is_file()}

    def environment(self, *, bash):
        env = {key: value for key, value in os.environ.items() if not key.startswith("SAIPEN_")}
        # Deliberately disagree, matching the measured Windows Bash boundary.
        env.update(
            HOME=str(self.target if bash else self.protected),
            USERPROFILE=str(self.protected if bash else self.target),
            PATH=self.path, PYTHONUTF8="1", PYTHONIOENCODING="utf-8",
            SAIPEN_TEST_ROOT=str(ROOT).replace("\\", "/"),
            SAIPEN_TEST_PYTHON=sys.executable.replace("\\", "/"),
            SAIPEN_PYTHON=sys.executable,
        )
        return env

    def assert_selected_profile_only(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.protected_bytes(), self.before,
                         "injector overwrote the other profile's owned launcher")
        view = PL.status(ROOT / "tools" / "saipen.py", self.target, {"PATH": self.path})
        self.assertEqual(view["code"], PL.CODE_READY, result.stdout + repr(view))

    def run_bash(self, *, explicit_python):
        source = (ROOT / "bootstrap" / "inject.sh").read_text(encoding="utf-8")
        start = source.index("install_path_launcher() {")
        end = source.index('\nif [ -z "$ADAPTER_FILTER" ]; then', start)
        program = ('ROOT="$SAIPEN_TEST_ROOT"\nPYTHON_BIN="$SAIPEN_TEST_PYTHON"\n'
                   + source[start:end] + "\ninstall_path_launcher\n")
        environment = self.environment(bash=True)
        if not explicit_python:
            environment.pop("SAIPEN_PYTHON")
        result = subprocess.run(
            [BASH, "-c", program], env=environment, cwd=self.base,
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=120,
        )
        self.assert_selected_profile_only(result)

    @unittest.skipUnless(BASH, "Bash runtime unavailable")
    def test_bash_names_its_home_with_an_explicit_python_interpreter(self):
        self.run_bash(explicit_python=True)

    @unittest.skipUnless(BASH, "Bash runtime unavailable")
    def test_bash_names_its_home_with_the_detected_python_interpreter(self):
        self.run_bash(explicit_python=False)

    @unittest.skipUnless(POWERSHELL, "PowerShell runtime unavailable")
    def test_powershell_names_its_userprofile_for_the_real_python_owner(self):
        source = (ROOT / "bootstrap" / "inject.ps1").read_text(encoding="utf-8-sig")
        start = source.index("function Install-PathLauncher {")
        end = source.index('\nif ([string]::IsNullOrWhiteSpace($AdapterId))', start)
        program = (
            'function Get-PythonBin { return $env:SAIPEN_TEST_PYTHON }\n'
            'function Get-SourcePath([string]$relative) { '
            'return (Join-Path $env:SAIPEN_TEST_ROOT $relative) }\n'
            + source[start:end] + "\nInstall-PathLauncher\n"
        )
        script = self.base / "launcher-boundary.ps1"
        script.write_text(program, encoding="utf-8")
        result = subprocess.run(
            [POWERSHELL, "-NoProfile", "-NonInteractive", "-File", str(script)],
            env=self.environment(bash=False), cwd=self.base,
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=120,
        )
        self.assert_selected_profile_only(result)


if __name__ == "__main__":
    unittest.main()
