"""The canonical lint surface lints what it says it lints (T-1571).

`python -m ruff check tools/ tests/` is the lint gate the harness card and CI
name. An allowlist in `ruff.toml` (`include = [validate.py, run_scenarios.py]`)
quietly narrowed it to two files, so every "ruff clean" reported since spoke
for those two while 400+ engine and test files went unscanned -- and a line
of 3.10-only syntax sat under the 3.8 floor unnoticed.

Pinned here, against the live `ruff.toml`:

- INVENTORY: the files ruff discovers are exactly the Python files under
  tools/ and tests/, minus the named exclusions (generated `.saipen`
  evidence, the byte-frozen tests/fixtures subjects).
- INJECTION: a violation planted in an engine file and in a test file is
  reported for both.
- FLOOR: the 3.8 target still rejects syntax newer than 3.8.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "ruff.toml"
SURFACE = ("tools/", "tests/")
EXCLUDED = ("tests/fixtures/",)


def _ruff_binary() -> str | None:
    """The ruff executable itself -- the one `python -m ruff` launches.

    Not `python -m ruff`: under the canonical test child every Popen gains
    CREATE_NO_WINDOW (`test_runner._install_quiet_child_site`), and on Windows
    the module re-spawns ruff.exe without stdio handles, so it exits 0 with
    EMPTY output -- which reads exactly like "no findings". Measured in the
    first T-1571 core run. The binary with captured pipes reports normally.
    """
    try:
        from ruff.__main__ import find_ruff_bin

        return os.fsdecode(find_ruff_bin())
    except (ImportError, FileNotFoundError):
        return shutil.which("ruff")


def _ruff(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_ruff_binary() or "ruff", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
    )


def _ruff_available() -> bool:
    """Available means it SPEAKS: a silent exit 0 is not a working linter."""
    if _ruff_binary() is None:
        return False
    try:
        return _ruff("--version", cwd=ROOT).stdout.startswith("ruff ")
    except (OSError, subprocess.SubprocessError):
        return False


def _relative(output: str, root: Path) -> set[str]:
    found = set()
    for raw in output.splitlines():
        line = raw.strip()
        if not line:
            continue
        path = Path(line)
        try:
            found.add(path.resolve().relative_to(root.resolve()).as_posix())
        except ValueError:
            continue
    return found


@unittest.skipUnless(_ruff_available(), "ruff is not installed: the lint surface is UNPROVEN here")
class CanonicalSurface(unittest.TestCase):
    def test_discovery_is_every_python_file_under_tools_and_tests(self) -> None:
        done = _ruff("check", *SURFACE, "--show-files", cwd=ROOT)
        discovered = _relative(done.stdout, ROOT)
        expected = {
            path.relative_to(ROOT).as_posix()
            for base in SURFACE
            for path in (ROOT / base).rglob("*.py")
            if "__pycache__" not in path.parts
        }
        expected = {path for path in expected if not path.startswith(EXCLUDED)}
        self.assertEqual(discovered, expected)
        # Representative owners, so a shrunken surface cannot pass vacuously.
        for path in (
            "tools/validate.py",
            "tools/saipen_engine/journal.py",
            "tools/saipen_engine/response_surface.py",
            "tools/test_t1571_lint_surface.py",
            "tests/test_audit_2026_08_23.py",
        ):
            self.assertIn(path, discovered)
        self.assertNotIn("tests/fixtures/t1563-vulnerable/protocol_admission.py", discovered)

    def test_the_python_floor_is_retained(self) -> None:
        text = CONFIG.read_text(encoding="utf-8")
        self.assertRegex(text, r'(?m)^target-version = "py38"$')
        self.assertIsNone(re.search(r"(?m)^include\s*=", text), "an allowlist narrows the surface")


@unittest.skipUnless(_ruff_available(), "ruff is not installed: the lint surface is UNPROVEN here")
class InjectedViolations(unittest.TestCase):
    """A planted violation is reported wherever it is planted."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="saipen-t1571-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        shutil.copy2(CONFIG, self.root / "ruff.toml")
        (self.root / "tools" / "saipen_engine").mkdir(parents=True)
        (self.root / "tests" / "fixtures").mkdir(parents=True)
        # The two scripts the old allowlist kept, clean, so only the planted
        # files can produce a finding.
        for name in ("validate.py", "run_scenarios.py"):
            (self.root / "tools" / name).write_text('"""Clean."""\n', encoding="utf-8")

    def _plant(self, relative: str, source: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")

    def _findings(self) -> str:
        done = _ruff("check", *SURFACE, "--output-format", "concise", cwd=self.root)
        return (done.stdout + done.stderr).replace("\\", "/")

    def test_an_engine_file_and_a_test_file_are_both_linted(self) -> None:
        self._plant("tools/saipen_engine/planted.py", "import os\n")
        self._plant("tools/test_planted.py", "import sys\n")
        out = self._findings()
        self.assertIn("tools/saipen_engine/planted.py", out)
        self.assertIn("tools/test_planted.py", out)
        self.assertEqual(out.count("F401"), 2, out)

    def test_an_excluded_fixture_is_not_linted(self) -> None:
        self._plant("tests/fixtures/frozen.py", "import os\n")
        self.assertNotIn("frozen.py", self._findings())

    def test_syntax_newer_than_the_floor_is_reported(self) -> None:
        self._plant(
            "tools/test_floor.py",
            "import contextlib\n\n"
            "with (\n    contextlib.nullcontext(),\n    contextlib.nullcontext(),\n):\n    pass\n",
        )
        self.assertIn("tools/test_floor.py", self._findings())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
