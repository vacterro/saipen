"""T-1518: the crew launcher's banner is one line and stderr stays empty.

The banner echo in `bootstrap/saipen_crew.sh` closed its string at the end of
one line, so the next line -- "(never what `saipen crew` means; project: ...)"
-- ran as a command: every run printed "No such file or directory" and lost
half the banner, whatever the launch outcome.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import run_scenarios as rs  # noqa: E402

BASH = rs.find_bash()
LAUNCHER = rs.HOME / "bootstrap" / "saipen_crew.sh"
ACCEPTING_SHIM = "#!/usr/bin/env sh\nexit 0\n"


@unittest.skipUnless(BASH, "no usable bash")
class CrewBannerTests(unittest.TestCase):
    def test_the_banner_is_one_line_and_stderr_is_empty(self):
        with tempfile.TemporaryDirectory(prefix="saipen-t1518-") as raw:
            shim_dir = Path(raw) / "bin"
            shim_dir.mkdir()
            for name in ("gnome-terminal", "konsole", "xterm"):
                shim = shim_dir / name
                shim.write_text(ACCEPTING_SHIM, encoding="utf-8", newline="\n")
                shim.chmod(0o755)
            env = rs.bash_env(BASH, Path(raw))
            env["PATH"] = str(shim_dir) + os.pathsep + env.get("PATH", "")
            done = subprocess.run(
                [BASH, str(LAUNCHER)],
                env=env,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=120,
            )
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(done.stderr, "")
        banner = done.stdout.splitlines()[0]
        self.assertTrue(
            banner.startswith("SAIPEN crew launcher -- optional manual multi-window helper ("),
            banner,
        )
        self.assertIn("(never what `saipen crew` means; project: ", banner)
        self.assertIn("Done. Launched 3 crew windows.", done.stdout)


if __name__ == "__main__":
    unittest.main()
