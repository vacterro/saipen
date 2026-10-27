"""T-1782: the producer check matches the capped builder, not its substring.

T-1326's structural check refused every engine line containing the text
`build_event`, so a helper that only READS LOG events,
`operations.no_delta_build_events`, turned the declared family red for every
ticket (core-unit record 8233b36d6d193077). The check's intent is a direct
reach of the capped builder `log.build_event`; these cases pin both directions
of that intent through the matcher the check itself uses.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from test_t1326_board_compaction import capped_builder_offenders  # noqa: E402


class CappedBuilderIdentifier(unittest.TestCase):
    def test_a_name_that_contains_the_builder_is_not_a_reach(self):
        source = (
            "def no_delta_build_events(ticket_id, events):\n"
            "    return no_delta_build_events(ticket_id, events)\n"
            "rebuild_event_index = {}\n"
            "build_events = []\n"
            "self.prebuild_event()\n"
        )
        self.assertEqual(capped_builder_offenders("m.py", source), [])

    def test_every_direct_reach_is_still_an_offender(self):
        source = (
            "from .log import build_event\n"
            "line = log.build_event(event)\n"
            "make = build_event\n"
            "build_event(\n"
        )
        self.assertEqual(
            capped_builder_offenders("m.py", source),
            [
                "m.py:1: from .log import build_event",
                "m.py:2: line = log.build_event(event)",
                "m.py:3: make = build_event",
                "m.py:4: build_event(",
            ],
        )

    def test_a_comment_is_not_a_reach(self):
        source = "x = 1  # the raw `build_event` raises\n# build_event(\n"
        self.assertEqual(capped_builder_offenders("m.py", source), [])


if __name__ == "__main__":
    unittest.main()
