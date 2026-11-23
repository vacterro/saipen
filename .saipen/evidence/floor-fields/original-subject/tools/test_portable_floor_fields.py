"""Portable dependency checks consume structured fields; parity uses the native floor."""

from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import audit_floor
import audit_parity
from saipen_engine.board import parse_board

ROOT = Path(__file__).resolve().parents[1]


class PortableNeedsFields(unittest.TestCase):
    def run_floors(self, board: str, *, valid: bool, diagnostic: str = "") -> None:
        parsed = parse_board(board)
        self.assertEqual(parsed.get("errors"), [], parsed)
        with tempfile.TemporaryDirectory(prefix="saipen-floor-field-") as tmp:
            fixture = Path(tmp)
            memory = fixture / ".saipen"
            memory.mkdir()
            for name, text in (
                ("STATE.md", audit_floor.GOOD_STATE),
                ("BOARD.md", board), ("LOG.md", audit_floor.GOOD_LOG),
            ):
                (memory / name).write_text(text, encoding="utf-8")
            runners = []
            bash = audit_floor.find_bash()
            pwsh = audit_floor.find_pwsh()
            if bash:
                runners.append((
                    "sh", [bash, str(ROOT / "tests/validate.sh")], audit_floor.bash_env(bash),
                ))
            if pwsh:
                runners.append((
                    "ps1", [pwsh, "-NoProfile", "-ExecutionPolicy", "Bypass",
                            "-File", str(ROOT / "tests/validate.ps1")], os.environ.copy(),
                ))
            self.assertTrue(runners, "no portable floor is available")
            before = {p.name: p.read_bytes() for p in memory.iterdir()}
            for label, command, environment in runners:
                with self.subTest(floor=label):
                    result = subprocess.run(command, cwd=fixture, env=environment,
                                            capture_output=True, text=True, encoding="utf-8",
                                            errors="replace", timeout=30)
                    output = result.stdout + result.stderr
                    if valid:
                        self.assertEqual(result.returncode, 0, output)
                    else:
                        self.assertNotEqual(result.returncode, 0, "known-bad control passed")
                        self.assertIn(diagnostic, output)
                    self.assertEqual({p.name: p.read_bytes() for p in memory.iterdir()}, before)

    def test_description_and_blocker_prose_do_not_create_dependencies(self) -> None:
        board = """# Board
## DOING
## TODO
- [ ] T-001 Documentation example needs: T-999 | verify: prose is opaque
- [ ] T-002 Actual dependency | needs: T-001 | verify: dependency resolves
## DONE
## BLOCKED
- [ ] T-003 Parked work | blocker: narrative mentions needs: T-999 and needs: external service
"""
        self.run_floors(board, valid=True)

    def test_narrative_self_reference_does_not_create_a_cycle(self) -> None:
        board = audit_floor.GOOD_BOARD.replace("a ticket", "Example needs: T-001")
        self.run_floors(board, valid=True)

    def test_real_dangling_field_still_fails(self) -> None:
        board = audit_floor.GOOD_BOARD.replace("a ticket", "a ticket | needs: T-999")
        self.run_floors(board, valid=False, diagnostic="dangling needs:")

    def test_real_cycle_still_fails(self) -> None:
        board = audit_floor.GOOD_BOARD.replace("a ticket", "a ticket | needs: T-002")
        board = board.replace("## DONE", "- [ ] T-002 second | needs: T-001\n## DONE")
        self.run_floors(board, valid=False, diagnostic="cyclic needs:")


class NativeParityTransport(unittest.TestCase):
    def probe(self, name: str, platform: str, *, validator_return: int,
              floor_return: int) -> tuple[list[list[str]], str]:
        with tempfile.TemporaryDirectory(prefix="saipen-parity-native-") as tmp:
            home = Path(tmp) / "home"
            (home / "tools").mkdir(parents=True)
            (home / "tools/audit_checks.py").write_text("IGNORE = None\n", encoding="utf-8")
            fake_os = types.SimpleNamespace(name=name, path=os.path, environ={})
            fake_sys = types.SimpleNamespace(platform=platform, executable=sys.executable,
                                             modules=sys.modules)
            calls = []

            def run(command, **kwargs):
                calls.append(command)
                result = validator_return if command[0] == sys.executable else floor_return
                return subprocess.CompletedProcess(
                    command, result, stdout="FAIL: deliberate control\n", stderr="",
                )

            output = io.StringIO()
            previous = sys.modules.get("audit_checks")
            try:
                with patch.object(audit_parity, "HOME", home), \
                        patch.object(audit_parity, "os", fake_os), \
                        patch.object(audit_parity, "sys", fake_sys), \
                        patch.object(audit_parity, "find_bash", return_value="test-bash"), \
                        patch.object(audit_parity, "bash_env", return_value={}), \
                        patch.object(audit_parity.subprocess, "run", side_effect=run), \
                        contextlib.redirect_stdout(output):
                    self.assertEqual(audit_parity.main(), 1, "known-bad preflight passed")
            finally:
                if previous is None:
                    sys.modules.pop("audit_checks", None)
                else:
                    sys.modules["audit_checks"] = previous
            return calls, output.getvalue()

    def test_win32_runtime_uses_powershell_without_changing_the_timeout(self) -> None:
        calls, _output = self.probe("nt", "win32", validator_return=1, floor_return=0)
        self.assertEqual(calls[1][0], "powershell.exe")
        self.assertIn("tests/validate.ps1", calls[1])
        self.assertEqual(audit_parity.VALIDATOR_TIMEOUT, 60)
        self.assertEqual(audit_parity.BASELINE, 11)

    def test_posix_runtime_keeps_the_bash_floor(self) -> None:
        calls, _output = self.probe("posix", "linux", validator_return=1, floor_return=0)
        self.assertEqual(calls[1], ["test-bash", "tests/validate.sh"])

    def test_native_floor_failure_names_the_runner_that_failed(self) -> None:
        _calls, output = self.probe("nt", "win32", validator_return=0, floor_return=1)
        self.assertIn("tests/validate.ps1 rejects an UNMODIFIED copy", output)


if __name__ == "__main__":
    unittest.main()
