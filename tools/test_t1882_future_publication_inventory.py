"""SRC-307 / T-1882 -- the FUTURE verbs stay published and the inventory agrees.

Two measured defects, one shared surface. The worktree `saipen/COMMANDS.md`
had lost every `saipen future` row that HEAD still carried, so the validator
answered four `FUTURE-OWNER` FAILs and those FAILs cascaded into 23 further
core-unit reds whose dumps merely quoted them. Separately, the worktree
`tools/validator_fail_sites.json` had drifted from the validator it inventories,
so the same four FAILs also surfaced as an unadjudicated inventory site.

Both halves are asserted here against the real repository, not a fixture: the
defect was a byte-level drift in shipped files, and a fixture would have been
built from the same stale bytes and passed.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import fail_site_inventory as I  # noqa: E402


#: The four verbs that mutate. `status`/`list`/`next` write nothing, so the
#: validator warns rather than fails on those, and asserting them here would
#: pin a warning that is not part of this defect.
MUTATING = ("add", "promote", "refine", "refresh")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


class FutureVerbsStayPublishedTests(unittest.TestCase):
    """The publication surface names every mutating FUTURE verb."""

    def test_every_mutating_future_verb_is_published(self):
        commands = _read(ROOT / "saipen" / "COMMANDS.md")
        missing = [verb for verb in MUTATING if f"`saipen future {verb}" not in commands]
        self.assertEqual(missing, [], f"COMMANDS.md does not publish {missing}")

    def test_the_published_verbs_are_the_declared_ones(self):
        effects = json.loads(_read(ROOT / "saipen" / "COMMAND_EFFECTS.json"))
        declared = set((effects.get("verbs") or {}).get("future", {}).get("subcommands") or {})
        self.assertTrue(
            set(MUTATING) <= declared,
            f"COMMAND_EFFECTS.json declares {sorted(declared)}, not all of {sorted(MUTATING)}",
        )

    def test_the_publication_fits_the_declared_budget(self):
        """The repair must not buy a green validator with a blown context budget.

        Measured before the repair: HEAD's 208-line document scores 57232/56320
        and the index's 213-line one scores 57656/56320. Both already failed, so
        restoring either would have traded one red for another.
        """
        proc = subprocess.run(
            [sys.executable, "-B", str(ROOT / "tools" / "protocol_budget.py"), "--summary"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=str(ROOT),
            timeout=300,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertNotIn("FAIL", proc.stdout, proc.stdout)


class InventoryAgreesWithTheValidatorTests(unittest.TestCase):
    """The ledger adjudicates the validator it actually ships with."""

    def test_the_live_repository_has_no_inventory_drift(self):
        self.assertEqual(I.inventory_errors(ROOT), [])

    def test_the_publication_site_keeps_its_adjudicated_verdict(self):
        """A regenerated ledger must not silently demote a covered check.

        The site identity is derived from the check's message and position, so
        an unrelated edit elsewhere in the validator re-mints the record. The
        verdict belongs to the control, not to the line number: regeneration
        alone must never be read as an adjudication.
        """
        ledger = I.load_ledger(ROOT)
        found = [
            record
            for record in ledger["sites"]
            if record["site_id"] == "e736f31b20f2d116"
        ]
        self.assertEqual(len(found), 1, "the future-publication site left the ledger")
        record = found[0]
        self.assertEqual(record["disposition"], I.COVERED, record)
        self.assertEqual(record.get("case"), "a future verb stops being published")
        self.assertNotEqual(record["disposition"], I.UNADJUDICATED)


if __name__ == "__main__":
    unittest.main()
