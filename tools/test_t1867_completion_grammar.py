"""T-1867: the canonical completion event stayed parseable when it grew.

T-1866 appended an `own_patch` publication decision to the SAME completion
event, turning a fixed string into a small grammar. The supersession ordering
proof matched that event with `fullmatch`, so every supersession route began
refusing with `SUPERSESSION_EVIDENCE_INVALID` -- and it did so SILENTLY: the
phrase it could no longer match was one it had already shipped, and nothing
compared the emitter to the readers.

These tests hold the two ends together. The accept cases are the events the
finish writer really emits; the refuse cases are the lookalikes an open grammar
would admit. If the release-route sentence is reworded in the writer, the
accept case goes red instead of the protocol going quiet.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import supersession  # noqa: E402
from saipen_engine.board import (  # noqa: E402
    PUBLICATION_RELEASE_ROUTE,
    PUBLICATION_STATES,
)


def _completion(publication: str = "") -> str:
    """The exact text `operations.finish_ticket` writes, for one closure.

    SHIP is the only phase it can close from -- the writer refuses anything
    else -- so the phase is a constant here rather than a parameter.
    """
    text = "ticket finished via SAIOPS -- completion (from SHIP)"
    if publication:
        text += f"; publication_state {publication}"
        if publication == "pending":
            text += "; " + PUBLICATION_RELEASE_ROUTE
    return text


class CompletionGrammarTests(unittest.TestCase):
    def test_every_emitted_completion_is_admitted(self) -> None:
        """The writer's output must satisfy the reader that proves ordering.

        `finish_ticket` refuses any phase other than SHIP, so `(from SHIP)` is
        the only phase the finish writer can emit; the variants here are the
        publication states it can append to that one form.
        """
        for publication in ("", *PUBLICATION_STATES):
            with self.subTest(publication=publication or "none"):
                text = _completion(publication)
                self.assertTrue(
                    supersession._COMPLETION_RE.fullmatch(text),
                    f"the finish writer emits this text but supersession "
                    f"refuses it: {text!r}",
                )

    def test_unsuffixed_completion_still_matches(self) -> None:
        """Old events and every non-own_patch closure keep their exact form."""
        self.assertTrue(
            supersession._COMPLETION_RE.fullmatch(
                "ticket finished via SAIOPS -- completion (from SHIP)"
            )
        )
        self.assertTrue(
            supersession._COMPLETION_RE.fullmatch("ticket finished via SAIOPS -- completion")
        )

    def test_lookalike_suffixes_are_refused(self) -> None:
        """The grammar is closed: plausible prose is not a publication record."""
        refusals = (
            # A state outside the owned vocabulary.
            "ticket finished via SAIOPS -- completion (from SHIP); publication_state shipped",
            # The right state with an invented route: prose cannot become a route.
            "ticket finished via SAIOPS -- completion (from SHIP); publication_state pending; "
            "release route: saipen ship, it will be fine",
            # A route with no state, so no reader can tell what is being routed.
            "ticket finished via SAIOPS -- completion (from SHIP); " + PUBLICATION_RELEASE_ROUTE,
            # The canonical text plus anything else appended behind it.
            "ticket finished via SAIOPS -- completion (from SHIP) -- and more",
            "ticket finished via SAIOPS -- completion (from SHIP); "
            "publication_state pending; " + PUBLICATION_RELEASE_ROUTE + "; and more",
            # The completion phrase must OPEN the event, not merely contain it.
            "NOTE: ticket finished via SAIOPS -- completion (from SHIP)",
            # An unknown closure phase is not this event.
            "ticket finished via SAIOPS -- completion (from NOWHERE)",
        )
        for text in refusals:
            with self.subTest(text=text[:60]):
                self.assertIsNone(
                    supersession._COMPLETION_RE.fullmatch(text),
                    f"an open grammar would let this read as a completion: {text!r}",
                )

    def test_control_the_pre_fix_matcher_fails_this_suite(self) -> None:
        """Red control: revert the grammar and the accept case must fail.

        The shipped T-1866 text is the input, and the pre-T-1867 pattern is the
        oracle. This is what makes the fix falsifiable: if the suffix were
        merely optional in a way that admitted nothing real, this control would
        still pass while the bug remained.
        """
        pre_fix = re.compile(
            r"^ticket finished via SAIOPS -- completion(?: \(from SHIP\))?$"
        )
        emitted = _completion("pending")
        self.assertIsNotNone(
            supersession._COMPLETION_RE.fullmatch(emitted),
            "precondition: the fixed grammar admits the emitted event",
        )
        self.assertIsNone(
            pre_fix.fullmatch(emitted),
            "the pre-fix matcher must reject the event the current writer emits, "
            "otherwise this control proves nothing",
        )

    def test_release_route_is_spelled_once(self) -> None:
        """The sentence the writer emits is the sentence the reader accepts."""
        source = (TOOLS / "saipen_engine" / "operations.py").read_text(encoding="utf-8")
        literal = PUBLICATION_RELEASE_ROUTE.split(" (")[0]
        self.assertEqual(
            source.count(literal),
            0,
            "operations.py re-spells the release-route sentence; it must import "
            "PUBLICATION_RELEASE_ROUTE so the writer and the matcher cannot drift",
        )


if __name__ == "__main__":
    unittest.main()
