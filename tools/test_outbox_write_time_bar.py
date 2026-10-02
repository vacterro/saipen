"""T-351: the OUTBOX write-time bar, red and green, cell by cell.

`saipen_engine.subs.validate_outbox_text` / `validate_outbox_file` are the bar a
role runs immediately after appending a package, and `saipen outbox check
<role>` is the CLI over them. Before this, the only strict parse over an OUTBOX
ran at CONSUMPTION, under `--gate collect:<role>`, and T-568 makes producer
findings WARN under `core` on purpose -- so a role nobody collected kept
whatever it wrote. Measured origin: one OUTBOX written in a single session
carried four independent closed-grammar violations and the project still
reported conformant.

The four classes below are the ones that actually occurred, one per mutation,
so a regression in any one of them is a named failure rather than a count:

  1. malformed package heading  -- `## TEST-106 (re-run after fixes): ...`
  2. prose `source_tree_fingerprint` -- free text where git-delta-v1:<64hex>
  3. `status` outside the closed enum  -- `resolved` is not a status
  4. duplicate field  -- `payload` twice in one package

Each RED case must be refused with a NAMED error, not merely counted, and the
corrected package must parse with zero. The file form is exercised too, because
that is the one a role actually runs, and it must go through the SAME resolver
the collect gate uses -- a check that looked at a different file than the gate
would be the defect T-313 just closed, re-opened one layer down.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from saipen_engine.subs import (
    ROLE_REGISTRY,
    outbox_rel,
    validate_outbox_file,
    validate_outbox_text,
)

FP = "a" * 64
ROLE_REV = "sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08"

GOOD = f"""# OUTBOX

## TEST-106: a corrected package
- **status:** reviewed
- **producer:** saitest
- **source_head:** 44f6b33868ef32dbb71130a1899d189fd2192328
- **source_tree_fingerprint:** git-delta-v1:{FP}
- **role_revision:** {ROLE_REV}
- **coverage:** the same four scenarios
- **payload:** []
- **verified:** PASS -- four scenarios, all NOT_REPRODUCED
- **instructions:** no further Core action
- **details:** prose
"""

CASES = {
    "malformed heading": (
        GOOD.replace("## TEST-106: a corrected package",
                     "## TEST-106 (re-run after fixes): a corrected package"),
        "malformed package heading",
    ),
    "prose fingerprint": (
        GOOD.replace(FP, "working-tree-dirty: wintage.user.js 7486 lines changed"),
        "invalid source_tree_fingerprint",
    ),
    "status outside enum": (
        GOOD.replace("- **status:** reviewed", "- **status:** resolved"),
        "outside closed enum",
    ),
    "duplicate field": (
        GOOD.replace("- **details:** prose", "- **payload:** [] duplicate\n- **details:** prose"),
        "duplicate field",
    ),
}


class OutboxWriteTimeBar(unittest.TestCase):
    def test_corrected_package_passes(self):
        self.assertEqual(validate_outbox_text(GOOD, "saitest"), [])

    def test_every_occurrence_class_is_refused_by_name(self):
        for label, (text, expected) in CASES.items():
            with self.subTest(violation=label):
                errors = validate_outbox_text(text, "saitest")
                self.assertTrue(errors, f"{label} was accepted by the write-time bar")
                self.assertTrue(
                    any(expected in e for e in errors),
                    f"{label} refused without naming it: {errors}",
                )

    def test_file_form_refuses_through_the_collect_gate_resolver(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            kitchen = root / ".saipen/extensions/subs/saitest/kitchen"
            kitchen.mkdir(parents=True)
            (kitchen / "OUTBOX.md").write_text(GOOD, encoding="utf-8")
            self.assertEqual(validate_outbox_file(root, "saitest"), [])
            # The path the bar reads is the path the collect gate reads.
            self.assertEqual(
                outbox_rel(root, "saitest"),
                ".saipen/extensions/subs/saitest/kitchen/OUTBOX.md",
            )
            for label, (text, expected) in CASES.items():
                with self.subTest(violation=label):
                    (kitchen / "OUTBOX.md").write_text(text, encoding="utf-8")
                    errors = validate_outbox_file(root, "saitest")
                    self.assertTrue(errors, f"{label} accepted through the file resolver")
                    self.assertTrue(any(expected in e for e in errors), errors)

    def test_missing_outbox_is_a_named_refusal_not_a_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            errors = validate_outbox_file(root, "saitest")
            self.assertEqual(len(errors), 1)
            self.assertIn("no OUTBOX", errors[0])
            self.assertIn(outbox_rel(root, "saitest"), errors[0])

    def test_saitranslate_resolves_to_its_own_namespace_not_subs(self):
        # T-313 in one line: a role is judged on the package its namespace
        # owns, so the bar and the collect gate can never read different files.
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                outbox_rel(Path(tmp), "saitranslate"),
                ".saipen/saitranslate/kitchen/OUTBOX.md",
            )
            self.assertEqual(
                outbox_rel(Path(tmp), "saitest"),
                ".saipen/extensions/subs/saitest/kitchen/OUTBOX.md",
            )

    def test_every_registered_role_is_reachable(self):
        for role in ROLE_REGISTRY:
            self.assertTrue(outbox_rel(".", role).endswith("kitchen/OUTBOX.md"), role)


if __name__ == "__main__":
    unittest.main()
