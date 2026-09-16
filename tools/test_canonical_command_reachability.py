"""T-1357: a command the engine prints must be one its own guard can admit.

Measured live on `__SAITULS`. `guard_events._saipen_cli_verb` refuses any
command containing a character in `_SHELL_SYNTAX_CHARS`, and both quote
characters are in that set -- deliberately, because quoting is how a compound
expression hides inside a line that looks canonical. The engine's own
`canonical_next_command` for a gated blocker was
`saipen recover resolve-blocker "<decision>"`, so the operator's only sanctioned
route classified as an ordinary SHELL effect and was refused under the very
invalid state it was printed to repair.

Widening the grammar would reopen the hole the grammar exists to close, so the
COMMAND was made to fit: `resolve-blocker` now reads its decision as the tokens
up to the next flag, and the printed form carries no quotes.

This test harvests the command literals out of the engine rather than restating
them, so a new unexecutable instruction fails here rather than in somebody's
frozen session. Placeholders are substituted first: a template is guidance, and
what has to classify is the command an operator actually types.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import guard_events  # noqa: E402

ENGINE = TOOLS / "saipen_engine"
#: A quoted string literal that begins a `saipen ...` command line.
_LITERAL = re.compile(r"""["'](saipen [^"'\n]{0,160})["']""")
#: `<placeholder>` and `{interpolation}` both stand for a value the operator or
#: the engine supplies; neither is what gets typed.
_PLACEHOLDER = re.compile(r"<[^<>]{1,40}>|\{[^{}]{0,60}\}")
#: What a substituted placeholder becomes: inside the canonical argument
#: alphabet, so substitution itself never decides the verdict.
_FILLER = "T-1"
#: Literals that are prose or a bare prefix, not a command anyone runs.
_NOT_COMMANDS = frozenset({"saipen", "saipen ...", "saipen push + build ccc"})


def harvested() -> dict[str, set[str]]:
    """Every `saipen ...` command literal in the engine, by source file."""
    found: dict[str, set[str]] = {}
    for path in sorted(ENGINE.glob("*.py")):
        for match in _LITERAL.finditer(path.read_text(encoding="utf-8")):
            found.setdefault(match.group(1).strip(), set()).add(path.name)
    return found


class CanonicalCommandReachabilityTests(unittest.TestCase):
    def test_the_harvest_actually_finds_commands(self):
        """Guard: an empty harvest would pass this file silently."""
        found = harvested()
        self.assertGreater(len(found), 10, found)
        self.assertIn("saipen recover resolve-blocker <decision>", found)

    def test_every_printed_command_classifies_as_canonical(self):
        unreachable = []
        for literal, sources in sorted(harvested().items()):
            if literal in _NOT_COMMANDS:
                continue
            typed = _PLACEHOLDER.sub(_FILLER, literal).strip()
            if guard_events._saipen_cli_verb(typed) is None:
                unreachable.append(f"{typed!r} (from {', '.join(sorted(sources))})")
        self.assertEqual(
            unreachable,
            [],
            "the engine prints commands its own guard refuses, so the route it "
            "names is unreachable from the state that names it: "
            + "; ".join(unreachable),
        )

    def test_the_blocker_decision_is_reachable_with_real_words(self):
        """The field shape: a multi-word decision, and the flag it combines with."""
        for command in (
            "saipen recover resolve-blocker operator approved the rebind",
            "saipen recover resolve-blocker approved --apply-approved-repair " + "a" * 64,
            "saipen recover normalize-log",
        ):
            with self.subTest(command=command):
                self.assertEqual(
                    guard_events._saipen_cli_verb(command),
                    "recover",
                    f"{command!r} is not reachable as a canonical operation",
                )

    def test_quoting_still_disqualifies_the_line(self):
        """The grammar did not move; the command was made to fit it."""
        for command in (
            'saipen recover resolve-blocker "quoted decision"',
            "saipen recover resolve-blocker 'quoted decision'",
            "saipen recover && rm -rf .saipen",
            "saipen status | tee out.txt",
        ):
            with self.subTest(command=command):
                self.assertIsNone(guard_events._saipen_cli_verb(command), command)


class BlockerDecisionParsingTests(unittest.TestCase):
    """The CLI reads what the printed form now tells an operator to type."""

    def parse(self, argv: list[str]) -> str | None:
        """Run `_recover`'s argument scan far enough to see the decision."""
        import saipen as cli

        captured: dict[str, object] = {}
        original = cli._emit
        cli._emit = lambda record, as_json: captured.setdefault("record", record)
        try:
            cli._recover(Path("."), argv, True, dry_run=True)
        except Exception as exc:  # pragma: no cover - the scan may refuse later
            captured.setdefault("raised", repr(exc))
        finally:
            cli._emit = original
        return str(captured.get("record", captured.get("raised", "")))

    def test_a_multi_word_decision_needs_no_quotes(self):
        reported = self.parse(["resolve-blocker", "operator", "approved", "the", "rebind"])
        self.assertNotIn("missing decision text", reported)
        self.assertNotIn("requires non-empty decision", reported)

    def test_a_missing_decision_still_refuses(self):
        reported = self.parse(["resolve-blocker"])
        self.assertIn("requires non-empty decision", reported)

    def test_a_following_flag_is_not_swallowed_into_the_decision(self):
        reported = self.parse(
            ["resolve-blocker", "approved", "--apply-approved-repair", "a" * 64]
        )
        self.assertNotIn("unknown recover argument", reported)


if __name__ == "__main__":
    unittest.main(verbosity=2)
