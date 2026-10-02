"""T-1287: a free-text verb must never swallow an option.

Measured on FastPrompter 18.09.26 (LOG E-2102): `saipen build --file <payload>`
joined its arguments verbatim, so the option string itself became a P0 build
directive and was queued as T-1287. Nothing the operator had asked for was
performed; the phantom outranked real P0 work until an operator neutralised it
(LOG E-2103). The intended action was recording BUILD evidence on T-1286, which
`saipen checkpoint` owns.

`build` takes free text ONLY. An option-shaped token is a zero-write refusal
naming the verbs that own the carriers (`start --file` for a request,
`checkpoint` for evidence), so one behaviour has exactly one door.

Run standalone:
    python -m unittest tools.test_t1287_build_directive_grammar
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
for _entry in (str(TOOLS), str(ROOT)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from saipen_engine import conformance as C  # noqa: E402
from test_t1412_conformance_truth import T1412Base  # noqa: E402


class BuildDirectiveGrammarTests(T1412Base):
    def setUp(self) -> None:
        super().setUp()
        self.root = self.make_project("t1287")
        self.payload = self.base / "payload.json"
        self.payload.write_text('{"note":"checkpoint payload"}\n', encoding="utf-8")

    def _board_hash(self) -> str:
        return C._hash_file(self.root / ".saipen" / "BOARD.md")

    def test_the_measured_misfire_is_refused_and_writes_nothing(self) -> None:
        """The exact invocation that created the phantom, twice: still refused."""
        before = self._board_hash()
        for _ in range(2):
            rc, payload, text = self.run_cli(
                self.root, "build", "--file", str(self.payload), "--dry-run"
            )
            self.assertEqual(payload.get("code"), "VALIDATION_FAILED", text)
            self.assertIn("--file", payload.get("detail", ""))
            self.assertIn("saipen start --file", payload.get("detail", ""))
            self.assertEqual(payload.get("usage"), "saipen build <directive>")
        self.assertEqual(self._board_hash(), before, "a refusal must write nothing")

    def test_any_option_shaped_token_is_refused(self) -> None:
        # Tokens the GLOBAL parser does not consume. `--json`/`-x` are global
        # flags and are stripped before the verb runs, so they are not the
        # verb's business -- pinned separately below.
        for option in ("--receipt", "--hex", "--priority", "--kind"):
            with self.subTest(option=option):
                before = self._board_hash()
                rc, payload, text = self.run_cli(
                    self.root, "build", option, "SRC-001", "--dry-run"
                )
                self.assertEqual(payload.get("code"), "VALIDATION_FAILED", text)
                self.assertIn(option, payload.get("detail", ""))
                self.assertEqual(self._board_hash(), before)

    def test_global_flags_are_consumed_globally_not_by_the_verb(self) -> None:
        """`--json` is the global transport flag, not a build option."""
        rc, payload, text = self.run_cli(
            self.root, "build", "--json", "the real directive"
        )
        self.assertEqual(payload.get("code"), "BUILD_WORK_STARTED", text)
        self.assertEqual(payload.get("directive"), "the real directive")

    def test_free_text_is_still_ingested_verbatim(self) -> None:
        rc, payload, text = self.run_cli(self.root, "build", "fix the thing", "--dry-run")
        self.assertEqual(payload.get("code"), "BUILD_WORK_STARTED", text)
        self.assertEqual(payload.get("directive"), "fix the thing")

    def test_a_multi_word_directive_survives(self) -> None:
        rc, payload, text = self.run_cli(
            self.root, "build", "make", "the", "window", "close", "--dry-run"
        )
        self.assertEqual(payload.get("code"), "BUILD_WORK_STARTED", text)
        self.assertEqual(payload.get("directive"), "make the window close")

    def test_empty_build_needs_a_directive(self) -> None:
        rc, payload, text = self.run_cli(self.root, "build", "--dry-run")
        self.assertEqual(payload.get("code"), "VALIDATION_FAILED", text)
        self.assertIn("free-text directive", payload.get("detail", ""))


if __name__ == "__main__":
    unittest.main()
