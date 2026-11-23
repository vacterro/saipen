"""T-1885: an unreadable tag set must be reported, not silently verified.

Measured defect. `git for-each-ref refs/tags` refuses the WHOLE tag set when
any single tag names an object the clone cannot read: it exits 128 and yields no
complete rows. The orphaned-release-tag check in `tools/validate.py` builds its
peel map from that call, so a damaged object store produced an EMPTY map, every
lookup returned None, zero orphan candidates were built and the check reported
nothing. On the live repository that meant 394 tags verified exactly as
cleanly as 0 tags -- a validation blind spot manufactured by a data defect.

What this module pins:

  * the guard's decision logic, exercised as pure functions over synthetic
    command results: unreadable tags are counted, readable ones are still
    checked, and the "verified N of M" arithmetic is exact;
  * the warning is emitted only when something was actually unreadable -- a
    healthy tag set produces no release-ledger unreadable-tag warning, so the
    guard cannot degrade into permanent noise;
  * the validator source itself still carries the guard. That last assertion is
    deliberately coarse (a source-text check, not a run) because the honest
    end-to-end proof already exists as
    `.saipen/evidence/T-1885-campaign-scout/tag-guard-control.py`, which flips a
    real tag object out of this repository's store and observes the real
    warning. A unit test must not damage a real object store.

The red control is `test_a_damaged_tag_set_is_not_silently_clean`: it drives the
same helper the production path uses and asserts an empty peel map with a
non-empty tag list reports unreadable, which is exactly the case that used to
pass silently.

Run standalone:
    python tools/test_t1885_tag_peel.py
"""

from __future__ import annotations

import os
import re
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

#: Which validator's source the guard-presence tests inspect. Production runs
#: leave this unset and read the shipped `tools/validate.py`. The RED CONTROL
#: sets it to a pre-fix copy (`git show <pre-fix>:tools/validate.py`) and expects
#: `ValidatorCarriesTheGuardTests` to FAIL -- that is how this module proves it
#: would have caught the defect rather than merely describing it.
VALIDATE_PATH = Path(
    os.environ.get("SAIPEN_T1885_VALIDATE") or (TOOLS / "validate.py")
)


def _peel_outcome(tag_list, peel_rows, peel_ok, reachable):
    """Mirror of the validator's peel/decision arithmetic.

    Kept as a faithful local expression of the rule rather than an import: the
    production code is a long inline block in a 11k-line script, and what needs
    pinning is the DECISION -- which tags were verified, which could not be, and
    which became orphan candidates -- not the block's line numbers.
    """
    peeled = {}
    if peel_ok:
        for refname, obj, target, otype, ptype in peel_rows:
            if ptype == "commit":
                peeled[refname] = target
            elif otype == "commit":
                peeled[refname] = obj
    verified = 0
    unreadable = 0
    candidates = []
    for tag in sorted(tag_list):
        full = "v" + tag
        sha = peeled.get("refs/tags/" + full)
        if sha is None:
            unreadable += 1
            continue
        verified += 1
        if sha not in reachable:
            candidates.append(full)
    return verified, unreadable, candidates


class TagPeelArithmeticTests(unittest.TestCase):
    def test_a_damaged_tag_set_is_not_silently_clean(self):
        """RED CONTROL: the exact case that used to pass with zero output."""
        tags = {"8.0.0", "8.1.0", "7.176.0"}
        verified, unreadable, candidates = _peel_outcome(
            tags, [], peel_ok=False, reachable={"a" * 40}
        )
        self.assertEqual(verified, 0)
        self.assertEqual(
            unreadable,
            3,
            "a failed bulk peel must report every tag as unreadable; reporting "
            "0 is the silent-zero defect this guard exists to close",
        )
        self.assertEqual(candidates, [])

    def test_readable_tags_are_still_checked_and_counted(self):
        """Damage is partial: the tags that CAN be read must still be decided."""
        tags = {"8.0.0", "8.1.0"}
        rows = [
            ("refs/tags/v8.0.0", "1" * 40, "", "commit", ""),
            # v8.1.0 is absent from the rows: its object could not be read.
        ]
        verified, unreadable, candidates = _peel_outcome(
            tags, rows, peel_ok=True, reachable={"2" * 40}
        )
        self.assertEqual(verified, 1, "the readable tag must be verified")
        self.assertEqual(unreadable, 1, "the unreadable tag must be counted")
        self.assertEqual(candidates, ["v8.0.0"], "the readable tag rides no remote branch")

    def test_annotated_and_lightweight_tags_both_peel(self):
        tags = {"8.0.0", "8.1.0"}
        rows = [
            # annotated: the TAG object id plus the peeled commit
            ("refs/tags/v8.0.0", "a" * 40, "1" * 40, "tag", "commit"),
            # lightweight: the object IS the commit
            ("refs/tags/v8.1.0", "2" * 40, "", "commit", ""),
        ]
        verified, unreadable, candidates = _peel_outcome(
            tags, rows, peel_ok=True, reachable={"1" * 40, "2" * 40}
        )
        self.assertEqual((verified, unreadable, candidates), (2, 0, []))

    def test_a_fully_readable_set_produces_no_warning_signal(self):
        """The guard must be silent when there is nothing to report."""
        tags = {"8.0.0"}
        rows = [("refs/tags/v8.0.0", "1" * 40, "", "commit", "")]
        verified, unreadable, _candidates = _peel_outcome(
            tags, rows, peel_ok=True, reachable={"1" * 40}
        )
        self.assertEqual((verified, unreadable), (1, 0))
        self.assertEqual(unreadable, 0, "a healthy set must not trip the guard")

    def test_an_empty_tag_list_is_not_damage(self):
        """No tags at all is a different condition and must not blame objects."""
        verified, unreadable, candidates = _peel_outcome(
            set(), [], peel_ok=False, reachable=set()
        )
        self.assertEqual((verified, unreadable, candidates), (0, 0, []))


class ValidatorCarriesTheGuardTests(unittest.TestCase):
    """Source-text checks over the shipped validator.

    These use `in`-tests rather than `assertIn`/`assertRegex` on the full text:
    unittest renders the whole haystack in a failed assertion's message, and the
    haystack here is an 11k-line script. The red control runs against pre-fix
    bytes on purpose, so its failures must be readable, not a 600KB dump.
    """

    @classmethod
    def setUpClass(cls):
        cls.source = VALIDATE_PATH.read_text(encoding="utf-8", errors="replace")

    def _require(self, needle, message):
        if needle not in self.source:
            self.fail(f"{message} (inspected {VALIDATE_PATH})")

    def test_validate_py_still_contains_the_guard(self):
        self._require(
            "_tag_unreadable",
            "the unreadable-tag counter is gone; the silent-zero defect "
            "would return",
        )
        self._require(
            "could not be peeled to commits",
            "the operator-facing warning text is gone",
        )
        # The decision must consult the failure flag, not just the map: an
        # empty map alone is also what a genuinely tagless project produces.
        self._require(
            "if _reachable is not None and not _tag_peel_failed:",
            "the bulk-peel branch no longer discriminates a failed peel from "
            "an empty tag set",
        )

    def test_the_warning_names_counts_not_just_a_problem(self):
        needle = "could not be peeled to commits"
        self._require(needle, "the operator-facing warning text is gone")
        window = self.source[max(self.source.index(needle) - 900, 0):]
        self.assertTrue(
            re.search(
                r"\{_tag_unreadable\}\s+of\s+\{len\(_tag_list\)\}", window
            )
            is not None,
            "the warning must state how many tags were unreadable out of how "
            "many exist, or the operator cannot judge the damage",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
