"""T-1527: Attempt evidence binds the SAIPEN seat to host runtime metadata."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.attempt import build_attempts  # noqa: E402
from saipen_engine.context import brief_projection  # noqa: E402
from saipen_engine.log import read_history_events  # noqa: E402
from saipen_engine.operations import attempt_lifecycle, checkpoint  # noqa: E402
from test_control_primitives import ControlFixture  # noqa: E402


class RuntimeProvenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = ControlFixture.make_project(self, active=True)
        self.tmp = tempfile.TemporaryDirectory(prefix="t1527-runtime-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def _host_info(self, **values: str) -> Path:
        path = self.base / "host-runtime.json"
        path.write_text(json.dumps(values), encoding="utf-8")
        return path

    def _attempts(self) -> dict:
        records, errors = build_attempts(read_history_events(self.project))
        self.assertEqual([], errors)
        return records

    def test_host_values_bind_separately_and_survive_checkpoint_and_restart(self):
        host_info = self._host_info(
            schema_version=1,
            provider="codex",
            model="gpt-6-luna",
            effort="xhigh",
        )
        with mock.patch.dict(os.environ, {"SAIPEN_RUNTIME_INFO": str(host_info)}):
            opened = attempt_lifecycle(self.project, "tester", "open")
        self.assertTrue(opened.ok, opened.to_dict())
        evidence = opened.data["runtime_provenance"]
        self.assertEqual("tester", evidence["executor_identity"])
        self.assertEqual("codex", evidence["runtime_provider"])
        self.assertEqual("gpt-6-luna", evidence["runtime_model"])
        self.assertEqual("xhigh", evidence["runtime_effort"])
        self.assertEqual("complete", evidence["provenance_status"])
        self.assertEqual("available", evidence["benchmark_evidence"])
        self.assertRegex(evidence["integrity_digest"], r"^[0-9a-f]{64}$")

        record = self._attempts()[opened.data["attempt"]]
        self.assertEqual("tester", record["agent"])
        self.assertEqual(evidence, record["runtime_provenance"])

        cold = brief_projection(self.project)
        self.assertTrue(cold.ok, cold.to_dict())
        self.assertEqual(
            evidence,
            cold.data["json"]["attempt"]["runtime_provenance"],
        )

        checkpointed = checkpoint(self.project, "tester", "RUN", "T-7", "later checkpoint")
        self.assertTrue(checkpointed.ok, checkpointed.to_dict())
        records_after_checkpoint = self._attempts()
        self.assertEqual(
            evidence, records_after_checkpoint[opened.data["attempt"]]["runtime_provenance"]
        )

        env = dict(os.environ)
        for key in (
            "SAIPEN_PROJECT_ROOT",
            "SAIPEN_PROJECT_LINEAGE",
            "SAIPEN_AGENT",
            "SAIPEN_RUNTIME_INFO",
        ):
            env.pop(key, None)
        closed = subprocess.run(
            [
                sys.executable,
                str(TOOLS / "saipen.py"),
                "--project-root",
                str(self.project),
                "--agent",
                "tester",
                "attempt",
                "close",
                "candidate",
                "completed_execution",
                "--json",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            timeout=30,
        )
        self.assertEqual(0, closed.returncode, closed.stderr + closed.stdout)
        records_after_restart = self._attempts()
        self.assertEqual(
            evidence, records_after_restart[opened.data["attempt"]]["runtime_provenance"]
        )

    def test_absent_or_invalid_host_context_is_explicitly_incomplete(self):
        spoofed_cli_info = self._host_info(
            provider="forged-provider",
            model="forged-model",
            effort="forged-effort",
        )
        before_log = (self.project / ".saipen" / "LOG.md").read_bytes()
        rejected = subprocess.run(
            [
                sys.executable,
                str(TOOLS / "saipen.py"),
                "--project-root",
                str(self.project),
                "--agent",
                "tester",
                "--runtime-info",
                str(spoofed_cli_info),
                "attempt",
                "open",
                "--json",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
        self.assertEqual(2, rejected.returncode, rejected.stderr + rejected.stdout)
        self.assertIn("VALIDATION_FAILED", rejected.stdout)
        self.assertEqual(before_log, (self.project / ".saipen" / "LOG.md").read_bytes())

        invalid_host_info = self._host_info(
            provider="forged-provider",
            model="forged-model",
            effort="forged-effort",
            executor_identity="forged-seat",
        )
        with mock.patch.dict(os.environ, {"SAIPEN_RUNTIME_INFO": str(invalid_host_info)}):
            opened = attempt_lifecycle(self.project, "tester", "open")
        self.assertTrue(opened.ok, opened.to_dict())
        evidence = opened.data["runtime_provenance"]
        self.assertEqual("tester", evidence["executor_identity"])
        self.assertIsNone(evidence["runtime_provider"])
        self.assertIsNone(evidence["runtime_model"])
        self.assertIsNone(evidence["runtime_effort"])
        self.assertEqual("unavailable", evidence["provenance_status"])
        self.assertEqual("incomplete", evidence["benchmark_evidence"])
        self.assertEqual("host_context_invalid", evidence["reason_code"])

    def test_missing_host_context_is_explicitly_unavailable(self):
        with mock.patch.dict(os.environ, {"SAIPEN_RUNTIME_INFO": ""}):
            opened = attempt_lifecycle(self.project, "tester", "open")
        self.assertTrue(opened.ok, opened.to_dict())
        evidence = opened.data["runtime_provenance"]
        self.assertEqual("tester", evidence["executor_identity"])
        self.assertIsNone(evidence["runtime_provider"])
        self.assertIsNone(evidence["runtime_model"])
        self.assertIsNone(evidence["runtime_effort"])
        self.assertEqual("unavailable", evidence["provenance_status"])
        self.assertEqual("incomplete", evidence["benchmark_evidence"])
        self.assertEqual("host_context_missing", evidence["reason_code"])

    def test_partial_host_metadata_is_not_benchmark_complete(self):
        host_info = self._host_info(provider="codex", model="gpt-6-luna")
        with mock.patch.dict(os.environ, {"SAIPEN_RUNTIME_INFO": str(host_info)}):
            opened = attempt_lifecycle(self.project, "tester", "open")
        self.assertTrue(opened.ok, opened.to_dict())
        evidence = opened.data["runtime_provenance"]
        self.assertEqual("codex", evidence["runtime_provider"])
        self.assertEqual("gpt-6-luna", evidence["runtime_model"])
        self.assertIsNone(evidence["runtime_effort"])
        self.assertEqual("incomplete", evidence["provenance_status"])
        self.assertEqual("incomplete", evidence["benchmark_evidence"])
        self.assertEqual(["runtime_effort"], evidence["missing_fields"])

    def test_provenance_digest_rejects_tampered_attempt_history(self):
        host_info = self._host_info(provider="codex", model="model-a", effort="high")
        with mock.patch.dict(os.environ, {"SAIPEN_RUNTIME_INFO": str(host_info)}):
            opened = attempt_lifecycle(self.project, "tester", "open")
        self.assertTrue(opened.ok, opened.to_dict())
        log_path = self.project / ".saipen" / "LOG.md"
        original = log_path.read_text(encoding="utf-8")
        match = re.search(r"; provenance ([A-Za-z0-9_-]+\.[0-9a-f]{64})", original)
        self.assertIsNotNone(match)
        tampered = original.replace(
            match.group(1), match.group(1).rsplit(".", 1)[0] + "." + "0" * 64
        )
        self.assertNotEqual(original, tampered)
        attempt_line = next(line for line in tampered.splitlines() if "attempt A-" in line)
        tampered_event = next(
            event for event in read_history_events(self.project) if "attempt A-" in event["text"]
        )
        tampered_event["text"] = attempt_line.split(" DEC: ", 1)[-1]
        _records, errors = build_attempts([tampered_event])
        self.assertEqual(1, len(errors))
        self.assertIn("integrity digest mismatch", errors[0])


if __name__ == "__main__":
    unittest.main()
