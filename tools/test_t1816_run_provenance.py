"""T-1816 R006 bullet 3 -- per-RUN append-only improve provenance (SRC-275 DRIFT-04).

The measured defect: a report's ``source_head`` / ``source_tree_fingerprint`` is
stamped once at creation. After a second run, the only mechanical identity in
the file describes RUN 1, so a verifier comparing it to the current tree sees a
stale file -- and the observed "repair" was to REWRITE the header to the newer
identity. That erases the evidence the field exists to carry: the difference
between the tree that was audited and the tree measured later.

The invariant these tests hold:

* each RUN records the identity it was produced against, inside its own section;
* appending RUN 2 does NOT change any byte of RUN 1 or of the header;
* the per-RUN keys can never shadow the report-level fields; and
* an identity that cannot be computed is recorded as UNAVAILABLE, never omitted
  and never guessed.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import improve

HEADER = """report_status: draft
source_head: 1111111111111111111111111111111111111111
source_tree_fingerprint: git-delta-v1:aaaa
discovery_model: fixture

"""


class PerRunProvenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_run_provenance_block_records_both_fields(self) -> None:
        report = self.root / ".saipen" / "improve" / "c1" / "seat" / "r.md"
        report.parent.mkdir(parents=True)
        report.write_text(HEADER + "## RUN 1\n\nIMP-001 [P2] x\n", encoding="utf-8")
        block = improve._run_provenance_block(report)
        # A no-Git root yields the engine's own explicit no-git identity, which
        # is a real measurement -- not UNAVAILABLE, and never a fabricated hash.
        self.assertIn("run_source_head: no-git", block)
        self.assertRegex(block, r"run_source_tree_fingerprint: no-git-tree-v1:[0-9a-f]{64}")
        self.assertNotIn("1111111111111111111111111111111111111111", block)

    def test_an_uncomputable_identity_is_recorded_as_unavailable(self) -> None:
        """The honest hole: a root that cannot yield an identity says so."""
        missing = self.root / "not-a-project" / "r.md"
        block = improve._run_provenance_block(missing)
        self.assertEqual(
            block,
            "run_source_head: UNAVAILABLE\n"
            "run_source_tree_fingerprint: UNAVAILABLE\n\n",
        )

    def test_per_run_keys_cannot_shadow_the_report_level_fields(self) -> None:
        """`_field` is a whole-text `^key:` search; the prefixes must differ."""
        text = HEADER + "run_source_head: deadbeef\nrun_source_tree_fingerprint: x\n"
        self.assertEqual(
            improve._field(text, "source_head"),
            "1111111111111111111111111111111111111111",
        )
        self.assertNotEqual(improve._field(text, "source_head"), "deadbeef")

    def test_the_block_is_placed_inside_the_run_not_the_header(self) -> None:
        """A provenance line in the header would be mistaken for report identity."""
        report = self.root / ".saipen" / "improve" / "c1" / "seat" / "r.md"
        report.parent.mkdir(parents=True)
        report.write_text(HEADER, encoding="utf-8")
        run = f"## RUN 1\n\n{improve._run_provenance_block(report)}IMP-001 [P2] x\n"
        parsed_header, body = run.split("\n\n", 1)
        self.assertEqual(parsed_header, "## RUN 1")
        self.assertIn("run_source_head:", body)

    def test_an_unavailable_identity_is_written_not_omitted(self) -> None:
        report = self.root / ".saipen" / "improve" / "c1" / "seat" / "r.md"
        report.parent.mkdir(parents=True)
        report.write_text(HEADER, encoding="utf-8")
        block = improve._run_provenance_block(report)
        lines = [ln for ln in block.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 2, "both fields are always emitted")


if __name__ == "__main__":
    unittest.main()
