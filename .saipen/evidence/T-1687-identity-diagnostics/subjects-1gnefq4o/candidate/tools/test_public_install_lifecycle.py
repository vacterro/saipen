"""Public-release acceptance through real installers and fresh CLI processes."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
POWERSHELL = (
    (shutil.which("powershell") or shutil.which("pwsh"))
    if os.name == "nt"
    else shutil.which("pwsh")
)
BASH = (
    str(Path("C:/Program Files/Git/bin/bash.exe"))
    if os.name == "nt" and Path("C:/Program Files/Git/bin/bash.exe").is_file()
    else shutil.which("bash")
)


class PublicInstallLifecycleTests(unittest.TestCase):
    def run_process(self, argv, env, cwd, *, json_output=False):
        result = subprocess.run(
            argv,
            env=env,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=240,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout) if json_output else result.stdout

    def lifecycle(self, transport):
        with tempfile.TemporaryDirectory(prefix="saipen-public-install-") as raw:
            base = Path(raw)
            home, project = base / "user home", base / "new project"
            home.mkdir()
            project.mkdir()
            env = {k: v for k, v in os.environ.items() if not k.startswith("SAIPEN_")}
            env.update(
                HOME=str(home),
                USERPROFILE=str(home),
                LOCALAPPDATA=str(home / "AppData/Local"),
                XDG_CONFIG_HOME=str(home / ".config"),
                SAIPEN_USER_CONFIG_HOME=str(home / ".saipen-user"),
                SAIPEN_UNINSTALL_SKIP_TASK="1",
                PYTHONUTF8="1",
                PYTHONDONTWRITEBYTECODE="1",
                SAIPEN_PYTHON=sys.executable,
            )
            env.pop("ZAICODE_HOME", None)
            env.pop("SAIMAIL_WORKSPACE", None)
            instructions = {}
            for relative in (
                ".claude/CLAUDE.md",
                ".codex/AGENTS.md",
                ".gemini/GEMINI.md",
                ".config/opencode/AGENTS.md",
                ".knowledge.md",
                ".AGENTS.md",
            ):
                path = home / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                original = b"\xef\xbb\xbfUser instructions: keep.\r\n\r\n"
                path.write_bytes(original)
                instructions[path] = original
            foreign_skill = home / ".agents/skills/user-skill/SKILL.md"
            foreign_skill.parent.mkdir(parents=True)
            foreign_skill.write_bytes(b"USER SKILL\n")
            foreign_hook = {"type": "command", "command": "echo user-hook"}
            original_configs = {}
            for relative, event in (
                (".claude/settings.json", "Stop"),
                (".codex/hooks.json", "Stop"),
                (".gemini/settings.json", "BeforeTool"),
            ):
                config = home / relative
                data = {"theme": "user-theme", "hooks": {event: [{"hooks": [foreign_hook]}]}}
                config.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
                original_configs[config] = data
            if transport == "powershell":
                install = [
                    POWERSHELL,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(ROOT / "bootstrap/inject.ps1"),
                ]
                uninstall = [
                    POWERSHELL,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(ROOT / "bootstrap/uninstall.ps1"),
                ]
            else:
                install = [BASH, str(ROOT / "bootstrap/inject.sh")]
                uninstall = [BASH, str(ROOT / "bootstrap/uninstall.sh")]
            self.run_process(install, env, project)
            skill = home / ".agents/skills/saipen"
            cli = skill / "tools/saipen.py"
            entry = (
                [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", str(skill / "bin/saipen.cmd")]
                if os.name == "nt" and transport == "powershell"
                else [BASH, str(skill / "bin/saipen")]
            )
            self.assertTrue(cli.is_file())
            init = self.run_process([*entry, "set", "--json"], env, project, json_output=True)
            self.assertEqual(init["code"], "INIT_COMPLETED")
            resumed = self.run_process(
                [*entry, "continue", "--json"],
                env,
                project,
                json_output=True,
            )
            self.assertEqual(
                resumed["action"], "WAIT: init -- provide the first project goal or raw backlog"
            )
            status = self.run_process([*entry, "status", "--json"], env, project, json_output=True)
            route = status["cold_route"]
            self.assertFalse(route["search_required"])
            for field in ("boot", "style", "phase_module"):
                self.assertTrue(Path(route[field]).is_file(), route)
            self.assertIn("execute", Path(route["boot"]).read_text(encoding="utf-8").lower())
            self.run_process(
                [*entry, "validate", "--json"],
                env,
                project,
                json_output=True,
            )
            memory = {
                path.relative_to(project): path.read_bytes()
                for path in (project / ".saipen").rglob("*")
                if path.is_file()
            }
            note = skill / "user-added-note.txt"
            note.write_bytes(b"KEEP MY NOTE\n")
            edited = skill / "SKILL.md"
            edited_bytes = edited.read_bytes() + b"\nUser annotation: keep this edit.\n"
            edited.write_bytes(edited_bytes)
            edited_hook = home / ".config/opencode/plugins/saipen-guard.js"
            hook_bytes = edited_hook.read_bytes() + b"\n// User annotation: keep this edit.\n"
            edited_hook.write_bytes(hook_bytes)
            suffix = b"User instructions added after install.\r\n"
            for path in instructions:
                path.write_bytes(path.read_bytes() + suffix)
            for config in original_configs:
                data = json.loads(config.read_text(encoding="utf-8"))
                data["post_install_setting"] = "keep"
                config.write_text(json.dumps(data) + "\n", encoding="utf-8")
            self.run_process(uninstall, env, project)
            for path, original in instructions.items():
                with self.subTest(transport=transport, path=path.name):
                    self.assertEqual(path.read_bytes(), original + suffix)
            for config, original in original_configs.items():
                with self.subTest(transport=transport, config=str(config.relative_to(home))):
                    self.assertEqual(
                        json.loads(config.read_text(encoding="utf-8")),
                        {**original, "post_install_setting": "keep"},
                    )
            self.assertEqual(foreign_skill.read_bytes(), b"USER SKILL\n")
            self.assertTrue(note.is_file(), "uninstall removed an unowned user file")
            self.assertEqual(note.read_bytes(), b"KEEP MY NOTE\n")
            self.assertEqual(edited.read_bytes(), edited_bytes)
            self.assertEqual(edited_hook.read_bytes(), hook_bytes)
            self.assertFalse(cli.exists())
            self.assertEqual(
                memory,
                {
                    path.relative_to(project): path.read_bytes()
                    for path in (project / ".saipen").rglob("*")
                    if path.is_file()
                },
            )
            self.run_process(install, env, project)
            self.assertEqual(note.read_bytes(), b"KEEP MY NOTE\n")
            self.run_process(
                [*entry, "validate", "--json"],
                env,
                project,
                json_output=True,
            )
            self.run_process(uninstall, env, project)
            self.assertEqual(note.read_bytes(), b"KEEP MY NOTE\n")

    @unittest.skipUnless(POWERSHELL, "PowerShell transport unavailable")
    def test_powershell_install_set_continue_validate_uninstall_reinstall(self):
        self.lifecycle("powershell")

    @unittest.skipUnless(BASH, "Bash transport unavailable")
    def test_bash_install_set_continue_validate_uninstall_reinstall(self):
        self.lifecycle("bash")


if __name__ == "__main__":
    unittest.main()
