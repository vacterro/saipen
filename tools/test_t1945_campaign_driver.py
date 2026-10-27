"""SRC-344 (audit/28.md) AUT-006: a campaign with no driver never advances.

`CampaignController.step()` runs exactly one generation. Its only caller was
`saipen campaign step`, so nothing connected generation N to generation N+1:
a MULTI_HOUR campaign sat at one step until a human typed the command again.
`run()` is the bounded driver, and `saipen campaign run --steps N` is its
production caller.

The boundary under test is boundedness, not throughput. Every test here fails
if the loop can spin without a declared bound, can race past a blocking state,
or can invent progress a step did not observe.
"""

from __future__ import annotations

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


class DriverBase(unittest.TestCase):
    """A campaign admitted by the scoped fixture issuer, driven by a stub worker."""

    def setUp(self) -> None:
        # AUT-006 is DRIVER mechanics. The grant fixture is the same declared
        # boundary the campaign matrix uses; the loop under test is downstream
        # of admission and never re-derives authority itself.
        patcher = mock.patch(
            "saipen_engine.host_authority_client.inspect_operator_campaign",
            side_effect=inspect_fixture_campaign,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.root = _make_project()
        self.controller = campaign.CampaignController(self.root)
        admitted = self.controller.admit_campaign(
            campaign_id="CAMP-AUT006",
            authority_proof_reference=".saipen/authority/grant.json",
        )
        self.assertTrue(admitted.get("ok"), admitted)

    def _running_work(self, monkeypatch_target):
        """Make continuation assessment always report executable Work."""
        return mock.patch.object(
            monkeypatch_target,
            "assess_continuation",
            return_value={
                "classification": ca.ACTIVE_WORK,
                "next_action": "execute_work",
            },
        )


class DriverIsBoundedTest(DriverBase):
    def test_rejects_a_non_positive_bound(self) -> None:
        for bound in (0, -1, True, "3", 2.5):
            with self.subTest(bound=bound):
                result = self.controller.run(max_steps=bound)
                self.assertFalse(result["ok"], result)
                self.assertEqual(result["code"], "INVALID_STEP_BOUND")
                self.assertNotIn(
                    "steps", result, "a refused invocation never took a step"
                )

    def test_takes_exactly_the_declared_number_of_steps(self) -> None:
        seen = []

        def worker(project_root, generation):
            seen.append(generation)
            return {"progress_verified": True, "mutated": True}

        with self._running_work(ca):
            result = self.controller.run(max_steps=3, worker_func=worker)
        self.assertTrue(result["ok"], result.get("detail"))
        self.assertEqual(result["status"], "STEP_BOUND_REACHED")
        self.assertEqual(len(result["steps"]), 3, "the bound is the ceiling")
        self.assertEqual(seen, [1, 2, 3], "each step is a new generation")

    def test_a_step_failure_stops_the_loop(self) -> None:
        calls = []

        def worker(project_root, generation):
            calls.append(generation)
            return {"ok": False, "error": "deliberate"}

        with self._running_work(ca):
            result = self.controller.run(max_steps=5, worker_func=worker)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "step_failed")
        self.assertEqual(len(calls), 1, "a failed step is not retried blindly")


class DriverStopsOnBlockingStatesTest(DriverBase):
    def _set_state(self, value: str) -> None:
        state = campaign.load_campaign_state(self.root)
        state["campaign_state"] = value
        campaign.save_campaign_state(self.root, state)

    def test_it_does_not_step_a_terminal_campaign(self) -> None:
        for value in (campaign.COMPLETE, campaign.CANCELLED):
            with self.subTest(state=value):
                self._set_state(value)
                result = self.controller.run(max_steps=3, worker_func=lambda *_: {"ok": True})
                self.assertTrue(result["ok"], result)
                self.assertEqual(result["status"], "STOPPED")
                self.assertEqual(result["steps"], [], "a finished campaign takes no step")

    def test_it_does_not_spin_while_waiting_for_an_operator(self) -> None:
        for value in (
            campaign.OPERATOR_BLOCKED,
            campaign.AUTHORITY_BLOCKED,
            campaign.EXTERNAL_BLOCKED,
            campaign.SAFETY_STOP,
        ):
            with self.subTest(state=value):
                self._set_state(value)
                result = self.controller.run(max_steps=4, worker_func=lambda *_: {"ok": True})
                self.assertTrue(result["ok"], result)
                self.assertEqual(result["steps"], [])
                self.assertIn("requires_operator", result["reason"])

    def test_a_proposal_is_not_executed_by_the_driver(self) -> None:
        self._set_state(campaign.PROPOSED)
        result = self.controller.run(max_steps=2, worker_func=lambda *_: {"ok": True})
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["steps"], [], "an unadmitted proposal is not executable")


class DriverRespectsUnproductiveWorkTest(DriverBase):
    def test_an_unproductive_step_stops_the_loop(self) -> None:
        calls = []

        def worker(project_root, generation):
            calls.append(generation)
            return {"ok": True, "progress_verified": False}

        with self._running_work(ca):
            result = self.controller.run(max_steps=10, worker_func=worker)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["reason"], "no_productive_progress")
        self.assertEqual(len(calls), 1, "no progress is not a reason to keep spinning")

    def test_the_persisted_generation_budget_still_stops_it(self) -> None:
        state = campaign.load_campaign_state(self.root)
        state["resource_budget"]["max_generations"] = 2
        campaign.save_campaign_state(self.root, state)

        def worker(project_root, generation):
            return {"progress_verified": True, "mutated": True}

        with self._running_work(ca):
            result = self.controller.run(max_steps=10, worker_func=worker)
        final = campaign.load_campaign_state(self.root)
        self.assertLessEqual(
            int(final.get("worker_generation", 0)), 2,
            "the driver cannot outrun the operator's generation budget",
        )
        self.assertIn(
            result["status"],
            ("STEP_BOUND_REACHED", "STOPPED"),
            result,
        )


class ProductionCallerTest(unittest.TestCase):
    """The driver must have a real entry point, not just a unit-tested method."""

    def test_campaign_run_is_a_cli_subcommand(self) -> None:
        source = (TOOLS / "saipen.py").read_text(encoding="utf-8")
        self.assertIn('if sub == "run":', source)
        marker = source.index('if sub == "run":')
        body = source[marker:marker + 2000]
        self.assertIn("ctrl.run(", body, "the subcommand must call the driver")
        self.assertIn("--steps", body, "the caller chooses the bound")


if __name__ == "__main__":
    unittest.main()
