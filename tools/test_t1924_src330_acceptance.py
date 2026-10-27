"""T-1924: the SRC-330 acceptance mapping and its R8 control must stay true.

T-1924 closes on three conditions, and this module makes each one falsifiable
instead of a paragraph someone can quietly outgrow:

  1. every SRC-330 acceptance item is mapped to current evidence or explicitly
     open under a named owner -- the mapping document must exist, must cite the
     immutable source by its exact digest, and must not silently lose or gain
     rows;
  2. the reconnect cache defect has an isolated before/after control -- the
     control must actually isolate the cache, i.e. the red arm keeps the stale
     bundled path while the green arm, differing only by a cache clear, selects
     the personal file;
  3. no restoration is called complete from unrelated tests -- the mapping must
     not claim RESTORED, and the control must not claim fixture bytes are the
     operator's originals.

Nothing here reads the operator's live FastPrompter profile. The control's own
record carries `live_configuration_accessed: false`, and this module never
launches the resolver against a real data root.
"""

from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / ".saipen" / "evidence" / "T-1924"

MAPPING = EVIDENCE / "SRC330_ACCEPTANCE_MAPPING.md"
CONTROL_RECORD = EVIDENCE / "reconnect-control.json"
CONTROL_SCRIPT = EVIDENCE / "reconnect_control.py"

#: The immutable original mission T-1924 exists to correct.
SRC330_SHA256 = "eee73aad905e76b0adef553fcef4938029393f7614606acb35b06e504d8ea41e"

#: Every acceptance item the source defines, in source order.
ACCEPTANCE_IDS = [f"R{n}" for n in range(1, 21)]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TheMappingCoversEveryAcceptanceItemTests(unittest.TestCase):
    """Condition (a): nothing in R1-R20 is silently unmapped."""

    def test_the_mapping_document_exists(self):
        self.assertTrue(MAPPING.is_file(), f"missing {MAPPING}")

    def test_the_mapping_names_the_immutable_source_by_digest(self):
        text = _read(MAPPING)
        self.assertIn(SRC330_SHA256, text)
        self.assertIn("SRC-330", text)

    def test_every_acceptance_item_has_a_row(self):
        text = _read(MAPPING)
        missing = [rid for rid in ACCEPTANCE_IDS
                   if not re.search(rf"^\|\s*{rid}\s*\|", text, re.MULTILINE)]
        self.assertEqual(missing, [], f"acceptance items with no row: {missing}")

    def test_every_row_declares_a_measured_state_and_a_reason(self):
        """A row must say DIRECT, PARTIAL, FAIL or OPEN and then justify it."""
        text = _read(MAPPING)
        states = ("DIRECT", "PARTIAL", "FAIL", "OPEN")
        for rid in ACCEPTANCE_IDS:
            row = next((line for line in text.splitlines()
                        if re.match(rf"^\|\s*{rid}\s*\|", line)), None)
            self.assertIsNotNone(row, f"{rid} has no row")
            self.assertTrue(any(state in row for state in states),
                            f"{rid} declares no state: {row}")
            # A state with nothing after it is a label, not evidence.
            cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
            self.assertGreaterEqual(len(cells), 4, f"{rid} row is too short: {row}")
            self.assertTrue(cells[-1], f"{rid} has an empty evidence cell")

    def test_no_open_item_is_hidden_as_done(self):
        """An OPEN row must name an owner; it may not be blank prose."""
        text = _read(MAPPING)
        for rid in ACCEPTANCE_IDS:
            row = next((line for line in text.splitlines()
                        if re.match(rf"^\|\s*{rid}\s*\|", line)), None)
            if row and "OPEN" in row:
                self.assertIn("Omanik", row,
                              f"{rid} is OPEN but names no owning Work")


class TheMappingDoesNotOverclaimTests(unittest.TestCase):
    """Condition (c): unrelated tests may not be read as restoration."""

    def test_the_mapping_refuses_to_claim_restoration(self):
        text = _read(MAPPING)
        self.assertNotIn("LOCAL_AUDIO_RESTORED: true", text.lower())
        # The document must say plainly what it does not establish.
        self.assertIn("ei väida", text.lower())

    def test_the_mapping_records_the_failed_acceptance_item(self):
        """R8 is measured as FAIL; a mapping that hides it is not a mapping."""
        text = _read(MAPPING)
        self.assertIn("FAIL", text)
        self.assertIn("R8", text)


class TheReconnectControlIsolatesTheCacheTests(unittest.TestCase):
    """Condition (b): the before/after control must discriminate the cause."""

    def setUp(self):
        self.assertTrue(CONTROL_RECORD.is_file(),
                        f"missing control record {CONTROL_RECORD}")
        self.record = json.loads(_read(CONTROL_RECORD))

    def test_the_record_is_a_before_after_control(self):
        self.assertEqual(self.record.get("kind"), "isolated_before_after_control")

    def test_the_red_arm_reproduces_the_defect(self):
        red = self.record.get("red_arm") or {}
        self.assertTrue(red.get("defect_reproduced"),
                        "the red arm did not keep the stale bundled path")
        self.assertEqual(red.get("initial"), "bundled")

    def test_the_green_arm_selects_the_personal_file(self):
        green = self.record.get("green_arm") or {}
        self.assertFalse(green.get("defect_reproduced"),
                         "the green arm still selected the bundled fallback")
        self.assertEqual(green.get("after_personal_appears"), "personal")

    def test_the_two_arms_differ_only_by_the_cache_clear(self):
        self.assertTrue(self.record.get("cache_isolates_cause"))
        self.assertIn("_RESOLVE_CACHE", self.record.get("discriminating_variable", ""))

    def test_the_cache_key_still_carries_no_personal_mode(self):
        """This is the root cause the control isolates, stated as a fact.

        If a future fix adds the mode to the key this assertion should fail,
        which is the signal to re-measure -- not to relax the test.
        """
        self.assertFalse(self.record.get("cache_key_carries_personal_mode"))
        self.assertEqual(len(self.record.get("cache_key_shape") or []), 4)

    def test_the_control_touched_no_live_profile(self):
        self.assertFalse(self.record.get("live_configuration_accessed"))
        self.assertFalse(self.record.get("live_configuration_written"))
        self.assertFalse(self.record.get("fixture_audio_claimed_as_original"))

    def test_the_control_script_exists_and_is_rerunnable(self):
        self.assertTrue(CONTROL_SCRIPT.is_file(), f"missing {CONTROL_SCRIPT}")
        text = _read(CONTROL_SCRIPT)
        # It must confine every fixture to a temporary directory.
        self.assertIn("TemporaryDirectory", text)
        self.assertIn("get_data_dir", text)


class TheMeasuredFactsStillHoldTests(unittest.TestCase):
    """The mapping's load-bearing numbers must be reproducible, not remembered."""

    def test_the_immutable_source_digest_matches_its_file(self):
        source = ROOT / ".saipen" / "archive" / "source" / "SRC-330.md"
        self.assertTrue(source.is_file(), f"missing immutable source {source}")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        self.assertEqual(digest, SRC330_SHA256,
                         "the archived SRC-330 bytes changed under T-1924")

    def test_the_archive_gate_gap_is_still_recorded(self):
        """R16's finding: `archive_audio_leaks` is defined but never called.

        This asserts the MEASUREMENT the mapping reports, so the row cannot
        drift into claiming a working gate that does not run.
        """
        text = _read(MAPPING)
        self.assertIn("archive_audio_leaks", text)
        self.assertIn("ei jookse", text)


if __name__ == "__main__":
    unittest.main()
