"""Canonical verifiers are independent of the host's per-tool-call diagnostic."""

import json
import os
import sys
from unittest import mock

from saipen_engine import core_unit, verification_cache as cache
from saipen_engine.test_runner import TestFamily, _run_family, family_environment
from test_core_unit_gate import CoreUnitFixture, _run
from test_hermetic_env import isolate_host_session


def setUpModule():
    isolate_host_session()


class ToolCallIdentity(CoreUnitFixture):
    def test_diagnostic_carrier_changes_neither_environment_nor_real_child(self):
        family = TestFamily("identity", (sys.executable,), 10)
        with mock.patch.dict(os.environ, {"CODEX_TOOL_CALL_ID": "first", "PROMPT": "first>"}):
            first = family_environment(family)
        with mock.patch.dict(os.environ, {"CODEX_TOOL_CALL_ID": "second", "PROMPT": "second>"}):
            second = family_environment(family)
            self.assertEqual(sorted(key for key in set(first) | set(second)
                                    if first.get(key) != second.get(key)), [])
            code = ("import json,os; print(json.dumps("
                    "[os.environ.get('CODEX_TOOL_CALL_ID'),os.environ.get('PROMPT')]))")
            result = _run_family(self.project,
                                 TestFamily("probe", (sys.executable, "-c", code), 10))
        self.assertEqual(result["status"], "PASS", result)
        self.assertEqual(json.loads(result["stdout"]), [None, None])

    def test_new_tool_call_reuses_evidence_but_semantic_changes_invalidate_it(self):
        fingerprint = core_unit.tree_fingerprint(self.project)
        with mock.patch.dict(os.environ, {"CODEX_TOOL_CALL_ID": "first",
                                          "SAIPEN_TEST_MODE": "A"}):
            written = core_unit.write_record(self.project, _run([]), fingerprint)
        with mock.patch.dict(os.environ, {"CODEX_TOOL_CALL_ID": "second",
                                          "SAIPEN_TEST_MODE": "A"}):
            identity = written["record"]["verification_identity"]
            self.assertTrue(cache.compatible(self.project, identity))
            self.assertIsNotNone(core_unit.reusable_record(self.project, fingerprint))
        with mock.patch.dict(os.environ, {"CODEX_TOOL_CALL_ID": "second",
                                          "SAIPEN_TEST_MODE": "B"}):
            self.assertFalse(cache.compatible(self.project, identity))
            self.assertIsNone(core_unit.reusable_record(self.project, fingerprint))
