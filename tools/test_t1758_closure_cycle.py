"""T-1758: a note logged after a ticket finished never re-judges its closure.

The closure-evidence classifiers read the newest decisive RUN of a ticket's
newest VERIFY cycle, and that cycle ran to the end of the history. On this
repository T-1695 finished with a review PASS conf: high (E-14040); two minutes
later a checkpoint tagged with it recorded a continuation boundary in words the
failure grammar reads as a claim (E-14046), and `validate.py --gate core` has
FAILed closure-evidence on DONE T-1695 ever since. The same rule is the
recorded trap where a later RUN with FAIL tokens made `ship` refuse.

The cycle now ends with the ticket's canonical finish. A reopened ticket that
is verified again is judged by its new cycle.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.log import bulk_verification_evidence, verification_evidence  # noqa: E402

T = "T-1695"


def _op(kind: str, n: int) -> str:
    return f"{kind}-{n:032x}"


def _ev(n: int, taxonomy: str, text: str, op: str, ticket: str = T) -> dict:
    return {"event": n, "ticket": ticket, "taxonomy": taxonomy, "text": text, "op_id": op}


#: The measured shape: E-14040..E-14046 of this repository's LOG, abridged.
FINISHED = [
    _ev(
        1,
        "RUN",
        "transition to VERIFY -- regression pair, declared family",
        _op("transition", 1),
    ),
    _ev(2, "RUN", "verify -> PASS conf: high -- pair red then green", _op("checkpoint", 2)),
    _ev(3, "RUN", "transition to REVIEW -- independent rerun", _op("transition", 3)),
    _ev(
        4,
        "RUN",
        "review -> PASS [target: T-1695] conf: high -- independent pair",
        _op("checkpoint", 4),
    ),
    _ev(5, "RUN", "transition to SHIP -- local finish", _op("transition", 5)),
    _ev(6, "RUN", "ship v8.1.0 -> skipped publish (no-publish: policy)", _op("finish", 6)),
    _ev(7, "DEC", "ticket finished via SAIOPS -- completion (from SHIP)", _op("finish", 6)),
]
#: E-14046, verbatim in its decisive part.
AFTER = _ev(
    8,
    "RUN",
    "Continuation boundary after E-14044/E-14045 local finish: continue returned "
    "audit-inbox-unworkable RESTATE_AND_STOP; audit/23 remains ACTIVE SRC-167/T-1606 "
    "at VERIFY_RETRY_CAP. All 62 parked ticket bytes, 15 failed candidates and "
    "inherited Git index unchanged.",
    _op("checkpoint", 8),
)


def both(events: list[dict]) -> tuple[bool, bool]:
    return verification_evidence(T, events)[0], bulk_verification_evidence(events, [T])[T][0]


class ClosureCycleTests(unittest.TestCase):
    def test_the_measured_post_finish_note_reads_as_a_failure_claim(self):
        """Control: the note does carry a failure claim, so only the cycle can save it."""
        self.assertEqual(both([*FINISHED[:1], AFTER]), (False, False))

    def test_a_note_after_the_finish_does_not_re_judge_the_closure(self):
        self.assertEqual(both([*FINISHED, AFTER]), (True, True))

    def test_a_failure_inside_the_cycle_still_wins(self):
        failed = [
            *FINISHED[:4],
            _ev(41, "RUN", "verify -> FAIL: 3 FAIL in the family", _op("checkpoint", 41)),
            *FINISHED[4:],
            AFTER,
        ]
        self.assertEqual(both(failed), (False, False))

    def test_a_reopened_ticket_is_judged_by_its_new_cycle(self):
        reopened = [
            *FINISHED,
            AFTER,
            _ev(9, "RUN", "transition to VERIFY -- reopened", _op("transition", 9)),
            _ev(10, "RUN", "verify -> FAIL: 2 FAIL after the reopen", _op("checkpoint", 10)),
        ]
        self.assertEqual(both(reopened), (False, False))

    def test_a_hand_typed_finish_does_not_close_the_cycle(self):
        forged = [
            *FINISHED[:6],
            _ev(7, "DEC", "ticket finished via SAIOPS -- typed", "finish-typed"),
            AFTER,
        ]
        self.assertEqual(both(forged), (False, False))

    def test_another_tickets_finish_does_not_close_this_cycle(self):
        other = [
            *FINISHED[:6],
            _ev(
                7,
                "DEC",
                "ticket finished via SAIOPS -- completion",
                _op("finish", 7),
                ticket="T-1",
            ),
            AFTER,
        ]
        self.assertEqual(both(other), (False, False))


if __name__ == "__main__":
    unittest.main()
