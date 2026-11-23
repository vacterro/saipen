"""T-923: an INVALID role snapshot must not take the crew fixed point down.

`sensor_executed` concatenated a role snapshot's `board.errors` with its
`outbox.errors` assuming both were lists. A role BOARD whose parse yields a
tuple (seen live when a role BOARD put a checkbox row under `## BLOCKED`)
made that `tuple + list` a TypeError, so the whole fixed point crashed instead
of reporting the invalid role evidence it had already detected.

Held here: the invalid-evidence reason is built for every container shape the
two error sources can arrive as, and it still names both sources.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import crew  # noqa: E402
from saipen_engine.subs import HEALTH_INVALID  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


def _invalid_role(board_errors, outbox_errors):
    role = SimpleNamespace(name="saihunt")
    snapshot = SimpleNamespace(
        roles={
            "saihunt": {
                "health": HEALTH_INVALID,
                "board": {"errors": board_errors},
                "outbox": {"errors": outbox_errors},
            }
        }
    )
    return snapshot, role


class InvalidRoleEvidence(unittest.TestCase):
    def test_tuple_board_errors_do_not_crash_the_fixed_point(self):
        snapshot, role = _invalid_role(("checkbox row under ## BLOCKED",), ["outbox problem"])
        ok, reason = crew._sensor_executed(snapshot, role)
        self.assertFalse(ok)
        self.assertIn("checkbox row under ## BLOCKED", reason)
        self.assertIn("outbox problem", reason)

    def test_both_sources_as_lists_still_work(self):
        snapshot, role = _invalid_role(["board problem"], ["outbox problem"])
        ok, reason = crew._sensor_executed(snapshot, role)
        self.assertFalse(ok)
        self.assertIn("board problem", reason)
        self.assertIn("outbox problem", reason)

    def test_tuple_outbox_errors_do_not_crash_the_fixed_point(self):
        snapshot, role = _invalid_role(["board problem"], ("outbox problem",))
        ok, reason = crew._sensor_executed(snapshot, role)
        self.assertFalse(ok)
        self.assertIn("outbox problem", reason)

    def test_missing_error_keys_report_the_invalid_evidence_without_errors(self):
        snapshot, role = _invalid_role(None, None)
        ok, reason = crew._sensor_executed(snapshot, role)
        self.assertFalse(ok)
        self.assertIn("invalid role evidence", reason)


if __name__ == "__main__":
    unittest.main()
