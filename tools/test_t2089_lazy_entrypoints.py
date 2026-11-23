"""T-2089 P0: the lazily-imported write entrypoints must be REAL callables.

The first W3 attempt used module `__getattr__` (PEP 562), which never fires
for plain name lookup inside this module's own functions: every mutating
route through the REPO CLI died with `NameError: name 'checkpoint' is not
defined` while `--help`, `import saipen` and the installed 8.1.0 launcher
stayed green and hid the break. This suite drives the repo CLI itself on an
isolated fixture and proves the mutating routes reach the engine's own
authority gates (a REFUSE is the correct outcome; a NameError crash is the
regression being guarded against).

Run standalone:
    python tools/test_t2089_lazy_entrypoints.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO_ROOT = TOOLS.parent


def _make_project(tmp: Path) -> Path:
    root = tmp / "project"
    (root / ".saipen").mkdir(parents=True)
    # The mutating routes require a protocol home; point at THIS repo, which
    # is the running install location for a fixture driver.
    home = REPO_ROOT.as_posix()
    (root / ".saipen" / "STATE.md").write_text(
        "---\n"
        "phase: SCOUT\n"
        "task: T-100\n"
        'next_action: "PHASE SCOUT T-100"\n'
        "blocker: none\n"
        "saipen_version: 8\n"
        "schema_version: 3\n"
        "last_event: 1\n"
        "style_contract: ded-069a4c52\n"
        f'saipen_home: "{home}"\n'
        "agent: saipen-cli\n"
        "mode: full\n"
        'updated: "2026-01-01T00:00:00Z"\n'
        "transition_from: DONE\n"
        "---\n",
        encoding="utf-8",
    )
    (root / ".saipen" / "BOARD.md").write_text(
        "# BOARD\n\n## DOING\n- [/] T-100 active work\n\n## TODO\n\n## DONE\n\n## BLOCKED\n",
        encoding="utf-8",
    )
    (root / ".saipen" / "LOG.md").write_text(
        "- 01.01.26 00:00 [E-001] [T-100] RUN: scout started\n",
        encoding="utf-8",
    )
    return root


class LazyEntrypoints(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="saipen-lazy-entry-")
        self.addCleanup(self.temporary.cleanup)
        self.root = _make_project(Path(self.temporary.name))

    def _cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(TOOLS / "saipen.py"), *args],
            capture_output=True,
            cwd=self.root,
        )

    def test_lazy_names_are_importable_and_callable(self) -> None:
        for name in ("checkpoint", "finish_ticket", "apply_claim", "auto_recover_pending"):
            obj = getattr(__import__("saipen"), name)
            self.assertTrue(callable(obj), name)

    def test_mutation_reaches_engine_gates_not_nameerror(self) -> None:
        proc = self._cli("checkpoint", "RUN", "T-100", "lazy entrypoint probe")
        combined = proc.stdout.decode("utf-8", "replace") + proc.stderr.decode("utf-8", "replace")
        self.assertNotIn("NameError", combined)
        self.assertNotIn("is not defined", combined)
        # Either the engine answered (rc 0 + ok) or its authority refused --
        # both prove the lazy global resolved.
        self.assertTrue(proc.returncode in (0, 1), proc.returncode)

    def test_full_mutation_chain_claims_and_checkpoints(self) -> None:
        proc = self._cli("claim", "T-100", "--json")
        self.assertEqual(proc.returncode, 0, proc.stdout.decode()[:200])
        proc = self._cli(
            "checkpoint", "RUN", "T-100", "lazy entrypoint mutation", "--json"
        )
        self.assertEqual(proc.returncode, 0, proc.stdout.decode()[:200])
        self.assertIn('"ok": true', proc.stdout.decode("utf-8", "replace"))

    def test_read_only_routes_after_lazy_change(self) -> None:
        for args in (("status", "--json"), ("status", "--view", "agent", "--json")):
            proc = self._cli(*args)
            self.assertEqual(proc.returncode, 0, args)


if __name__ == "__main__":
    unittest.main()
