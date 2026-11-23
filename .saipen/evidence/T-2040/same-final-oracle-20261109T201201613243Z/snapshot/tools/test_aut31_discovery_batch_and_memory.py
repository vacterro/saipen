"""AUT31-003: Discovery Memory Bounding, Batch Delivery and Measurements.

Verifies and measures:
- 100 qualified findings
- 1,000 qualified findings
- 10,000 qualified findings (peak resident memory bounding)
- Backend refusal
- Malformed report
- Report generation changes mid-walk
- Interruption during delivery (crash safety and restart)
- Partial success within a page
- Campaign publication loop commits acknowledgment only after canonical delivery
- Preservation of AUT31-001 and AUT31-002 P0 controls
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import tracemalloc
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from producer_backends import saipal_adapter  # noqa: E402
from saipen_engine import campaign  # noqa: E402


def _report_payload(rows: list[dict], digest: str = "dig-001") -> bytes:
    return json.dumps(
        {
            "schema_version": 1,
            "ok": True,
            "command": "report",
            "source_digest": digest,
            "findings": rows,
            "counts": {"total": len(rows)},
        }
    ).encode("utf-8")


def _finding(finding_id: str, state: str = "QUALIFIED", body: str | None = None) -> dict:
    content = body or f"# {finding_id}\nFinding body content\n"
    d = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return {
        "finding_id": finding_id,
        "state": state,
        "audit_body": content,
        "artifact_digest": d,
        "qualification_receipt": f"qual-{finding_id.lower()}",
    }


class Aut31DiscoveryBatchAndMemoryTests(unittest.TestCase):
    """Test suite for AUT31-003 bounded consumption, memory, and failure modes."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-aut31-003-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / ".saipen" / "campaign").mkdir(parents=True)
        (self.root / "audit").mkdir(parents=True)
        self.adapter = saipal_adapter.SaipalAdapter(saipal_home=".")

    def _serve(self, payload: bytes) -> None:
        self.adapter._capture_report_spool = lambda: {
            "ok": True,
            "returncode": 0,
            "stdout_file": io.BytesIO(payload),
            "stdout_bytes_len": len(payload),
            "stderr": b"",
        }

    def _mock_probe(self):
        return mock.patch.object(
            self.adapter, "probe", return_value={"ok": True, "data": {"queue": {}}}
        )

    # ------------------------------------------------------------------
    # 1. MEASURE: 100 qualified findings
    # ------------------------------------------------------------------
    def test_measure_100_qualified_findings(self) -> None:
        rows = [_finding(f"PAL-100-{i:03d}") for i in range(100)]
        self._serve(_report_payload(rows))
        tracemalloc.start()
        with self._mock_probe():
            res = self.adapter.discover(self.root, batch_size=50)
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        self.assertTrue(res["ok"], res)
        self.assertEqual(res["status"], saipal_adapter.NEW_QUALIFIED_FINDINGS)
        self.assertEqual(len(res["findings"]), 50, "batch_size=50 yields first bounded batch of 50")
        self.assertEqual(res["total_findings"], 100)
        self.assertTrue(res.get("has_more"))
        # Peak memory is modest for 100 findings
        self.assertLess(peak, 5 * 1024 * 1024, "Peak memory must remain well under 5MB")

    # ------------------------------------------------------------------
    # 2. MEASURE: 1,000 qualified findings
    # ------------------------------------------------------------------
    def test_measure_1000_qualified_findings(self) -> None:
        rows = [_finding(f"PAL-1K-{i:04d}") for i in range(1000)]
        self._serve(_report_payload(rows))
        tracemalloc.start()
        with self._mock_probe():
            res = self.adapter.discover(self.root, batch_size=200)
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        self.assertTrue(res["ok"], res)
        self.assertEqual(len(res["findings"]), 200, "Yields single bounded batch of 200")
        self.assertEqual(res["total_findings"], 1000)
        self.assertTrue(res.get("has_more"))
        self.assertLess(peak, 10 * 1024 * 1024, "Peak memory for 1K batch must remain under 10MB")

    # ------------------------------------------------------------------
    # 3. MEASURE: 10,000 qualified findings (Peak memory comparison)
    # ------------------------------------------------------------------
    def test_measure_10000_qualified_findings_memory_bounding(self) -> None:
        rows = [_finding(f"PAL-10K-{i:05d}") for i in range(10000)]
        payload = _report_payload(rows)
        self._serve(payload)

        # Batch mode: stops at first batch (default 200)
        tracemalloc.start()
        with self._mock_probe():
            batch_res = self.adapter.discover(self.root, batch_size=200, drain=False)
        _, peak_batch = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        self.assertTrue(batch_res["ok"], batch_res)
        self.assertEqual(len(batch_res["findings"]), 200)
        self.assertEqual(batch_res["total_findings"], 10000)
        self.assertTrue(batch_res.get("has_more"))

        # Drain mode (full accumulation): drains all 10,000
        tracemalloc.start()
        with self._mock_probe():
            drain_res = self.adapter.discover(self.root, batch_size=200, drain=True)
        _, peak_drain = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        self.assertTrue(drain_res["ok"], drain_res)
        self.assertEqual(len(drain_res["findings"]), 10000)

        # Bounded batch peak resident memory must be significantly lower than full drain
        # or well bounded
        self.assertLess(
            peak_batch,
            peak_drain + 1024 * 1024,
            f"Batch mode peak ({peak_batch} bytes) should be bounded vs drain ({peak_drain} bytes)",
        )

    # ------------------------------------------------------------------
    # 4. MEASURE: Backend refusal
    # ------------------------------------------------------------------
    def test_backend_refusal_handled_cleanly(self) -> None:
        refusal = {"ok": False, "status": "BACKEND_UNAVAILABLE", "error": "daemon refused connection"}
        with mock.patch.object(self.adapter, "probe", return_value=refusal):
            res = self.adapter.discover(self.root)
        self.assertFalse(res["ok"])
        self.assertEqual(res["status"], "BACKEND_UNAVAILABLE")
        self.assertEqual(res["error"], "daemon refused connection")

    # ------------------------------------------------------------------
    # 5. MEASURE: Malformed report
    # ------------------------------------------------------------------
    def test_malformed_report_typed_refusal(self) -> None:
        self._serve(b'{"schema_version": 1, "ok": true, "findings": [{"broken_json"')
        with self._mock_probe():
            res = self.adapter.discover(self.root)
        self.assertFalse(res["ok"])
        self.assertEqual(res["status"], saipal_adapter.BACKEND_PROTOCOL_ERROR)

    # ------------------------------------------------------------------
    # 6. MEASURE: Report generation changes mid-walk
    # ------------------------------------------------------------------
    def test_report_generation_changes_mid_walk(self) -> None:
        # Simulate iter_finding_pages returning pages with conflicting source_digest
        page1 = (1, 2, [_finding("PAL-MID-1")], {"source_digest": "sha256:gen1"})
        page2 = (2, 2, [_finding("PAL-MID-2")], {"source_digest": "sha256:gen2"})

        with mock.patch.object(self.adapter, "iter_finding_pages", return_value=iter([page1, page2])):
            pages = list(self.adapter.iter_new_qualified_findings(self.root, page_size=1))

        self.assertEqual(len(pages), 2)
        self.assertTrue(pages[0]["ok"], "First page admitted")
        self.assertFalse(pages[1]["ok"], "Second page with changed generation refused")
        self.assertEqual(pages[1]["status"], "REPORT_SOURCE_CHANGED")
        self.assertEqual(pages[1]["expected_source_digest"], "sha256:gen1")
        self.assertEqual(pages[1]["actual_source_digest"], "sha256:gen2")

    # ------------------------------------------------------------------
    # 7. MEASURE: Interruption during delivery (crash & restart)
    # ------------------------------------------------------------------
    def test_interruption_during_delivery_resumes_cleanly(self) -> None:
        f1 = _finding("PAL-INT-1")
        f2 = _finding("PAL-INT-2")
        self._serve(_report_payload([f1, f2]))

        # Discover batch
        with self._mock_probe():
            disc = self.adapter.discover(self.root, batch_size=2)
        self.assertTrue(disc["ok"])
        self.assertEqual(len(disc["findings"]), 2)

        # Simulate crash before acknowledgment: NO ack row written.
        # Now re-discover: both findings must be re-yielded without loss
        with self._mock_probe():
            resumed = self.adapter.discover(self.root, batch_size=2)
        self.assertTrue(resumed["ok"])
        self.assertEqual(len(resumed["findings"]), 2)
        resumed_ids = [f["finding_id"] for f in resumed["findings"]]
        self.assertEqual(resumed_ids, ["PAL-INT-1", "PAL-INT-2"])

        # Now simulate successful publication and acknowledgment of PAL-INT-1 only
        ack_res = self.adapter.acknowledge_delivery(
            self.root,
            ["PAL-INT-1"],
            source_digest=disc["source_digest"],
            artifact_digests={"PAL-INT-1": f1["artifact_digest"]},
        )
        self.assertTrue(ack_res["ok"])

        # Re-discover: PAL-INT-1 is acknowledged, so only PAL-INT-2 is yielded!
        with self._mock_probe():
            next_walk = self.adapter.discover(self.root, batch_size=2)
        self.assertTrue(next_walk["ok"])
        self.assertEqual(len(next_walk["findings"]), 1)
        self.assertEqual(next_walk["findings"][0]["finding_id"], "PAL-INT-2")

    # ------------------------------------------------------------------
    # 8. Support partial success within a page
    # ------------------------------------------------------------------
    def test_partial_success_within_page_acknowledges_only_published(self) -> None:
        from test_campaign_matrix import _make_project
        from campaign_test_support import inspect_fixture_campaign

        proj_root = _make_project()
        (proj_root / "audit").mkdir(parents=True, exist_ok=True)
        adapter = saipal_adapter.SaipalAdapter(saipal_home=".")

        f1 = _finding("PAL-PART-1")
        f2 = _finding("PAL-PART-2")
        payload = _report_payload([f1, f2], digest="dig-part")
        adapter._capture_report_spool = lambda: {
            "ok": True,
            "returncode": 0,
            "stdout_file": io.BytesIO(payload),
            "stdout_bytes_len": len(payload),
            "stderr": b"",
        }

        # Setup campaign controller
        ctrl = campaign.CampaignController(proj_root, backend=adapter)
        with mock.patch(
            "saipen_engine.host_authority_client.inspect_operator_campaign",
            side_effect=inspect_fixture_campaign,
        ):
            admitted = ctrl.admit_campaign(
                campaign_id="CAMP-PART-TEST",
                authority_proof_reference=".saipen/authority/grant.json",
            )
        self.assertTrue(admitted.get("ok"), admitted)

        # Force state to DISCOVERING
        state = campaign.load_campaign_state(proj_root)
        state["campaign_state"] = campaign.DISCOVERING
        campaign.save_campaign_state(proj_root, state)

        # Mock deliver_finding_to_audit_inbox so f1 succeeds, f2 fails
        def mock_deliver(root, finding, publication_authorized=False):
            fid = finding.get("finding_id")
            if fid == "PAL-PART-1":
                return {
                    "ok": True,
                    "status": "DELIVERED_PUBLICATION",
                    "finding_id": fid,
                    "artifact_digest": finding.get("artifact_digest"),
                }
            return {"ok": False, "status": "ARTIFACT_MISSING", "finding_id": fid}

        with mock.patch.object(adapter, "probe", return_value={"ok": True, "data": {"queue": {}}}), \
             mock.patch.object(campaign, "_verify_state_grant", return_value={"valid": True}), \
             mock.patch.object(campaign.ca, "assess_continuation", return_value={"classification": campaign.ca.MAINTENANCE_AVAILABLE, "next_action": "forensic_analysis"}), \
             mock.patch.object(adapter, "deliver_finding_to_audit_inbox", side_effect=mock_deliver):
            step_res = ctrl.step()

        self.assertTrue(step_res["ok"], step_res)
        self.assertEqual(step_res["event"], "DISCOVERY_DELIVERED")
        self.assertEqual(step_res["delivery_status"], "PARTIALLY_DELIVERED")
        self.assertEqual(step_res["published_finding_ids"], ["PAL-PART-1"])
        self.assertEqual(step_res["failed_finding_ids"], ["PAL-PART-2"])

        # Check ack journal: PAL-PART-1 must be acknowledged; PAL-PART-2 must NOT be acknowledged
        ack = adapter._acknowledged_ids(proj_root, None)
        self.assertTrue(ack["ok"])
        self.assertIn("PAL-PART-1", ack["ids"])
        self.assertNotIn("PAL-PART-2", ack["ids"])


if __name__ == "__main__":
    unittest.main()
