"""T-1686: the real launch boundary respects the operator's admission policy."""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import host_launch, host_taxonomy, runtime_bootstrap  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


DEGRADING_HOSTS = tuple(
    str(adapter["id"])
    for adapter in host_launch._registry_adapters()
    if adapter.get("launch_executable")
    and adapter.get("degraded_mode") == "DEGRADED_ALLOWED_DEFAULT"
)


class LaunchPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="saipen-t1686-")
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.project = self.home / "project"
        (self.project / ".saipen").mkdir(parents=True)
        self.policy_file = self.home / ".saipen" / "authority.json"
        home_patch = patch.object(Path, "home", return_value=self.home)
        home_patch.start()
        self.addCleanup(home_patch.stop)

    def _policy(self, value: object) -> None:
        self.policy_file.parent.mkdir(parents=True, exist_ok=True)
        self.policy_file.write_text(json.dumps(value), encoding="utf-8")

    def _launch(self, host: str, report: dict) -> tuple[str, str]:
        warning = io.StringIO()
        with patch.object(runtime_bootstrap, "prelaunch", return_value=report) as prelaunch, \
                patch.object(host_launch.shutil, "which", return_value=str(self.home / host)), \
                patch.dict(os.environ, {host_launch.ENV_FORBID_HOST_SPAWN: "1"}), \
                patch.object(host_launch.subprocess, "run") as spawn, \
                contextlib.redirect_stderr(warning), \
                self.assertRaises(host_launch.HostLaunchRefusal) as caught:
            host_launch.launch_host(host, self.project, "tester")
        prelaunch.assert_called_once_with(host, resync=True)
        spawn.assert_not_called()
        return str(caught.exception), warning.getvalue()

    @staticmethod
    def _unproven() -> dict:
        return {"ok": False, "code": runtime_bootstrap.PRELAUNCH_FAILED, "detail": "unproven"}

    def _assert_strict_refusal(self) -> None:
        self.assertIn("claude", DEGRADING_HOSTS)
        self.assertIn("opencode", DEGRADING_HOSTS)
        for host in DEGRADING_HOSTS:
            with self.subTest(host=host):
                message, warning = self._launch(host, self._unproven())
                self.assertNotIn(host_launch.ENV_FORBID_HOST_SPAWN, message)
                self.assertIn("not the canonical generation", message)
                self.assertIn(host_taxonomy.REPAIR, message)
                self.assertEqual(warning, "")

    def _assert_degraded_launch(self) -> None:
        self.assertTrue(DEGRADING_HOSTS)
        for host in DEGRADING_HOSTS:
            with self.subTest(host=host):
                message, warning = self._launch(host, self._unproven())
                self.assertIn(host_launch.ENV_FORBID_HOST_SPAWN, message)
                self.assertIn(f"starting {host} without a proven installed runtime", warning)
                self.assertIn(host_taxonomy.REPAIR, warning)

    def test_strict_policy_refuses_every_degrading_host_before_spawn(self) -> None:
        self._policy({"mode": "strict"})
        self._assert_strict_refusal()

    def test_invalid_policy_refuses_instead_of_silently_degrading(self) -> None:
        self._policy({"mode": "unknown"})
        self._assert_strict_refusal()

    def test_unreadable_policy_refuses_instead_of_silently_degrading(self) -> None:
        self.policy_file.mkdir(parents=True)
        self._assert_strict_refusal()

    def test_missing_policy_keeps_the_default_degraded_launch(self) -> None:
        self._assert_degraded_launch()

    def test_explicit_degraded_policy_keeps_the_warning(self) -> None:
        self._policy({"mode": "degraded"})
        self._assert_degraded_launch()

    def test_strict_policy_allows_a_proven_runtime(self) -> None:
        self._policy({"mode": "strict"})
        for host in DEGRADING_HOSTS:
            with self.subTest(host=host):
                message, warning = self._launch(
                    host, {"ok": True, "code": runtime_bootstrap.PRELAUNCH_CURRENT}
                )
                self.assertIn(host_launch.ENV_FORBID_HOST_SPAWN, message)
                self.assertEqual(warning, "")

    def test_degraded_policy_preserves_registry_fail_closed_hosts(self) -> None:
        self._policy({"mode": "degraded"})
        for host in host_launch.SUPPORTED_HOSTS:
            if host in DEGRADING_HOSTS:
                continue
            with self.subTest(host=host):
                message, warning = self._launch(host, self._unproven())
                self.assertNotIn(host_launch.ENV_FORBID_HOST_SPAWN, message)
                self.assertIn("not the canonical generation", message)
                self.assertEqual(warning, "")


if __name__ == "__main__":
    unittest.main()
