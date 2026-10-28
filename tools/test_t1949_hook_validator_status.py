"""T-1949: a failing validator must never be masked by a passing one.

The pre-commit hook runs two validators: `tools/validate.py` when Python exists,
then the portable floor `tests/validate.sh`. They used to write their exit
status into ONE shell variable, so the floor's green overwrote a red Python
gate and the hook exited 0 -- and `git commit` went through. Measured on
2026-10-28: `tools/validate.py` exited 1 on the pre-existing EX-000022 closure
provenance FAIL, `tests/validate.sh` exited 0, and the commit landed with no
warning. That is precisely the "unvalidated commit that LOOKS validated" the
hook's own comments say the protocol keeps digging out.

The hook text is baked into `.git/hooks/pre-commit` at install time, so a test
of the installer's string would not prove what a commit actually does. Each case
below installs the hook into a throwaway project and RUNS it, which is the only
way to show which exit status a real commit would see.

Ordering matters and is asserted in both directions: red-then-green is the case
that failed, and green-then-red is its mirror, so a fix that merely recorded the
LAST validator instead of the worst one would still be caught.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "tools" / "install_hook.py"

PASSING_PY = "import sys\nprint('PY-VALIDATOR-OK')\nsys.exit(0)\n"
FAILING_PY = "import sys\nprint('PY-VALIDATOR-RED')\nsys.exit(1)\n"
PASSING_SH = "#!/bin/sh\necho FLOOR-OK\nexit 0\n"
FAILING_SH = "#!/bin/sh\necho FLOOR-RED\nexit 1\n"


def _sh():
    """The interpreter git itself would use to run a `#!/bin/sh` hook."""
    return shutil.which("bash") or shutil.which("sh")


class HookValidatorStatusTests(unittest.TestCase):
    """Install the real hook into a sandbox and observe its exit status."""

    def _install_and_run(self, py_body: str, sh_body: str):
        shell = _sh()
        if shell is None:
            self.skipTest("no POSIX shell to run a /bin/sh hook")
        with tempfile.TemporaryDirectory(prefix="t1949-hook-") as raw:
            root = Path(raw)
            home = root / "saipen-home"
            (home / "tools").mkdir(parents=True)
            (home / "tests").mkdir()
            shutil.copy2(INSTALLER, home / "tools" / "install_hook.py")
            (home / "tools" / "validate.py").write_text(py_body, encoding="utf-8", newline="\n")
            (home / "tests" / "validate.sh").write_text(sh_body, encoding="utf-8", newline="\n")

            project = root / "project"
            (project / ".saipen").mkdir(parents=True)
            subprocess.run(["git", "init", "-q"], cwd=project, check=True)
            install = subprocess.run(
                [sys.executable, str(home / "tools" / "install_hook.py")],
                cwd=project,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertEqual(install.returncode, 0, install.stdout + install.stderr)
            hook = project / ".git" / "hooks" / "pre-commit"
            self.assertTrue(hook.is_file(), "installer wrote no hook")

            run = subprocess.run(
                [shell, str(hook)],
                cwd=project,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            return run.returncode, run.stdout + run.stderr

    def test_a_red_python_gate_is_not_masked_by_a_green_floor(self):
        # The measured defect. Before the fix this returned 0 and printed
        # nothing, because the floor's success replaced the Python failure.
        code, output = self._install_and_run(FAILING_PY, PASSING_SH)
        self.assertNotEqual(code, 0, "a failing validate.py did not block the commit:\n" + output)
        self.assertIn("validate.py", output, "the refusal does not name the failing validator")
        self.assertIn("PY-VALIDATOR-RED", output)

    def test_a_red_floor_is_not_masked_by_a_green_python_gate(self):
        # The mirror: a fix that kept only the LAST status would pass the first
        # test and fail here.
        code, output = self._install_and_run(PASSING_PY, FAILING_SH)
        self.assertNotEqual(code, 0, "a failing validate.sh did not block the commit:\n" + output)
        self.assertIn("validate.sh", output, "the refusal does not name the failing validator")
        self.assertIn("FLOOR-RED", output)

    def test_both_green_lets_the_commit_through(self):
        # Control: the gate must not become unconditional. Without this the two
        # refusals above would be satisfied by a hook that always exits 1.
        code, output = self._install_and_run(PASSING_PY, PASSING_SH)
        self.assertEqual(code, 0, "a passing hook blocked the commit:\n" + output)
        self.assertIn("PY-VALIDATOR-OK", output)
        self.assertIn("FLOOR-OK", output)


if __name__ == "__main__":
    unittest.main()
