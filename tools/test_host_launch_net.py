"""T-1343 Target D: a unit fixture cannot start a real host by accident.

The T-1327 launch fixture believed it had replaced `prelaunch`. It had replaced
the attribute on a DIFFERENT module object of the same file (T-1343), so the
real prelaunch ran, `subprocess.run` was reached, and the operator's real
OpenCode host started -- with its MCP children -- and the suite hung until the
process tree was killed by hand. The module-identity repair removes THAT cause.
This suite exists because the next missed stub will have a different cause.

The net is therefore not a stronger monkeypatch and not a timeout. A timeout
only shortens the damage, and any patch-based guard shares the failure mode it
is supposed to catch. `saipen_engine.host_launch` reads one interlock from the
PROCESS environment and refuses BEFORE `subprocess.run` exists; the harness
arms it for every module that calls `isolate_host_session()`.

Proof here is a real executable, not an assertion about a mock: the fake host
WRITES A FILE when it runs. Absence of that file is the evidence that no
process was created, and the control case -- the same fixture with the
interlock cleared -- proves the file appears when the launch is allowed
through, so the refusal is the interlock and not a broken fixture.
"""

from __future__ import annotations

import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import host_launch  # noqa: E402
from test_hermetic_env import FORBID_HOST_SPAWN, hermetic_env, isolate_host_session  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


class _FakeHost:
    """A real `opencode` executable that records the fact that it ran."""

    def __init__(self, base: Path) -> None:
        self.bin = base / "bin"
        self.bin.mkdir(parents=True)
        self.receipt = base / "the-host-ran.txt"
        if os.name == "nt":
            script = self.bin / "opencode.CMD"
            script.write_text(
                "@echo off\r\n" f'> "{self.receipt}" echo ran\r\n', encoding="ascii"
            )
        else:
            script = self.bin / "opencode"
            script.write_text(
                "#!/bin/sh\n" f'printf ran > "{self.receipt}"\n', encoding="ascii"
            )
            script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)
        self.executable = script

    def env(self) -> dict[str, str]:
        """The operator's environment with the fake host ahead of the real one."""
        env = dict(os.environ)
        env["PATH"] = str(self.bin) + os.pathsep + env.get("PATH", "")
        return env

    def ran(self) -> bool:
        return self.receipt.exists()


class _InterlockCleared:
    """Clear the process-level interlock for one deliberate launch."""

    def __enter__(self) -> None:
        self._previous = os.environ.pop(FORBID_HOST_SPAWN, None)

    def __exit__(self, *_exc: object) -> None:
        if self._previous is not None:
            os.environ[FORBID_HOST_SPAWN] = self._previous


class _FakeClaudeHost:
    """A real `claude` executable that records the envelope it was started with."""

    def __init__(self, base: Path) -> None:
        self.bin = base / "bin"
        self.bin.mkdir(parents=True)
        self.receipt = base / "claude-ran.txt"
        self.envelope = base / "claude-envelope.txt"
        if os.name == "nt":
            script = self.bin / "claude.CMD"
            script.write_text(
                "@echo off\r\n"
                f'> "{self.receipt}" echo ran\r\n'
                f'> "{self.envelope}" echo %SAIPEN_AGENT%^|%SAIPEN_PROJECT_ROOT%\r\n',
                encoding="ascii",
            )
        else:
            script = self.bin / "claude"
            script.write_text(
                "#!/bin/sh\n"
                f'printf ran > "{self.receipt}"\n'
                f'printf "%s|%s" "$SAIPEN_AGENT" "$SAIPEN_PROJECT_ROOT" > "{self.envelope}"\n',
                encoding="ascii",
            )
            script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)
        self.executable = script

    def env(self) -> dict[str, str]:
        env = dict(os.environ)
        env["PATH"] = str(self.bin) + os.pathsep + env.get("PATH", "")
        return env

    def ran(self) -> bool:
        return self.receipt.exists()


def _project(base: Path) -> Path:
    root = base / "project"
    (root / ".saipen").mkdir(parents=True)
    return root


class RealHostSpawnNetTests(unittest.TestCase):
    def test_the_interlock_refuses_before_any_process_is_created(self) -> None:
        with tempfile.TemporaryDirectory(prefix="saipen-t1343-net-") as tmp:
            base = Path(tmp)
            host = _FakeHost(base)
            self.assertEqual(os.environ.get(FORBID_HOST_SPAWN), "1")

            with self.assertRaises(host_launch.HostLaunchRefusal) as caught:
                host_launch.launch_host(
                    "opencode",
                    _project(base),
                    "t1343-fixture",
                    base_env=host.env(),
                    prelaunch=False,
                )

            message = str(caught.exception)
            self.assertIn(FORBID_HOST_SPAWN, message)
            self.assertIn("No process was created", message)
            self.assertIn("opencode", message)
            self.assertFalse(
                host.ran(),
                "the host executable ran despite the refusal: "
                f"{host.receipt} exists",
            )

    def test_the_same_fixture_does_start_a_host_once_the_interlock_is_cleared(
        self,
    ) -> None:
        """The red control: without this, the refusal above proves nothing."""
        with tempfile.TemporaryDirectory(prefix="saipen-t1343-net-") as tmp:
            base = Path(tmp)
            host = _FakeHost(base)

            with _InterlockCleared():
                returncode = host_launch.launch_host(
                    "opencode",
                    _project(base),
                    "t1343-fixture",
                    base_env=host.env(),
                    prelaunch=False,
                )

            self.assertEqual(returncode, 0)
            self.assertTrue(
                host.ran(),
                "the fixture never reached the executable, so the refusal case "
                "is not evidence about the interlock",
            )

    def test_a_fixture_scrubbing_the_launch_environment_cannot_disarm_it(self) -> None:
        """The interlock is process state; the launch environment is fixture state."""
        with tempfile.TemporaryDirectory(prefix="saipen-t1343-net-") as tmp:
            base = Path(tmp)
            host = _FakeHost(base)
            scrubbed = host.env()
            scrubbed.pop(FORBID_HOST_SPAWN, None)

            with self.assertRaises(host_launch.HostLaunchRefusal):
                host_launch.launch_host(
                    "opencode",
                    _project(base),
                    "t1343-fixture",
                    base_env=scrubbed,
                    prelaunch=False,
                )
            self.assertFalse(host.ran())


class HarnessArmsTheNetTests(unittest.TestCase):
    """Every module that isolates its host session gets the net with it."""

    def test_isolate_host_session_arms_the_interlock(self) -> None:
        self.assertEqual(os.environ.get(FORBID_HOST_SPAWN), "1")

    def test_hermetic_env_carries_the_interlock_into_children(self) -> None:
        self.assertEqual(hermetic_env().get(FORBID_HOST_SPAWN), "1")
        self.assertEqual(
            hermetic_env({"PATH": os.environ.get("PATH", "")}).get(FORBID_HOST_SPAWN),
            "1",
        )
        self.assertNotIn(
            FORBID_HOST_SPAWN,
            hermetic_env(**{FORBID_HOST_SPAWN: None}),
            "a deliberate real-host smoke must be able to clear it explicitly",
        )


class ClaudeLaunchTargetTests(unittest.TestCase):
    """Claude Code is a canonical launch target, through the same abstraction.

    The registry already owns Claude as a first-class adapter; the launcher must
    reach it by host id, never by a special case in the CLI dispatcher.
    """

    def test_claude_resolves_through_the_host_registry(self) -> None:
        self.assertEqual(host_launch.SUPPORTED_HOSTS.get("claude"), "claude")
        self.assertIn(
            "claude",
            host_launch._HOST_IDENTITIES,
            "a host name is never a SAIPEN seat",
        )

    def test_the_interlock_refuses_claude_before_any_process_is_created(self) -> None:
        with tempfile.TemporaryDirectory(prefix="saipen-claude-launch-") as tmp:
            base = Path(tmp)
            host = _FakeClaudeHost(base)

            with self.assertRaises(host_launch.HostLaunchRefusal) as caught:
                host_launch.launch_host(
                    "claude",
                    _project(base),
                    "claude1",
                    base_env=host.env(),
                    prelaunch=False,
                )

            message = str(caught.exception)
            self.assertIn(FORBID_HOST_SPAWN, message)
            self.assertIn("claude", message)
            self.assertFalse(host.ran())

    def test_a_cleared_interlock_launches_claude_with_the_seat_and_project(self) -> None:
        with tempfile.TemporaryDirectory(prefix="saipen-claude-launch-") as tmp:
            base = Path(tmp)
            host = _FakeClaudeHost(base)
            project = _project(base)

            with _InterlockCleared():
                returncode = host_launch.launch_host(
                    "claude",
                    project,
                    "claude1",
                    base_env=host.env(),
                    prelaunch=False,
                )

            self.assertEqual(returncode, 0)
            self.assertTrue(host.ran())
            envelope = host.envelope.read_text(encoding="utf-8")
            self.assertIn("claude1", envelope)
            self.assertIn(str(project), envelope)


if __name__ == "__main__":
    unittest.main(verbosity=2)
