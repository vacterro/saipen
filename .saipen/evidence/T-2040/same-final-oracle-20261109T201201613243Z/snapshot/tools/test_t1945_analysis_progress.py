"""SRC-344 (audit/28.md) AUT-007: one analysis slice is not a finished objective.

`discover()` returning ANALYSIS_PROGRESS means "a bounded SAIPAL slice ran and
more eligible slices remain". The controller used to fall through to the
no-findings branch, save QUIESCENT_WAIT and report DISCOVERY_NO_NEW_FINDINGS --
so after its first slice a campaign with pending hot/cold sessions slept
through its own remaining work.

Reproduced before the repair by driving `step()` with a discovery stub that
returns ANALYSIS_PROGRESS and reading the persisted state back.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import campaign, continuation_assessment as ca  # noqa: E402
from campaign_test_support import inspect_fixture_campaign  # noqa: E402
from test_campaign_matrix import _make_project  # noqa: E402


def _read_state(root: Path) -> dict:
    path = root / ".saipen" / "campaign" / "state.json"
    return json.loads(path.read_text(encoding="utf-8"))


class AnalysisProgressStaysSchedulableTest(unittest.TestCase):
    """A partial slice keeps FORENSIC_ANALYSIS and an explicit next action."""

    def setUp(self) -> None:
        # AUT-007 is CAMPAIGN-SCHEDULING mechanics, not issuer trust. The
        # scoped fixture broker stands in for the native issuer exactly as the
        # campaign matrix does; the analysis-progress edge under test is
        # downstream of admission and does not depend on how the grant was
        # proven.
        patcher = mock.patch(
            "saipen_engine.host_authority_client.inspect_operator_campaign",
            side_effect=inspect_fixture_campaign,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.root = _make_project()
        self.controller = campaign.CampaignController(self.root, backend=mock.Mock())
        admitted = self.controller.admit_campaign(
            campaign_id="CAMP-AUT007",
            authority_proof_reference=".saipen/authority/grant.json",
        )
        self.assertTrue(admitted.get("ok"), admitted)
        self.assertEqual(admitted["state"]["campaign_state"], campaign.ADMITTED)

    def _step_with_discovery(self, discovery: dict) -> dict:
        assessment = {
            "classification": ca.MAINTENANCE_AVAILABLE,
            "next_action": "forensic_analysis",
        }
        with mock.patch.object(ca, "assess_continuation", return_value=assessment), \
             mock.patch.object(self.controller.backend, "discover", return_value=discovery):
            return self.controller.step()

    def test_analysis_progress_does_not_quiesce(self) -> None:
        result = self._step_with_discovery(
            {"ok": True, "status": "ANALYSIS_PROGRESS", "slice": {"session": "hot-1"}}
        )
        state = _read_state(self.root)
        self.assertNotEqual(
            state.get("campaign_state"),
            campaign.QUIESCENT_WAIT,
            "a slice with more work pending must not put the campaign to sleep",
        )
        self.assertEqual(state.get("campaign_state"), campaign.FORENSIC_ANALYSIS)
        self.assertTrue(result.get("ok"), result)
        self.assertEqual(result.get("event"), "ANALYSIS_PROGRESS")

    def test_analysis_progress_is_not_reported_as_no_findings(self) -> None:
        result = self._step_with_discovery(
            {"ok": True, "status": "ANALYSIS_PROGRESS", "slice": {"session": "hot-2"}}
        )
        self.assertNotEqual(result.get("event"), "DISCOVERY_NO_NEW_FINDINGS")
        self.assertIn("further eligible slices", result.get("detail", ""))

    def test_analysis_progress_names_the_next_action(self) -> None:
        self._step_with_discovery({"ok": True, "status": "ANALYSIS_PROGRESS"})
        state = _read_state(self.root)
        self.assertEqual(state.get("next_action"), "forensic_analysis_slice")

    def test_each_slice_advances_the_recorded_generation(self) -> None:
        self._step_with_discovery({"ok": True, "status": "ANALYSIS_PROGRESS"})
        first = _read_state(self.root).get("last_analysis_generation")
        self._step_with_discovery({"ok": True, "status": "ANALYSIS_PROGRESS"})
        second = _read_state(self.root).get("last_analysis_generation")
        self.assertEqual(second, first + 1, "each executed slice is a generation")

    def test_the_slice_is_recorded_with_its_identity(self) -> None:
        self._step_with_discovery(
            {"ok": True, "status": "ANALYSIS_PROGRESS", "slice": {"session": "cold-7"}}
        )
        state = _read_state(self.root)
        recorded = state.get("last_analysis_slice") or {}
        self.assertEqual(recorded.get("slice"), {"session": "cold-7"})
        self.assertTrue(recorded.get("at"), "the slice must carry a timestamp")

    def test_a_completed_objective_may_still_quiesce(self) -> None:
        """The repair must not turn a genuine empty corpus into a hot loop."""
        result = self._step_with_discovery({"ok": True, "status": "NO_NEW_EVIDENCE"})
        state = _read_state(self.root)
        self.assertEqual(state.get("campaign_state"), campaign.QUIESCENT_WAIT)
        self.assertEqual(result.get("event"), "DISCOVERY_NO_NEW_FINDINGS")

    def test_new_findings_still_reach_delivery(self) -> None:
        """ANALYSIS_PROGRESS support must not swallow the findings branch."""
        published = {
            "ok": True,
            "status": "DELIVERED_PUBLICATION",
            "finding_id": "PAL-1",
        }
        discovery = {
            "ok": True,
            "status": "NEW_QUALIFIED_FINDINGS",
            "findings": [{"finding_id": "PAL-1"}],
        }
        with mock.patch.object(
            self.controller.backend,
            "deliver_finding_to_audit_inbox",
            return_value=published,
        ):
            result = self._step_with_discovery(discovery)
        self.assertEqual(result.get("event"), "DISCOVERY_DELIVERED")
        self.assertEqual(result.get("delivery_status"), "ALL_DELIVERED")
        self.assertEqual(
            result.get("published_finding_ids"), ["PAL-1"],
            "a qualified finding must still be published by its own branch",
        )


class AnalysisProgressOrderTest(unittest.TestCase):
    """The progress branch is checked before the no-findings `else`."""

    def test_progress_branch_precedes_the_findings_branch(self) -> None:
        source = (TOOLS / "saipen_engine" / "campaign.py").read_text(encoding="utf-8")
        progress = source.index(
            'if disc_res.get("status") == backend_protocol.ANALYSIS_PROGRESS'
        )
        findings = source.index(
            'if disc_res.get("status") == backend_protocol.NEW_QUALIFIED_FINDINGS'
        )
        self.assertLess(progress, findings, "progress must be handled on its own edge")


class MissingBackendIsATypedRefusalTest(unittest.TestCase):
    """T-1947: no backend injected is a deployment fact, not a silent skip.

    The engine may not resolve a producer itself any more, so the one case it
    cannot serve is a controller with no backend at all. That must stay a
    refusal the campaign persists and can act on -- never a fake
    NO_NEW_EVIDENCE, which would put a campaign to sleep on an unanswered
    question.
    """

    def setUp(self) -> None:
        patcher = mock.patch(
            "saipen_engine.host_authority_client.inspect_operator_campaign",
            side_effect=inspect_fixture_campaign,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.root = _make_project()
        self.controller = campaign.CampaignController(self.root)
        admitted = self.controller.admit_campaign(
            campaign_id="CAMP-NOBACKEND",
            authority_proof_reference=".saipen/authority/grant.json",
        )
        self.assertTrue(admitted.get("ok"), admitted)

    def _maintenance_step(self) -> dict:
        assessment = {"classification": ca.MAINTENANCE_AVAILABLE}
        with mock.patch.object(ca, "assess_continuation", return_value=assessment), \
             mock.patch.object(
                 campaign, "_verify_state_grant", return_value={"valid": True}
             ):
            return self.controller.step()

    def test_a_controller_without_a_backend_refuses_typed(self) -> None:
        self.assertIsNone(self.controller.backend)
        result = self._maintenance_step()
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["event"], "FORENSIC_DISCOVERY_FAILED")
        self.assertEqual(result["status"], "RUNTIME_UNAVAILABLE")

    def test_the_refusal_is_persisted_with_a_recovery_action(self) -> None:
        self._maintenance_step()
        state = _read_state(self.root)
        self.assertEqual(state.get("campaign_state"), campaign.EXTERNAL_BLOCKED)
        self.assertEqual(state.get("next_action"), "configure_analysis_backend")
        self.assertEqual(
            (state.get("last_discovery_failure") or {}).get("status"),
            "RUNTIME_UNAVAILABLE",
        )
        self.assertEqual(
            state.get("last_analysis_generation"), 0,
            "an unanswered question advances no generation",
        )


if __name__ == "__main__":
    unittest.main()
