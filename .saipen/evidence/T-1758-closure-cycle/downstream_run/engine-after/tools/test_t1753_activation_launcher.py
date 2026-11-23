"""T-1753: Activation block launcher names an existing launcher for clone and installed homes.

AC:
1. The rendered block names an existing launcher for a clone and for an installed home.
   Under clone layout (home = saipen/), the pre-fix block substituted {{SAIPEN_HOME}}/bin/saipen
   which rendered <clone>/saipen/bin/saipen -- a path that does not exist.
   The fixed block either names existing files or resolves <saipen_home> from STATE.md,
   where ROOT/bin/saipen and ROOT/bin/saipen.cmd exist.
2. instruction_status reads 'current' for both spellings of the home (clone and installed).
3. A test renders the block for each layout and executes the POSIX and cmd launcher lines.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
PROTOCOL_DIR = ROOT / "saipen"
ACTIVATION = PROTOCOL_DIR / "ACTIVATION_BLOCK.md"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import autoinject  # noqa: E402
from test_hermetic_env import hermetic_env, isolate_host_session  # noqa: E402

BASH = (
    str(Path("C:/Program Files/Git/bin/bash.exe"))
    if os.name == "nt" and Path("C:/Program Files/Git/bin/bash.exe").is_file()
    else shutil.which("bash")
)


def setUpModule() -> None:
    isolate_host_session()


def _render(home: Path) -> str:
    return ACTIVATION.read_text(encoding="utf-8").replace("{{SAIPEN_HOME}}", str(home))


def _extract_rendered_launcher_paths(text: str) -> list[str]:
    """Extract literal launcher paths from backticks in the LAUNCHER section."""
    m = re.search(r"LAUNCHER:.*?(?:never search for it|Generic skill)", text, re.DOTALL)
    if not m:
        return []
    block = m.group(0)
    found = re.findall(r"`([^`]+)`", block)
    return [p for p in found if "bin" in p and "saipen" in p]


class ActivationLauncherTests(unittest.TestCase):
    def test_rendered_block_launcher_names_existing_file_for_clone_and_installed(self):
        """Under clone layout, no rendered launcher may point to a missing file."""
        rendered_clone = _render(PROTOCOL_DIR)
        launcher_paths = _extract_rendered_launcher_paths(rendered_clone)
        self.assertTrue(launcher_paths, "LAUNCHER line must contain backticked launcher references")

        # In pre-fix ACTIVATION_BLOCK.md, the line was:
        # run `{{SAIPEN_HOME}}/bin/saipen` ... or `{{SAIPEN_HOME}}\bin\saipen.cmd`
        # which rendered as <clone>/saipen/bin/saipen (does NOT exist).
        # In current ACTIVATION_BLOCK.md, it is `<saipen_home>/bin/saipen` from STATE.md.
        for raw_path in launcher_paths:
            if "<saipen_home>" in raw_path:
                # Resolved via STATE.md saipen_home
                state_home = ROOT
                resolved = Path(raw_path.replace("<saipen_home>", str(state_home)))
                self.assertTrue(
                    resolved.is_file(),
                    f"Resolved launcher from STATE.md does not exist: {resolved}",
                )
            else:
                # If a concrete path was rendered, it MUST exist (fails on pre-fix)
                resolved = Path(raw_path)
                self.assertTrue(
                    resolved.is_file(),
                    f"Rendered launcher names a missing file: {resolved}",
                )

        # For an installed home layout:
        with tempfile.TemporaryDirectory(prefix="saipen-inst-home-") as tmp:
            inst_home = Path(tmp)
            (inst_home / "bin").mkdir()
            (inst_home / "bin" / "saipen").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            (inst_home / "bin" / "saipen.cmd").write_text("@exit /b 0\n", encoding="utf-8")
            rendered_inst = _render(inst_home)
            inst_paths = _extract_rendered_launcher_paths(rendered_inst)
            for raw_path in inst_paths:
                if "<saipen_home>" in raw_path:
                    resolved = Path(raw_path.replace("<saipen_home>", str(inst_home)))
                    self.assertTrue(resolved.is_file())
                else:
                    resolved = Path(raw_path)
                    self.assertTrue(resolved.is_file())

    def test_instruction_status_reads_current_for_both_spellings_of_home(self):
        """instruction_status reads 'current' for clone spelling and installed skill spelling."""
        import contextlib
        from test_instruction_home_parity import AUTHORITY, _home, _template_block

        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(autoinject, "HOME", AUTHORITY))
            tmp = stack.enter_context(tempfile.TemporaryDirectory(prefix="saipen-instr-status-"))
            tmp_path = Path(tmp)
            skill = _home(tmp_path / "skill")
            clone = _home(tmp_path / "clone" / "saipen")

            instr_file = tmp_path / "INSTRUCTIONS.md"
            adapter = {"instruction_surfaces": [str(instr_file)]}

            template = _template_block()

            # 1. Spelling 1: Clone layout (clone / saipen)
            rendered_clone = template.replace("{{SAIPEN_HOME}}", str(clone))
            instr_file.write_text(f"# Notes\n\n{rendered_clone}\n", encoding="utf-8")
            status_clone = autoinject.instruction_status(adapter, skill)
            self.assertEqual(status_clone, "current", "clone spelling must read current")

            # 2. Spelling 2: Installed skill layout (skill)
            rendered_skill = template.replace("{{SAIPEN_HOME}}", str(skill))
            instr_file.write_text(f"# Notes\n\n{rendered_skill}\n", encoding="utf-8")
            status_skill = autoinject.instruction_status(adapter, skill)
            self.assertEqual(status_skill, "current", "installed skill must read current")

            # 3. Corrupted / altered prose reads stale
            mangled = rendered_skill.replace("FIRST ACTION", "FIRST STEP")
            instr_file.write_text(f"# Notes\n\n{mangled}\n", encoding="utf-8")
            status_mangled = autoinject.instruction_status(adapter, skill)
            self.assertEqual(status_mangled, "stale", "altered block must read stale")

    def test_executes_posix_and_cmd_launcher_lines(self):
        """Executes the cmd and POSIX launcher lines resolved from the rendered block."""
        rendered = _render(PROTOCOL_DIR)
        launcher_paths = _extract_rendered_launcher_paths(rendered)
        self.assertTrue(launcher_paths)

        # Resolve cmd launcher and posix launcher
        cmd_launcher = None
        posix_launcher = None
        for p in launcher_paths:
            resolved = Path(p.replace("<saipen_home>", str(ROOT)))
            if p.endswith(".cmd") or "cmd" in p:
                cmd_launcher = resolved
            else:
                posix_launcher = resolved

        self.assertIsNotNone(cmd_launcher)
        self.assertIsNotNone(posix_launcher)
        self.assertTrue(cmd_launcher.is_file(), f"cmd launcher must exist: {cmd_launcher}")
        self.assertTrue(posix_launcher.is_file(), f"POSIX launcher must exist: {posix_launcher}")

        # Execute cmd launcher line
        comspec = os.environ.get("COMSPEC", "cmd.exe")
        proc_cmd = subprocess.run(
            [comspec, "/d", "/c", str(cmd_launcher), "--help"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=hermetic_env(),
            timeout=60,
        )
        self.assertEqual(proc_cmd.returncode, 0, f"cmd launcher failed: {proc_cmd.stderr}")
        self.assertIn("usage: saipen", proc_cmd.stdout)

        # Execute POSIX launcher line
        if BASH:
            proc_bash = subprocess.run(
                [BASH, str(posix_launcher), "--help"],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=hermetic_env(),
                timeout=60,
            )
            self.assertEqual(proc_bash.returncode, 0, f"POSIX launcher failed: {proc_bash.stderr}")
            self.assertIn("usage: saipen", proc_bash.stdout)


if __name__ == "__main__":
    unittest.main()
