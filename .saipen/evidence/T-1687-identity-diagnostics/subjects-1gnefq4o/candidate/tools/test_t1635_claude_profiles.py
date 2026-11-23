"""T-1635: profile discovery, scoped installation and process-bound hook proof."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import install_host_guard
from saipen_engine import host_authority_identity as identity
from saipen_engine import host_authority_process as processes
from saipen_engine import host_integration as integration
from saipen_engine import runtime_bootstrap as bootstrap
from test_hermetic_env import isolate_host_session

ROOT = Path(__file__).resolve().parent.parent


def setUpModule() -> None:
    # T-1685: the operator's host profile and binding never reach a fixture.
    isolate_host_session()


class Profiles(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.home = Path(scratch.name)
        self.first = self.home / ".claude"
        self.second = self.home / ".claude-account2"
        self.first.mkdir()
        self.second.mkdir()
        environment = mock.patch.dict(os.environ, {
            "HOME": str(self.home), "USERPROFILE": str(self.home),
            "HOMEDRIVE": "", "HOMEPATH": "", "CLAUDE_CONFIG_DIR": "",
        })
        environment.start()
        self.addCleanup(environment.stop)

    def test_doctor_lists_each_profile_without_reading_credentials(self):
        for directory in (self.first, self.second):
            (directory / ".credentials.json").write_text("must not be read", encoding="utf-8")
        original = Path.open

        def guarded(path, *args, **kwargs):
            if "credential" in path.name:
                raise AssertionError("credential file was opened")
            return original(path, *args, **kwargs)

        with mock.patch.object(Path, "open", guarded):
            report = integration.doctor(home=self.home, only="claude")
        rows = {Path(item["facts"]["host_home"]): item for item in report["hosts"]}
        self.assertEqual(set(rows), {self.first, self.second})
        self.assertEqual(rows[self.second]["state"], integration.STATE_UNINSTALLED)
        self.assertIn(str(self.second), integration.render(report))

    def test_environment_profile_outside_home_is_observed_beside_default(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": directory}):
                report = integration.doctor(home=self.home, only="claude")
            homes = {Path(item["facts"]["host_home"]) for item in report["hosts"]}
            self.assertIn(Path(directory), homes)
            self.assertIn(self.first, homes)

    def test_native_install_selects_one_profile_and_keeps_unrelated_settings(self):
        config = self.second / "settings.json"
        config.write_text(json.dumps({"permissions": {"allow": ["Read"]}}), encoding="utf-8")
        first_bytes = b'{"first":true}\n'
        (self.first / "settings.json").write_bytes(first_bytes)
        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.second)}):
            result = install_host_guard.install("claude", self.home, ROOT, verify=False)
        self.assertEqual(Path(result["artifact"]), self.second / "hooks" / "saipen-guard.py")
        self.assertEqual(Path(result["config"]), config)
        self.assertEqual(json.loads(config.read_text())["permissions"], {"allow": ["Read"]})
        self.assertEqual((self.first / "settings.json").read_bytes(), first_bytes)
        self.assertFalse((self.first / "hooks").exists())

    def test_explicit_repair_installs_only_the_requested_profile(self):
        source = {"canonical": str(ROOT), "generation": "test", "proven": True,
                  "detail": "", "kind": "checkout", "version": "test"}
        installed = subprocess.CompletedProcess([], 0, "installed", "")
        with mock.patch.object(integration, "_source_facts", return_value=source), \
             mock.patch.object(bootstrap, "_invoke_installer", return_value=installed) as invoke, \
             mock.patch.object(integration, "_start_authority", return_value={"ok": True}):
            integration.repair(home=self.home, only="claude", profile=self.second)
        self.assertEqual(invoke.call_count, 1)
        self.assertEqual(invoke.call_args.args[:2], (ROOT, "claude"))
        self.assertEqual(Path(invoke.call_args.kwargs["profile"]), self.second)

    def test_registered_launcher_profile_is_discovered_without_scanning_its_parent(self):
        registry = integration.load_registry(ROOT)
        launcher_profile = self.home / "launcher-home" / "account"
        launcher_profile.mkdir(parents=True)
        adapter = next(item for item in registry["adapters"] if item["id"] == "claude")
        adapter["launchers"] = [{"env": {"CLAUDE_CONFIG_DIR": str(launcher_profile)}}]
        with mock.patch.object(integration, "load_registry", return_value=registry):
            report = integration.doctor(home=self.home, only="claude")
        homes = {Path(item["facts"]["host_home"]) for item in report["hosts"]}
        self.assertIn(launcher_profile, homes)

    def test_health_records_do_not_overwrite_another_profiles_verification(self):
        from saipen_engine.claude_profiles import health_file

        for profile, state in ((self.first, "ADMITTED"), (self.second, "DEGRADED")):
            path = health_file(self.home, profile)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"state": state}), encoding="utf-8")
        self.assertEqual(integration.read_health("claude", self.home, self.first)["state"],
                         "ADMITTED")
        self.assertEqual(integration.read_health("claude", self.home, self.second)["state"],
                         "DEGRADED")

    def test_selected_profile_uninstall_preserves_the_other_profile_and_credentials(self):
        install_host_guard.install("claude", self.home, ROOT, verify=False)
        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.second)}):
            install_host_guard.install("claude", self.home, ROOT, verify=False)
            credentials = self.second / ".credentials.json"
            credentials.write_bytes(b"preserve exactly")
            result = install_host_guard.uninstall("claude", self.home, ROOT, live_host=False)
        self.assertTrue(result["artifact_removed"])
        self.assertTrue((self.first / "hooks" / "saipen-guard.py").is_file())
        self.assertFalse((self.second / "hooks" / "saipen-guard.py").exists())
        self.assertEqual(credentials.read_bytes(), b"preserve exactly")

    def test_named_profile_cli_is_reachable_and_requires_claude(self):
        command = [sys.executable, "-B", str(ROOT / "tools" / "saipen.py"), "host", "doctor",
                   "--home", str(self.home), "--host", "claude", "--profile", str(self.second),
                   "--json"]
        result = subprocess.run(command, capture_output=True, stdin=subprocess.DEVNULL,
                                timeout=90, cwd=str(self.home), check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(json.loads(result.stdout)["hosts"]), 1)
        command[command.index("claude")] = "codex"
        result = subprocess.run(command, capture_output=True, stdin=subprocess.DEVNULL,
                                timeout=90, cwd=str(self.home), check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["code"], "VALIDATION_FAILED")

    def test_canonical_injector_installs_runtime_into_only_the_selected_profile(self):
        from test_runtime_bootstrap import POWERSHELL, _disposable_env

        if os.name == "nt":
            self.assertIsNotNone(POWERSHELL, "PowerShell runtime unavailable")
            command = [POWERSHELL, "-NoProfile", "-NonInteractive", "-File",
                       str(ROOT / "bootstrap" / "inject.ps1"), "-SkillHome", str(ROOT / "saipen"),
                       "-AdapterId", "claude"]
        else:
            command = ["bash", str(ROOT / "bootstrap" / "inject.sh"), "--adapter", "claude"]
        env = _disposable_env(self.home)
        env["CLAUDE_CONFIG_DIR"] = str(self.second)
        result = subprocess.run(command, capture_output=True, stdin=subprocess.DEVNULL,
                                timeout=600, cwd=str(ROOT), env=env, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        runtime = self.second / "skills" / "saipen"
        self.assertTrue((runtime / "tools" / "saipen.py").is_file())
        self.assertTrue((self.second / "hooks" / "saipen-guard.py").is_file())
        self.assertFalse((self.first / "skills" / "saipen").exists())
        self.assertFalse((self.first / "hooks").exists())
        installed = install_host_guard.install("claude", self.home, ROOT,
                                              check=True, profile=self.second)
        self.assertTrue(installed["current"])
        self.assertEqual(Path(installed["saipen_root"]), runtime)

    def test_bash_injector_expands_selected_profile_and_keeps_other_hosts(self):
        bash = shutil.which("bash") if os.name != "nt" else None
        if os.name == "nt":
            candidate = (Path(os.environ.get("PROGRAMFILES", "C:/Program Files"))
                         / "Git/bin/bash.exe")
            bash = str(candidate) if candidate.is_file() else None
        if bash is None:
            self.skipTest("Bash runtime unavailable; native injector covered separately")
        source = (ROOT / "bootstrap/inject.sh").read_text(encoding="utf-8")
        # Execute the shipped expansion function, without the installer's effects.
        function = source[source.index("expand_home() {"):].split("\n}\n", 1)[0] + "\n}\n"
        command = (function + "expand_home '~/.claude/skills/saipen'\n"
                   "expand_home '~/.config/opencode'\n")
        env = dict(os.environ, CLAUDE_CONFIG_DIR="/selected/profile with spaces",
                   HOME="/default/home")
        result = subprocess.run([bash, "--noprofile", "--norc"], input=command,
                                env=env, capture_output=True, text=True,
                                timeout=30, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [
            "/selected/profile with spaces/skills/saipen", "/default/home/.config/opencode",
        ])


class HookProfileProof(unittest.TestCase):
    def proof(self, hook, selected):
        chain = [
            processes.ProcessFact(20, 10, "python", "python", (
                "python", hook, "--host", "claude", "--saipen-root", "/runtime"), 20),
            processes.ProcessFact(10, 1, "claude", "claude", ("claude",), 10),
        ]
        policy = identity.IdentityPolicy(
            host="claude", host_images=("claude",),
            hook_artifacts=("/user/.claude/hooks/saipen-guard.py",),
            profile_hook="hooks/saipen-guard.py",
        )
        return identity.prove_hook_invocation(
            chain, policy, hook_for_host=lambda pid: selected,
            artifact_current=lambda script: True,
        )

    def test_selected_profile_hook_is_accepted(self):
        hook = "/user/.claude-account2/hooks/saipen-guard.py"
        self.assertTrue(self.proof(hook, hook).ok)

    def test_other_profile_hook_is_refused_even_with_current_bytes(self):
        hook = "/user/.claude/hooks/saipen-guard.py"
        selected = "/user/.claude-account2/hooks/saipen-guard.py"
        proof = self.proof(hook, selected)
        self.assertFalse(proof.ok)
        self.assertEqual(proof.reason, identity.REASON_HOOK_ARTIFACT_MISMATCH)

    def test_unobservable_profile_is_not_treated_as_default(self):
        proof = self.proof("/user/.claude/hooks/saipen-guard.py", None)
        self.assertFalse(proof.ok)
        self.assertEqual(proof.reason, identity.REASON_IDENTITY_UNAVAILABLE)

    def test_real_process_environment_observes_only_requested_value(self):
        env = dict(os.environ)
        env["CLAUDE_CONFIG_DIR"] = str(ROOT / "tests" / "profile with spaces")
        child = subprocess.Popen(
            [sys.executable, "-c", "import time; print('ready', flush=True); time.sleep(30)"],
            env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        try:
            self.assertEqual(child.stdout.readline().strip(), b"ready")
            self.assertEqual(processes.environment_value(child.pid, "CLAUDE_CONFIG_DIR"),
                             (True, env["CLAUDE_CONFIG_DIR"]))
            self.assertEqual(processes.environment_value(child.pid, "SAIPEN_MISSING_PROFILE_TEST"),
                             (True, None))
        finally:
            child.kill()
            child.wait(timeout=10)
            child.stdout.close()


class SharedAuthority(unittest.TestCase):
    def test_real_hooks_in_two_profiles_share_one_service_without_profile_confusion(self):
        from saipen_engine import protocol_admission
        from test_host_fixture import HostFixture
        from test_protocol_admission import World

        with tempfile.TemporaryDirectory() as temporary:
            scratch = Path(temporary)
            world = World(scratch, mode="strict")
            try:
                second = world.home / ".claude-account2"
                second.mkdir()
                shutil.copyfile(world.home / ".claude" / "CLAUDE.md", second / "CLAUDE.md")
                with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(second)}):
                    install_host_guard.install(
                        "claude", world.home, ROOT, verify=False, profile=second
                    )
                fixture = HostFixture(scratch, home=world.home, project=world.project,
                                      authority=world.authority)
                try:
                    self.assertTrue(fixture.available, "stand-in host interpreter unavailable")
                    # The service is started in the default profile's environment.
                    with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": ""}):
                        first = fixture.prompt(session="profile-1")
                    self.assertNotIn("decision", first, first)
                    with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(second)}):
                        with mock.patch.object(fixture, "hook_path",
                                               return_value=second / "hooks" / "saipen-guard.py"):
                            admitted = fixture.prompt(session="profile-2")
                        self.assertNotIn("decision", admitted, admitted)
                        context = admitted["hookSpecificOutput"]["additionalContext"]
                        self.assertIn("=== BOOT.md", context)
                        # Identical current bytes from another profile are still refused.
                        foreign = fixture.prompt(session="profile-foreign")
                    self.assertEqual(foreign["decision"], "block", foreign)
                    self.assertIn("another configuration profile", foreign["reason"])
                    for session in ("profile-1", "profile-2"):
                        ledger = protocol_admission._ledger_path(world.project, session)
                        self.assertTrue(ledger.is_file(), session)
                finally:
                    fixture.close()
            finally:
                shutil.rmtree(world.project)


if __name__ == "__main__":
    unittest.main()
