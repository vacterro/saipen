"""SAIPAL boundaries: real local CLI probes, no external forensic effects."""

from __future__ import annotations

import base64
import concurrent.futures
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from saipen_engine import saipal_adapter as adapter_module


class SaipalBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-saipal-boundary-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / "backend"
        (self.home / "tools").mkdir(parents=True)
        (self.home / ".saipal").mkdir()
        self.cli = self.home / "tools/saipal.py"
        self.cli.write_text(
            "import base64,json,pathlib,sys,time\n"
            "d=json.loads(pathlib.Path(__file__).with_suffix('.response.json')"
            ".read_text(encoding='utf-8'))\n"
            "sys.stdout.buffer.write(base64.b64decode(d['stdout'])); sys.stdout.flush()\n"
            "sys.stderr.buffer.write(base64.b64decode(d['stderr'])); sys.stderr.flush()\n"
            "time.sleep(d.get('delay',0))\n"
            "sys.exit(d['returncode'])\n",
            encoding="utf-8",
        )
        self.adapter = adapter_module.SaipalAdapter(self.home)
        self.project = self.root / "project"
        self.log_dir = self.project / ".saipen/campaign"
        self.log_dir.mkdir(parents=True)

    def response(self, payload, *, raw=False, returncode=0, stderr=b"", delay=0):
        body = payload if raw else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        config = {
            "stdout": base64.b64encode(body).decode(),
            "stderr": base64.b64encode(stderr).decode(),
            "returncode": returncode,
            "delay": delay,
        }
        self.cli.with_suffix(".response.json").write_text(json.dumps(config), encoding="utf-8")

    def report(self, **changes):
        return {"ok": True, "command": "report", "findings": [], "counts": {}, **changes}

    def status(self, **changes):
        return {"ok": True, "command": "status", "phase": "IDLE", "queue": {}, **changes}

    def history(self, name):
        result = (
            self.adapter.get_dispositions(self.project)
            if name == "dispositions.jsonl"
            else self.adapter.collect_publication_receipts(self.project)
        )
        # Normalize only the old success API, to measure semantic baseline defects.
        if isinstance(result, list):
            return {"ok": True, "status": "LOG_VALID", "records": result}
        return result

    def test_backend_operation_refusals_remain_failures(self):
        for code in ("ANALYSIS_BLOCKED", "AUTHORITY_REQUIRED", "SOURCE_NOT_ENROLLED", "REFUSED"):
            for ok in (False, True):
                with self.subTest(code=code, ok=ok):
                    self.response(
                        self.report(ok=ok, status=code, error="original evidence missing")
                    )
                    result = self.adapter._run_cmd("report")
                    self.assertFalse(result["ok"])
                    self.assertEqual(result["status"], code)
                    self.assertEqual(result["transport_status"], "EXITED")
                    self.assertEqual(result["operation_status"], "FAILED")
                    self.assertIn("original evidence", result["error"])

    def test_invalid_common_fields_are_protocol_errors(self):
        for value in (
            [],
            None,
            True,
            7,
            "result",
            {},
            {"ok": "true"},
            {"ok": 1},
            self.report(status=[]),
            self.report(code={}),
            self.report(ok=False, schema_version=99),
            self.report(ok=False, command="status", status="ANALYSIS_BLOCKED"),
        ):
            with self.subTest(value=value):
                self.response(value)
                result = self.adapter._run_cmd("report")
                self.assertFalse(result["ok"], result)
                self.assertEqual(result["status"], "BACKEND_PROTOCOL_ERROR")
                self.assertEqual(result["protocol_status"], "INVALID")

    def test_command_specific_shapes_are_validated(self):
        cases = [
            ("report", x)
            for x in (
                {"ok": True, "command": "report"},
                self.report(findings={}),
                self.report(findings=["forged"]),
                self.report(counts=[]),
                self.report(command="status"),
                self.report(schema_version=99),
            )
        ] + [
            ("status", x)
            for x in (
                self.status(queue=[]),
                self.status(phase=7),
                self.status(queue={"hot": -1}),
                self.status(queue={"hot": True}),
            )
        ]
        for command, value in cases:
            with self.subTest(value=value):
                self.response(value)
                self.assertEqual(self.adapter._run_cmd(command)["status"], "BACKEND_PROTOCOL_ERROR")

    def test_valid_report_preserves_utf8_under_narrow_locale(self):
        text = "\u00f5\u0448\u4e00"
        self.response(
            self.report(findings=[{"finding_id": "PAL-1", "state": "DRAFT", "note": text}])
        )
        with mock.patch.dict(os.environ, {"PYTHONIOENCODING": "cp1251", "PYTHONUTF8": "0"}):
            result = self.adapter._run_cmd("report")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["data"]["findings"][0]["note"], text)
        self.assertEqual(result["protocol_status"], "VALID")

    def test_transport_failure_remains_distinct(self):
        self.response(b"not JSON", raw=True, returncode=7, stderr=b"provider unavailable")
        result = self.adapter._run_cmd("report")
        self.assertFalse(result["ok"])
        self.assertEqual(result["returncode"], 7)
        self.assertEqual(result["transport_status"], "FAILED")
        self.assertIn("provider unavailable", result["error"])

    def test_invalid_json_encoding_constants_and_duplicate_fields_are_typed(self):
        for raw in (b"{", b"\xff", b'{"ok":NaN}', b'{"ok":false,"ok":true}', b"[" * 2000):
            with self.subTest(raw=raw[:30]):
                self.response(raw, raw=True)
                result = self.adapter._run_cmd("report")
                self.assertFalse(result["ok"])
                self.assertEqual(result["status"], "BACKEND_PROTOCOL_ERROR")

    def test_failed_collection_is_not_an_empty_list(self):
        self.response({"ok": False, "status": "ANALYSIS_BLOCKED", "error": "evidence missing"})
        result = self.adapter.collect_findings()
        self.assertIsInstance(result, dict)
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "ANALYSIS_BLOCKED")

    def test_discovery_does_not_swallow_status_or_analysis_failures(self):
        failure = {"ok": False, "status": "ANALYSIS_BLOCKED", "error": "blocked"}
        for outcomes in ([failure], [{"ok": True, "data": self.status(queue={"hot": 1})}, failure]):
            with self.subTest(outcomes=outcomes), mock.patch.object(
                self.adapter,
                "probe",
                return_value={"ok": True},
            ), mock.patch.object(self.adapter, "_run_cmd", side_effect=outcomes) as backend:
                result = self.adapter.discover(self.project)
                self.assertFalse(result["ok"])
                self.assertEqual(result["status"], "ANALYSIS_BLOCKED")
                self.assertEqual(backend.call_count, len(outcomes))

    def test_valid_empty_discovery_report_is_no_new_evidence(self):
        # AUT-005: discovery reads through the bounded incremental transport,
        # not `_run_cmd("report")`, so the control drives the report spool the
        # production path actually consumes instead of a materialising seam
        # discovery no longer calls.
        self.response(self.report())
        with mock.patch.object(
            self.adapter, "probe", return_value={"ok": True, "data": {"queue": {}}}
        ):
            result = self.adapter.discover(self.project)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["status"], adapter_module.NO_NEW_EVIDENCE)

    def test_large_stdout_and_stderr_are_resource_errors(self):
        # PERF-004 gives `report` a larger declared spool ceiling than a generic
        # response, so the oversized-output control patches that ceiling rather
        # than the generic one; the typed refusal is what stays invariant.
        with mock.patch.object(
            adapter_module, "MAX_BACKEND_STDOUT_BYTES", 32768, create=True
        ), mock.patch.object(
            adapter_module, "REPORT_SPOOL_LIMIT_BYTES", 32768, create=True
        ), mock.patch.object(
            adapter_module,
            "MAX_BACKEND_STDERR_BYTES",
            4096,
            create=True,
        ):
            for payload, stderr in (
                (self.report(padding="x" * 65536), b""),
                (self.report(), b"e" * 8192),
            ):
                with self.subTest(stderr=bool(stderr)):
                    self.response(payload, stderr=stderr)
                    result = self.adapter._run_cmd("report")
                    self.assertFalse(result["ok"])
                    self.assertEqual(result["status"], "BACKEND_RESOURCE_LIMIT")
                    self.assertNotIn("data", result)

    def test_deadline_preserves_uncertain_outcome(self):
        self.response(self.report(), delay=2)
        with mock.patch.object(adapter_module, "BACKEND_TIMEOUT_SECONDS", 0.15, create=True):
            result = self.adapter._run_cmd("report")
        self.assertFalse(result["ok"])
        self.assertEqual(result["transport_status"], "TIMEOUT")
        self.assertTrue(result["outcome_unknown"])

    def test_missing_and_valid_empty_logs_are_distinct(self):
        for name in ("dispositions.jsonl", "saipal_receipts.jsonl"):
            with self.subTest(name=name):
                self.assertEqual(self.history(name)["status"], "LOG_ABSENT")
                (self.log_dir / name).write_bytes(b"")
                self.assertEqual(self.history(name)["status"], "LOG_VALID")

    def test_complete_history_preserves_all_records(self):
        records = [{"finding_id": "PAL-\u00f5"}, {"finding_id": "PAL-2"}]
        raw = b"\r\n".join(json.dumps(x, ensure_ascii=False).encode() for x in records) + b"\r\n"
        for name in ("dispositions.jsonl", "saipal_receipts.jsonl"):
            with self.subTest(name=name):
                (self.log_dir / name).write_bytes(raw)
                result = self.history(name)
                self.assertTrue(result["ok"])
                self.assertEqual(result["records"], records)
                self.assertEqual(result["snapshot_size"], len(raw))

    def test_corrupt_result_is_explicit_and_not_a_legacy_partial_list(self):
        (self.log_dir / "dispositions.jsonl").write_bytes(b'{"finding_id":"PAL-1"}\n{bad}\n')
        result = self.adapter.get_dispositions(self.project)
        self.assertIsInstance(result, dict)
        self.assertFalse(result["ok"])

    def test_corrupt_history_refuses_new_dispositions_without_touching_evidence(self):
        path = self.log_dir / "dispositions.jsonl"
        raw = b'{"finding_id":"PAL-1"}\n{torn'
        path.write_bytes(raw)
        result = self.adapter.record_maintainer_disposition(
            self.project,
            "PAL-2",
            disposition="BLOCKED",
            task_id="T-1",
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "LOG_TRUNCATED")
        self.assertEqual(path.read_bytes(), raw)

    def test_unsafe_history_node_is_refused_even_when_target_looks_absent(self):
        with mock.patch.object(
            adapter_module.paths,
            "prove_owned_regular",
            side_effect=ValueError("history node is a dangling link"),
        ):
            result = self.adapter.record_maintainer_disposition(
                self.project,
                "PAL-2",
                disposition="BLOCKED",
                task_id="T-1",
            )
        self.assertFalse(result["ok"])
        self.assertFalse((self.log_dir / "dispositions.jsonl").exists())

    def test_concurrent_disposition_writes_are_serialized_or_explicitly_busy(self):
        def append(number):
            deadline = time.monotonic() + 3
            while True:
                result = self.adapter.record_maintainer_disposition(
                    self.project,
                    f"PAL-{number}",
                    disposition="BLOCKED",
                    task_id="T-1",
                )
                if result.get("status") != "HISTORY_BUSY" or time.monotonic() >= deadline:
                    return result
                time.sleep(0.005)

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(append, range(12)))
        self.assertTrue(all(result["ok"] for result in results), results)
        history = self.history("dispositions.jsonl")
        self.assertTrue(history["ok"], history)
        self.assertEqual(
            {row["finding_id"] for row in history["records"]},
            {f"PAL-{number}" for number in range(12)},
        )
        self.assertEqual(len(history["records"]), 12)

    def test_unreadable_discovery_watermark_does_not_reset_to_clean_evidence(self):
        marker = self.log_dir / "saipal_watermark.json"
        marker.write_bytes(b"{broken")
        # AUT-005: the same moved seam as the empty-report control. The durable
        # marker must still be refused and its bytes preserved on the path that
        # actually runs.
        self.response(self.report())
        with mock.patch.object(
            self.adapter, "probe", return_value={"ok": True, "data": {"queue": {}}}
        ):
            result = self.adapter.discover(self.project)
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["status"], adapter_module.ANALYSIS_BLOCKED)
        self.assertEqual(marker.read_bytes(), b"{broken")

    def test_middle_corruption_preserves_prefix_and_original_bytes(self):
        prefix = b'{"finding_id":"PAL-1"}\n'
        raw = prefix + b"{bad}\n" + b'{"finding_id":"PAL-3"}\n'
        for name in ("dispositions.jsonl", "saipal_receipts.jsonl"):
            with self.subTest(name=name):
                path = self.log_dir / name
                path.write_bytes(raw)
                result = self.history(name)
                self.assertFalse(result["ok"], result)
                self.assertEqual(result["status"], "LOG_CORRUPT")
                self.assertEqual(result["records"], [{"finding_id": "PAL-1"}])
                self.assertEqual((result["error_offset"], result["error_line"]), (len(prefix), 2))
                self.assertEqual(result["suffix_status"], "UNVERIFIED")
                self.assertEqual(bytes.fromhex(result["damaged_record_hex"]), b"{bad}\n")
                self.assertEqual(path.read_bytes(), raw)

    def test_torn_final_record_is_never_a_complete_history(self):
        for suffix in (b'{"finding_id":', b'{"finding_id":"PAL-2"}'):
            for name in ("dispositions.jsonl", "saipal_receipts.jsonl"):
                with self.subTest(suffix=suffix, name=name):
                    raw = b'{"finding_id":"PAL-1"}\n' + suffix
                    path = self.log_dir / name
                    path.write_bytes(raw)
                    result = self.history(name)
                    self.assertFalse(result["ok"])
                    self.assertEqual(result["status"], "LOG_TRUNCATED")
                    self.assertEqual(len(result["records"]), 1)
                    self.assertEqual(path.read_bytes(), raw)

    def test_bad_record_types_and_unreadable_logs_are_not_empty_success(self):
        for raw in (b"[]\n", b"null\n", b"\xff\n", b'{"value":NaN}\n'):
            with self.subTest(raw=raw):
                (self.log_dir / "dispositions.jsonl").write_bytes(raw)
                result = self.history("dispositions.jsonl")
                self.assertFalse(result["ok"])
                self.assertEqual(result["status"], "LOG_CORRUPT")
        path = self.log_dir / "saipal_receipts.jsonl"
        path.mkdir()
        self.assertEqual(self.history(path.name)["status"], "LOG_IO_ERROR")

    def test_concurrent_append_is_truncated_until_newline_commits(self):
        path = self.log_dir / "dispositions.jsonl"
        path.write_bytes(b'{"finding_id":"PAL-1"}\n')
        with path.open("ab") as writer:
            writer.write(b'{"finding_id":')
            writer.flush()
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                result = pool.submit(self.history, path.name).result(timeout=3)
            self.assertEqual(result["status"], "LOG_TRUNCATED")
            writer.write(b'"PAL-2"}\n')
            writer.flush()
        result = self.history(path.name)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["records"]), 2)


if __name__ == "__main__":
    unittest.main()
