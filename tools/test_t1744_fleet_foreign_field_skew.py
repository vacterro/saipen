"""T-1744: Fleet preflight BOARD_FOREIGN_FIELD saipen_version skew guard."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
REPO_ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.fleet import CLASS_BLOCKED, CLASS_SAFE, preflight  # noqa: E402
from saipen_engine.paths import project_lineage_identity  # noqa: E402
from test_guard_hostile_matrix import fresh_project  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


def _foreign_project(field: str = "source: saihunt HUNT-001", **state) -> Path:
    fields = {
        "phase": "DONE",
        "task": "none",
        "next_action": "saipen continue",
        "agent": "test-agent",
    }
    fields.update(state)
    root = fresh_project(**fields)
    row = f"- [ ] T-0001 [P1] Remediate hunt defects | verify: regression passes | {field}\n"
    board = "## DOING\n## TODO\n" + row + "## DONE\n## BLOCKED\n"
    (root / ".saipen" / "BOARD.md").write_text(board, encoding="utf-8")
    return root


class FleetForeignFieldSkewTests(unittest.TestCase):
    def test_preflight_on_project_newer_than_runtime_is_blocked_and_names_newer_runtime(self):
        root = _foreign_project()
        state_path = root / ".saipen" / "STATE.md"
        text = state_path.read_text(encoding="utf-8")
        state_path.write_text(
            text.replace("saipen_version: 7", "saipen_version: 99", 1),
            encoding="utf-8",
        )
        with patch("saipen_engine.state.running_protocol_major", return_value=8):
            result = preflight(
                explicit_root=root,
                host_root=root,
                host_lineage=project_lineage_identity(root),
            )
        self.assertNotEqual(result["classification"], CLASS_SAFE, result)
        self.assertEqual(result["classification"], CLASS_BLOCKED, result)
        self.assertEqual(result["reason_code"], "BOARD_FOREIGN_FIELD", result)
        self.assertIn("newer runtime", result["canonical_next_command"])
        self.assertIn("newer runtime", result["instruction"])
        self.assertIn("newer runtime", result["reason"])

    def test_preflight_on_project_at_or_below_major_stays_safe_naming_ticket_compact(self):
        root = _foreign_project()
        with patch("saipen_engine.state.running_protocol_major", return_value=7):
            result = preflight(
                explicit_root=root,
                host_root=root,
                host_lineage=project_lineage_identity(root),
            )
        self.assertEqual(result["classification"], CLASS_SAFE, result)
        self.assertEqual(result["reason_code"], "BOARD_FOREIGN_FIELD", result)
        self.assertEqual(result["canonical_next_command"], "saipen ticket compact T-0001")
        self.assertIn("saipen ticket compact", result["instruction"])


if __name__ == "__main__":
    unittest.main()
