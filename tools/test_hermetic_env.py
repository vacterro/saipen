"""Hermetic test environment: an outer host session never binds a fixture.

Production SAIPEN honours the host/session carriers on purpose -- a verified
`SAIPEN_PROJECT_ROOT`/`SAIPEN_PROJECT_LINEAGE` pair outranks the Git worktree,
`SAIPEN_AGENT` names the acting seat, `SAIPEN_CAPABILITY` narrows the session.
A test suite launched from inside such a session (an OpenCode seat running
`python -m unittest`) inherits all of them. Every fixture that resolves a
project, spawns the CLI or drives the guard then binds the OPERATOR's live
project instead of its disposable one: measured with a valid foreign binding,
eleven guard/adapter/recovery families failed and the fixtures ran their
recovery against the foreign project.

The repair belongs to the harness, never to the production binding checks:
`isolate_host_session()` removes the host-session carriers for the lifetime of
one test module and restores them afterwards. A test that verifies binding
inheritance sets the carriers it is testing explicitly, exactly as before.

Usage, once per test module that builds SAIPEN fixtures::

    from test_hermetic_env import isolate_host_session

    def setUpModule() -> None:
        isolate_host_session()
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

#: Every variable through which a HOST SESSION declares something the engine
#: or a host adapter acts on. None of them is test input unless a test sets it.
HOST_SESSION_VARIABLES = (
    "SAIPEN_PROJECT_ROOT",
    "SAIPEN_PROJECT_LINEAGE",
    "SAIPEN_AGENT",
    "SAIPEN_CAPABILITY",
    "SAIPEN_HOST_ENFORCEMENT",
    "SAIPEN_RUNTIME_INFO",
    "SAIPEN_SKILL_ROOT",
    "SAIPEN_GUARD_STARTUP_PROBE",
)


def isolate_host_session() -> dict[str, str]:
    """Remove host-session carriers now; restore them when the module ends.

    Call from `setUpModule`. The removed values are returned for diagnostics
    and put back by a module cleanup, so the next module -- and the operator's
    shell -- sees the environment exactly as it was.
    """
    removed = {
        key: os.environ.pop(key) for key in HOST_SESSION_VARIABLES if key in os.environ
    }

    def restore() -> None:
        for key in HOST_SESSION_VARIABLES:
            os.environ.pop(key, None)
        os.environ.update(removed)

    unittest.addModuleCleanup(restore)
    return removed


def hermetic_env(base: dict[str, str] | None = None, **overrides: str | None) -> dict[str, str]:
    """A child-process environment with no host-session carrier.

    `overrides` are applied last; a value of None removes the key. Use it where
    a subprocess must be hermetic independent of module setup.
    """
    env = dict(os.environ if base is None else base)
    for key in HOST_SESSION_VARIABLES:
        env.pop(key, None)
    for key, value in overrides.items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    return env


_HOSTILE = (
    ("SAIPEN_PROJECT_ROOT", str(Path(tempfile.gettempdir()) / "saipen-foreign-project")),
    ("SAIPEN_PROJECT_LINEAGE", "lineage-" + "f" * 32),
    ("SAIPEN_AGENT", "foreign-seat"),
)


class HermeticEnvironmentTests(unittest.TestCase):
    """The helper itself: hostile outer values never reach a fixture."""

    def test_hermetic_env_strips_every_carrier_and_keeps_overrides(self) -> None:
        base = {**dict(_HOSTILE), "PATH": os.environ.get("PATH", ""), "KEEP": "1"}
        env = hermetic_env(base, SAIPEN_AGENT="fixture-seat", KEEP=None)
        for key in HOST_SESSION_VARIABLES:
            if key != "SAIPEN_AGENT":
                self.assertNotIn(key, env)
        self.assertEqual(env["SAIPEN_AGENT"], "fixture-seat")
        self.assertNotIn("KEEP", env)

    def test_a_child_process_sees_no_outer_binding(self) -> None:
        env = hermetic_env({**os.environ, **dict(_HOSTILE)})
        probe = subprocess.run(
            [
                sys.executable,
                "-c",
                "import json, os; print(json.dumps({k: os.environ.get(k) for k in "
                + repr(list(HOST_SESSION_VARIABLES))
                + "}))",
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
            check=True,
        )
        self.assertNotIn("foreign", probe.stdout)
        self.assertNotIn("lineage-", probe.stdout)


if __name__ == "__main__":
    unittest.main()
