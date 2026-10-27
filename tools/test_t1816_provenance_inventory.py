"""T-1816 R006 bullet 1 -- the provenance inventory must stay true (SRC-275).

The inventory's whole value is that it is MEASURED against the protected original
AUDAPACK root rather than asserted. If the root moves on, or the inventory drifts
back into prose, these tests fail. They are read-only against that root: the same
probes the audit used, no writes, no `saipen` invocation.

Two rules the source set and this oracle enforces:

* the audit may not alter the root -- proven by a before/after hash around every
  probe, so a future edit that mutates it fails here; and
* no missing event id may be synthesized -- the inventory must record the
  committed ledger's ABSENCE of E-3133/E-3136/E-3145 as a fact and must not claim
  they were restored.

The root is an external managed project. Every test skips explicitly when it is
absent rather than passing vacuously.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDAPACK = Path(r"V:\___VAC\__K\__CODE\_PY\_AUDAPACK")
INVENTORY = ROOT / ".saipen" / "evidence" / "T-1816-audapack-provenance-inventory.md"

PROTECTED = (".saipen/STATE.md", ".saipen/LOG.md", ".saipen/BOARD.md", ".saipen/IDENTITY.md")
#: The true gap. E-2947/E-2948 are NOT here: they exist without a `[parent:]`
#: field, which is a schema irregularity a strict parser miscounts as a loss.
MISSING_IDS = (3133, 3136, 3145)
#: Entries present but carrying no parent field; recorded so the distinction stays
#: visible instead of being re-derived by a future scan.
PARENTLESS_IDS = (2947, 2948)
RENUMBERED = (3132, 3134, 3135, 3137, 3138, 3139, 3140, 3141, 3142, 3143, 3144, 3146)
ARCHIVE = (
    ".saipen/recovery/log-foreign-tail/"
    "quarantine-log-tail-e48dacd80fad4e1a916e2dcf0c8b00ab/LOG.md"
)
ARCHIVE_SHA = "680044550b990b8075fcb96d2313d0dc2da6e2056db14b01596adc4e0d2eb364"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=AUDAPACK, capture_output=True, text=True, check=False
    ).stdout


def _hashes() -> dict[str, str]:
    return {
        name: hashlib.sha256((AUDAPACK / name).read_bytes()).hexdigest()
        for name in PROTECTED
    }


def _entry_lines(text: str) -> dict[int, str]:
    """Every entry, with or without a parent field.

    E-2947/E-2948 carry no ``[parent:]``, so a parse that required it would report
    them as missing and overstate the corruption from 3 to 5. Presence is the
    question here, not schema conformance.
    """
    found: dict[int, str] = {}
    for line in text.splitlines():
        match = re.match(
            r"^\s*-\s+\d{2}\.\d{2}\.\d{2} \d{2}:\d{2}\s+\[E-(\d+)\]\s+\[(parent: E-|T-|agent:)",
            line,
        )
        if match:
            found.setdefault(int(match.group(1)), line.strip())
    return found


@unittest.skipUnless(AUDAPACK.is_dir(), "original AUDAPACK root not present on this host")
class ProvenanceInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.before = _hashes()
        cls.head_text = _git("show", "HEAD:.saipen/LOG.md")
        cls.worktree = (AUDAPACK / ".saipen" / "LOG.md").read_text(
            encoding="utf-8", errors="replace"
        )
        cls.head = _entry_lines(cls.head_text)
        cls.live = _entry_lines(cls.worktree)
        cls.doc = INVENTORY.read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        assert cls.before == _hashes(), "the audit must never alter the protected root"

    # -- the measurement itself ------------------------------------------------

    def test_committed_ledger_still_misses_exactly_the_cited_events(self) -> None:
        self.assertTrue(self.head, "committed LOG.md must parse")
        low, high = min(self.head), max(self.head)
        missing = [n for n in range(low, high + 1) if n not in self.head]
        self.assertEqual(sorted(missing), list(MISSING_IDS))

    def test_parentless_entries_are_present_and_not_counted_as_a_gap(self) -> None:
        for work in PARENTLESS_IDS:
            self.assertIn(work, self.head)
            self.assertNotRegex(
                self.head[work],
                r"\[parent: E-\d+\]",
                f"E-{work} documents the schema irregularity; do not 'fix' it in prose",
            )
        # The distinction has to survive in the document too, or a future reader
        # re-derives 5 missing from a strict parse and overstates the corruption.
        self.assertIn("E-2947", self.doc)
        self.assertIn("schema irregularity", self.doc)

    def test_committed_ledger_cites_the_missing_ids_as_parents(self) -> None:
        for child, parent in ((3134, 3133), (3137, 3136), (3146, 3145)):
            match = re.search(rf"\[E-{child}\]\s+\[parent: E-(\d+)\]", self.head_text)
            self.assertIsNotNone(match, f"committed E-{child} must exist")
            self.assertEqual(int(match.group(1)), parent)
            self.assertNotIn(parent, self.head, "a cited parent must be absent from HEAD")

    def test_working_tree_renumbers_committed_ids_instead_of_repairing(self) -> None:
        shared = set(self.head) & set(self.live)
        self.assertGreater(len(shared), 700)
        collisions = [n for n in RENUMBERED if self.head[n] != self.live[n]]
        self.assertEqual(collisions, list(RENUMBERED))
        for work in RENUMBERED:
            self.assertNotIn(
                self.head[work],
                self.worktree,
                f"E-{work}'s committed body must not survive elsewhere in the worktree",
            )

    def test_displaced_bodies_are_gone_but_the_archive_kept_them(self) -> None:
        archive = (AUDAPACK / ARCHIVE).read_bytes()
        self.assertEqual(hashlib.sha256(archive).hexdigest(), ARCHIVE_SHA)
        text = archive.decode("utf-8", errors="replace")
        for needle in ("npm cache segments", "P1-A attached data never enters"):
            self.assertIn(needle, text, "the archive is the evidence of record")
            self.assertNotIn(needle, self.worktree, "and the active ledger dropped it")

    def test_the_only_surviving_copy_is_git_ignored(self) -> None:
        ignored = subprocess.run(
            ["git", "check-ignore", "-v", ARCHIVE],
            cwd=AUDAPACK,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(ignored.returncode, 0)
        self.assertIn(".saipen/recovery/", ignored.stdout)

    # -- the document must keep saying so -------------------------------------

    def test_inventory_records_absence_without_claiming_restoration(self) -> None:
        for needle in ("E-3133", "E-3136", "E-3145"):
            self.assertIn(needle, self.doc)
        self.assertIn("Do not synthesize", self.doc)
        self.assertIn("not as the missing ones restored", self.doc)

    def test_inventory_carries_the_three_labels(self) -> None:
        for label in ("PROVEN", "UNPROVEN", "CONTRADICTED"):
            self.assertIn(label, self.doc)

    def test_inventory_does_not_invent_operator_approval(self) -> None:
        lowered = self.doc.lower()
        for forbidden in (
            "operator approved the oct 13",
            "authorized by the operator",
            "operator granted",
        ):
            self.assertNotIn(forbidden, lowered)
        self.assertIn("UNPROVEN", self.doc)
        self.assertIn("no independent witness", self.doc)

    def test_inventory_states_the_control_that_was_missing(self) -> None:
        self.assertIn("effect-aware", self.doc)
        self.assertIn("READ_ONLY_DIAGNOSIS_ONLY", self.doc)

    def test_inventory_records_that_it_left_the_root_untouched(self) -> None:
        self.assertIn("e746cdc944d2bd9b738303825af53ff0900d050ebeef2b9d120219dbe2b69c04", self.doc)
        self.assertIn("d054c1c60b835f21c797b8ef0e69d691c10ea24f6701049f8ae3c58d78fa4aa8", self.doc)


if __name__ == "__main__":
    unittest.main()
