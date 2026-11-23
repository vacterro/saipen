"""T-1687: unavailable identity is a named refusal and red records keep its reason."""
from __future__ import annotations

import json
import shutil
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import test_hermetic_env as hermetic  # noqa: E402
import test_host_authority_broker as fixtures  # noqa: E402
from saipen_engine import core_unit  # noqa: E402
from saipen_engine import host_authority_identity as identity  # noqa: E402
from saipen_engine.test_runner import TestFamily  # noqa: E402


def setUpModule():
    hermetic.isolate_host_session()


METHODS = (
    "test_an_arbitrary_same_user_python_client_is_refused",
    "test_an_ordinary_process_is_not_a_hook_invocation_and_starts_nothing",
)


class IdentityDiagnostics(unittest.TestCase):
    def test_a_real_probe_outage_is_a_named_refusal_in_both_borrowed_cases(self):
        # The actual pure proof consumes an empty OS observation. Keep the
        # real broker, client, transport and refusal bookkeeping in service.
        with mock.patch.object(fixtures.HB.proc, "ancestry", return_value=[]):
            for method in METHODS:
                with self.subTest(method=method):
                    result = hermetic.borrow(fixtures.IdentityTests(method))
                    self.assertEqual(result.testsRun, 1)
                    self.assertTrue(result.wasSuccessful(), result.failures + result.errors)

    def test_an_unnamed_refusal_still_fails_both_borrowed_checks(self):
        failed = identity.Proof(False, reason="T1687_UNKNOWN_REFUSAL", detail="red control")
        with mock.patch.object(identity, "prove_hook_invocation", return_value=failed):
            for method in METHODS:
                with self.subTest(method=method):
                    result = hermetic.borrow(fixtures.IdentityTests(method))
                    self.assertEqual(result.testsRun, 1)
                    self.assertFalse(result.wasSuccessful())
                    errors = "\n".join(message for _, message in result.failures + result.errors)
                    self.assertIn("T1687_UNKNOWN_REFUSAL", errors)

    def test_the_record_retains_the_decisive_real_unittest_failure_section(self):
        sandbox = core_unit.new_sandbox_root(ROOT)
        self.addCleanup(core_unit.reclaim, sandbox)
        root = sandbox / "project"
        tools = root / "tools"
        tools.mkdir(parents=True)
        shutil.copyfile(ROOT / "tools" / "core_unit_baseline.json",
                        tools / "core_unit_baseline.json")
        (tools / "test_outage.py").write_text(
            "import unittest\n"
            "class Outage(unittest.TestCase):\n"
            "    def test_reason(self):\n"
            "        self.fail('identity probe: IDENTITY_UNAVAILABLE; T1687_SENTINEL')\n",
            encoding="utf-8",
        )
        spool = root / "spool"
        spool.mkdir()
        family = TestFamily(
            "unit", (sys.executable, "-B", "-m", "unittest", "discover", "-s",
                     "tools", "-p", "test_*.py", "-v"), 60,
        )
        started = time.monotonic()
        run = core_unit._run_whole(root, family, spool)
        self.assertEqual(run["ran"], 1)
        self.assertEqual(run["status"], "FAIL")
        self.assertEqual(run["red"], ["test_outage.Outage.test_reason"])
        run.update(command=list(family.command), duration_s=time.monotonic() - started,
                   timeout_s=60)
        written = core_unit.write_record(root, run, core_unit.tree_fingerprint(root))
        persisted = json.loads((root / written["path"]).read_text(encoding="utf-8"))
        self.assertEqual(persisted["verdict"], "FAIL")
        sections = persisted.get("red_sections", {})
        self.assertIn("test_outage.Outage.test_reason", sections)
        self.assertIn("IDENTITY_UNAVAILABLE; T1687_SENTINEL",
                      sections["test_outage.Outage.test_reason"])
        self.assertIn("AssertionError", sections["test_outage.Outage.test_reason"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
