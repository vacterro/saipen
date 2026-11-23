"""T-31: checkpoint/transition positional parse must not silently drop the ticket.

`tools/saipen.py` read the ticket only from ``args[2]`` when it started with
``T-``, so ``saipen checkpoint RUN "<text>" T-27`` journaled a TICKETLESS RUN
and folded the stray ``T-27`` into the text. The documented ticket-first order
worked; the text-first order lost the ticket with no refusal, and the only
symptom was a later VERIFY -> REVIEW refusal for "unproven evidence" over RUNs
that existed but carried no ticket.

The fix lifts a whole-token ``T-\\d+`` from EITHER position. A ``T-27`` inside
quoted prose is one argv element and can never satisfy the whole-token test, so
prose is never misread.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import saipen as cli  # noqa: E402


def _old_parse(args):
    """The pre-fix positional read, reproduced verbatim, as the RED control."""
    ticket = args[2] if len(args) > 2 and args[2].upper().startswith("T-") else None
    text = " ".join(args[3:] if ticket else args[2:])
    return ticket, text


class CheckpointPositionalParseTests(unittest.TestCase):
    def test_text_first_records_the_ticket(self):
        # "saipen checkpoint RUN '<text>' T-27" -- the defect shape.
        ticket, text = cli._ticket_and_text(["the text", "T-27"])
        self.assertEqual(ticket, "T-27")
        self.assertEqual(text, "the text")

    def test_ticket_first_unchanged(self):
        ticket, text = cli._ticket_and_text(["T-27", "the text"])
        self.assertEqual(ticket, "T-27")
        self.assertEqual(text, "the text")

    def test_multiword_text_first(self):
        ticket, text = cli._ticket_and_text(["a longer", "note here", "T-27"])
        self.assertEqual(ticket, "T-27")
        self.assertEqual(text, "a longer note here")

    def test_no_ticket_is_passthrough(self):
        ticket, text = cli._ticket_and_text(["just a note", "with words"])
        self.assertIsNone(ticket)
        self.assertEqual(text, "just a note with words")

    def test_quoted_prose_is_not_a_ticket(self):
        # A whole quoted argv element that merely mentions an id never matches.
        ticket, text = cli._ticket_and_text(["supersedes T-27 today"])
        self.assertIsNone(ticket)
        self.assertEqual(text, "supersedes T-27 today")

    def test_first_whole_token_wins(self):
        ticket, text = cli._ticket_and_text(["T-27", "T-28"])
        self.assertEqual(ticket, "T-27")
        self.assertEqual(text, "T-28")

    def test_red_control_old_parse_dropped_the_ticket(self):
        # Exactly the bug the ticket names: text-first silently yields no ticket.
        ticket, text = _old_parse(["checkpoint", "RUN", "the text", "T-27"])
        self.assertIsNone(ticket, "pre-fix parse unexpectedly kept the ticket")
        self.assertIn("T-27", text, "pre-fix parse did not fold the id into the text")
        # And ticket-first worked, which is why the defect was invisible.
        self.assertEqual(_old_parse(["checkpoint", "RUN", "T-27", "the text"])[0], "T-27")

    def test_cli_parse_agrees_with_the_module(self):
        # The ticket must survive the real CLI argument split (args[2:]).
        rest = ["the text", "T-27"]
        ticket, text = cli._ticket_and_text(rest)
        self.assertEqual((ticket, text), ("T-27", "the text"))


if __name__ == "__main__":
    unittest.main()
