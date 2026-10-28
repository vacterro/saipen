"""SRC-344 (audit/28.md) AUT-005: the bounded walk had no production caller.

`iter_new_qualified_findings` and `iter_finding_pages` were fully implemented,
fully tested, and completely unused: production discovery called
`_run_cmd("report")`, which materialises the ENTIRE corpus before a single row
is classified. The incremental transport was dead code.

`discover()` now walks the validated spool page by page. These tests pin that
down from the outside: discovery must not use the materialising API at all, the
qualified rows must still arrive, and a malformed corpus must still be a typed
refusal rather than an empty-but-ok result.
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from producer_backends import saipal_adapter  # noqa: E402


def _report_payload(rows: list[dict]) -> bytes:
    return json.dumps(
        {
            "schema_version": 1,
            "ok": True,
            "command": "report",
            "findings": rows,
            "counts": {"total": len(rows)},
        }
    ).encode("utf-8")


def _finding(finding_id: str, state: str = "QUALIFIED") -> dict:
    return {
        "finding_id": finding_id,
        "state": state,
        "audit_body": f"# {finding_id}\nbody\n",
    }


class IncrementalDiscoveryTest(unittest.TestCase):
    """Discovery reads through the paged transport, never the whole corpus."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="saipen-aut005-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / ".saipen" / "campaign").mkdir(parents=True)
        self.adapter = saipal_adapter.SaipalAdapter(saipal_home=".")

    def _serve(self, payload: bytes) -> None:
        self.adapter._capture_report_spool = lambda: {
            "ok": True,
            "returncode": 0,
            "stdout_file": io.BytesIO(payload),
            "stdout_bytes_len": len(payload),
            "stderr": b"",
        }

    def _discover(self, project_root=True):
        """Run discovery with the ruler: `_run_cmd` must never be reached."""
        with mock.patch.object(
            self.adapter, "probe", return_value={"ok": True, "data": {"queue": {}}}
        ), mock.patch.object(
            self.adapter,
            "_run_cmd",
            side_effect=AssertionError(
                "discovery must not use the materialising backend transport"
            ),
        ):
            return self.adapter.discover(self.root if project_root else None)

    def test_discovery_does_not_use_the_materialising_report_api(self) -> None:
        self._serve(_report_payload([_finding("PAL-1")]))
        result = self._discover()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["status"], saipal_adapter.NEW_QUALIFIED_FINDINGS)

    def test_only_qualified_findings_are_reported(self) -> None:
        self._serve(
            _report_payload(
                [
                    _finding("PAL-1", "QUALIFIED"),
                    _finding("PAL-2", "OPEN"),
                    _finding("PAL-3", "CONFIRMED"),
                    _finding("PAL-4", "DISMISSED"),
                ]
            )
        )
        result = self._discover()
        self.assertEqual(result["status"], saipal_adapter.NEW_QUALIFIED_FINDINGS)
        self.assertEqual(
            sorted(row["finding_id"] for row in result["findings"]),
            ["PAL-1", "PAL-3"],
        )
        self.assertEqual(
            result["total_findings"], 4,
            "the corpus size is reported, not just the qualified subset",
        )

    def test_an_empty_corpus_is_no_new_evidence(self) -> None:
        self._serve(_report_payload([]))
        result = self._discover()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["status"], saipal_adapter.NO_NEW_EVIDENCE)

    def test_a_malformed_corpus_is_a_typed_refusal(self) -> None:
        self._serve(b'{"ok": true, "findings": [{"finding_id": "PAL-1"')
        result = self._discover()
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["status"], saipal_adapter.BACKEND_PROTOCOL_ERROR)

    def test_the_bounded_walk_pages_a_large_corpus(self) -> None:
        rows = [_finding(f"PAL-{index:04d}") for index in range(600)]
        self._serve(_report_payload(rows))
        pages = []
        original = self.adapter.iter_finding_pages

        def counting_pages(*args, **kwargs):
            for page in original(*args, **kwargs):
                pages.append(len(page[2]))
                yield page

        with mock.patch.object(self.adapter, "iter_finding_pages", counting_pages):
            result = self._discover()
        self.assertTrue(result["ok"], result)
        self.assertGreater(len(pages), 1, "a 600-row corpus must span several pages")
        self.assertLessEqual(
            max(pages), saipal_adapter.REPORT_PAGE_DEFAULT,
            "no page may exceed the declared page bound",
        )
        self.assertEqual(len(result["findings"]), 600)

    def test_an_unchanged_unqualified_corpus_is_deduplicated(self) -> None:
        self._serve(_report_payload([_finding("PAL-1", "OPEN")]))
        first = self._discover()
        self.assertEqual(first["status"], saipal_adapter.NO_NEW_EVIDENCE)
        second = self._discover()
        self.assertEqual(second["status"], saipal_adapter.NO_NEW_EVIDENCE)
        self.assertIn("unchanged", second.get("detail", ""))

    def test_the_watermark_is_the_corpus_identity_from_the_walk(self) -> None:
        self._serve(_report_payload([_finding("PAL-1", "OPEN")]))
        self._discover()
        marker = json.loads(
            (self.root / ".saipen" / "campaign" / "saipal_watermark.json").read_text(
                encoding="utf-8"
            )
        )
        digest = marker["report_hash"]
        self.assertIn(":", digest, "the paged identity is envelope:corpus, not a bare hash")
        self.assertTrue(marker["updated_at"])

    def test_discovery_without_a_project_root_still_pages(self) -> None:
        self._serve(_report_payload([_finding("PAL-1")]))
        result = self._discover(project_root=False)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["status"], saipal_adapter.NEW_QUALIFIED_FINDINGS)
        self.assertEqual([row["finding_id"] for row in result["findings"]], ["PAL-1"])


class DiscoveryUsesThePagedTransportTest(unittest.TestCase):
    """Structural pin: the materialising call must not come back."""

    def test_discovery_source_calls_the_incremental_walk(self) -> None:
        source = (
            TOOLS / "producer_backends" / "saipal_adapter.py"
        ).read_text(encoding="utf-8")
        start = source.index("    def discover(self, project_root")
        end = source.index("    def checkpoint(self, project_root")
        body = source[start:end]
        self.assertIn("iter_new_qualified_findings", body)
        # Comments in this body deliberately NAME the removed call, so the pin
        # has to read code, not prose. A materialising call is a statement.
        code_lines = [
            line for line in body.splitlines()
            if not line.lstrip().startswith("#")
        ]
        offenders = [line for line in code_lines if '_run_cmd("report")' in line]
        self.assertEqual(
            offenders, [],
            "discovery must not fall back to the whole-corpus transport",
        )


if __name__ == "__main__":
    unittest.main()
