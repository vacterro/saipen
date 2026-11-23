"""T-1897: the validator's own manifest and closure-provenance failures.

Measured 2026-10-24 on this repository: `--gate core` emitted 41 problems and
`findings.classify` named exactly one of them. The other 40 -- 38 manifest
failures naming DIFFERENT files, one closure-provenance drift, one coverage
gap -- all fell through to `rule_id: "unclassified"`, `subject_kind: "global"`,
`subject_id: None`. Because `finding_key` is rule|kind|subject, forty distinct
offending files collapsed into ONE key, and `finding_ownership.partition`
routed all of them to UNKNOWN: `engine_work_count` stayed 1 for a tree whose
real engine debt was 41 items.

Two separate defects, both proven here:

1. recognition -- the two families were absent from the rule table; and
2. subject -- even once recognized, a rule with no subject extractor and no
   id pattern in the message has nothing to key on, so the per-file failures
   would still collapse unless the offending path becomes the subject.
"""

from __future__ import annotations

import unittest

from saipen_engine import findings

MANIFEST = (
    "runtime manifest names a file git does not track: tools/test_t1897_x.py "
    "-- it exists here and in no clone, so this home ships complete and every "
    "checkout of it does not. Commit the file or drop the manifest entry"
)
MANIFEST_OTHER = MANIFEST.replace("tools/test_t1897_x.py", "tools/saipen_engine/probe.py")
PROVENANCE = (
    "closure provenance does not resolve: EX-000022 was verified against "
    "installed engine generation sha256:fbbb910716437391... but the running "
    "engine is sha256:98fdbbf06d2b3ca6... -- the dependency moved"
)
COVERAGE = (
    "coverage gap -- 2 shipped document(s) are read by no check and declared "
    "exempt by none: saipen/COMMANDS_REFERENCE.md, docs/x.md"
)


def classify(message: str) -> dict:
    return findings.classify("problem", message)


class RecognitionTests(unittest.TestCase):
    def test_the_manifest_family_is_named(self):
        row = classify(MANIFEST)
        self.assertEqual(row["rule_id"], "runtime_manifest_untracked")

    def test_the_closure_provenance_family_is_named(self):
        row = classify(PROVENANCE)
        self.assertEqual(row["rule_id"], "closure_provenance_drift")

    def test_the_coverage_gap_family_is_named(self):
        row = classify(COVERAGE)
        self.assertEqual(row["rule_id"], "coverage_gap")

    def test_no_family_here_stays_unclassified(self):
        for message in (MANIFEST, PROVENANCE, COVERAGE):
            self.assertNotEqual(
                classify(message)["rule_id"], "unclassified", message[:60]
            )


class SubjectTests(unittest.TestCase):
    def test_two_different_manifest_files_are_two_findings(self):
        first = classify(MANIFEST)
        second = classify(MANIFEST_OTHER)
        self.assertEqual(first["subject_kind"], "path")
        self.assertEqual(first["subject_id"], "tools/test_t1897_x.py")
        self.assertEqual(second["subject_id"], "tools/saipen_engine/probe.py")
        self.assertNotEqual(first["finding_key"], second["finding_key"])

    def test_an_unresolved_closure_binds_its_experience_subject(self):
        row = classify(PROVENANCE)
        self.assertEqual(row["subject_kind"], "event")
        self.assertEqual(row["subject_id"], "EX-000022")

    def test_the_manifest_key_survives_a_reworded_explanation(self):
        reworded = (
            "runtime manifest names a file git does not track: tools/test_t1897_x.py "
            "-- a different sentence entirely, but the same offending path"
        )
        self.assertEqual(
            classify(MANIFEST)["finding_key"], classify(reworded)["finding_key"]
        )

    def test_a_cited_core_rule_is_not_mistaken_for_an_event_id(self):
        """`CORE-003` used to yield a phantom `E-003` detail on every message.

        Measured on the real receipt: the closure-provenance finding whose only
        real subject is EX-000022 carried `detail: "E-003"`. An id must begin a
        token, or every CORE citation invents an event.
        """
        row = classify(PROVENANCE + " (CORE-003)")
        self.assertEqual(row["subject_id"], "EX-000022")
        self.assertNotEqual(row["detail"], "E-003")
        self.assertIn("closure provenance", row["detail"] or "")


class CollapseRegressionTests(unittest.TestCase):
    """The measured defect, as one assertion: 40 files -> 40 keys."""

    def test_forty_distinct_manifest_paths_yield_forty_distinct_keys(self):
        keys = {
            classify(
                MANIFEST.replace("tools/test_t1897_x.py", f"tools/probe_{index}.py")
            )["finding_key"]
            for index in range(40)
        }
        self.assertEqual(len(keys), 40)


if __name__ == "__main__":
    unittest.main()
