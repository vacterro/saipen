"""T-2174: raw environment dumps must never enter a handoff/AUDAPACK export.

The canonical export boundary is `saipen_engine.distribution.is_non_exportable_path`,
used by both `build_handoff_archive.py` and `verify_handoff_archive.py`. Before
this fix it excluded only `.saipen/quarantine/`, so tracked raw environment
dumps (`_TEMP_/env1.json`, `_TEMP_/env_A.json`, `.saipen/tmp/env_probe_1.json`,
...) were packaged into the delivery artifact even though they carry plaintext
credential entries. The AUDAPACK export reported `SECURITY_CHECK_PASSED: false`.

This control names PATH SHAPES only. It never reads a dump's contents and never
prints a value: the classifier is path-based, so the proof is that the raw dump
shapes are refused while safe, non-secret verification evidence (environment
key *digests*, not raw values) stays exportable.
"""

from __future__ import annotations

import unittest

from saipen_engine.distribution import is_non_exportable_path


class ExportCredentialContainmentTests(unittest.TestCase):
    # Exactly the dump shapes observed in the AUDAPACK export. No contents.
    RAW_DUMPS = (
        "_TEMP_/env1.json",
        "_TEMP_/env2.json",
        "_TEMP_/env3.json",
        "_TEMP_/env_A.json",
        "_TEMP_/env_B.json",
        "_TEMP_/env_ba_py.json",
        "_TEMP_/env_ps_py.json",
        ".saipen/tmp/env_probe_1.json",
        ".saipen/tmp/env_probe_2.json",
        "scratch/env_ps_t1.txt",
    )

    # HANDOFF 2026-11-23: four untracked top-level research-kitchen files carry
    # plaintext EXA_API_KEY. Current T-2174 classifier covers scratch roots and
    # env-like stems, but not `.saipen/kitchen/` or *family.json exports.
    KITCHEN_ENV_EXPORTS = (
        ".saipen/kitchen/bg.env",
        ".saipen/kitchen/fg.env",
        ".saipen/kitchen/bgfamily.json",
        ".saipen/kitchen/fgfamily.json",
    )

    # Non-secret verification identity evidence must stay exportable.
    SAFE_EVIDENCE = (
        ".saipen/evidence/T-2045/gateway-boundary-20261110/environment-key-digests.json",
        ".saipen/evidence/T-1833-owner-guard/environment-key-hashes.json",
        ".saipen/evidence/T-1729-gate-decision-20261016/environment-first.json",
    )

    def test_raw_environment_dumps_are_non_exportable(self):
        for path in self.RAW_DUMPS:
            with self.subTest(path=path):
                self.assertTrue(
                    is_non_exportable_path(path),
                    f"raw environment dump {path!r} would leak into an export",
                )

    def test_kitchen_environment_exports_are_non_exportable(self):
        for path in self.KITCHEN_ENV_EXPORTS:
            with self.subTest(path=path):
                self.assertTrue(
                    is_non_exportable_path(path),
                    f"kitchen environment export {path!r} would leak into an export",
                )

    def test_kitchen_backslash_variants_are_also_refused(self):
        self.assertTrue(is_non_exportable_path(".saipen\\kitchen\\bg.env"))
        self.assertTrue(is_non_exportable_path(".saipen\\kitchen\\fgfamily.json"))

    def test_kitchen_allowed_registry_and_receipts_stay_exportable(self):
        for path in (
            ".saipen/kitchen/cohort_registry.json",
            ".saipen/kitchen/digest.md",
            ".saipen/kitchen/release_receipt.json",
            ".saipen/kitchen/release_receipts/T-1668.json",
        ):
            with self.subTest(path=path):
                self.assertFalse(
                    is_non_exportable_path(path),
                    f"allowed kitchen project-memory file {path!r} must not be dropped",
                )

    def test_backslash_variants_are_also_refused(self):
        self.assertTrue(is_non_exportable_path("_TEMP_\\env_A.json"))
        self.assertTrue(is_non_exportable_path(".saipen\\tmp\\env_probe_1.json"))

    def test_safe_environment_evidence_stays_exportable(self):
        for path in self.SAFE_EVIDENCE:
            with self.subTest(path=path):
                self.assertFalse(
                    is_non_exportable_path(path),
                    f"non-secret evidence {path!r} must not be dropped",
                )


if __name__ == "__main__":
    unittest.main()
