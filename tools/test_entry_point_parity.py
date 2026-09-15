"""T-1339: both invocation forms of the tools package must resolve the engine.

Python puts the SCRIPT'S OWN directory on `sys.path` for `python tools/x.py`
and the REPOSITORY ROOT for `python -m tools.x`. Every module here imports
`saipen_engine` at top level, so the module form raised

    ModuleNotFoundError: No module named 'saipen_engine'

from the project's own CLI. Both spellings look supported and nothing says one
is not, so the traceback reads as a broken protocol install rather than as a
wrong invocation. The repository also disagreed with itself: test modules that
inserted the path by hand ran under `python -m unittest` while fourteen others
died on import.

`tools/__init__.py` owns the fix, and this suite pins the CONTRACT rather than
the files that happened to be noticed today:

  * importing the package makes the flat `saipen_engine` spelling RESOLVABLE,
    which is what every module in it needs;
  * the repository root stays ahead of it, so `tools.x` still resolves as
    `tools.x`;
  * the CLI answers identically under both forms;
  * test modules that used to die on import now run under `python -m unittest`.

Resolvability is checked with `find_spec`, never by importing each module:
several shipped modules are SCRIPTS that do their work at import time
(`validate.py` runs a whole gate), so importing them to prove a path contract
would execute the repository's gates as a side effect of a unit test.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent


def _modules_importing_the_engine() -> list[str]:
    """Shipped `tools/*.py` files whose top level imports `saipen_engine`.

    Parsed, never imported -- see the module docstring.
    """
    names: list[str] = []
    for path in sorted(TOOLS.glob("*.py")):
        if path.name == "__init__.py":
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                "saipen_engine"
            ):
                names.append(path.name)
                break
            if isinstance(node, ast.Import) and any(
                alias.name.startswith("saipen_engine") for alias in node.names
            ):
                names.append(path.name)
                break
    return names


class PackagePathContractTests(unittest.TestCase):
    def test_importing_the_package_resolves_the_engine_spelling(self):
        import tools  # noqa: F401 -- importing the package IS the contract

        self.assertIn(str(TOOLS), sys.path)
        self.assertIsNotNone(
            importlib.util.find_spec("saipen_engine"),
            "tools/__init__.py did not make `saipen_engine` resolvable",
        )

    def test_the_repository_root_stays_ahead_of_the_tools_directory(self):
        """Appended, never prepended: `tools.x` must still resolve as `tools.x`."""
        import tools  # noqa: F401

        if str(REPO) in sys.path:
            self.assertLess(sys.path.index(str(REPO)), sys.path.index(str(TOOLS)))

    def test_the_contract_covers_every_module_that_needs_it(self):
        """The fix is one owner, so the set it serves is measured, not listed."""
        needing = _modules_importing_the_engine()
        self.assertGreater(len(needing), 10, needing)
        self.assertIn("saipen.py", needing)
        self.assertIn("validate.py", needing)
        import tools  # noqa: F401

        self.assertIsNotNone(importlib.util.find_spec("saipen_engine"))


class CliInvocationParityTests(unittest.TestCase):
    def _status(self, argv: list[str]) -> dict:
        completed = subprocess.run(
            [sys.executable, *argv, "status", "--json"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=600,
        )
        self.assertEqual(
            completed.returncode,
            0,
            f"{argv} exited {completed.returncode}\n{completed.stderr[-1500:]}",
        )
        return json.loads(completed.stdout)

    def test_the_module_form_and_the_script_form_agree(self):
        script = self._status(["tools/saipen.py"])
        module = self._status(["-m", "tools.saipen"])
        for field in ("ok", "protocol_version", "phase", "task", "head"):
            self.assertEqual(script.get(field), module.get(field), field)

    def test_the_module_form_does_not_report_a_missing_engine(self):
        completed = subprocess.run(
            [sys.executable, "-m", "tools.saipen", "status", "--json"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=600,
        )
        self.assertNotIn("No module named", completed.stderr)
        self.assertNotIn("ModuleNotFoundError", completed.stderr)


class TestModuleFormTests(unittest.TestCase):
    """The exact modules that used to die on `python -m unittest`."""

    def _unittest(self, dotted: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "unittest", dotted],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=900,
        )

    def test_previously_unimportable_suites_now_run(self):
        for dotted in (
            "tools.test_cold_agent_truth",
            "tools.test_ledger_gap",
            "tools.test_acceptance",
        ):
            with self.subTest(module=dotted):
                completed = self._unittest(dotted)
                self.assertNotIn("ModuleNotFoundError", completed.stderr)
                self.assertNotIn("Failed to import test module", completed.stderr)
                self.assertEqual(completed.returncode, 0, completed.stderr[-1200:])


if __name__ == "__main__":
    unittest.main(verbosity=2)
