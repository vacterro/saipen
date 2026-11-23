"""T-1475: the writer of the root strays is named, and its path is proven.

`BLOCKED`, `` M` ``, `str` and `5` appeared at the root of saipen_home during
the T-1446 soak and in ordinary sessions. The writer is a host hook of the form
`cmd.exe /d /v:off /s /c '""<hook>.cmd""'` run through Git Bash: the switches
become paths, cmd.exe runs interactive, and the hook payload -- text the agent
read -- executes as command lines (E-8945). These controls hold three things:

* the detector flags exactly that command form and nothing that is safe;
* on a real Windows Git Bash, that form turns a Read-shaped payload into a
  stray file while a direct invocation runs the hook and creates nothing;
* the `[root-file-set]` FAIL names the hook when one is configured.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import host_hooks  # noqa: E402

#: The command installed in the field, byte for byte.
FIELD_COMMAND = (
    "cmd.exe /d /v:off /s /c "
    "'\"\"%USERPROFILE%\\.claude\\hooks\\cbm-code-discovery-gate.cmd\"\"'"
)


def settings(*commands: str, event: str = "PostToolUse", matcher: str = "Read") -> str:
    return json.dumps(
        {
            "hooks": {
                event: [
                    {
                        "matcher": matcher,
                        "hooks": [{"type": "command", "command": c} for c in commands],
                    }
                ]
            }
        }
    )


class DetectorTests(unittest.TestCase):
    def test_the_field_command_is_flagged(self):
        found = host_hooks.payload_hooks(settings(FIELD_COMMAND))
        self.assertEqual(len(found), 1)
        self.assertEqual((found[0]["event"], found[0]["matcher"]), ("PostToolUse", "Read"))

    def test_other_single_slash_spellings_are_flagged(self):
        for command in (
            "cmd /c hook.cmd",
            "CMD.EXE /C hook.cmd",
            '"C:\\Windows\\System32\\cmd.exe" /s /k hook.cmd',
        ):
            with self.subTest(command=command):
                self.assertEqual(len(host_hooks.payload_hooks(settings(command))), 1)

    def test_safe_commands_are_not_flagged(self):
        for command in (
            "'C:/Users/me/.claude/hooks/cbm-code-discovery-gate.cmd'",
            "C:/tools/codebase-memory-mcp.exe hook-augment",
            "cmd.exe //d //s //c hook.cmd",
            "printf '%s' '{\"ok\":true}'",
            "python tools/check.py /c",
        ):
            with self.subTest(command=command):
                self.assertEqual(host_hooks.payload_hooks(settings(command)), [])

    def test_malformed_settings_never_raise(self):
        for text in ("", "not json", "[]", '{"hooks": []}', '{"hooks": {"X": [1, {"hooks": 3}]}}'):
            with self.subTest(text=text):
                self.assertEqual(host_hooks.payload_hooks(text), [])

    def test_only_windows_is_affected(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".claude").mkdir()
            (home / ".claude" / "settings.json").write_text(
                settings(FIELD_COMMAND), encoding="utf-8"
            )
            self.assertEqual(len(host_hooks.hazards(home / "p", home, "win32")), 1)
            self.assertEqual(host_hooks.hazards(home / "p", home, "linux"), [])

    def test_the_hint_names_file_event_and_matcher(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".claude").mkdir()
            path = home / ".claude" / "settings.json"
            path.write_text(settings(FIELD_COMMAND), encoding="utf-8")
            hint = host_hooks.stray_hint(home / "p", home, "win32")
            self.assertIn(str(path), hint)
            self.assertIn("PostToolUse/Read", hint)
            self.assertIn(host_hooks.CODE, hint)
            self.assertEqual(host_hooks.stray_hint(home / "p", home, "linux"), "")


def _git_bash() -> str | None:
    if sys.platform != "win32":
        return None
    git = shutil.which("git")
    if not git:
        return None
    # git.exe sits in <Git>/cmd, <Git>/bin or <Git>/mingw64/bin; bash in <Git>/bin.
    for parent in Path(git).resolve().parents[:3]:
        candidate = parent / "bin" / "bash.exe"
        if candidate.is_file():
            return str(candidate)
    return None


@unittest.skipUnless(_git_bash(), "needs Windows Git Bash, the shell that runs host hooks")
class RealShellTests(unittest.TestCase):
    """The incident path itself: a Read payload through Git Bash into cmd.exe."""

    #: Shaped like a Read hook payload: a JSON-escaped quote leaves the
    #: redirect outside cmd.exe's quoting, as protocol text did in the field.
    PAYLOAD = '{"tool_response":"x\\" goal_tickets N-> PROBE"}\n'

    def drive(self, command: str) -> tuple[bool, list[str]]:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / "hook.cmd").write_bytes(
                b'@echo off\r\necho HOOK_RAN> "%~dp0ran.txt"\r\nexit /b 0\r\n'
            )
            hook = work / "hook.cmd"
            command = command.replace("{HOOK}", str(hook))
            command = command.replace("{HOOK_POSIX}", hook.as_posix())
            subprocess.run(
                [_git_bash(), "-c", command],
                cwd=work, input=self.PAYLOAD, text=True, capture_output=True, timeout=60,
            )
            ran = (work / "ran.txt").is_file()
            strays = sorted(p.name for p in work.iterdir() if p.name.startswith("PROBE"))
            return ran, strays

    def test_the_field_form_runs_the_payload_and_never_the_hook(self):
        ran, strays = self.drive("cmd.exe /d /v:off /s /c '\"\"{HOOK}\"\"'")
        self.assertFalse(ran)
        self.assertTrue(strays, "the payload redirect should have created a stray")

    def test_a_direct_invocation_runs_the_hook_and_creates_nothing(self):
        ran, strays = self.drive("'{HOOK_POSIX}'")
        self.assertTrue(ran)
        self.assertEqual(strays, [])


if __name__ == "__main__":
    unittest.main()
