"""T-1686: exercise the real launch boundary while its spawn interlock stays armed."""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import test_hermetic_env as hermetic  # noqa: E402
from saipen_engine import host_authority_client as policy  # noqa: E402
from saipen_engine import host_launch as launch, host_taxonomy as taxonomy  # noqa: E402


def setUpModule():
    hermetic.isolate_host_session()


class StrictLaunch(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory(prefix="saipen-t1686-")
        self.addCleanup(scratch.cleanup)
        self.tmp = Path(scratch.name)
        self.home = self.tmp / "home"
        self.project = self.tmp / "project"
        self.home.mkdir()
        (self.project / ".saipen").mkdir(parents=True)
        environment = mock.patch.dict(os.environ, {
            "HOME": str(self.home), "USERPROFILE": str(self.home),
            "HOMEDRIVE": "", "HOMEPATH": "", launch.ENV_FORBID_HOST_SPAWN: "1",
        })
        environment.start()
        self.addCleanup(environment.stop)
        self.hosts = [str(item["id"]) for item in launch._registry_adapters()
                      if item.get("launch_executable")
                      and item.get("degraded_mode") == "DEGRADED_ALLOWED_DEFAULT"]
        self.assertTrue(self.hosts)

    def choose(self, mode):
        if mode == "absent":
            return
        if mode == "malformed":
            path = policy.mode_path(self.home)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("not a policy", encoding="utf-8")
            return
        self.assertTrue(policy.set_authority_mode(mode, self.home)["ok"])

    def boundary(self, host, *, prelaunch=True, proven=False):
        fault = None if proven else launch.HostLaunchRefusal("fixture installed runtime unproven")
        warning = io.StringIO()
        with mock.patch.object(launch, "prelaunch_runtime", side_effect=fault,
                               return_value={"ok": True}) as proof, \
                mock.patch.object(launch.shutil, "which", return_value=str(self.tmp / "host")) as locate, \
                mock.patch.object(launch.subprocess, "run") as spawn, \
                contextlib.redirect_stderr(warning):
            with self.assertRaises(launch.HostLaunchRefusal) as caught:
                launch.launch_host(host, self.project, "oracle-seat", prelaunch=prelaunch)
        spawn.assert_not_called()
        return caught.exception, warning.getvalue(), proof, locate

    def test_strict_refuses_every_degrading_host_before_executable_selection(self):
        self.choose("strict")
        for host in self.hosts:
            with self.subTest(host=host):
                self.assertFalse(launch.launch_degrades(host))
                error, warning, proof, locate = self.boundary(host)
                proof.assert_called_once_with(host)
                locate.assert_not_called()
                self.assertEqual(warning, "")
                self.assertEqual(getattr(error, "operator_action", None), taxonomy.REPAIR)
                self.assertIn(taxonomy.REPAIR, str(error))

    def test_strict_cannot_skip_the_proof_with_the_legacy_prelaunch_flag(self):
        self.choose("strict")
        for host in self.hosts:
            with self.subTest(host=host):
                error, warning, proof, locate = self.boundary(host, prelaunch=False)
                proof.assert_called_once_with(host)
                locate.assert_not_called()
                self.assertEqual(warning, "")
                self.assertEqual(getattr(error, "operator_action", None), taxonomy.REPAIR)

    def test_malformed_policy_is_strict_at_the_launch_boundary(self):
        self.choose("malformed")
        for host in self.hosts:
            with self.subTest(host=host):
                self.assertFalse(launch.launch_degrades(host))
                error, warning, _, locate = self.boundary(host)
                locate.assert_not_called()
                self.assertEqual(warning, "")
                self.assertEqual(getattr(error, "operator_action", None), taxonomy.REPAIR)

    def allowed(self, mode):
        self.choose(mode)
        for host in self.hosts:
            with self.subTest(host=host):
                self.assertTrue(launch.launch_degrades(host))
                error, warning, proof, locate = self.boundary(host)
                proof.assert_called_once_with(host)
                locate.assert_called_once()
                self.assertIn("without a proven installed runtime", warning)
                self.assertIn(launch.ENV_FORBID_HOST_SPAWN, str(error))

    def test_the_missing_policy_retains_the_default_warning_and_spawn_boundary(self):
        self.allowed("absent")

    def test_explicit_degraded_policy_retains_the_warning_and_spawn_boundary(self):
        self.allowed("degraded")

    def test_a_proven_runtime_reaches_the_spawn_interlock_under_strict(self):
        self.choose("strict")
        for host in self.hosts:
            with self.subTest(host=host):
                error, warning, proof, locate = self.boundary(host, proven=True)
                proof.assert_called_once_with(host)
                locate.assert_called_once()
                self.assertEqual(warning, "")
                self.assertIn(launch.ENV_FORBID_HOST_SPAWN, str(error))


    def test_the_cli_exposes_the_canonical_repair_action_without_starting_a_host(self):
        self.choose("strict")
        child = """
import sys
from unittest import mock
import tools.saipen as cli
from saipen_engine import host_launch, runtime_bootstrap
report = {"ok": False, "code": "T1686_UNPROVEN", "detail": "unproven runtime"}
with mock.patch.object(runtime_bootstrap, "prelaunch", return_value=report) as proof, \
        mock.patch.object(host_launch.shutil, "which") as locate, \
        mock.patch.object(host_launch.subprocess, "run") as spawn:
    code = cli.main(["--json", "--project-root", sys.argv[1], "--agent", "oracle-seat",
                     "launch", "claude"])
    proof.assert_called_once_with("claude", resync=True)
    locate.assert_not_called()
    spawn.assert_not_called()
raise SystemExit(code)
"""
        completed = subprocess.run(
            [sys.executable, "-B", "-c", child, str(self.project)], cwd=ROOT,
            env=hermetic.hermetic_env(HOME=str(self.home), USERPROFILE=str(self.home),
                                      HOMEDRIVE="", HOMEPATH="", PYTHONUTF8="1"),
            capture_output=True, encoding="utf-8", timeout=30,
        )
        self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
        reply = json.loads(completed.stdout)
        self.assertFalse(reply["ok"])
        self.assertEqual(reply["code"], "HOST_LAUNCH_REFUSED")
        self.assertEqual(reply.get("operator_action"), taxonomy.REPAIR)
        self.assertIn("T1686_UNPROVEN", reply["detail"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
