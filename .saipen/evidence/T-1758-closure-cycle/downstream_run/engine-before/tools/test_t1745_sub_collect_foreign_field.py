"""T-1745: Prevent hand-written sub-agent collects and refuse foreign-field BOARD in sub_collect."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO_ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.subs import sub_collect, sub_spawn  # noqa: E402
from test_guard_hostile_matrix import fresh_project  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


def _section_4_text(doc_path: Path) -> str:
    text = doc_path.read_text(encoding="utf-8")
    start = text.index("## 4. Handoff")
    end = text.index("## 5. MANIFEST.md", start)
    return text[start:end]


class ProtocolSection4CanonicalCollectTests(unittest.TestCase):
    def test_section_4_names_only_canonical_collection_commands_and_forbids_hand_edits(self):
        for rel in (
            Path("extensions/subs/PROTOCOL.md"),
            Path(".saipen/extensions/subs/PROTOCOL.md"),
        ):
            path = REPO_ROOT / rel
            if not path.is_file():
                continue
            sec4 = _section_4_text(path)
            self.assertIn("saipen collect <producer>", sec4, str(rel))
            self.assertIn("saipen sub collect", sec4, str(rel))
            self.assertIn("NEVER by hand-editing `BOARD.md` or `LOG.md`", sec4, str(rel))
            self.assertIn(
                "`source: <name>-###` is ONLY the `_shared/inbox.md` row shape",
                sec4,
                str(rel),
            )
            self.assertIn("saipen ticket compact <T-###>", sec4, str(rel))
            self.assertNotIn("Write the taxonomy text as", sec4, str(rel))


class SubCollectForeignFieldRefusalTests(unittest.TestCase):
    def test_sub_collect_on_board_with_foreign_field_refuses_with_compact_and_writes_nothing(self):
        root = fresh_project(
            phase="DONE",
            task="none",
            next_action="saipen continue",
            agent="test-agent",
        )
        spawned = sub_spawn(root, "saihunt", str(REPO_ROOT), agent="test-agent")
        self.assertTrue(spawned.ok, spawned.to_dict())

        board_path = root / ".saipen" / "BOARD.md"
        log_path = root / ".saipen" / "LOG.md"
        state_path = root / ".saipen" / "STATE.md"
        manifest_path = root / ".saipen" / "extensions" / "subs" / "MANIFEST.md"

        foreign_row = (
            "- [ ] T-0199 [P2] Review hunt finding"
            " | verify: regression test passes"
            " | source: saihunt-019\n"
        )
        board_path.write_text(
            "## DOING\n## TODO\n" + foreign_row + "## DONE\n## BLOCKED\n",
            encoding="utf-8",
        )

        before = {
            "board": board_path.read_bytes(),
            "log": log_path.read_bytes(),
            "state": state_path.read_bytes(),
            "manifest": manifest_path.read_bytes(),
        }

        result = sub_collect(root, agent="test-agent")
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["code"], "VALIDATION_FAILED", result)
        self.assertEqual(
            result.get("canonical_next_command"),
            "saipen ticket compact T-0199",
            result,
        )
        self.assertIn("saipen ticket compact T-0199", result.message, result)

        after = {
            "board": board_path.read_bytes(),
            "log": log_path.read_bytes(),
            "state": state_path.read_bytes(),
            "manifest": manifest_path.read_bytes(),
        }
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
