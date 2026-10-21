"""T-1705: host-relative writes must preserve canonical namespace protection.

These are pre-execution guard tests. They do not claim a hook exists in a host
that declares only advisory enforcement, and never mutate a consumer project.
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

from saipen_engine import guard_events  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_t1671_lifecycle_authority import AGENT, _project  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


class LifecycleWritePreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = _project()
        cls.addClassCleanup(lambda: shutil.rmtree(cls.root, ignore_errors=True))
        (cls.root / "src").mkdir(exist_ok=True)
        (cls.root / ".saipen" / "evidence").mkdir(exist_ok=True)

    def event(self, tool: str, args: dict, *, cwd: Path | None = None) -> dict:
        return {
            "event": "before_tool",
            "host": "opencode",
            "cwd": str(cwd or self.root),
            "actor": AGENT,
            "tool_name": tool,
            "tool_input": args,
        }

    def assert_protected(self, event: dict) -> None:
        paths = [self.root / ".saipen" / name for name in ("STATE.md", "BOARD.md", "LOG.md")]
        before = {path: path.read_bytes() for path in paths}
        answer = guard_events.evaluate_event(event)
        self.assertFalse(answer["admitted"], answer)
        self.assertEqual(answer["code"], "PROTECTED_CANONICAL_NAMESPACE", answer)
        self.assertEqual({path: path.read_bytes() for path in paths}, before)

    def test_relative_file_targets_from_canonical_cwd_are_refused(self) -> None:
        for name in ("STATE.md", "BOARD.md", "LOG.md"):
            with self.subTest(name=name):
                self.assert_protected(self.event(
                    "str_replace", {"path": name, "old_str": "x", "new_str": "y"},
                    cwd=self.root / ".saipen",
                ))

    def test_relative_shell_redirection_from_canonical_cwd_is_refused(self) -> None:
        self.assert_protected(self.event(
            "bash", {"command": 'printf "fabricated closure" >> LOG.md'},
            cwd=self.root / ".saipen",
        ))

    def test_execution_cwd_is_separate_from_project_binding_cwd(self) -> None:
        for tool, args in (("write", {"path": "STATE.md"}),
                           ("bash", {"command": 'echo "typed closure" >> LOG.md'})):
            with self.subTest(tool=tool):
                event = self.event(tool, args)
                event["tool_cwd"] = str(self.root / ".saipen")
                self.assert_protected(event)

    def test_invalid_execution_cwd_carrier_is_not_silently_ignored(self) -> None:
        for value in (None, "", [], 7):
            with self.subTest(value=value):
                event = self.event("write", {"path": "STATE.md"})
                event["tool_cwd"] = value
                with self.assertRaises(guard_events.EventError):
                    guard_events.load_event(json.dumps(event))

    @unittest.skipUnless(shutil.which("node"), "node runtime unavailable")
    def test_opencode_transport_preserves_execution_directory_and_workdir(self) -> None:
        from test_opencode_adapter import PLUGIN, run_cases

        cases = [
            {
                "id": "file-from-memory-directory", "tool": "write",
                "directory": str(self.root / ".saipen"),
                "args": {"filePath": "STATE.md", "content": "typed closure\n"},
            },
            {
                "id": "shell-workdir", "tool": "bash", "directory": str(self.root),
                "args": {"command": 'echo "typed closure" >> LOG.md',
                         "workdir": str(self.root / ".saipen")},
            },
        ]
        with tempfile.TemporaryDirectory(prefix="t1705-transport-") as temp:
            home = Path(temp) / "home"
            home.mkdir()
            before = {name: (self.root / ".saipen" / name).read_bytes()
                      for name in ("STATE.md", "BOARD.md", "LOG.md")}
            rows = run_cases(PLUGIN, [
                {
                    "id": case["id"], "project": str(self.root),
                    "context_directory": case["directory"],
                    "context_worktree": str(self.root),
                    "env": {"SAIPEN_SKILL_ROOT": str(TOOLS.parent),
                            "SAIPEN_PYTHON": sys.executable, "SAIPEN_AGENT": AGENT,
                            "HOME": str(home), "USERPROFILE": str(home)},
                    "input": {"tool": case["tool"], "sessionID": "ses_t1705"},
                    "output": {"args": case["args"]},
                } for case in cases
            ], Path(temp) / "driver")
            for row in rows:
                with self.subTest(case=row["id"]):
                    self.assertEqual(row["outcome"], "blocked", row)
                    self.assertIn("PROTECTED_CANONICAL_NAMESPACE", row["message"], row)
            self.assertEqual(before, {name: (self.root / ".saipen" / name).read_bytes()
                                      for name in before})

    def test_relative_patch_batch_cannot_hide_a_canonical_target(self) -> None:
        self.assert_protected(self.event("apply_patch", {"patchText": (
            "*** Begin Patch\n*** Add File: scratch.txt\n+x\n"
            "*** Update File: BOARD.md\n@@\n-x\n+y\n*** End Patch\n"
        )}, cwd=self.root / ".saipen"))

    def test_both_relative_move_endpoints_use_the_host_cwd(self) -> None:
        for source, destination in (("LOG.md", "scratch.txt"), ("scratch.txt", "STATE.md")):
            with self.subTest(source=source, destination=destination):
                self.assert_protected(self.event("move", {
                    "source_path": source, "destination_path": destination,
                }, cwd=self.root / ".saipen"))

    def test_relative_parent_path_resolves_from_a_source_subdirectory(self) -> None:
        self.assert_protected(self.event(
            "edit", {"file_path": "../.saipen/STATE.md"}, cwd=self.root / "src",
        ))

    def test_structured_relative_escape_still_fails_closed(self) -> None:
        answer = guard_events.evaluate_event(self.event(
            "write", {"path": "../../outside.txt"}, cwd=self.root / "src",
        ))
        self.assertFalse(answer["admitted"], answer)
        self.assertEqual(answer["code"], "PATH_ESCAPES_PROJECT", answer)

    def test_direct_canonical_paths_and_absolute_aliases_stay_refused(self) -> None:
        for target in (".saipen/LOG.md", str(self.root / ".saipen" / "STATE.md")):
            with self.subTest(target=target):
                self.assert_protected(self.event("write", {"path": target}))

    def test_canonical_read_and_ordinary_relative_edit_stay_available(self) -> None:
        for event in (
            self.event("read", {"path": "LOG.md"}, cwd=self.root / ".saipen"),
            self.event("write", {"path": "notes.txt"}, cwd=self.root / ".saipen" / "evidence"),
        ):
            with self.subTest(event=event):
                answer = guard_events.evaluate_event(event)
                self.assertTrue(answer["admitted"], answer)

    def test_shell_redirection_spellings_and_wrappers_are_refused(self) -> None:
        for command in (
            'printf x>LOG.md', 'printf x 2>>"LOG.md"',
            'printf x >&LOG.md', 'printf x &>LOG.md', 'printf x >> L\'OG\'.md',
            "bash -c 'printf x >> LOG.md'", 'cmd /c "echo x >> LOG.md"',
            'powershell -Command "Write-Output x >> LOG.md"',
            'pushd ..; popd; printf x >> LOG.md',
        ):
            with self.subTest(command=command):
                self.assert_protected(self.event(
                    "bash", {"command": command}, cwd=self.root / ".saipen",
                ))

    def test_unreadable_named_writer_is_refused(self) -> None:
        for command in (r'Set-Content \"LOG.md\" x', 'timeout 5 tee LOG.md'):
            with self.subTest(command=command):
                answer = guard_events.evaluate_event(self.event(
                    "bash", {"command": command}, cwd=self.root / ".saipen",
                ))
                self.assertFalse(answer["admitted"], answer)
                self.assertEqual(answer["code"], "TARGET_UNRESOLVED", answer)

    def test_named_shell_writers_are_refused(self) -> None:
        for command in (
            'printf x | tee -a LOG.md',
            'Set-Content -Value x -LiteralPath LOG.md',
            'Add-Content LOG.md x', 'Write-Output x | Out-File LOG.md',
        ):
            with self.subTest(command=command):
                self.assert_protected(self.event(
                    "bash", {"command": command}, cwd=self.root / ".saipen",
                ))

    def test_computed_output_target_is_not_assumed_safe(self) -> None:
        answer = guard_events.evaluate_event(self.event(
            "bash", {"command": "printf x >> $target"}, cwd=self.root / ".saipen",
        ))
        self.assertFalse(answer["admitted"], answer)
        self.assertEqual(answer["code"], "TARGET_UNRESOLVED", answer)

    def test_ordinary_output_and_quoted_redirection_text_are_allowed(self) -> None:
        for command in (
            'printf x >> notes.txt', 'printf "%s" ">> LOG.md"', 'printf x 2>&1',
        ):
            with self.subTest(command=command):
                answer = guard_events.evaluate_event(self.event(
                    "bash", {"command": command}, cwd=self.root / ".saipen" / "evidence",
                ))
                self.assertTrue(answer["admitted"], answer)

    def test_guard_decision_does_not_fabricate_a_freebuff_blocking_hook(self) -> None:
        event = self.event("str_replace", {"path": "LOG.md"}, cwd=self.root / ".saipen")
        event["host"] = "freebuff"
        answer = guard_events.evaluate_event(event)
        self.assertFalse(answer["admitted"], answer)
        self.assertEqual(answer["code"], "PROTECTED_CANONICAL_NAMESPACE", answer)
        self.assertEqual(answer["strength"]["effective"], "ADVISORY", answer)

    def test_cli_refuses_before_a_host_could_apply_the_edit(self) -> None:
        event = self.event("str_replace", {"path": "LOG.md"}, cwd=self.root / ".saipen")
        before = (self.root / ".saipen" / "LOG.md").read_bytes()
        result = subprocess.run(
            [sys.executable, str(TOOLS / "saipen.py"), "guard", "--event-json", "-", "--json"],
            input=json.dumps(event), text=True, encoding="utf-8", capture_output=True,
            cwd=self.root, check=False, timeout=30,
        )
        answer = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1, result)
        self.assertFalse(answer["admitted"], answer)
        self.assertEqual(answer["code"], "PROTECTED_CANONICAL_NAMESPACE", answer)
        self.assertEqual((self.root / ".saipen" / "LOG.md").read_bytes(), before)

    def test_unknown_relative_host_cwd_does_not_grant_a_target_base(self) -> None:
        answer = guard_events.evaluate_event(
            self.event("write", {"path": "LOG.md"}, cwd=Path("relative-cwd")),
            project_root=str(self.root),
        )
        self.assertFalse(answer["admitted"], answer)
        self.assertEqual(answer["code"], "TARGET_UNRESOLVED", answer)

    def test_non_saipen_project_remains_non_interfering(self) -> None:
        with tempfile.TemporaryDirectory(prefix="t1705-unbound-") as temporary:
            event = self.event("write", {"path": "LOG.md"}, cwd=Path(temporary))
            answer = guard_events.evaluate_event(event)
            self.assertTrue(answer["admitted"], answer)
            self.assertFalse(answer["applicable"], answer)


if __name__ == "__main__":
    unittest.main()
