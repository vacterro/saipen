"""The injector installs SAIPEN into ZAICODE's isolated profile (T-1504, SRC-116).

ZAICODE (a ZCode fork) runs with its own HOME -- `<workspace>/.zaicode/home` --
and reads `<HOME>/.zcode/AGENTS.md` for user instructions and
`<HOME>/.zcode/skills/<name>/SKILL.md` for skills. The registry names that HOME
through ZAICODE_HOME; an unset variable means ZAICODE is not configured here.
"""

from __future__ import annotations

import json
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

from test_adapter_parity import BASH, POWERSHELL, PS1, SH  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

REGISTRY = REPO / "extensions" / "adapters" / "registry.json"


def setUpModule():
    isolate_host_session()


def _adapter() -> dict:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return next(entry for entry in registry["adapters"] if entry["id"] == "zaicode")


class ZaicodeRegistryTests(unittest.TestCase):
    def test_surfaces_follow_the_zcode_loader_contract(self):
        adapter = _adapter()
        self.assertEqual(adapter["home_variable"], "ZAICODE_HOME")
        self.assertEqual(adapter["install"]["home"], "$ZAICODE_HOME/.zcode")
        self.assertEqual(adapter["install"]["skill"], "$ZAICODE_HOME/.zcode/skills/saipen")
        self.assertEqual(adapter["install"]["instruction"], "$ZAICODE_HOME/.zcode/AGENTS.md")
        self.assertEqual(adapter["skill_surfaces"], [adapter["install"]["skill"]])
        self.assertEqual(adapter["instruction_surfaces"], [adapter["install"]["instruction"]])
        # No machine path in the canonical registry.
        for value in adapter["install"].values():
            self.assertNotIn(":", value)


@unittest.skipUnless(POWERSHELL, "PowerShell runtime unavailable")
class ZaicodeInjectorTests(unittest.TestCase):
    def _inject(self, **env: str) -> tuple[subprocess.CompletedProcess, Path]:
        profile = Path(tempfile.mkdtemp(prefix="t1504-profile-"))
        self.addCleanup(shutil.rmtree, profile, True)
        proc = subprocess.run(
            [
                POWERSHELL,
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(PS1),
                "-AdapterId",
                "zaicode",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "USERPROFILE": str(profile), "HOME": str(profile), **env},
            timeout=300,
        )
        return proc, profile

    def test_installs_skill_and_instruction_block_into_the_isolated_home(self):
        zaicode_home = Path(tempfile.mkdtemp(prefix="t1504-zaicode-"))
        self.addCleanup(shutil.rmtree, zaicode_home, True)
        (zaicode_home / ".zcode").mkdir()
        proc, profile = self._inject(ZAICODE_HOME=str(zaicode_home))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        skill = zaicode_home / ".zcode" / "skills" / "saipen"
        self.assertTrue((skill / "SKILL.md").is_file(), proc.stdout)
        self.assertTrue((skill / "BOOT.md").is_file(), proc.stdout)
        agents = (zaicode_home / ".zcode" / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("<!-- SAIPEN:BEGIN -->", agents)
        self.assertIn("<!-- SAIPEN:END -->", agents)
        # The user's own profile is not ZAICODE's and receives nothing.
        self.assertFalse((profile / ".zcode").exists())

    def test_unset_home_variable_is_not_configured_and_writes_nothing(self):
        proc, profile = self._inject()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("ZAICODE", proc.stdout)
        self.assertIn("not installed - skip", proc.stdout)
        # PowerShell may seed its own AppData; nothing of SAIPEN may appear.
        self.assertFalse((profile / ".zcode").exists())
        self.assertEqual([p for p in profile.rglob("*") if "saipen" in p.name.lower()], [])


@unittest.skipUnless(BASH, "working bash runtime unavailable")
class ZaicodeShellInjectorTests(unittest.TestCase):
    def test_bash_injector_reaches_the_same_isolated_home(self):
        profile = Path(tempfile.mkdtemp(prefix="t1504-sh-profile-"))
        zaicode_home = Path(tempfile.mkdtemp(prefix="t1504-sh-zaicode-"))
        for path in (profile, zaicode_home):
            self.addCleanup(shutil.rmtree, path, True)
        (zaicode_home / ".zcode").mkdir()
        proc = subprocess.run(
            [BASH, str(SH), "--adapter", "zaicode"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={
                **os.environ,
                "HOME": str(profile).replace("\\", "/"),
                "ZAICODE_HOME": str(zaicode_home).replace("\\", "/"),
            },
            timeout=300,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue((zaicode_home / ".zcode" / "skills" / "saipen" / "SKILL.md").is_file())
        agents = (zaicode_home / ".zcode" / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("<!-- SAIPEN:BEGIN -->", agents)
        self.assertFalse((profile / ".zcode").exists())


if __name__ == "__main__":
    unittest.main()
