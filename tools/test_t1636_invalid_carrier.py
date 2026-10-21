"""T-1636: a carrier that names nothing usable never hides the session's project.

The Claude hook let an explicit SAIPEN_PROJECT_ROOT win, and when it named a
directory that is no SAIPEN project it answered None before the binding owner
was asked: a real project's UserPromptSubmit then proceeded as ordinary chat
-- no admission, no authority, no UNVERIFIED marker, and STRICT blocked
nothing. host_taxonomy already registers BINDING_CARRIER_INVALID as degradable
with the recovery "ignore the carrier and use the project the session
directory belongs to"; this path never reached it.

On the real artifacts:

* an invalid carrier with the session inside a project: the hook asks the
  engine about THAT project, DEGRADED_ALLOWED proceeds marked UNVERIFIED with
  BINDING_CARRIER_INVALID, STRICT blocks with the one action;
* a carrier naming ANOTHER project still blocks in every mode;
* outside any project nothing fires;
* the Codex Stop transport had the same shortcut and binds the same way. The
  OpenCode plugin delegates binding to the engine and has no such shortcut.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import protocol_admission as PA  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_protocol_admission import HOOK, World  # noqa: E402

CODEX_HOOK = ROOT / "extensions" / "adapters" / "codex" / "saipen-guard.py"
OPENCODE_PLUGIN = ROOT / "extensions" / "adapters" / "opencode" / "saipen-guard.js"


def setUpModule() -> None:
    isolate_host_session()


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ClaudeHookTests(unittest.TestCase):
    def world(self, mode: str | None) -> World:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return World(Path(tmp.name), mode=mode)

    def nowhere(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name)

    def prompt(self, world: World, cwd: Path, carrier: Path) -> tuple[int, dict | None]:
        argv = [
            sys.executable,
            str(HOOK),
            "--host",
            "claude",
            "--saipen-root",
            str(ROOT),
            "--home",
            str(world.home),
            "--authority-root",
            str(world.authority),
            "--runtime",
            str(world.runtime),
        ]
        env = {key: value for key, value in os.environ.items() if not key.startswith("SAIPEN_")}
        env["SAIPEN_PROJECT_ROOT"] = str(carrier)
        proc = subprocess.run(
            argv,
            input=json.dumps(
                {"hook_event_name": "UserPromptSubmit", "session_id": "session-1", "cwd": str(cwd)}
            ).encode("utf-8"),
            capture_output=True,
            cwd=str(ROOT),
            env=env,
            timeout=300,
            check=False,
        )
        text = proc.stdout.decode("utf-8").strip()
        return proc.returncode, (json.loads(text) if text else None)

    def test_degraded_proceeds_marked_unverified_with_the_carrier_named(self):
        world = self.world(None)
        code, out = self.prompt(world, world.project, self.nowhere())
        self.assertEqual(code, 0)
        self.assertIsNotNone(out, "the project the session is in was asked about")
        self.assertNotEqual(out.get("decision"), "block", out)
        context = json.dumps(out)
        self.assertIn(PA.DEGRADED_MARKER, context)
        self.assertIn("BINDING_CARRIER_INVALID", context)

    def test_strict_blocks_with_the_one_action(self):
        world = self.world("strict")
        code, out = self.prompt(world, world.project, self.nowhere())
        self.assertEqual(code, 0)
        self.assertEqual((out or {}).get("decision"), "block", out)
        self.assertIn("BINDING_CARRIER_INVALID", out["reason"])

    def test_a_carrier_naming_another_project_blocks_in_every_mode(self):
        for mode in (None, "strict"):
            with self.subTest(mode=mode):
                world, other = self.world(mode), self.world(None)
                _code, out = self.prompt(world, world.project, other.project)
                self.assertEqual((out or {}).get("decision"), "block", out)
                self.assertIn("BINDING_CONFLICT", out["reason"])

    def test_outside_any_project_nothing_fires(self):
        world = self.world("strict")
        code, out = self.prompt(world, self.nowhere(), self.nowhere())
        self.assertEqual(code, 0)
        self.assertTrue(out is None or out.get("decision") != "block", out)
        self.assertNotIn(PA.DEGRADED_MARKER, json.dumps(out or {}))


class TransportBindingTests(unittest.TestCase):
    """The same binding question in each transport's own project_root."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        self.project = base / "project"
        (self.project / ".saipen").mkdir(parents=True)
        (self.project / ".saipen" / "STATE.md").write_text("---\n---\n", encoding="utf-8")
        (self.project / "src").mkdir()
        self.nowhere = base / "nowhere"
        self.nowhere.mkdir()

    def check(self, module) -> None:
        inside = str(self.project / "src")
        with mock.patch.dict(os.environ, {"SAIPEN_PROJECT_ROOT": str(self.nowhere)}):
            self.assertEqual(module.project_root(inside), self.project.resolve())
            self.assertIsNone(module.project_root(str(self.nowhere)))
        with mock.patch.dict(os.environ, {"SAIPEN_PROJECT_ROOT": str(self.project)}):
            self.assertEqual(module.project_root(str(self.nowhere)), self.project.resolve())

    def test_the_claude_transport(self):
        self.check(_load(HOOK, "t1636_claude_guard"))

    def test_the_codex_transport(self):
        self.check(_load(CODEX_HOOK, "t1636_codex_guard"))

    def test_the_opencode_plugin_leaves_binding_to_the_engine(self):
        text = OPENCODE_PLUGIN.read_text(encoding="utf-8")
        self.assertNotIn("process.env.SAIPEN_PROJECT_ROOT", text)
        self.assertNotIn('env["SAIPEN_PROJECT_ROOT"]', text)


if __name__ == "__main__":
    unittest.main()
