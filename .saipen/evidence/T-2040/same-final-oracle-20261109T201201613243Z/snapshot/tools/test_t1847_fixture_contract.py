"""Observe the actual nested runner/marker, independently of fixture assertions."""

from pathlib import Path
import unittest
from unittest import mock

from saipen_engine import core_unit, inflight
from saipen_engine.state import parse_state
from test_hermetic_env import borrow, isolate_host_session
import test_t1575_parallel_lane as marker_fixture
import test_t1687_identity_diagnostics as diagnostic_fixture


def setUpModule():
    isolate_host_session()


class FixtureContract(unittest.TestCase):
    def test_diagnostic_fixture_executes_its_real_single_failure(self):
        observed = []
        actual = core_unit._run_whole

        def record(*args, **kwargs):
            result = actual(*args, **kwargs)
            observed.append(result)
            return result

        case = diagnostic_fixture.IdentityDiagnostics(
            "test_the_record_retains_the_decisive_real_unittest_failure_section"
        )
        with mock.patch.object(core_unit, "_run_whole", side_effect=record):
            result = borrow(case)
        self.assertEqual(len(observed), 1)
        run = observed[0]
        self.assertEqual(run["ran"], 1, run)
        self.assertEqual(run["red"], ["test_outage.Outage.test_reason"])
        self.assertIn("T1687_SENTINEL", run["sections"]["test_outage.Outage.test_reason"])
        self.assertTrue(result.wasSuccessful(), result.failures + result.errors)

    def test_marker_fixture_reaches_and_releases_the_real_owned_gate(self):
        observed = []
        actual = inflight.begin

        def record(root, ticket, command):
            marker = actual(root, ticket, command)
            observed.append((Path(root), inflight.current(root)))
            return marker

        case = marker_fixture.RunnerWiringTests(
            "test_the_evidence_run_holds_the_marker_and_always_releases_it"
        )
        with mock.patch.object(inflight, "begin", side_effect=record):
            result = borrow(case)
        self.assertEqual(len(observed), 1)
        root, during = observed[0]
        state = parse_state((root / ".saipen/STATE.md").read_text(encoding="utf-8"))
        self.assertIsNotNone(during)
        self.assertEqual(during["ticket"], state["task"])
        self.assertIsNone(inflight.current(root))
        self.assertTrue(result.wasSuccessful(), result.failures + result.errors)


if __name__ == "__main__":
    unittest.main()
