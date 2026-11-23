"""T-2040 supplementary seams; original 26-control oracle stays untouched.

Run: python -B tools/test_t2040_terminal_consumer_supplementary.py -v
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from saipen_engine import board, continuation_assessment as CA, goal_authority, outcome_truth
from test_campaign_continuation_assessment import _format_state
from test_fixture_support import checked_discovery_evidence
from test_hermetic_env import isolate_host_session

BOARD = "## DOING\n## TODO\n## DONE\n## BLOCKED\n"


def setUpModule():
    isolate_host_session()


class GoalCompletionForwarding(unittest.TestCase):
    def test_same_publication_carrier_and_discovery_kwargs_reach_board(self):
        with tempfile.TemporaryDirectory(prefix="saipen-terminal-forward-") as temp:
            root = Path(temp)
            (root / ".saipen").mkdir()
            carrier = outcome_truth.read_publication_evidence(root, tickets={})
            evidence = checked_discovery_evidence("100")
            hint = {"source_name": "improve_candidates", "source_generation": "100",
                    "action": "saipen improve", "bounded": True}
            with mock.patch.object(board, "classify_idle_work", return_value={"sentinel": True}) as classify:
                result = goal_authority.goal_completion_verdict(
                    {}, {}, persistent_goals=[], source_evidence=evidence,
                    publication_evidence=carrier, source_generation="100",
                    discovery_dispatch=hint, current_agent="tester",
                )
            self.assertEqual(result, {"sentinel": True})
            self.assertIs(classify.call_args.kwargs["publication_evidence"], carrier)
            self.assertIs(classify.call_args.kwargs["source_evidence"], evidence)
            self.assertIs(classify.call_args.kwargs["discovery_dispatch"], hint)
            self.assertEqual(classify.call_args.kwargs["source_generation"], "100")
            self.assertEqual(classify.call_args.kwargs["current_agent"], "tester")


if __name__ == "__main__":
    unittest.main()
