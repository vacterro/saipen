"""T-150: legacy DONE execution proof must come from the ticket's OWN generation.

RED CONTROL. `bulk_legacy_completion_evidence` scans history newest-first and
lets the first decisive ticket-scoped RUN win. A RUN written AFTER the legacy
generation closed carries the old ticket's id, so it was decisive even though it
says nothing about the grammar that ticket actually executed under. Two failure
modes, both measured on a real project (SAIPAL, T-016):

  - a progress note containing none of the execution markers reported
    `unproven` and raised `legacy-done-review` over a closure that had been
    settled for weeks;
  - a later note that happened to contain the token VERIFY reported `proven`.

So the verdict tracked the vocabulary of the most recent sentence attached to
the id rather than the history. `generation_end` bounds the RUN scan to the
legacy generation; an operator attestation stays exempt, because it is a
deliberate decision recorded now.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = str(Path(__file__).resolve().parent)
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

from saipen_engine.log import bulk_legacy_completion_evidence  # noqa: E402

FRONTIER = 59
LEGACY = "T-016"


def _ev(ticket: str | None, text: str, taxonomy: str = "RUN") -> dict:
    return {"ticket": ticket, "text": text, "taxonomy": taxonomy}


class LegacyGenerationEvidenceBoundary(unittest.TestCase):
    def _events(self, later: dict) -> list[dict]:
        # The legacy generation closes here; T-016's own RUN carries a marker.
        legacy_run = _ev(LEGACY, "BUILD the runtime hardening surface and SHIP it")
        after = _ev(f"T-{FRONTIER + 1}", "the closure contract became observable")
        return [legacy_run, after, later]

    def _decide(self, later: dict) -> bool:
        verdicts = bulk_legacy_completion_evidence(
            self._events(later), [LEGACY], generation_end=FRONTIER
        )
        return verdicts[LEGACY][0]

    def test_the_tickets_own_generation_still_proves_it(self):
        """The T-150 baseline: this path already worked and must keep working."""
        later = _ev(LEGACY, "unrelated bookkeeping with no execution marker")
        self.assertTrue(self._decide(later))

    def test_a_later_note_without_a_marker_cannot_unprove_it(self):
        """The defect: incidental vocabulary decided a settled closure."""
        self.assertTrue(self._decide(_ev(LEGACY, "progress note, no markers here")))

    def test_a_later_note_cannot_manufacture_proof_either(self):
        """Symmetry: the later prose must not be able to grant proof."""
        legacy_run = _ev(LEGACY, "churning on the problem, no execution recorded")
        events = [
            legacy_run,
            _ev(f"T-{FRONTIER + 1}", "the closure contract became observable"),
            _ev(LEGACY, "verify -> PASS, says VERIFY and PASS in passing"),
        ]
        verdicts = bulk_legacy_completion_evidence(
            events, [LEGACY], generation_end=FRONTIER
        )
        self.assertFalse(verdicts[LEGACY][0])

    def test_a_later_failure_claim_cannot_condemn_it(self):
        """A present-tense complaint about today's run is not evidence about 2019."""
        legacy_run = _ev(LEGACY, "BUILD and VERIFY the runtime hardening surface")
        events = [
            legacy_run,
            _ev(f"T-{FRONTIER + 1}", "the closure contract became observable"),
            _ev(LEGACY, "the suite is failing now, 3 of 9 checks red. FAILURES: 3 of 9"),
        ]
        verdicts = bulk_legacy_completion_evidence(
            events, [LEGACY], generation_end=FRONTIER
        )
        self.assertTrue(verdicts[LEGACY][0])

    def test_an_operator_attestation_still_wins_after_the_boundary(self):
        """The sanctioned exit must keep working; it is a decision, not history."""
        self.assertTrue(
            self._decide(_ev(LEGACY, "legacy completion attested for T-016 -- operator decision"))
        )

    def test_without_a_boundary_the_old_behaviour_is_unchanged(self):
        """Callers that pass no boundary keep the original whole-history scan."""
        events = [_ev(LEGACY, "no marker anywhere in the legacy record")]
        before = bulk_legacy_completion_evidence(events, [LEGACY])
        self.assertFalse(before[LEGACY][0])


if __name__ == "__main__":
    unittest.main()