"""T-1910: refuse a proposed LOG event by its input, not a nonexistent line."""

from __future__ import annotations

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.log import MAX_NEW_EVENT_BYTES, parse_log_line, prepare_bounded_event  # noqa: E402
from saipen_engine.operations import checkpoint  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_orchestration_repair import OrchestrationFixture  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


class LogInputDiagnosticTests(OrchestrationFixture):
    def canonical(self, root: Path) -> dict[str, bytes]:
        return {name: (root / ".saipen" / name).read_bytes()
                for name in ("STATE.md", "BOARD.md", "LOG.md")}

    def test_checkpoint_names_the_message_character_and_writes_nothing(self):
        root = self.make_project(active=True)
        before = self.canonical(root)
        result = checkpoint(root, "tester", "RUN", "T-7", "first\nsecond")
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(result.code, "VALIDATION_FAILED")
        detail = result.to_dict().get("detail") or result.to_dict().get("message", "")
        self.assertIn("message", detail)
        self.assertIn(r"\n", detail)
        self.assertIn("U+000A", detail)
        self.assertNotIn("LOG.md:", detail)
        self.assertNotIn("first", detail)
        self.assertEqual(before, self.canonical(root))

    def test_each_physical_line_separator_has_an_exact_diagnostic(self):
        for separator in ("\r", "\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029"):
            with self.subTest(codepoint=ord(separator)):
                root = self.make_project(active=True)
                before = self.canonical(root)
                result = checkpoint(root, "tester", "RUN", "T-7", "a" + separator + "b")
                self.assertFalse(result.ok, result.to_dict())
                self.assertEqual(result.code, "VALIDATION_FAILED")
                self.assertIn(f"U+{ord(separator):04X}", str(result.to_dict()))
                self.assertEqual(before, self.canonical(root))

    def prepare(self, root: Path, **fields):
        args = {"ticket": "T-7", "agent": "tester", "now": "25.10.26 14:00",
                "op_id": "checkpoint-fixture"}
        args.update(fields)
        return prepare_bounded_event(root, 1, "RUN", args.pop("message", "ordinary work"), **args)

    def test_metadata_delimiters_name_the_field_and_character(self):
        root = self.make_project(active=True)
        for field in ("agent", "ticket", "op_id"):
            with (
                self.subTest(field=field),
                self.assertRaisesRegex(ValueError, field + r".*U\+005D"),
            ):
                self.prepare(root, **{field: "T-bad]suffix"})
        with self.assertRaisesRegex(ValueError, "now"):
            self.prepare(root, now="2026-10-25T14:00Z")

    def test_legal_message_punctuation_and_unicode_still_round_trip(self):
        root = self.make_project(active=True)
        message = 'work [case] {value}: "quoted" \\path \u2013 valmis'
        _event, line, targets = self.prepare(root, message=message)
        self.assertEqual(parse_log_line(line)["text"], message)
        self.assertEqual(targets, ())

    def test_oversized_multiline_detail_keeps_its_existing_lossless_route(self):
        root = self.make_project(active=True)
        message = "x" * MAX_NEW_EVENT_BYTES + "\nfull detail"
        _event, line, targets = self.prepare(root, message=message)
        self.assertIsNotNone(parse_log_line(line))
        self.assertEqual(len(line.splitlines()), 1)
        self.assertTrue(any(message.encode("utf-8") in target.content for target in targets))


if __name__ == "__main__":
    import unittest

    unittest.main()
