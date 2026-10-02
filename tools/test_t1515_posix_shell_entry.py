"""T-1515: a POSIX-shell host on Windows is never handed the cmd.exe launcher.

`host entry` named `bin\\saipen.cmd` whenever `os.name` is `nt`. A `.cmd` hands
its arguments to cmd.exe, which parses them again, and Git Bash (MSYS2) does
not escape for cmd. Measured 2026-09-24 from Git Bash: one argument
`x"y > injected.txt` made cmd.exe create the file `injected.txt --json`; with
`&` the same shape runs a command. The rendered `bin/saipen` carries the same
argument intact from that shell.

`argv_prefix` is what a PROGRAM spawns and stays the `.cmd` (a sh script is
not a Win32 executable, and `exec_prefix` is the programmatic safe path since
T-1501); `command_form`, what the host's shell types, is what changes.
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
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import test_host_bootstrap as hbt  # noqa: E402
import test_t1501_entry_resolver as t1501  # noqa: E402
from saipen_engine import entry_resolver as er  # noqa: E402

WINDOWS_ONLY = unittest.skipUnless(os.name == "nt", "a cmd.exe launcher exists only on Windows")


@WINDOWS_ONLY
class PosixShellHostTransport(unittest.TestCase):
    def setUp(self) -> None:
        self.home = t1501._runnable_home()
        self.root = hbt._project(home=str(self.home))

    def posix_form(self) -> str:
        return f'"{(self.home / "bin" / "saipen").resolve().as_posix()}"'

    def test_an_msys_shell_types_the_posix_launcher(self):
        resolved = t1501._resolve(self.root, MSYSTEM="MINGW64")
        self.assertEqual(resolved["code"], er.DIRECT_LAUNCHER, resolved)
        self.assertEqual(resolved["host_shell"], "posix")
        self.assertEqual(resolved["command_form"], self.posix_form())
        # A program still spawns what CreateProcess can run.
        self.assertEqual(
            resolved["argv_prefix"], [str((self.home / "bin" / "saipen.cmd").resolve())]
        )

    def test_a_posix_shell_variable_alone_is_enough(self):
        resolved = t1501._resolve(self.root, SHELL="/usr/bin/bash")
        self.assertEqual(resolved["command_form"], self.posix_form())

    def test_cmd_and_powershell_hosts_keep_the_cmd_launcher(self):
        resolved = t1501._resolve(self.root)
        self.assertEqual(resolved["code"], er.DIRECT_LAUNCHER, resolved)
        self.assertEqual(resolved["host_shell"], "windows")
        self.assertIn("saipen.cmd", resolved["command_form"])

    def test_an_unproven_posix_launcher_falls_back_to_the_engine_never_the_cmd(self):
        (self.home / "bin" / "saipen").write_text(
            '#!/bin/sh\nexec "python" "C:/elsewhere/tools/saipen.py" "$@"\n', encoding="utf-8"
        )
        resolved = t1501._resolve(self.root, MSYSTEM="MINGW64")
        self.assertNotIn(".cmd", resolved["command_form"])
        self.assertNotIn("elsewhere", resolved["command_form"])
        self.assertTrue(resolved["command_form"].endswith('/tools/saipen.py"'), resolved)
        self.assertTrue(
            any(d["code"] == "posix_launcher_unavailable" for d in resolved["diagnostics"])
        )

    @unittest.skipUnless(shutil.which("bash"), "needs a POSIX shell on this Windows host")
    def test_argument_text_reaches_the_engine_without_cmd_reparsing_it(self):
        env = t1501._cold_env(MSYSTEM="MINGW64")
        resolved = er.resolve_entry(self.root, env=env, honor_environment=False)
        with tempfile.TemporaryDirectory(prefix="saipen-t1515-") as scratch:
            script = f'{resolved["command_form"]} search \'x"y > injected.txt\' --json'
            subprocess.run(
                [shutil.which("bash"), "-c", script],
                cwd=scratch, capture_output=True, text=True, timeout=120,
                env={**env, "PATH": os.environ.get("PATH", "")},
            )
            self.assertEqual(sorted(os.listdir(scratch)), [])


if __name__ == "__main__":
    unittest.main()
