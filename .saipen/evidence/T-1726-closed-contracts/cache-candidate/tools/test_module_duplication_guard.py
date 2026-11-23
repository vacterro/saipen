"""T-1348: direct tools modules share identity across import spellings.

The declared discovery and the mixed package/flat form must both load one
live object per file. CLI mutable state and test-harness state then have one
owner. A deliberate second execution through an explicit file-location spec
bypasses ordinary import routing and supplies the detector's known-bad
control; fixing ordinary imports must never make the detector blind.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import test_hermetic_env as harness  # noqa: E402
from test_hermetic_env import hermetic_env, isolate_host_session  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


def retained_fixtures() -> list:
    """Resolved at call time so this oracle stays IMPORTABLE against a subject
    that has no shared keeper yet; otherwise the whole file collapses into one
    import error and says nothing about the behaviour it measures."""
    keeper = getattr(harness, "retained_fixtures", None)
    if keeper is None:
        raise AssertionError(
            "test_hermetic_env has no retained_fixtures: the disposable-fixture "
            "keeper is module-global, so a second copy of the file keeps a "
            "second list"
        )
    return keeper()


#: Imports the modules and reports duplicates; it never RUNS a test, so the
#: probe costs an import sweep rather than a suite.
_PROBE = """
import json, os, sys, unittest

TOOLS = os.path.join(os.getcwd(), "tools")
loader = unittest.TestLoader()
MODE = sys.argv[1]
if MODE == "discover":
    loader.discover("tools", pattern="test_*.py")
else:
    loader.loadTestsFromNames(sys.argv[2:])

assert not loader.errors, loader.errors

if MODE == "forced-duplicate":
    import importlib.util
    original = sys.modules["test_hermetic_env"]
    spec = importlib.util.spec_from_file_location("t1348_forced_duplicate", original.__file__)
    duplicate = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = duplicate
    spec.loader.exec_module(duplicate)

by_file = {}
for name, module in list(sys.modules.items()):
    path = getattr(module, "__file__", None)
    if not path:
        continue
    real = os.path.normcase(os.path.abspath(path))
    if not real.startswith(os.path.normcase(TOOLS) + os.sep):
        continue
    by_file.setdefault(real, set()).add(id(module))

duplicated = sorted(
    os.path.relpath(path, os.getcwd()).replace(chr(92), "/")
    for path, ids in by_file.items()
    if len(ids) > 1
)
print("<<<DUP>>>" + json.dumps({"loaded": len(by_file), "duplicated": duplicated}))
"""


def _probe(mode: str, *names: str) -> dict:
    completed = subprocess.run(
        [sys.executable, "-c", _PROBE, mode, *names],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=hermetic_env(),
        timeout=900,
    )
    if completed.returncode or "<<<DUP>>>" not in completed.stdout:
        raise AssertionError(
            f"probe exited {completed.returncode}\n{completed.stdout[-1500:]}\n"
            f"{completed.stderr[-1500:]}"
        )
    return json.loads(completed.stdout.split("<<<DUP>>>", 1)[1].splitlines()[0])


class DeclaredHarnessTests(unittest.TestCase):
    def test_the_declared_harness_loads_one_object_per_file(self) -> None:
        """`discover -s tools` is the family saipen_engine/test_runner declares."""
        report = _probe("discover")
        self.assertGreater(report["loaded"], 100, report)
        self.assertEqual(report["duplicated"], [], report)

    def test_the_mixed_form_shares_every_loaded_file(self) -> None:
        report = _probe(
            "names", "tools.test_guard_hostile_matrix",
            "tools.test_t1327_zero_manual_recovery", "tools.test_hermetic_env",
        )
        self.assertGreater(report["loaded"], 20, report)
        self.assertEqual(report["duplicated"], [], report)

    def test_the_detector_fires_on_a_forced_second_copy(self) -> None:
        report = _probe(
            "forced-duplicate", "tools.test_guard_hostile_matrix",
            "tools.test_t1327_zero_manual_recovery", "tools.test_hermetic_env",
        )
        self.assertIn("tools/test_hermetic_env.py", report["duplicated"], report)


class CooperatingHarnessStateTests(unittest.TestCase):
    """The state that gets hurt cooperates instead of duplicating."""

    def test_isolation_is_reference_counted_and_restores_once(self) -> None:
        """Two copies isolating must strip once and restore once.

        Before T-1353 each copy kept its own snapshot, so the second restore
        put back a picture taken AFTER the first had already stripped -- the
        outer session's value came back as absent.

        Measured in a fresh interpreter on purpose: this module's own
        `setUpModule` has already isolated, so the registry here is mid-flight
        and a full restore cannot be observed without undoing the isolation
        every other case in this file depends on.
        """
        probe = """
import json, os, sys
sys.path.insert(0, os.path.join(os.getcwd(), "tools"))
os.environ["SAIPEN_AGENT"] = "outer-session-value"

import test_hermetic_env as harness

restores = []


class Collector:
    @staticmethod
    def addModuleCleanup(fn, *a, **k):
        restores.append(fn)


harness.unittest = Collector
harness.isolate_host_session()
harness.isolate_host_session()
stripped = os.environ.get("SAIPEN_AGENT")
restores[0]()
after_first = os.environ.get("SAIPEN_AGENT")
restores[1]()
after_last = os.environ.get("SAIPEN_AGENT")
print("<<<REF>>>" + json.dumps(
    {"stripped": stripped, "after_first": after_first, "after_last": after_last}
))
"""
        completed = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=hermetic_env(),
            timeout=300,
        )
        self.assertIn("<<<REF>>>", completed.stdout, completed.stdout + completed.stderr)
        seen = json.loads(completed.stdout.split("<<<REF>>>", 1)[1].splitlines()[0])
        self.assertIsNone(seen["stripped"], "the carrier survived isolation")
        self.assertIsNone(
            seen["after_first"],
            "the first of two cleanups restored; the environment is repaired "
            "once, by the last",
        )
        self.assertEqual(
            seen["after_last"],
            "outer-session-value",
            "the last cleanup must put the original value back",
        )

    def test_an_intermediate_cleanup_still_strips_what_its_module_set(self) -> None:
        """Reference counting must not turn into carrier leakage.

        Modules that test binding inheritance SET a carrier on purpose. Before
        reference counting, every module cleanup stripped all carriers and then
        restored the snapshot. If an intermediate cleanup returned early
        without stripping, a carrier set by one module would survive into the
        next -- trading a duplicate-snapshot bug for a worse isolation bug.
        """
        probe = """
import json, os, sys
sys.path.insert(0, os.path.join(os.getcwd(), "tools"))
os.environ["SAIPEN_AGENT"] = "outer-session-value"

import test_hermetic_env as harness

restores = []


class Collector:
    @staticmethod
    def addModuleCleanup(fn, *a, **k):
        restores.append(fn)


harness.unittest = Collector
harness.isolate_host_session()          # outer module, still open
harness.isolate_host_session()          # inner module
os.environ["SAIPEN_AGENT"] = "set-by-the-inner-module"
restores[1]()                           # inner module ends
leaked = os.environ.get("SAIPEN_AGENT")
restores[0]()
print("<<<LEAK>>>" + json.dumps(
    {"leaked": leaked, "final": os.environ.get("SAIPEN_AGENT")}
))
"""
        completed = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=hermetic_env(),
            timeout=300,
        )
        self.assertIn("<<<LEAK>>>", completed.stdout, completed.stdout + completed.stderr)
        seen = json.loads(completed.stdout.split("<<<LEAK>>>", 1)[1].splitlines()[0])
        self.assertIsNone(
            seen["leaked"],
            "a carrier set by one module survived its own cleanup into the next",
        )
        self.assertEqual(seen["final"], "outer-session-value")

    def test_the_retained_fixture_list_is_one_list(self) -> None:
        from test_guard_hostile_matrix import _TEMP

        self.assertIs(_TEMP, retained_fixtures(), "the fixture keeper forked")


if __name__ == "__main__":
    unittest.main(verbosity=2)
