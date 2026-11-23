"""T-1786 / SRC-252: a weaker model reaches `saipen` in one call.

A MiMo 2.6 Pro session in FreeBuff Desktop was given `cc` and spent minutes
before its first SAIPEN command. The injected activation block caused most of
it; three of its defects are pinned here:

- the LAUNCHER line rendered `{{SAIPEN_HOME}}/bin/saipen`, but the block's home
  is the PROTOCOL directory, which holds no `bin/` in a source clone: every
  installed instruction surface named a launcher that does not exist;
- the shortcut gate (and BOOT step 7) sent the model to "CORE.md 1.10's
  shortcut table", which does not exist -- `REGISTRY.json` is the table and
  `COMMANDS.md` its human view -- while `saipen <token>` already resolves it;
- nothing said that the CLI binds the project and validates STATE, so the
  model planned to read BOOT, INDEX, CORE, STYLE, EXECUTION and STATE before
  the one command that answers all of them.

The fourth defect lived in the installer: the sibling backup of an edited
install kept `SKILL.md`, and every host registered it as a second `saipen`
skill claiming every shortcut.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
PROTOCOL_DIR = ROOT / "saipen"
ACTIVATION = PROTOCOL_DIR / "ACTIVATION_BLOCK.md"
BOOT = PROTOCOL_DIR / "BOOT.md"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from test_hermetic_env import hermetic_env, isolate_host_session  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


def _flat(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


def _render(home: Path) -> str:
    """The block as both injectors install it: the one placeholder replaced."""
    return ACTIVATION.read_text(encoding="utf-8").replace("{{SAIPEN_HOME}}", str(home))


def _absolute_launchers(text: str) -> list[str]:
    """Every backticked launcher path the block hands a model verbatim."""
    found = re.findall(r"`([^`]*bin[\\/]saipen(?:\.cmd)?)`", text)
    return [path for path in found if re.match(r"^([A-Za-z]:|/|\\\\)", path)]


class LauncherTests(unittest.TestCase):
    def test_no_rendered_launcher_names_a_missing_file(self):
        # A source clone renders the block with its protocol directory; the
        # BOOT pointer proves the render itself is real.
        rendered = _render(PROTOCOL_DIR)
        self.assertIn(str(PROTOCOL_DIR), rendered)
        self.assertTrue((PROTOCOL_DIR / "BOOT.md").is_file())
        for path in _absolute_launchers(rendered):
            if path.startswith("%ProgramData%"):
                continue
            self.assertTrue(
                Path(path).is_file(), f"the block names a launcher that does not exist: {path}"
            )

    def test_the_launcher_rule_is_the_state_one_read_rule(self):
        block = _flat(ACTIVATION)
        self.assertIn(
            "LAUNCHER: `saipen` not on PATH -> run `<saipen_home>/bin/saipen`", block
        )
        self.assertIn("`<saipen_home>\\bin\\saipen.cmd`", block)
        self.assertIn("the `saipen_home:` line of `.saipen/STATE.md`", block)
        self.assertNotIn("{{SAIPEN_HOME}}/bin", block)
        # STATE names the runtime root, the folder that holds the launchers.
        self.assertTrue((ROOT / "bin" / "saipen").is_file())
        self.assertTrue((ROOT / "bin" / "saipen.cmd").is_file())


class ShortcutTableTests(unittest.TestCase):
    def test_no_entry_document_points_at_a_core_shortcut_table(self):
        for doc in (ACTIVATION, BOOT):
            self.assertNotRegex(_flat(doc), r"CORE\.md (§ )?1\.10's (shortcut )?table", doc.name)
        core = (PROTOCOL_DIR / "CORE.md").read_text(encoding="utf-8")
        self.assertNotIn("| `cc` |", core, "CORE now carries a table; repoint the docs")
        registry = json.loads((PROTOCOL_DIR / "REGISTRY.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(registry["shortcuts"]["cc"], "saipen continue")
        self.assertIn("A shortcut resolves via `saipen <token>` (`REGISTRY.json`)", _flat(BOOT))


class CliFirstTests(unittest.TestCase):
    def test_the_block_orders_one_cli_call_before_any_read(self):
        block = _flat(ACTIVATION)
        for phrase in (
            "FIRST ACTION: a declared SAIPEN token or a `saipen ...` command is ONE tool "
            "call before any text, cwd = workspace: `saipen <token> --json`",
            "a new task is `saipen start '<task>'`",
            "Never pre-read BOOT, INDEX, CORE or STATE for that call",
            "a tool call is not assistant text",
            "`saipen response style --json` compiles both in one call",
            "SAIPEN owns it even when a skill or persona also lists it",
        ):
            self.assertIn(phrase, block)

    def test_an_unbound_workspace_refuses_and_writes_nothing(self):
        # The block promises: no `.saipen/` -> NOT_SAIPEN_PROJECT, nothing written.
        with tempfile.TemporaryDirectory(prefix="saipen-t1786-unbound-") as tmp:
            workspace = Path(tmp)
            owners = [p for p in (workspace, *workspace.parents) if (p / ".saipen").exists()]
            if owners:
                self.skipTest(f"temp root sits under a SAIPEN project: {owners[0]}")
            proc = subprocess.run(
                [sys.executable, "-B", str(TOOLS / "saipen.py"), "cc", "--json"],
                cwd=str(workspace),
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=hermetic_env(),
                timeout=300,
            )
            payload = json.loads(proc.stdout)
            self.assertEqual(payload.get("code"), "NOT_SAIPEN_PROJECT", payload)
            self.assertEqual(list(workspace.iterdir()), [])


def _install_ownership():
    spec = importlib.util.spec_from_file_location(
        "t1786_install_ownership", ROOT / "bootstrap" / "install_ownership.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class InstallerBackupTests(unittest.TestCase):
    def test_a_backed_up_skill_never_registers_as_a_second_skill(self):
        ownership = _install_ownership()
        with tempfile.TemporaryDirectory(prefix="saipen-t1786-skills-") as tmp:
            skills = Path(tmp) / "skills"
            destination = skills / "saipen"
            destination.mkdir(parents=True)
            edited = b"---\nname: saipen\ndescription: edited by the user\n---\n"
            (destination / "SKILL.md").write_bytes(edited)
            (destination / "BOOT.md").write_bytes(b"old boot\n")
            stage = Path(tmp) / "stage"
            stage.mkdir()
            (stage / "SKILL.md").write_bytes(b"---\nname: saipen\n---\n")
            (stage / "BOOT.md").write_bytes(b"new boot\n")
            (stage / "MANIFEST.json").write_text('{"managed_dirs": []}', encoding="utf-8")

            ownership.record(stage, destination)

            registered = sorted(path.parent.name for path in skills.glob("*/SKILL.md"))
            self.assertEqual(registered, ["saipen"])
            [backup] = [p for p in skills.iterdir() if p.name.startswith(".saipen-user-backup-")]
            # The user's bytes survive, under a name no host loads.
            self.assertEqual((backup / "SKILL.md.user-backup").read_bytes(), edited)
            self.assertEqual((backup / "BOOT.md").read_bytes(), b"old boot\n")


if __name__ == "__main__":
    unittest.main()
