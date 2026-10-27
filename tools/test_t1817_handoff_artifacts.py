"""SRC-276 R006/R008: the owner-separated delivery retains every finding.

The source's own acceptance bar is coverage, not prose. R008 says the final
diagnosis "must retain all source F-01 through F-12 findings, defenses,
confidence and unknowns"; R006 says the host-owned set (F-06/F-08/F-09/F-10/
F-12) must leave as a SEPARATE handoff and must not be claimed complete here.

Both documents are durable artifacts, so both claims are checkable against the
source receipt itself: parse the finding ids out of `.saipen/intake/active/
SRC-276.md` and require the artifacts to carry them. A shortened diagnosis that
silently drops F-05 or F-12 fails here.

Nothing in this module writes to the project or to the observed target.
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

SOURCE = ROOT / ".saipen" / "intake" / "active" / "SRC-276.md"
DIAGNOSIS = ROOT / ".saipen" / "evidence" / "T-1817-diagnosis-delivery.md"
HANDOFF = ROOT / ".saipen" / "evidence" / "T-1817-zaicode-host-handoff.md"

#: The findings whose corrective owner is the host, per the source's own
#: "ZAICODE agent (host, отдельный handoff)" section.
HOST_OWNED = ("F-06", "F-08", "F-09", "F-10", "F-12")

#: Engine-owned findings delivered in this project.
ENGINE_OWNED = ("F-01", "F-02", "F-03", "F-05", "F-07", "F-11")


def source_findings() -> list[str]:
    """Every `F-NN · P# ·` heading in the source receipt, in file order."""
    text = SOURCE.read_text(encoding="utf-8")
    return re.findall(r"^(F-\d{2}) · P\d+ ·", text, re.MULTILINE)


class FindingInventoryTests(unittest.TestCase):
    def test_the_source_really_carries_twelve_findings(self):
        ids = source_findings()
        self.assertEqual(len(ids), 12, ids)
        self.assertEqual(ids, [f"F-{n:02d}" for n in range(1, 13)])

    def test_every_finding_appears_in_the_diagnosis(self):
        text = DIAGNOSIS.read_text(encoding="utf-8")
        missing = [fid for fid in source_findings() if fid not in text]
        self.assertEqual(missing, [], f"diagnosis dropped {missing}")

    def test_every_finding_appears_in_the_host_handoff(self):
        text = HANDOFF.read_text(encoding="utf-8")
        missing = [fid for fid in HOST_OWNED if fid not in text]
        self.assertEqual(missing, [], f"handoff dropped {missing}")

    def test_the_engine_owned_findings_do_not_leak_into_the_host_handoff(self):
        # R006 is scoped to the host's five. Listing F-01 or F-03 as a host
        # obligation would repeat the exact F-11 misclassification.
        text = HANDOFF.read_text(encoding="utf-8")
        for fid in ENGINE_OWNED:
            self.assertNotRegex(
                text,
                rf"^###\s+{re.escape(fid)}\b",
                f"{fid} is engine-owned and must not head a host section",
            )


class ClaimBoundaryTests(unittest.TestCase):
    def test_the_handoff_does_not_claim_a_zai_code_edit_exists(self):
        text = HANDOFF.read_text(encoding="utf-8").lower()
        self.assertIn("does not claim any zaicode edit exists", text)

    def test_the_diagnosis_keeps_the_unknowns_unknown(self):
        text = DIAGNOSIS.read_text(encoding="utf-8")
        self.assertIn("historical cause of the missing sidecars", text)
        self.assertIn("historical writer of E-371", text)

    def test_the_fresh_foreign_receipt_is_not_claimed(self):
        text = DIAGNOSIS.read_text(encoding="utf-8")
        self.assertIn("STALE_PASS", text)
        self.assertIn("not claimed", text)

    def test_no_operator_grant_is_asserted(self):
        for path in (DIAGNOSIS, HANDOFF):
            text = path.read_text(encoding="utf-8").lower()
            for forbidden in (
                "operator has approved",
                "operator approved the debt",
                "decision b granted",
                "decision b was granted",
            ):
                self.assertNotIn(forbidden, text, f"{path.name} asserts a grant")


class OwnershipVocabularyTests(unittest.TestCase):
    def test_both_artifacts_use_the_typed_owner_classes(self):
        from saipen_engine import findings

        for path in (DIAGNOSIS, HANDOFF):
            text = path.read_text(encoding="utf-8")
            for cls in findings.ALL_OWNER_CLASSES:
                self.assertIn(cls, text, f"{path.name} omits owner class {cls}")


if __name__ == "__main__":
    unittest.main()
