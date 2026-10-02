"""T-1535: canonical ticket intake can arm the regression-pair gate."""

from __future__ import annotations

import contextlib
import io
import json
import re
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen import main as saipen_main  # noqa: E402
from saipen_engine.state import style_contract_token  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_t1363_zero_manual_entry import board_of, healthy  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


def current_project(case: unittest.TestCase) -> Path:
    root = healthy(case)
    state_path = root / ".saipen" / "STATE.md"
    state = state_path.read_text(encoding="utf-8")
    marker = style_contract_token((ROOT / "saipen" / "STYLE.md").read_text(encoding="utf-8"))
    state, count = re.subn(r"(?m)^style_contract:\s*\S+\s*$", f"style_contract: {marker}", state)
    case.assertEqual(count, 1, "fixture must carry exactly one style contract marker")
    state_path.write_text(state, encoding="utf-8")
    return root


def cli(root: Path, *args: str) -> tuple[int, dict, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = saipen_main(
            ["--json", "--project-root", str(root), "--agent", "test-agent", *args]
        )
    text = stdout.getvalue() + stderr.getvalue()
    return code, json.loads(stdout.getvalue()), text


class RegressionRequirementIntakeTests(unittest.TestCase):
    def test_ticket_add_persists_required_regression_flag(self):
        root = current_project(self)
        code, payload, output = cli(
            root,
            "ticket",
            "add",
            "P2",
            "fix cache invalidation",
            "--verify",
            "cache invalidates after update",
            "--regression",
            "required",
        )
        self.assertEqual(code, 0, output)
        fields = board_of(root)["tickets"][payload["ticket"]]["fields"]
        self.assertEqual(fields["regression"], "required")

    def test_compacted_ticket_keeps_required_regression_flag_live(self):
        root = current_project(self)
        description = "investigate cache " + ("invalidation behavior " * 90)
        code, payload, output = cli(
            root,
            "ticket",
            "add",
            "P2",
            description,
            "--verify",
            "the invalidation acceptance passes",
            "--regression",
            "required",
        )
        self.assertEqual(code, 0, output)
        ticket = board_of(root)["tickets"][payload["ticket"]]
        self.assertEqual(ticket["fields"]["regression"], "required")
        self.assertTrue(ticket["fields"].get("detail_ref"))

    def test_missing_verify_route_retains_regression_requirement(self):
        root = current_project(self)
        code, payload, output = cli(
            root,
            "ticket",
            "add",
            "P2",
            "fix cache invalidation",
            "--regression",
            "required",
        )
        self.assertEqual(code, 1, output)
        self.assertEqual(payload["code"], "INCOMPLETE_TICKET")
        self.assertIn("--regression required", payload["canonical_next_command"])
        self.assertIn("--verify", payload["canonical_next_command"])

    def test_unmarked_ticket_remains_unmarked(self):
        root = current_project(self)
        code, payload, output = cli(
            root,
            "ticket",
            "add",
            "P2",
            "ordinary improvement",
            "--verify",
            "ordinary behavior passes",
        )
        self.assertEqual(code, 0, output)
        fields = board_of(root)["tickets"][payload["ticket"]]["fields"]
        self.assertNotIn("regression", fields)


if __name__ == "__main__":
    unittest.main(verbosity=2)