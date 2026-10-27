"""T-1880 / SRC-305 DRIFT-05 / SRC-306 D-05: a phase move never lifts a WAIT.

Measured on a downstream project: `saipen hh` at the bounded safety valve
returned `phase: HUNT`, `next_action: PHASE HUNT` and a RUN event, while the
valve was still tripped. The next `saipen continue` then refused with "safety
valve reached", so the STATE carried two contradictory answers: a phase
shortcut promising continuation and a brake refusing it.

The invariant is narrow on purpose. A transition may change the PHASE -- that
is what a phase verb is for -- but a `WAIT:` in `next_action` is an operator
decision the transition did not earn, and it survives verbatim. Ordinary
routing is untouched: with no WAIT, the destination's route is still written.

RED before the repair: the tripped-valve case answered `PHASE HUNT`.
GREEN after: it keeps the WAIT, and both ordinary cases still route.
"""

import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import operations  # noqa: E402
from saipen_engine.state import parse_state  # noqa: E402

REAL_STATE = (ROOT / ".saipen" / "STATE.md").read_text(encoding="utf-8-sig")

#: The exact form the valve writes, as `operations` writes it.
VALVE_WAIT = (
    'WAIT: safety valve reached (0 waves / 20 tickets) -- run \'cc\' to continue'
)
EMPTY_BOARD = "## DOING\n## TODO\n## DONE\n## BLOCKED\n"


def _seat(text, **fields):
    """Set lifecycle fields by grammar, never by assuming a live seat."""
    for key, value in fields.items():
        line = f"{key}: {value}"
        if re.search(rf"(?m)^{key}:.*$", text):
            text = re.sub(rf"(?m)^{key}:.*$", line, text)
        else:
            close = text.index("\n---", 3)
            text = text[:close] + "\n" + line + text[close:]
    return text


class PhaseShortcutKeepsAnEarnedWaitTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="t1880-wait-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        (self.root / ".saipen").mkdir()

    def _project(self, next_action):
        state = _seat(
            REAL_STATE,
            phase="DONE",
            task="none",
            next_action=f'"{next_action}"',
            blocker="none",
            transition_from="CLEAN",
            execution_intent="goal",
            goal_tickets=20,
            goal_waves=0,
        )
        (self.root / ".saipen" / "STATE.md").write_text(state, encoding="utf-8")
        (self.root / ".saipen" / "BOARD.md").write_text(EMPTY_BOARD, encoding="utf-8")
        (self.root / ".saipen" / "LOG.md").write_text(
            "- 24.10.26 00:00 [E-1] [agent: test] DEC: fixture\n", encoding="utf-8"
        )

    def _transition_to_hunt(self):
        result = operations.transition_phase(
            self.root, "HUNT", "test", ticket_id=None, event_text="", dry_run=False
        )
        self.assertTrue(
            result.ok,
            f"transition refused before the invariant could be observed: {result.to_dict()}",
        )
        return parse_state((self.root / ".saipen" / "STATE.md").read_text(encoding="utf-8"))

    def test_the_tripped_valve_wait_survives_the_phase_shortcut(self):
        """The measured defect: `hh` replaced the brake with `PHASE HUNT`."""
        self._project(VALVE_WAIT)
        state = self._transition_to_hunt()
        self.assertEqual(state.get("phase"), "HUNT")
        self.assertTrue(
            str(state.get("next_action") or "").startswith("WAIT:"),
            "the phase shortcut lifted the bounded safety-valve WAIT: "
            f"next_action is {state.get('next_action')!r}",
        )
        self.assertEqual(state.get("next_action"), VALVE_WAIT)

    def test_an_ordinary_transition_still_writes_the_destination_route(self):
        """The control: without a WAIT the phase move routes as it always did."""
        self._project("PHASE DONE")
        state = self._transition_to_hunt()
        self.assertEqual(state.get("phase"), "HUNT")
        self.assertEqual(state.get("next_action"), "PHASE HUNT")

    def test_a_plain_continue_is_not_treated_as_a_brake(self):
        """Only `WAIT:` is a hard stop; an ordinary route is not preserved."""
        self._project("saipen continue")
        state = self._transition_to_hunt()
        self.assertEqual(state.get("next_action"), "PHASE HUNT")


if __name__ == "__main__":
    unittest.main(verbosity=2)
