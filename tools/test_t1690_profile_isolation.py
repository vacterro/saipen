"""T-1690: fixture writes and nested unittest runs cannot escape their home.

Every profile, including the ambient operator stand-in, is disposable. The
observation API still follows the host's launch profile; a writer for another
home must use that home's default unless the caller names a profile explicitly.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import case as unittest_case
from unittest import mock

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import install_host_guard  # noqa: E402
import test_hermetic_env as hermetic  # noqa: E402
from saipen_engine import claude_profiles, host_integration, runtime_bootstrap  # noqa: E402
from saipen_engine.claude_profiles import ENVIRONMENT  # noqa: E402


def setUpModule() -> None:
    hermetic.isolate_host_session()


def contents(directory: Path) -> dict[str, bytes]:
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in directory.rglob("*") if path.is_file()
    }


class StandIn(unittest.TestCase):
    def setUp(self) -> None:
        scratch = tempfile.TemporaryDirectory(prefix="saipen-t1690-")
        self.addCleanup(scratch.cleanup)
        self.tmp = Path(scratch.name)
        self.operator = self.tmp / "operator"
        self.fixture = self.tmp / "fixture-home"
        self.standin = self.tmp / "standin" / ".claude"
        for directory in (self.operator, self.fixture, self.standin):
            directory.mkdir(parents=True)
        (self.standin / "operator-note").write_bytes(b"leave these bytes alone")
        self.before = contents(self.standin)
        environment = mock.patch.dict(os.environ, {
            "HOME": str(self.operator), "USERPROFILE": str(self.operator),
            "HOMEDRIVE": "", "HOMEPATH": "", ENVIRONMENT: str(self.standin),
        })
        environment.start()
        self.addCleanup(environment.stop)

    def assert_standin_unchanged(self) -> None:
        self.assertEqual(contents(self.standin), self.before)


class InstallerFixtureTests(StandIn):
    def test_a_foreign_home_install_never_follows_the_carrier(self):
        installed = install_host_guard.install("claude", self.fixture, ROOT, verify=False)
        self.assert_standin_unchanged()
        own = self.fixture / ".claude"
        self.assertEqual(Path(installed["artifact"]), own / "hooks" / "saipen-guard.py")
        self.assertEqual(Path(installed["config"]), own / "settings.json")

    def test_a_foreign_home_uninstall_removes_only_its_installed_guard(self):
        own = self.fixture / ".claude"
        install_host_guard.install("claude", self.fixture, ROOT, verify=False, profile=own)
        removed = install_host_guard.uninstall("claude", self.fixture, ROOT, live_host=False)
        self.assertTrue(removed["artifact_removed"], removed)
        self.assertFalse((own / "hooks" / "saipen-guard.py").exists())
        self.assert_standin_unchanged()

    def test_a_foreign_home_rollback_restores_its_kept_generation(self):
        own = self.fixture / ".claude"
        installed = install_host_guard.install(
            "claude", self.fixture, ROOT, verify=False, profile=own
        )
        artifact = Path(installed["artifact"])
        original = artifact.read_bytes()
        install_host_guard.previous_artifact(artifact).write_bytes(original)
        artifact.write_bytes(original + b"\n# current fixture generation\n")
        result = install_host_guard.rollback("claude", self.fixture, ROOT)
        self.assertTrue(result["rolled_back"], result)
        self.assertEqual(artifact.read_bytes(), original)
        self.assert_standin_unchanged()

    def test_the_world_fixture_names_its_profile_without_module_isolation(self):
        from test_protocol_admission import World

        parent = self.tmp / "world"
        parent.mkdir()
        # Keep the inherited writer even after the product repair: this proves
        # that World itself names its profile, independently of that repair.
        selector = "write_directory" if hasattr(claude_profiles, "write_directory") else "directory"
        with mock.patch.object(claude_profiles, selector, claude_profiles.directory):
            world = World(parent, project=self.fixture)
        self.assert_standin_unchanged()
        self.assertTrue((world.home / ".claude" / "hooks" / "saipen-guard.py").is_file())

    def test_the_operator_home_still_installs_into_its_launch_profile(self):
        installed = install_host_guard.install("claude", self.operator, ROOT, verify=False)
        self.assertEqual(Path(installed["artifact"]), self.standin / "hooks" / "saipen-guard.py")

    def test_an_explicit_profile_still_wins_for_a_foreign_home(self):
        chosen = self.tmp / "chosen-profile"
        installed = install_host_guard.install(
            "claude", self.fixture, ROOT, verify=False, profile=chosen
        )
        self.assertEqual(Path(installed["artifact"]), chosen / "hooks" / "saipen-guard.py")
        self.assert_standin_unchanged()


class ProfileSelectionTests(StandIn):
    def writer(self, *args):
        selector = getattr(claude_profiles, "write_directory", None)
        self.assertTrue(callable(selector), "writers need their own profile selection boundary")
        return selector(*args)

    def test_observation_keeps_the_hosts_carrier_for_an_explicit_home(self):
        for home in (None, self.operator, self.fixture):
            with self.subTest(home=home):
                self.assertEqual(claude_profiles.directory(home), self.standin)

    def test_only_the_operator_home_inherits_the_carrier_for_writes(self):
        self.assertEqual(self.writer(), self.standin)
        self.assertEqual(self.writer(self.operator), self.standin)
        self.assertEqual(self.writer(self.fixture), self.fixture / ".claude")

    def test_explicit_profiles_win_and_empty_profiles_select_the_default(self):
        chosen = self.tmp / "explicit"
        for home in (None, self.operator, self.fixture):
            with self.subTest(home=home):
                self.assertEqual(self.writer(home, chosen), chosen)
        self.assertEqual(self.writer(self.fixture, ""), self.fixture / ".claude")

    def test_an_uncomparable_home_cannot_inherit_the_carrier(self):
        with mock.patch.object(Path, "home", side_effect=RuntimeError("no home")):
            self.assertEqual(self.writer(self.fixture), self.fixture / ".claude")

    def test_repair_does_not_select_the_ambient_foreign_profile(self):
        report = {
            "ok": True, "hosts": [{
                "id": "claude", "profile": str(self.standin),
                "state": host_integration.STATE_BROKEN, "host_present": True,
                "contract": {"separated_authority": False}, "reasons": [],
                "action": "repair",
            }],
            "authority": {"running": False},
        }
        with mock.patch.object(host_integration, "doctor", return_value=report), \
                mock.patch.object(runtime_bootstrap, "canonical_source_root", return_value=ROOT), \
                mock.patch.object(runtime_bootstrap, "_invoke_installer") as invoke:
            result = host_integration.repair(home=self.fixture, only="claude")
        invoke.assert_not_called()
        self.assertEqual(result["steps"], [])
        self.assert_standin_unchanged()


    def test_repair_names_a_foreign_homes_profile_even_without_a_carrier(self):
        selected = self.fixture / ".claude"
        report = {
            "ok": True, "hosts": [{
                "id": "claude", "profile": str(selected),
                "state": host_integration.STATE_BROKEN, "host_present": True,
                "contract": {"separated_authority": False}, "reasons": [],
                "action": "repair",
            }],
            "authority": {"running": False},
        }
        completed = subprocess.CompletedProcess([], 1, stdout="fixture failure", stderr="")
        with mock.patch.dict(os.environ, {ENVIRONMENT: ""}), \
                mock.patch.object(host_integration, "doctor", return_value=report), \
                mock.patch.object(runtime_bootstrap, "canonical_source_root", return_value=ROOT), \
                mock.patch.object(runtime_bootstrap, "_invoke_installer",
                                  return_value=completed) as invoke:
            host_integration.repair(home=self.fixture, only="claude")
        invoke.assert_called_once_with(ROOT, "claude", profile=selected)
        self.assert_standin_unchanged()


NESTED = r'''
import io, json, os, sys, unittest
sys.path.insert(0, sys.argv[1])
import test_hermetic_env as hermetic
from unittest import case
from saipen_engine import host_authority_broker as broker

class Inner(unittest.TestCase):
    def test_inner(self):
        pass

def picture():
    return {"carrier": os.environ.get("CLAUDE_CONFIG_DIR"),
            "interlock": os.environ.get(hermetic.FORBID_HOST_SPAWN),
            "project_write": getattr(hermetic, "project_write_interlock", lambda: "unavailable")(),
            "authority": str(broker.runtime_root()),
            "cleanups": len(case._module_cleanups)}

hermetic.isolate_host_session()
report = {"isolated": picture()}
suite = unittest.TestSuite([Inner("test_inner")])
with io.StringIO() as sink:
    if sys.argv[2] == "helper":
        with hermetic.nested_run():
            result = unittest.TextTestRunner(stream=sink, verbosity=0).run(suite)
    else:
        result = unittest.TextTestRunner(stream=sink, verbosity=0).run(suite)
report["ran"] = result.testsRun
report["after_nested_run"] = picture()
case.doModuleCleanups()
report["after_module_end"] = picture()
print(json.dumps(report))
'''


class NestedRunTests(StandIn):
    def nested(self, form: str) -> dict:
        script = self.tmp / "nested.py"
        script.write_text(NESTED, encoding="utf-8")
        env = hermetic.hermetic_env(
            HOME=str(self.operator), USERPROFILE=str(self.operator),
            CLAUDE_CONFIG_DIR=str(self.standin), PYTHONUTF8="1",
            SAIPEN_FORBID_HOST_SPAWN=None,
        )
        result = subprocess.run(
            [sys.executable, "-B", str(script), str(TOOLS), form],
            env=env, capture_output=True, text=True, encoding="utf-8", timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        return json.loads(result.stdout.strip().splitlines()[-1])

    def test_the_bare_nested_suite_reproduces_the_cleanup_hazard(self):
        report = self.nested("bare")
        self.assertIsNone(report["isolated"]["carrier"])
        self.assertEqual(report["ran"], 1)
        self.assertEqual(report["after_nested_run"]["carrier"], str(self.standin))
        self.assertIsNone(report["after_nested_run"]["interlock"])

    def test_a_supported_nested_run_keeps_every_outer_isolation_until_module_end(self):
        report = self.nested("helper")
        self.assertEqual(report["ran"], 1)
        self.assertEqual(report["isolated"]["project_write"], str(ROOT))
        self.assertEqual(report["after_nested_run"], report["isolated"])
        self.assertEqual(report["after_module_end"]["carrier"], str(self.standin))
        self.assertIsNone(report["after_module_end"]["interlock"])
        self.assertEqual(report["after_module_end"]["cleanups"], 0)


class BorrowTests(unittest.TestCase):
    def test_nested_context_restores_cleanup_order_after_an_exception(self):
        helper = getattr(hermetic, "nested_run", None)
        self.assertTrue(callable(helper))
        cleanups = unittest_case._module_cleanups
        before = list(cleanups)
        try:
            with self.assertRaisesRegex(RuntimeError, "inner failed"), helper():
                self.assertEqual(cleanups, [])
                unittest.addModuleCleanup(lambda: None)
                inner = list(cleanups)
                with helper():
                    self.assertEqual(cleanups, [])
                self.assertEqual(cleanups, inner)
                raise RuntimeError("inner failed")
            self.assertEqual(cleanups, before + inner)
        finally:
            cleanups[:] = before

    def borrow(self, test):
        helper = getattr(hermetic, "borrow", None)
        self.assertTrue(callable(helper), "a borrowed test must not run a top-level suite")
        return helper(test)

    def test_borrow_preserves_module_cleanup_and_runs_test_fixtures(self):
        calls = []

        class Inner(unittest.TestCase):
            def setUp(self):
                calls.append("setup")
                self.addCleanup(calls.append, "cleanup")

            def runTest(self):
                calls.append("test")

            def tearDown(self):
                calls.append("teardown")

        before = list(unittest_case._module_cleanups)
        self.assertTrue(before, "outer module isolation must be registered")
        result = self.borrow(Inner())
        self.assertEqual((result.testsRun, result.failures, result.errors), (1, [], []))
        self.assertEqual(calls, ["setup", "test", "teardown", "cleanup"])
        self.assertEqual(list(unittest_case._module_cleanups), before)
        self.assertEqual(os.environ.get(hermetic.FORBID_HOST_SPAWN), "1")
        self.assertNotIn(ENVIRONMENT, os.environ)

    def test_a_borrowed_failure_is_returned_to_the_caller(self):
        class Red(unittest.TestCase):
            def runTest(self):
                self.fail("borrowed and red")

        result = self.borrow(Red())
        self.assertEqual(result.testsRun, 1)
        self.assertIn("borrowed and red", result.failures[0][1])

    def test_class_fixtures_are_refused_before_the_test_runs(self):
        helper = getattr(hermetic, "borrow", None)
        self.assertTrue(callable(helper))

        class WithClassFixture(unittest.TestCase):
            @classmethod
            def setUpClass(cls):
                raise AssertionError("must not run")

            def runTest(self):
                raise AssertionError("must not run")

        with self.assertRaises(ValueError):
            helper(WithClassFixture())


if __name__ == "__main__":
    unittest.main()
