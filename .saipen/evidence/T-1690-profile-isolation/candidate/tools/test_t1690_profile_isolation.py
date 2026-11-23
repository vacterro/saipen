"""A fixture's home is never redirected into the operator's Claude profile (T-1690).

Measured 2026-10-08 21:08:26Z. A draft test, run from a disposable copy of the
tree inside a live Claude Code session, ran one borrowed test through
`unittest.TestSuite.run`. Two holes lined up:

* unittest keeps ONE process-wide list of module cleanups and drains all of it
  when ANY top-level suite run ends -- a run started inside a test included.
  `isolate_host_session` restores through that list, so the nested run handed
  CLAUDE_CONFIG_DIR and the interlocks back while the module was still running;
* `claude_profiles.directory` let that ambient carrier outrank an explicitly
  named home, so the next installer fixture wrote the hook and five
  settings.json entries of the operator's live profile, naming the disposable
  copy as the runtime. The operator's next prompt ran degraded.

T-1685 had closed the second hole in the harness only (strip the carrier), so
anything that dropped the harness reopened it. Here the product rule itself is
pinned -- an ambient carrier belongs to the home it was set for and to no other
-- and the nested run gets a supported form that leaves the isolation alone.

Every case names a disposable stand-in profile and a disposable operator home.
No real profile is read or written, with or without the repair.
"""

from __future__ import annotations

import json
import os
import re
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
from saipen_engine import claude_profiles  # noqa: E402
from saipen_engine.claude_profiles import ENVIRONMENT  # noqa: E402
from test_hermetic_env import HOST_SESSION_VARIABLES, isolate_host_session  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


def contents(directory: Path) -> list[str]:
    return sorted(path.relative_to(directory).as_posix() for path in directory.rglob("*"))


class StandIn(unittest.TestCase):
    """An operator home, a carrier set for it, and a fixture home beside both."""

    def setUp(self) -> None:
        scratch = tempfile.TemporaryDirectory(prefix="saipen-t1690-")
        self.addCleanup(scratch.cleanup)
        self.tmp = Path(scratch.name)
        self.operator = self.tmp / "operator"
        self.fixture = self.tmp / "fixture-home"
        self.standin = self.tmp / "standin" / ".claude"
        for directory in (self.operator, self.fixture, self.standin):
            directory.mkdir(parents=True)
        environment = mock.patch.dict(os.environ, {
            "HOME": str(self.operator), "USERPROFILE": str(self.operator),
            "HOMEDRIVE": "", "HOMEPATH": "", ENVIRONMENT: str(self.standin),
        })
        environment.start()
        self.addCleanup(environment.stop)


class AmbientCarrierTests(StandIn):
    def test_the_carrier_selects_the_profile_of_the_home_it_was_set_for(self):
        # Production is unchanged: a hook running under a second profile names
        # no home, or its own, and must serve that profile.
        self.assertEqual(claude_profiles.directory(), self.standin)
        self.assertEqual(claude_profiles.directory(self.operator), self.standin)

    def test_the_carrier_never_redirects_another_home(self):
        self.assertEqual(claude_profiles.directory(self.fixture), self.fixture / ".claude")

    def test_an_explicit_profile_wins_for_every_home(self):
        chosen = self.tmp / "chosen"
        for home in (None, self.operator, self.fixture):
            with self.subTest(home=home):
                self.assertEqual(claude_profiles.directory(home, chosen), chosen)

    def test_without_a_carrier_each_home_has_its_default(self):
        with mock.patch.dict(os.environ, {ENVIRONMENT: ""}):
            self.assertEqual(claude_profiles.directory(), self.operator / ".claude")
            self.assertEqual(claude_profiles.directory(self.fixture), self.fixture / ".claude")

    def test_a_home_that_cannot_be_compared_is_not_the_operators(self):
        # No answer about the operator's home is not permission to follow it.
        with mock.patch.object(Path, "home", side_effect=RuntimeError("no home")):
            self.assertEqual(
                claude_profiles.directory(self.fixture), self.fixture / ".claude"
            )


class InstallerFixtureTests(StandIn):
    def test_install_uninstall_and_rollback_stay_in_the_named_home(self):
        installed = install_host_guard.install("claude", self.fixture, ROOT, verify=False)
        own = self.fixture / ".claude"
        self.assertEqual(Path(installed["artifact"]), own / "hooks" / "saipen-guard.py")
        self.assertEqual(Path(installed["config"]), own / "settings.json")
        self.assertEqual(contents(self.standin), [])
        install_host_guard.rollback("claude", self.fixture, ROOT)
        self.assertEqual(contents(self.standin), [])
        removed = install_host_guard.uninstall("claude", self.fixture, ROOT, live_host=False)
        self.assertTrue(removed["artifact_removed"])
        self.assertEqual(contents(self.standin), [])

    def test_the_world_fixture_never_follows_the_carrier(self):
        from test_protocol_admission import World

        world = World(self.tmp / "world")
        self.assertTrue((world.home / ".claude" / "hooks" / "saipen-guard.py").is_file())
        self.assertTrue((world.home / ".claude" / "settings.json").is_file())
        self.assertEqual(contents(self.standin), [])

    def test_a_named_profile_is_still_where_the_install_goes(self):
        # The supported way to install into a second profile of another home.
        second = self.fixture / ".claude-account2"
        second.mkdir()
        installed = install_host_guard.install(
            "claude", self.fixture, ROOT, verify=False, profile=second
        )
        self.assertEqual(Path(installed["artifact"]), second / "hooks" / "saipen-guard.py")
        self.assertEqual(contents(self.standin), [])
        self.assertFalse((self.fixture / ".claude").exists())


def borrowed_cases() -> tuple[type, type]:
    """Stand-ins for a test of another module, built where discovery cannot see them."""

    class Green(unittest.TestCase):
        def runTest(self) -> None:
            self.assertTrue(True)

    class NeedsClassFixture(Green):
        @classmethod
        def setUpClass(cls) -> None:
            cls.ready = True

    return Green, NeedsClassFixture


#: One interpreter, isolated, running a suite from inside its own "module".
NESTED = r'''
import io, json, os, sys, unittest
sys.path.insert(0, sys.argv[1])
import test_hermetic_env as hermetic
from unittest import case

class Inner(unittest.TestCase):
    def test_inner(self):
        pass

def picture():
    return {"carrier": os.environ.get("CLAUDE_CONFIG_DIR"),
            "interlock": os.environ.get(hermetic.FORBID_HOST_SPAWN),
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
case.doModuleCleanups()   # what unittest does when the outer module really ends
report["after_module_end"] = picture()
print(json.dumps(report))
'''


class NestedRunTests(StandIn):
    def nested(self, form: str) -> dict:
        script = self.tmp / "nested.py"
        script.write_text(NESTED, encoding="utf-8")
        env = {
            key: value for key, value in os.environ.items()
            if key not in HOST_SESSION_VARIABLES and not key.startswith("SAIPEN_")
        }
        env.update({
            "HOME": str(self.operator), "USERPROFILE": str(self.operator),
            "HOMEDRIVE": "", "HOMEPATH": "", ENVIRONMENT: str(self.standin),
            "PYTHONUTF8": "1",
        })
        result = subprocess.run(
            [sys.executable, "-B", str(script), str(TOOLS), form],
            env=env, capture_output=True, text=True, encoding="utf-8", timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        return json.loads(result.stdout.strip().splitlines()[-1])

    def test_a_bare_suite_run_inside_a_test_ends_the_isolation(self):
        # Instrument control: the hazard is real on this interpreter. If
        # unittest stops draining module cleanups at the end of a nested run,
        # this goes red and says the helper below has nothing left to defend.
        report = self.nested("bare")
        self.assertEqual(report["isolated"]["carrier"], None)
        self.assertEqual(report["isolated"]["interlock"], "1")
        self.assertEqual(report["ran"], 1)
        self.assertEqual(report["after_nested_run"]["carrier"], str(self.standin))
        self.assertIsNone(report["after_nested_run"]["interlock"])

    def test_nested_run_keeps_the_isolation_and_the_module_end_still_restores(self):
        report = self.nested("helper")
        self.assertEqual(report["ran"], 1)
        self.assertEqual(report["after_nested_run"], report["isolated"])
        self.assertEqual(report["after_module_end"]["carrier"], str(self.standin))
        self.assertIsNone(report["after_module_end"]["interlock"])
        self.assertEqual(report["after_module_end"]["cleanups"], 0)


class BorrowTests(unittest.TestCase):
    def test_borrowing_one_test_leaves_every_module_cleanup_in_place(self):
        before = list(unittest_case._module_cleanups)
        self.assertTrue(before, "this module's own isolation must be registered")
        result = hermetic.borrow(borrowed_cases()[0]())
        self.assertEqual((result.testsRun, result.failures, result.errors), (1, [], []))
        self.assertEqual(list(unittest_case._module_cleanups), before)
        self.assertEqual(os.environ.get(hermetic.FORBID_HOST_SPAWN), "1")
        self.assertNotIn(ENVIRONMENT, os.environ)

    def test_a_borrowed_failure_is_reported_not_raised(self):
        class Red(unittest.TestCase):
            def runTest(self) -> None:
                self.fail("borrowed and red")

        result = hermetic.borrow(Red())
        self.assertEqual(result.testsRun, 1)
        self.assertIn("borrowed and red", result.failures[0][1])

    def test_a_test_that_needs_a_class_fixture_is_refused(self):
        # `borrow` runs no class and no module fixture; saying so beats a
        # borrowed test that silently ran without the setup it depends on.
        with self.assertRaises(ValueError):
            hermetic.borrow(borrowed_cases()[1]())


class SuiteRunSitesTests(unittest.TestCase):
    #: A suite run from inside a test module, in either spelling.
    SUITE_RUN = re.compile(r"\b(?:TestSuite|TextTestRunner)\(")

    def test_every_suite_run_inside_a_test_module_goes_through_nested_run(self):
        # The helper is advisory until something refuses its absence.
        bare = []
        for path in sorted(TOOLS.glob("test_*.py")):
            source = path.read_text(encoding="utf-8")
            if path.name == "test_hermetic_env.py" or not self.SUITE_RUN.search(source):
                continue
            if "nested_run(" not in source and "hermetic.borrow(" not in source:
                bare.append(path.name)
        self.assertEqual(bare, [])


if __name__ == "__main__":
    unittest.main()
