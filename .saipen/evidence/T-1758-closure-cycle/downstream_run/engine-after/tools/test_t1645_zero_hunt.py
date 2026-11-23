"""T-1645 / SRC-187: a cold agent reaches the current Work without hunting.

A downstream agent given `/goal cc all` met `saipen: command not found`,
searched the SAIPEN repository for a launcher, then grepped BOARD for its
ticket and the filesystem for the ticket's source receipt. Every fact it
hunted for was already known to the project: `.saipen/STATE.md` names
`saipen_home`, and the router knows the current Work and its receipts.

Pinned here:

- the PATH-miss rule: one read of STATE's `saipen_home:` line, the launcher
  under that home, the PROJECT root as working directory (BOOT, ACTIVATION);
- routing precedes a generic skill or persona bootstrap (BOOT, ACTIVATION);
- `continue --json` carries `work`: the routed ticket's BOARD record and the
  exact paths of its source receipt, so entering the phase needs no search;
- end to end, with `saipen` absent from PATH, the documented read plus the
  home's own launcher route a fixture project to its current ticket.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import test_t1614_future_gate as H  # noqa: E402
from test_hermetic_env import hermetic_env, isolate_host_session  # noqa: E402

BOOT = ROOT / "saipen" / "BOOT.md"
ACTIVATION = ROOT / "saipen" / "ACTIVATION_BLOCK.md"


def setUpModule() -> None:
    isolate_host_session()


def _flat(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


def _home_from_state(project: Path) -> Path | None:
    """The documented PATH-miss read: the `saipen_home:` line, YAML-unescaped."""
    text = (project / ".saipen" / "STATE.md").read_text(encoding="utf-8")
    match = re.search(r'(?m)^saipen_home:\s*"?([^"\r\n]+?)"?\s*$', text)
    return Path(match.group(1).replace("\\\\", "\\")) if match else None


def _env_without_saipen() -> dict:
    env = hermetic_env()
    keep = [
        entry
        for entry in env.get("PATH", "").split(os.pathsep)
        if entry and not any((Path(entry) / name).exists() for name in ("saipen", "saipen.cmd"))
    ]
    env["PATH"] = os.pathsep.join(keep)
    return env


class BootstrapRuleTests(unittest.TestCase):
    def test_boot_states_the_one_read_path_miss_rule(self):
        boot = _flat(BOOT)
        for phrase in (
            "runs with the PROJECT root as working directory",
            "else under `<saipen_home>` `bin/saipen`",
            "`bin/saipen.cmd` (cmd, PowerShell)",
            "A PATH miss costs one read: the `saipen_home:` line of `.saipen/STATE.md`",
            "Never search or try another home",
        ):
            self.assertIn(phrase, boot)

    def test_boot_puts_routing_before_a_generic_bootstrap(self):
        boot = _flat(BOOT)
        self.assertIn("Routing is the first operational action.", boot)
        self.assertIn("precedes any generic skill or persona bootstrap", boot)
        self.assertIn("never grep BOARD or search `.saipen` for them", boot)

    def test_the_injected_block_names_the_launcher_and_the_order(self):
        block = _flat(ACTIVATION)
        # T-1786: `{{SAIPEN_HOME}}` renders the PROTOCOL directory, which has
        # no `bin/` in a source clone; the launcher is under STATE's home.
        self.assertIn("LAUNCHER: `saipen` not on PATH -> run `<saipen_home>/bin/saipen`", block)
        self.assertIn("`<saipen_home>\\bin\\saipen.cmd`", block)
        self.assertIn("the `saipen_home:` line of `.saipen/STATE.md`", block)
        self.assertIn("Generic skill/persona bootstrap waits for routing.", block)

    def test_the_injected_block_never_orders_a_public_clone(self):
        # SRC-188: a public clone is not a project's runtime; the old line
        # sent a cold agent to fetch HEAD and continue on a mismatched version.
        block = _flat(ACTIVATION)
        self.assertNotIn("clone github.com", block)
        self.assertIn("never clone a public copy to continue Work", block)


class WorkContextTests(unittest.TestCase):
    def setUp(self):
        self.base, self.project = H._project(intent="goal")
        self.addCleanup(shutil.rmtree, self.base, True)
        self.tid = H._add(self.project, "the current work")
        board = self.project / ".saipen" / "BOARD.md"
        text = board.read_text(encoding="utf-8")
        line = next(ln for ln in text.splitlines() if f"] {self.tid} [" in ln)
        board.write_text(text.replace(line, line + " | source_receipts: SRC-001"), encoding="utf-8")
        active = self.project / ".saipen" / "intake" / "active"
        active.mkdir(parents=True)
        (active / "SRC-001.md").write_text("# User request\n\nthe current work\n", encoding="utf-8")

    def _continue(self) -> dict:
        proc = subprocess.run(
            [
                sys.executable,
                str(TOOLS / "saipen.py"),
                "continue",
                "--json",
                "--dry-run",
                "--project-root",
                str(self.project),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=hermetic_env(),
            timeout=300,
        )
        return json.loads(proc.stdout)

    def test_continue_names_the_work_record_and_its_source_by_path(self):
        payload = self._continue()
        self.assertEqual(payload.get("ticket"), self.tid, payload)
        work = payload.get("work")
        self.assertIsInstance(work, dict, payload)
        self.assertEqual(work["id"], self.tid)
        self.assertIn(f"{self.tid} [", work["record"])
        self.assertEqual(Path(work["board"]), self.project / ".saipen" / "BOARD.md")
        [source] = work["source_receipts"]
        self.assertEqual(source["id"], "SRC-001")
        self.assertTrue(Path(source["body"]).is_file(), source)
        self.assertNotIn("contract", source, "a locator names only paths that exist")


class PathMissColdStartTests(unittest.TestCase):
    """The incident: `saipen` is not on PATH and no session context exists."""

    def setUp(self):
        self.base, self.project = H._project(intent="goal")
        self.addCleanup(shutil.rmtree, self.base, True)
        self.tid = H._add(self.project, "the current work")
        self.env = _env_without_saipen()
        self.assertIsNone(shutil.which("saipen", path=self.env["PATH"]))

    def _check(self, command: list[str]) -> None:
        proc = subprocess.run(
            [*command, "continue", "--json", "--dry-run"],
            cwd=str(self.project),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=self.env,
            timeout=300,
        )
        payload = json.loads(proc.stdout or "{}")
        self.assertEqual(payload.get("ticket"), self.tid, proc.stdout + proc.stderr)
        self.assertTrue(str(payload.get("action") or "").startswith("PHASE "), payload)
        self.assertEqual(
            Path(payload["cold_route"]["project_root"]).resolve(), self.project.resolve()
        )
        self.assertEqual((payload.get("work") or {}).get("id"), self.tid, payload)

    def test_the_state_read_resolves_the_home_launcher(self):
        home = _home_from_state(self.project)
        self.assertIsNotNone(home)
        self.assertEqual(home.resolve(), ROOT.resolve())
        native = home / "bin" / ("saipen.cmd" if os.name == "nt" else "saipen")
        if not native.is_file():
            self.skipTest("this checkout carries no generated launcher in bin/")
        self._check(["cmd", "/c", str(native)] if os.name == "nt" else [str(native)])

    def test_git_bash_runs_the_posix_launcher_with_forward_slashes(self):
        home = _home_from_state(self.project)
        posix = home / "bin" / "saipen"
        sh = shutil.which("sh", path=self.env["PATH"])
        if not posix.is_file() or sh is None:
            self.skipTest("no POSIX launcher or no sh on this host")
        self._check([sh, str(posix).replace("\\", "/")])


if __name__ == "__main__":
    unittest.main()
