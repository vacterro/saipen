"""Regression coverage for current STYLE-derived test fixtures."""

from __future__ import annotations

import ast
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.state import parse_frontmatter, state_contract_errors  # noqa: E402
from test_fixture_support import CURRENT_STYLE_CONTRACT, current_style_contract  # noqa: E402


CURRENT_STATE = f"""---
phase: BUILD
task: T-500
next_action: "PHASE BUILD T-500"
blocker: ""
transition_from: PLAN
saipen_version: 7
schema_version: 3
last_event: 3
style_contract: {CURRENT_STYLE_CONTRACT}
mode: full
updated: 2026-09-15T00:00:00Z
agent: test-agent
---
"""


class FixtureStyleAuthorityTests(unittest.TestCase):
    def _errors(self, text: str, token: str) -> list[str]:
        fields, error = parse_frontmatter(text)
        self.assertIsNone(error, error)
        return state_contract_errors(
            fields, style_token=token, current_schema_version=3
        )

    def test_current_fixture_uses_running_style_contract(self) -> None:
        self.assertEqual(CURRENT_STYLE_CONTRACT, current_style_contract())
        self.assertEqual(self._errors(CURRENT_STATE, CURRENT_STYLE_CONTRACT), [])

    def test_fixture_tracks_a_changed_install_style_without_mutating_it(self) -> None:
        style_path = TOOLS.parent / "saipen" / "STYLE.md"
        original = style_path.read_bytes()
        with tempfile.TemporaryDirectory(prefix="style-fixture-") as temporary:
            root = Path(temporary)
            target = root / "saipen" / "STYLE.md"
            target.parent.mkdir()
            shutil.copyfile(style_path, target)
            changed = target.read_text(encoding="utf-8").replace(
                "reply_language: et", "reply_language: en", 1
            )
            target.write_text(changed, encoding="utf-8")

            token = current_style_contract(root)
            self.assertNotEqual(token, CURRENT_STYLE_CONTRACT)
            fixture = CURRENT_STATE.replace(CURRENT_STYLE_CONTRACT, token)
            self.assertEqual(self._errors(fixture, token), [])

        self.assertEqual(style_path.read_bytes(), original)

    def test_stale_fixture_still_fails_exact_style_check(self) -> None:
        fixture = CURRENT_STATE.replace(CURRENT_STYLE_CONTRACT, "ded-00000000")
        errors = self._errors(fixture, CURRENT_STYLE_CONTRACT)
        self.assertTrue(any("style_contract" in error for error in errors))

    def test_historical_incident_fixture_keeps_its_recorded_marker(self) -> None:
        """The incident fixture replays a real STATE; its shape is pinned.

        The `style_contract` line is excluded from the pinned hash on purpose.
        It is a property of the INSTALLED `STYLE.md`, not of the E-7925
        incident the fixture replays, and nothing under test here reads it --
        so hashing it coupled a changelog edit in a voice document to a
        cold-recovery regression, and made a documentation edit red as loudly
        as a real defect. Every field the recovery code actually parses stays
        pinned: phase, task, next_action, transition_from, last_event, agent,
        execution_intent, goal_waves and goal_tickets.
        """
        source = (TOOLS / "test_cold_recovery.py").read_text(encoding="utf-8")
        module = ast.parse(source)
        incident = next(
            node.value
            for node in module.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "INCIDENT_STATE"
                for target in node.targets
            )
        )
        self.assertIsInstance(incident, ast.JoinedStr, type(incident))
        segment = ast.get_source_segment(source, incident) or ""
        self.assertIn("style_contract: {LIVE_STYLE_CONTRACT}", segment)
        # Every field the recovery code actually parses stays pinned, so a
        # change to the replayed incident still reds here.
        for pinned in (
            "phase: DONE",
            "task: none",
            'next_action: "PHASE SCOUT T-1446"',
            'blocker: ""',
            "transition_from: BUILD",
            "saipen_version: 8",
            "schema_version: 3",
            "last_event: 7925",
            "agent: astra",
            "mode: full",
            'updated: "2026-09-21T21:43:02Z"',
            "execution_intent: goal",
            "goal_waves: 1",
            "goal_tickets: 0",
        ):
            self.assertIn(pinned, segment, pinned)
        # The interpolated value is the live installed contract, so a STYLE
        # edit can never make this fixture structurally invalid.
        self.assertRegex(CURRENT_STYLE_CONTRACT, r"^ded-[0-9a-f]{8}$", CURRENT_STYLE_CONTRACT)

    def test_schema_v3_missing_style_contract_still_fails(self) -> None:
        missing = CURRENT_STATE.replace(
            f"style_contract: {CURRENT_STYLE_CONTRACT}\n", ""
        )
        errors = self._errors(missing, CURRENT_STYLE_CONTRACT)
        self.assertTrue(any("style_contract" in error for error in errors))

    def test_style_contract_comparison_remains_exact(self) -> None:
        self.assertEqual(self._errors(CURRENT_STATE, CURRENT_STYLE_CONTRACT), [])
        wrong = CURRENT_STATE.replace(
            CURRENT_STYLE_CONTRACT, CURRENT_STYLE_CONTRACT + "x"
        )
        errors = self._errors(wrong, CURRENT_STYLE_CONTRACT)
        self.assertTrue(any("style_contract" in error for error in errors))