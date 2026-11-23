"""T-1749: a stray file in the SAIPEN home is the home's finding, not a project's.

The validator's closed root-file-set check read the root of the home it runs
from (`_tools_parent`) whatever project it was pointed at, so validating a
managed project through the runtime home (`--project-root`) answered
`FAIL: cross-doc drift [root-file-set]` for a zero-byte file in the SAIPEN
checkout, and one stray refused the closure gate of every project bound to the
home (measured on a copy of a downstream project, T-1746 evidence
wintage-copy-8-ship-canonical-validator.json). Four such files appeared in one
session, written by a host hook from tool-payload fragments (T-1475).

The check still runs, and still names the stray, when the home validates
itself. Both halves run the real validator from a disposable copy of this
home, so the stray never touches the repository.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.paths import identity_file_content, new_project_lineage  # noqa: E402
from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

STRAY = "str"
_TREES = ("tools", "saipen", "extensions", "bootstrap", "tests")
_TEMPS: list[tempfile.TemporaryDirectory] = []

STATE = (
    "---\n"
    "phase: DONE\n"
    "task: none\n"
    'next_action: "saipen continue"\n'
    'blocker: ""\n'
    "transition_from: SHIP\n"
    "saipen_version: 8\n"
    "schema_version: 3\n"
    "last_event: 1\n"
    "style_contract: " + CURRENT_STYLE_CONTRACT + "\n"
    "mode: full\n"
    "updated: 2026-10-13T00:00:00Z\n"
    "agent: test-agent\n"
    "---\n"
)
BOARD = "## DOING\n## TODO\n## DONE\n## BLOCKED\n"
LOG = "- 13.10.26 00:00 [E-001] [agent: test-agent] DEC: fixture\n"


def setUpModule() -> None:
    isolate_host_session()


def _tempdir(prefix: str) -> Path:
    tmp = tempfile.TemporaryDirectory(prefix=prefix)
    _TEMPS.append(tmp)
    return Path(tmp.name)


def _memory(root: Path) -> Path:
    memory = root / ".saipen"
    memory.mkdir(parents=True, exist_ok=True)
    (memory / "IDENTITY.md").write_text(
        identity_file_content(new_project_lineage()), encoding="utf-8"
    )
    (memory / "STATE.md").write_text(STATE, encoding="utf-8")
    (memory / "BOARD.md").write_text(BOARD, encoding="utf-8")
    (memory / "LOG.md").write_text(LOG, encoding="utf-8")
    return root


def _home_with_a_stray() -> Path:
    """This home's validator surface, copied, plus one zero-byte stray at its root."""
    home = _tempdir("saipen-t1749-home-") / "home"
    home.mkdir()
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".ruff_cache")
    for name in _TREES:
        if (REPO / name).is_dir():
            shutil.copytree(REPO / name, home / name, ignore=ignore)
    for item in REPO.iterdir():
        if item.is_file():
            shutil.copy2(item, home / item.name)
    (home / STRAY).write_bytes(b"")
    return home


def _validate(home: Path, project: Path) -> str:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
    env["PYTHONUTF8"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", str(home / "tools" / "validate.py"), "--project-root",
         str(project), "--no-receipt"],
        capture_output=True, env=env, cwd=str(project), timeout=900, check=False,
    )
    return proc.stdout.decode("utf-8", "replace") + proc.stderr.decode("utf-8", "replace")


class HomeRootFilesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.home = _home_with_a_stray()

    def test_a_managed_project_is_not_judged_by_the_home_root(self):
        project = _memory(_tempdir("saipen-t1749-project-") / "project")
        output = _validate(self.home, project)
        self.assertNotIn("[root-file-set]", output)

    def test_the_home_validating_itself_still_names_the_stray(self):
        _memory(self.home)
        output = _validate(self.home, self.home)
        lines = [line for line in output.splitlines() if "[root-file-set]" in line]
        self.assertTrue(lines, output[-2000:])
        self.assertIn(repr(STRAY), lines[0])


if __name__ == "__main__":
    unittest.main()
