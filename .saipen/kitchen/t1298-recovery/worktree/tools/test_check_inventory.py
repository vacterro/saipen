"""T-1292: the KNOWLEDGE structured-surface check gets a permanent control.

`tools/validate.py`'s KNOWLEDGE card/index check landed in v7.254.0 proven by a
hand transcript: the gate was driven red twice and restored, and none of that
survived the session. `tools/audit_checks.py` CASES is hand-maintained and
nothing bound it to the validator, so the closing sweep line read the same
total before the check landed and after it landed -- the one sentence a
checkpoint quotes as proof the control ledger is intact did not move when a
check arrived uncovered.

Proven here:
- both failure classes of that check have a CASE, and the sweep total grew;
- each mutation drives the real `validate_knowledge` red on its own condition
  and the SAME verifier returns green once the mutation is restored;
- the check-inventory tripwire agrees with the live validator, sees an added
  fail site (its red control), and names what a count cannot prove.

Run standalone:
    python tools/test_check_inventory.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import audit_checks as A  # noqa: E402
from saipen_engine.knowledge import validate_knowledge, write_index  # noqa: E402

KNOWLEDGE_CASES = (
    ("a KNOWLEDGE card declares a kind outside the closed set", "invalid kind"),
    ("a changed KNOWLEDGE card leaves the index projection stale", "INDEX.md is stale"),
)


def case_by_label(label: str):
    matches = [case for case in A.CASES if case[0] == label]
    if len(matches) != 1:
        raise AssertionError(f"expected exactly one CASE named {label!r}, found {len(matches)}")
    return A.case_parts(matches[0])


class CasePresenceTests(unittest.TestCase):
    """AC-01 -- the check has controls and the denominator grew to match."""

    def test_both_failure_classes_have_a_case(self) -> None:
        for label, expected in KNOWLEDGE_CASES:
            _, rel, _, declared_expected, gate = case_by_label(label)
            self.assertEqual(rel, A.KNOWLEDGE_CARD, label)
            self.assertEqual(declared_expected, expected, label)
            self.assertIsNone(gate, label)

    def test_the_two_cases_are_not_one_condition_twice(self) -> None:
        first = case_by_label(KNOWLEDGE_CASES[0][0])
        second = case_by_label(KNOWLEDGE_CASES[1][0])
        self.assertNotEqual(first[3], second[3])

    def test_the_sweep_total_counts_them(self) -> None:
        self.assertEqual(A.FULL_CASE_COUNT, len(A.CASES))
        labels = {case[0] for case in A.CASES}
        for label, _ in KNOWLEDGE_CASES:
            self.assertIn(label, labels)

    def test_the_card_target_selects_exactly_these_controls(self) -> None:
        changed = A.scoped_paths(["--changed", A.KNOWLEDGE_CARD])
        selected = {case[0] for case in A.select_cases(A.CASES, changed)}
        self.assertEqual(selected, {label for label, _ in KNOWLEDGE_CASES})

    def test_the_mutated_card_is_a_real_tracked_file(self) -> None:
        self.assertTrue((ROOT / A.KNOWLEDGE_CARD).is_file())
        self.assertTrue(A.case_available(ROOT, A.KNOWLEDGE_CARD, case_by_label(
            KNOWLEDGE_CASES[0][0]
        )[2]))


class MutationEfficacyTests(unittest.TestCase):
    """AC-02 -- red on its own condition, green again once restored.

    The verifier is held fixed across both halves: the same
    `validate_knowledge` call, over the same fixture, with only the card's
    bytes moving. Driving the whole CLI validator is what `audit_checks.py`
    does; repeating that here would buy a slower copy of the same proof.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-check-inventory-")
        self.root = Path(self.tmp.name) / "project"
        cards = self.root / ".saipen" / "KNOWLEDGE" / "cards"
        cards.mkdir(parents=True)
        self.card = cards / Path(A.KNOWLEDGE_CARD).name
        shutil.copyfile(ROOT / A.KNOWLEDGE_CARD, self.card)
        self.assertTrue(write_index(self.root)["ok"])
        self.original = self.card.read_bytes()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def errors(self) -> str:
        return " ".join(validate_knowledge(self.root)["errors"])

    def test_the_fixture_starts_green(self) -> None:
        result = validate_knowledge(self.root)
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["index"], "fresh")

    def test_each_mutation_goes_red_then_green_again(self) -> None:
        for label, expected in KNOWLEDGE_CASES:
            _, _, mutation, _, _ = case_by_label(label)
            with self.subTest(label):
                text = self.card.read_text(encoding="utf-8")
                mutated = mutation(text)
                self.assertNotEqual(mutated, text, "mutation is a no-op")
                self.card.write_text(mutated, encoding="utf-8", newline="\n")
                self.assertIn(expected, self.errors(), label)

                self.card.write_bytes(self.original)
                self.assertEqual(validate_knowledge(self.root)["errors"], [], label)

    def test_neither_expected_string_is_printed_by_the_clean_fixture(self) -> None:
        # An expectation the unmutated subject already satisfies is not evidence.
        clean = self.errors()
        for _, expected in KNOWLEDGE_CASES:
            self.assertNotIn(expected, clean)

    def test_the_stale_mutation_does_not_rely_on_prose_wording(self) -> None:
        # An anchor inside the card's claim would silently no-op the day the
        # prose is rewritten; this mutation appends instead.
        _, _, mutation, _, _ = case_by_label(KNOWLEDGE_CASES[1][0])
        self.assertIsNone(getattr(mutation, "anchor", None))
        rewritten = "---\nkind: convention\n---\n\nEvery word of this card was rewritten.\n"
        self.assertNotEqual(mutation(rewritten), rewritten)


class CheckInventoryTripwireTests(unittest.TestCase):
    """AC-03/AC-04 -- the binding, its red control, and its stated bound."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-fail-sites-")
        self.workdir = Path(self.tmp.name)
        self.source = (ROOT / "tools" / "validate.py").read_text(encoding="utf-8-sig")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def fake_root(self, source: str) -> Path:
        root = self.workdir / "fake-root"
        (root / "tools").mkdir(parents=True, exist_ok=True)
        (root / "tools" / "validate.py").write_text(source, encoding="utf-8", newline="\n")
        return root

    def test_the_recorded_count_matches_the_live_validator(self) -> None:
        self.assertEqual(A.count_fail_sites(self.source), A.VALIDATOR_FAIL_SITES)

    def test_the_probe_passes_on_the_real_repository(self) -> None:
        self.assertIsNone(A.check_inventory_probe(ROOT, self.workdir))

    def test_an_added_fail_site_is_detected(self) -> None:
        root = self.fake_root(A.add_fail_site(self.source))
        error = A.check_inventory_probe(root, self.workdir)
        self.assertIsNotNone(error, "a new uncovered check went unnoticed")
        self.assertIn("grew to", error)
        self.assertIn(str(A.VALIDATOR_FAIL_SITES + 1), error)

    def test_a_removed_fail_site_is_detected_too(self) -> None:
        # The other direction: a deleted check leaves a CASE testing nothing.
        trimmed = self.source.replace('fail("', 'ok("', 1)
        self.assertNotEqual(trimmed, self.source)
        error = A.check_inventory_probe(self.fake_root(trimmed), self.workdir)
        self.assertIsNotNone(error)
        self.assertIn("shrank to", error)

    def test_the_failure_names_the_remedy(self) -> None:
        error = A.check_inventory_probe(self.fake_root(A.add_fail_site(self.source)), self.workdir)
        self.assertIn("VALIDATOR_FAIL_SITES", error)
        self.assertIn("CASE", error)

    def test_an_unparsable_validator_is_reported_not_counted(self) -> None:
        error = A.check_inventory_probe(self.fake_root("def broken(:\n"), self.workdir)
        self.assertIsNotNone(error)
        self.assertIn("does not parse", error)

    def test_the_probe_leaves_no_directory_behind(self) -> None:
        before = sorted(p.name for p in self.workdir.iterdir())
        A.check_inventory_probe(ROOT, self.workdir)
        self.assertEqual(sorted(p.name for p in self.workdir.iterdir()), before)

    def test_the_bound_is_stated_rather_than_trusted(self) -> None:
        text = A.CHECK_INVENTORY_LIMITATION.lower()
        self.assertIn("never", text)
        self.assertIn("which", text)
        self.assertIn("not detected", text)

    def test_the_named_blind_spot_is_the_real_one(self) -> None:
        # Add one fail site and remove another: the count is unchanged, so the
        # tripwire passes. That is the limitation, proven rather than asserted.
        swapped = A.add_fail_site(self.source).replace('fail("', 'ok("', 1)
        self.assertEqual(A.count_fail_sites(swapped), A.VALIDATOR_FAIL_SITES)
        self.assertIsNone(A.check_inventory_probe(self.fake_root(swapped), self.workdir))


if __name__ == "__main__":
    unittest.main()
