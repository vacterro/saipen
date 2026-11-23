"""Add the status automation-block case to the T-1776 module (review finding).

    python apply_t1776_test.py <path to test_t1776_protocol_home_valve.py>

The mutation controls showed the automation block's SRC-249 branch had no
test: turning it off left every case green. The anchor is asserted once.
"""

from __future__ import annotations

import sys
from pathlib import Path

ANCHOR = '\n\nif __name__ == "__main__":\n'

CASE = '''
    def test_status_automation_block_continues_through_the_home_valve(self):
        from saipen_engine import automation
        from saipen_engine.board import parse_board
        from saipen_engine.router import route_next

        def block(proj: Path) -> dict:
            state_text = codec.read_doc(proj / ".saipen" / "STATE.md")
            board_text = codec.read_doc(proj / ".saipen" / "BOARD.md")
            return automation.automation_block(
                proj,
                state=state.parse_state(state_text),
                board=parse_board(board_text),
                routed=route_next(state_text, board_text),
                agent="aleks",
            )

        home = block(self._tripped_goal("protocol", HOME_LINEAGE))
        self.assertEqual(
            (home["disposition"], home["reason_code"], home["next_command"]),
            (automation.CONTINUE, "wait-safety-valve", "cc"),
            home,
        )
        self.assertFalse(home["operator_action_due"])
        consumer = block(self._tripped_goal("consumer", OTHER_LINEAGE))
        self.assertEqual(consumer["disposition"], automation.WAIT_USER, consumer)
        self.assertTrue(consumer["operator_action_due"])
'''


def main(path: str) -> int:
    target = Path(path)
    raw = target.read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8").replace("\r\n", "\n")
    if text.count(ANCHOR) != 1:
        raise SystemExit("anchor not unique")
    if "test_status_automation_block_continues_through_the_home_valve" in text:
        raise SystemExit("already applied")
    text = text.replace(ANCHOR, "\n" + CASE + ANCHOR)
    target.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
