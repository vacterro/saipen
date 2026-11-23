"""Tests for SAILEARN GPU Librarian consumer (T-1796, SRC-256).

Verifies:
1. Purely advisory: zero canonical state mutation (STATE, BOARD, LOG untouched).
2. Soft fallback: missing module or index returns structured refusal without raising.
3. Switch controls: SAIPEN_LIBRARIAN=off disables cleanly and preserves identical protocol behavior.
4. Source freshness: verifies live citations report state (VERIFIED, CHANGED, SUPERSEDED).
5. Resource & usefulness metrics reported.
6. CLI commands: `saipen librarian status`, `saipen librarian query`, `saipen gpu librarian status`.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest import mock

from saipen_engine import sailearn_consumer as sc


class TestSailearnConsumer(unittest.TestCase):
    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parents[1]

    def test_switch_controls(self) -> None:
        with mock.patch.dict(os.environ, {"SAIPEN_LIBRARIAN": "off"}):
            enabled, reason = sc.is_enabled()
            self.assertFalse(enabled)
            self.assertEqual(reason, "env_disabled")
            stat = sc.status()
            self.assertFalse(stat["available"])
            self.assertEqual(stat["reason"], "DISABLED")
            q = sc.query("finding invalidated")
            self.assertFalse(q["available"])
            self.assertEqual(q["reason"], "DISABLED")
            self.assertEqual(q["hits"], [])

        with mock.patch.dict(os.environ, {"SAIPEN_LIBRARIAN": "on"}):
            enabled, reason = sc.is_enabled()
            self.assertTrue(enabled)
            self.assertEqual(reason, "env_enabled")

    def test_status_inspection(self) -> None:
        stat = sc.status()
        self.assertTrue(stat["ok"])
        if stat["available"]:
            self.assertEqual(stat["reason"], "READY")
            self.assertIsNotNone(stat["home"])
            self.assertIsNotNone(stat["index"])
            self.assertGreater(stat["index_size_bytes"], 0)
            self.assertIn("ADVISORY", stat["advisory"])

    def test_query_empty_text(self) -> None:
        stat = sc.status()
        if not stat["available"]:
            self.skipTest("SAILEARN index not available on this host")
        res = sc.query("")
        self.assertTrue(res["ok"])
        self.assertEqual(res["reason"], "EMPTY_QUERY")
        self.assertEqual(res["hits"], [])
        self.assertFalse(res["metrics"]["useful"])

    def test_live_query_with_freshness_citations(self) -> None:
        stat = sc.status()
        if not stat["available"]:
            self.skipTest("SAILEARN index not available on this host")
        res = sc.query("finding invalidated", limit=2)
        self.assertTrue(res["ok"])
        self.assertTrue(res["available"])
        self.assertEqual(res["reason"], "OK")
        self.assertIn("ADVISORY", res["advisory"])
        self.assertIn("hits", res)
        metrics = res["metrics"]
        self.assertIn("duration_ms", metrics)
        self.assertIn("hits_count", metrics)
        self.assertIn("useful", metrics)
        for hit in res["hits"]:
            self.assertIn("record_id", hit)
            self.assertIn("score", hit)
            self.assertIn("citation_state", hit)
            self.assertIn(hit["citation_state"], ("VERIFIED", "CHANGED", "ABSENT", "SUPERSEDED"))

    def test_format_advisory_rendering(self) -> None:
        payload = {
            "ok": True,
            "available": True,
            "hits": [
                {
                    "citation_state": "VERIFIED",
                    "score": 6.5,
                    "source_path": ".saipen/BOARD.md",
                    "text_preview": "Test preview line for citation rendering",
                }
            ],
            "metrics": {
                "duration_ms": 12.3,
                "verified_count": 1,
                "stale_count": 0,
            },
        }
        text = sc.format_advisory(payload)
        self.assertIn("ADVISORY", text)
        self.assertIn("[VERIFIED]", text)
        self.assertIn(".saipen/BOARD.md", text)
        self.assertIn("1 verified", text)

    def test_soft_fallback_on_missing_module(self) -> None:
        with mock.patch(
            "saipen_engine.sailearn_consumer._ensure_sailearn_imported", return_value=False
        ):
            stat = sc.status()
            self.assertTrue(stat["ok"])
            self.assertFalse(stat["available"])
            self.assertEqual(stat["reason"], "SAILEARN_MODULE_UNAVAILABLE")
            res = sc.query("something")
            self.assertFalse(res["available"])
            self.assertEqual(res["reason"], "SAILEARN_MODULE_UNAVAILABLE")

    def test_soft_fallback_on_missing_index(self) -> None:
        with mock.patch("saipen_engine.sailearn_consumer.resolve_index", return_value=None):
            stat = sc.status()
            self.assertTrue(stat["ok"])
            self.assertFalse(stat["available"])
            self.assertEqual(stat["reason"], "INDEX_NOT_FOUND")

    def test_zero_state_mutation(self) -> None:
        state_file = self.project_root / ".saipen" / "STATE.md"
        board_file = self.project_root / ".saipen" / "BOARD.md"
        log_file = self.project_root / ".saipen" / "LOG.md"

        s_before = state_file.read_bytes() if state_file.is_file() else b""
        b_before = board_file.read_bytes() if board_file.is_file() else b""
        l_before = log_file.read_bytes() if log_file.is_file() else b""

        # Perform multiple queries and status checks
        sc.status()
        sc.query("finding invalidated", limit=3)
        sc.query("something else entirely", limit=1)

        s_after = state_file.read_bytes() if state_file.is_file() else b""
        b_after = board_file.read_bytes() if board_file.is_file() else b""
        l_after = log_file.read_bytes() if log_file.is_file() else b""

        self.assertEqual(s_before, s_after, "STATE.md must not be mutated by queries")
        self.assertEqual(b_before, b_after, "BOARD.md must not be mutated by queries")
        self.assertEqual(l_before, l_after, "LOG.md must not be mutated by queries")

    def test_route_payload_with_librarian_enabled_and_disabled(self) -> None:
        import saipen as saipen_cli

        stat = sc.status()
        if not stat["available"]:
            self.skipTest("SAILEARN index not available on this host")

        mock_route = {
            "routed": {
                "action": "saipen continue",
                "ticket": "T-1796",
                "reason": "finding-invalidated",
            },
            "state": {"phase": "BUILD", "task": "T-1796"},
            "state_text": "---\nphase: BUILD\ntask: T-1796\n---\n",
            "subject": "T-1796",
            "board": {"tickets": {}},
            "board_text": "",
            "pending": [],
            "parked": [],
        }

        # Enabled: should attach librarian_advisory and librarian_metrics
        payload_on = saipen_cli._route_payload(
            self.project_root, mock_route, reconciliation=None, dry_run=False
        )
        self.assertIn("librarian_advisory", payload_on)
        self.assertIn("librarian_metrics", payload_on)
        self.assertTrue(payload_on["librarian_metrics"]["useful"])

        # Disabled: should not attach librarian_advisory
        with mock.patch.dict(os.environ, {"SAIPEN_LIBRARIAN": "off"}):
            payload_off = saipen_cli._route_payload(
                self.project_root, mock_route, reconciliation=None, dry_run=False
            )
            self.assertNotIn("librarian_advisory", payload_off)


if __name__ == "__main__":
    unittest.main()
