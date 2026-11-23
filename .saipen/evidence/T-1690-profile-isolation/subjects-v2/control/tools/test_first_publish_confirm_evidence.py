"""First-publish confirmation must rest on a journaled gate, not on prose (T-185).

`STATE.next_action` is a free-text field. Before T-185, `first-publish-confirm`
accepted it as the sole proof that a first-publish gate had fired, so any writer
of that field -- a hand edit, or a reconcile op -- could satisfy the precondition
with a line that merely *looks* canonical (proved live by T-184, where a
hand-written `WAIT: first-publish -- ...` line stood in for a gate the release
engine never ran).

The fix adds `_first_publish_wait_journaled`, which requires a real LOG event
with taxonomy `WAIT` whose text starts `first-publish --` -- the exact shape
`_plan_first_publish_wait` emits. These tests pin the boundary:

  1. the engine's own WAIT event satisfies the gate;
  2. prose-only (no journaled event) does NOT;
  3. a non-parsable / unrelated event does NOT;
  4. a WAIT event for some *other* reason does NOT (the marker is scoped, so a
     generic `WAIT: safety valve reached` cannot stand in for a publish gate).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.log import HistorySnapshot  # noqa: E402
from saipen_engine.operations import _first_publish_wait_journaled  # noqa: E402


def _snapshot(*event_lines: str) -> HistorySnapshot:
    return HistorySnapshot(
        hash="h", text="", tail=len(event_lines) or None, events=(), event_lines=tuple(event_lines)
    )


#: Exactly what `_plan_first_publish_wait` writes.
ENGINE_WAIT_EVENT = (
    "- 03.10.26 01:00 [E-1] [parent: E-0] [T-179] [agent: saipen-cli] [op: wait-abc123] "
    "WAIT: first-publish -- confirm repo name '<origin>' and public/private before I push"
)

#: A hand-written line that borrows the canonical prefix but has no journaled event.
PROSE_ONLY = (
    "- 03.10.26 01:00 [E-9] [parent: E-8] [T-179] [agent: saipen-cli] [op: reconcile-xyz] "
    "DEC: reconcile protocol state -- blocker 'OPERATOR_REQUIRED'->'none'"
)


class FirstPublishConfirmEvidence(unittest.TestCase):
    def test_the_engines_own_wait_event_satisfies_the_gate(self) -> None:
        self.assertTrue(_first_publish_wait_journaled({"_history": _snapshot(ENGINE_WAIT_EVENT)}))

    def test_prose_without_a_journaled_event_does_not_satisfy_the_gate(self) -> None:
        # This is the T-184 forgery: STATE.next_action said WAIT: first-publish,
        # but nothing journaled a WAIT event. Must NOT be accepted.
        self.assertFalse(_first_publish_wait_journaled({"_history": _snapshot(PROSE_ONLY)}))

    def test_no_history_at_all_does_not_satisfy_the_gate(self) -> None:
        self.assertFalse(_first_publish_wait_journaled({"_history": _snapshot()}))

    def test_a_wait_for_another_reason_does_not_stand_in_for_a_publish_gate(self) -> None:
        other_wait = (
            "- 03.10.26 01:00 [E-2] [parent: E-1] [agent: saipen-cli] [op: wait-def456] "
            "WAIT: safety valve reached (3 waves / 12)"
        )
        self.assertFalse(_first_publish_wait_journaled({"_history": _snapshot(other_wait)}))

    def test_an_unparsable_line_does_not_satisfy_the_gate(self) -> None:
        # A line that is not a legal event cannot be a journaled WAIT, even if
        # its text happens to carry the marker.
        forged = "first-publish -- confirm repo name 'evil' and public/private before I push"
        self.assertFalse(_first_publish_wait_journaled({"_history": _snapshot(forged)}))

    def test_the_marker_must_be_at_the_start_of_the_event_text(self) -> None:
        # The engine writes the marker first; a mention buried mid-text is a
        # different event and must not count.
        buried = (
            "- 03.10.26 01:00 [E-3] [parent: E-1] [agent: saipen-cli] [op: note-1] "
            "WAIT: unrelated note mentioning first-publish -- only in passing"
        )
        self.assertFalse(_first_publish_wait_journaled({"_history": _snapshot(buried)}))


if __name__ == "__main__":
    unittest.main()
