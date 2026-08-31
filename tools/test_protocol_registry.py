"""Semantic-baseline and machine-registry regressions (SRC-010)."""

from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import commands, errors, phases, state  # noqa: E402
from saipen_engine.registry import load_registry  # noqa: E402


ROOT = TOOLS.parent
PROTOCOL = ROOT / "saipen"
GOLDEN = ROOT / "tests" / "protocol_semantic_golden.json"
OWNER_RE = re.compile(r"<!-- RULE-OWNER: ([A-Z][A-Z0-9-]+) -->")


class ProtocolRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = load_registry(PROTOCOL)

    def test_runtime_closed_sets_derive_from_registry(self):
        reg = self.registry
        self.assertEqual(commands.load_shortcut_table(PROTOCOL), reg["shortcuts"])
        self.assertEqual(commands.CYRILLIC_CONFUSABLE_MAP, reg["cyrillic_confusables"])
        self.assertEqual(phases.VALID_TRANSITIONS, reg["phases"]["valid_transitions"])
        self.assertEqual(set(phases.ALL_PHASES), set(reg["phases"]["all"]))
        self.assertEqual(set(errors.CODES), set(reg["error_codes"]))
        self.assertEqual(tuple(state.STATE_REQUIRED_FIELDS), tuple(reg["state"]["required_fields"]))
        self.assertEqual(set(state.STATE_KNOWN_FIELDS), set(reg["state"]["known_fields"]))
        self.assertEqual(tuple(state.WAIT_CATEGORIES), tuple(reg["wait_categories"]))

    def test_prose_rewrite_cannot_change_shortcut_behavior(self):
        expected = commands.load_shortcut_table(PROTOCOL)
        with tempfile.TemporaryDirectory(prefix="saipen-registry-prose-") as td:
            root = Path(td)
            (root / "REGISTRY.json").write_text(
                json.dumps(self.registry, ensure_ascii=False), encoding="utf-8"
            )
            (root / "CORE.md").write_text("entirely rewritten prose\n", encoding="utf-8")
            (root / "COMMANDS.md").write_text("different words\n", encoding="utf-8")
            self.assertEqual(commands.load_shortcut_table(root), expected)

    def test_golden_command_and_chain_snapshots(self):
        golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
        table = commands.load_shortcut_table(PROTOCOL)
        for raw, expected in golden["command_resolution"].items():
            actual = commands.resolve_compound_command(raw, table=table)
            projection = [
                {"kind": item["kind"], "command": item["command"]}
                for item in actual
            ]
            self.assertEqual(projection, expected, raw)
        chain = golden["chain_disposition"]
        self.assertEqual(commands.chain_disposition(chain["input"]), chain["output"])

    def test_semantic_facts_name_owner_and_test(self):
        facts = self.registry["semantic_baseline"]["facts"]
        owners = self.registry["rule_owners"]
        self.assertEqual(set(facts), set(owners))
        for rule_id, fact in facts.items():
            self.assertEqual(fact["owner"], owners[rule_id], rule_id)
            self.assertTrue(fact["test"], rule_id)
            self.assertTrue(fact["subject"], rule_id)

    def test_one_rule_one_owner(self):
        declared: dict[str, list[str]] = {}
        for path in sorted(PROTOCOL.rglob("*.md")):
            if path.name == "CONFORMANCE.md":
                text = path.read_text(encoding="utf-8-sig")
            else:
                text = path.read_text(encoding="utf-8-sig")
            rel = path.relative_to(ROOT).as_posix()
            for rule_id in OWNER_RE.findall(text):
                declared.setdefault(rule_id, []).append(rel)
        expected = self.registry["rule_owners"]
        self.assertEqual(set(declared), set(expected))
        for rule_id, owner in expected.items():
            self.assertEqual(declared[rule_id], [owner], rule_id)

    def test_all_16_phase_documents_exist(self):
        expected = set(self.registry["phases"]["all"])
        actual = {path.stem.upper() for path in (PROTOCOL / "phases").glob("*.md")}
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
