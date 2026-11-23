"""T-1513: an argv whose quotes no shell consumed is refused before any write.

Measured 2026-09-24: a host wrapped the launcher in an extra shell layer
(Git Bash `cmd //c "... \\"text\\" ..."`), cmd.exe does not treat a
backslash-escaped quote as an escape, and `tools/saipen.py` received one
quoted text as separate words with the quote characters still attached. The
free-text verbs joined them verbatim: seven LOG events and two ticket titles
carry literal quotes, one of them a `"verify -> PASS [target: T-1511]` line
that the `^verify -> PASS` readers cannot see, and a split `--` word ended
option parsing for `ticket block`.
"""

from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import saipen as cli  # noqa: E402
import test_t1363_zero_manual_entry as fixtures  # noqa: E402


def run(argv: list[str]) -> tuple[int, dict]:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = cli.main(argv)
    return code, json.loads(buffer.getvalue())


class UnconsumedQuoteSpanTests(unittest.TestCase):
    def test_a_quoted_phrase_split_into_words_is_found(self):
        tokens = ["checkpoint", "RUN", "T-1", '"SCOUT', "--", "found", 'it."', "--json"]
        self.assertEqual(cli.unconsumed_quote_span(tokens), (3, 6))

    def test_text_the_shell_delivered_whole_is_not_damage(self):
        for tokens in (
            ["checkpoint", "RUN", "T-1", 'He said "hi" and left'],
            ["checkpoint", "RUN", "T-1", 'a 5" screen', "--json"],
            ["checkpoint", "RUN", "T-1", '"whole"'],
            ["checkpoint", "RUN", "T-1", "plain", "words", "--", "tail"],
            ["ticket", "add", "P2", '"one', "word"],
        ):
            with self.subTest(tokens=tokens):
                self.assertIsNone(cli.unconsumed_quote_span(tokens))


class DamagedArgvRefusalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = fixtures.project(self)
        self.log = self.root / ".saipen" / "LOG.md"
        self.board = self.root / ".saipen" / "BOARD.md"

    def test_a_damaged_checkpoint_is_refused_and_writes_nothing(self):
        before = (self.log.read_bytes(), self.board.read_bytes())
        code, result = run([
            "checkpoint", "RUN", '"verify', "->", "PASS", "--", 'green."',
            "--project-root", str(self.root), "--json",
        ])
        self.assertNotEqual(code, 0)
        self.assertEqual(result["code"], "ARGV_QUOTES_UNCONSUMED")
        self.assertIn("bin/saipen", result["detail"])
        self.assertEqual((self.log.read_bytes(), self.board.read_bytes()), before)

    def test_a_damaged_ticket_title_is_refused_and_writes_nothing(self):
        before = (self.log.read_bytes(), self.board.read_bytes())
        code, result = run([
            "ticket", "add", "P2", '"Fix', "the", 'importer"', "--verify", '"it', 'holds"',
            "--project-root", str(self.root), "--json",
        ])
        self.assertNotEqual(code, 0)
        self.assertEqual(result["code"], "ARGV_QUOTES_UNCONSUMED")
        self.assertEqual((self.log.read_bytes(), self.board.read_bytes()), before)

    def test_the_same_text_delivered_whole_still_records_unchanged(self):
        code, result = run([
            "checkpoint", "RUN", "verify -> PASS -- green.",
            "--project-root", str(self.root), "--json",
        ])
        self.assertEqual(code, 0, result)
        tail = self.log.read_text(encoding="utf-8").splitlines()[-1]
        self.assertTrue(tail.endswith("RUN: verify -> PASS -- green."), tail)


if __name__ == "__main__":
    unittest.main()
