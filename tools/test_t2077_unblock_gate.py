"""T-2077: the unblock gate classifies the blocker HEAD, not free prose.

Measured defect (E-21472): after its dependency T-2059 reached DONE, T-2062
still refused ``ticket unblock`` with WAIT_USER_DECISION because the row's
explanatory TAIL mentioned that token while its HEAD was a pure
ACTIVE_DEPENDENCY hold. ``board.blocker_class``,
``board.deferred_operator_class`` and ``cold_recovery.classify_blocker`` all
already read only the head, so the gate contradicted the engine's own policy
owners. These controls drive ``ticket_move`` itself: a dependency hold must
lift, and a genuine head class must still refuse with zero writes.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.operations import ticket_move  # noqa: E402
from test_t1363_zero_manual_entry import _allocation_log, project  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

DEPENDENCY_TAIL = (
    "ACTIVE_DEPENDENCY:T-9000 -- measured: this Work waits for T-9000, whose "
    "own seat is parked on an operator question (WAIT_USER_DECISION, "
    "authenticated ingress unavailable)"
)
GENUINE_GATE = "WAIT_USER_DECISION -- the operator chooses the publication policy"
TAIL_ONLY_VENDOR = (
    "ACTIVE_DEPENDENCY:T-9000 -- the blocked path also mentions "
    "VENDOR_ACCEPTANCE in passing while the hold is a dependency"
)


def setUpModule() -> None:
    isolate_host_session()


def _board(blocker: str) -> str:
    return (
        "## DOING\n"
        "## TODO\n"
        "## DONE\n"
        "## BLOCKED\n"
        f"- [ ] T-9100 [P1] parked work | verify: it holds | blocker: {blocker} "
        "| blocker_scope: ticket\n"
    )


class UnblockGateTests(unittest.TestCase):
    def _move(self, blocker: str, decision: str):
        root = project(self, board=_board(blocker), log=_allocation_log("T-9100"))
        before = {
            name: (root / ".saipen" / name).read_bytes()
            for name in ("STATE.md", "BOARD.md", "LOG.md")
        }
        result = ticket_move(root, "unblock", "T-9100", "test-agent", decision)
        after = {
            name: (root / ".saipen" / name).read_bytes()
            for name in ("STATE.md", "BOARD.md", "LOG.md")
        }
        return result, before, after

    def test_dependency_hold_lifts_despite_an_operator_token_in_its_tail(self):
        result, _before, _after = self._move(
            DEPENDENCY_TAIL, "the dependency completed; release the seat"
        )
        self.assertTrue(result.ok, result.to_dict())

    def test_genuine_head_class_still_requires_operator_authority(self):
        result, before, after = self._move(
            GENUINE_GATE, "the dependency completed; release the seat"
        )
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(result.code, "WAIT_USER_DECISION")
        self.assertEqual(before, after)

    def test_vendor_tail_does_not_arm_the_vendor_refusal(self):
        result, _before, _after = self._move(
            TAIL_ONLY_VENDOR, "the dependency completed; release the seat"
        )
        self.assertTrue(result.ok, result.to_dict())

    def test_genuine_vendor_head_still_refuses(self):
        result, before, after = self._move(
            "VENDOR_ACCEPTANCE -- the vendor must accept the live run",
            "the dependency completed; release the seat",
        )
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(result.code, "VENDOR_ACCEPTANCE_BLOCKED")
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
