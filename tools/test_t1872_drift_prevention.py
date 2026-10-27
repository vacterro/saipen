"""Unit tests for T-1872 / SRC-301:
Drift Prevention & Contractual LIVE Gate / Unblock Verification.

Verifies:
1. Attempting to satisfy a LIVE acceptance clause with a unit test command
   returns EVIDENCE_SCOPE_TOO_WEAK (DRIFT-001/003/007).
2. Authentic live vendor receipts satisfy LIVE acceptance.
3. Unblocking an operator/vendor blocked ticket without operator authority
   or proof is refused (DRIFT-002).
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from saipen_engine import intake, operations


def _init_saipen_repo(root: Path, ticket: str = "T-001") -> None:
    saipen_dir = root / ".saipen"
    saipen_dir.mkdir(parents=True, exist_ok=True)
    (saipen_dir / "STATE.md").write_text(
        f"---\nphase: INIT\ntask: {ticket}\nnext_action: idle\nblocker: none\n"
        "agent: saipen-cli\nmode: full\nsaipen_version: 7\nschema_version: 3\nlast_event: 1\n"
        "updated: '2026-10-24T00:00:00Z'\n---\n",
        encoding="utf-8",
    )
    (saipen_dir / "LOG.md").write_text(
        "# LOG\n\n- 24.10.26 00:00 [E-1] [parent: none] [agent: saipen-cli] INIT\n",
        encoding="utf-8",
    )
    board_text = (
        f"# BOARD\n\n## DOING\n- [ ] {ticket} [P1] Active task\n\n"
        "## TODO\n\n## BLOCKED\n\n## DONE\n"
    )
    (saipen_dir / "BOARD.md").write_text(board_text, encoding="utf-8")


class TestT1872DriftPrevention(unittest.TestCase):
    def test_live_acceptance_refuses_unit_test(self):
        """DRIFT-001/003: unit test cannot satisfy LIVE acceptance clause."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _init_saipen_repo(root, "T-001")
            cap = intake.capture(
                root,
                "Requirement 1: perform live vendor acceptance of composer copy/paste",
                source_kind="user_instruction",
            )
            receipt = cap["receipt"]
            intake.ensure_request_clause(root, receipt)

            # Attempt to dispose with unit test command
            result = intake.set_disposition(
                root,
                receipt,
                f"{receipt}:R001",
                "VERIFIED",
                work="T-001",
                evidence="E-001",
                verification="python -m unittest tests/test_foo.py -> PASS",
            )
            self.assertFalse(result["ok"])
            self.assertEqual(result["code"], "EVIDENCE_SCOPE_TOO_WEAK")
            self.assertIn("live vendor/host", result["detail"])

    def test_live_acceptance_accepts_live_receipt(self):
        """Authentic live receipt satisfies LIVE acceptance clause."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _init_saipen_repo(root, "T-001")
            cap = intake.capture(
                root,
                "Requirement 1: perform live vendor acceptance of composer copy/paste",
                source_kind="user_instruction",
            )
            receipt = cap["receipt"]
            intake.ensure_request_clause(root, receipt)

            # Dispose with genuine live vendor probe evidence
            result = intake.set_disposition(
                root,
                receipt,
                f"{receipt}:R001",
                "VERIFIED",
                work="T-001",
                evidence="E-001 (live_receipt: vendor_session_probe.ps1)",
                verification="vendor_session_probe.ps1 -> PASS (observed clipboard copy/paste)",
            )
            self.assertTrue(result["ok"])
            self.assertEqual(result["code"], "COVERAGE_UPDATED")

    def test_unblock_refuses_agent_assertion_for_operator_block(self):
        """DRIFT-002: agent cannot arbitrarily unblock ticket blocked on operator decision."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            saipen_dir = root / ".saipen"
            saipen_dir.mkdir(parents=True)
            (saipen_dir / "STATE.md").write_text(
                "---\nphase: INIT\ntask: none\nnext_action: idle\nblocker: none\n"
                "agent: saipen-cli\nmode: full\nsaipen_version: 7\nschema_version: 3\n"
                "last_event: 1\nupdated: '2026-10-24T00:00:00Z'\n---\n",
                encoding="utf-8",
            )
            (saipen_dir / "LOG.md").write_text(
                "# LOG\n\n- 24.10.26 00:00 [E-1] [parent: none] [agent: saipen-cli] INIT\n",
                encoding="utf-8",
            )
            board_text = (
                "# BOARD\n\n"
                "## DOING\n\n"
                "## TODO\n\n"
                "## BLOCKED\n\n"
                "- [ ] T-999 [P1] Vendor integration | "
                "blocker: WAIT_USER_DECISION: needs operator\n\n"
                "## DONE\n"
            )
            (saipen_dir / "BOARD.md").write_text(board_text, encoding="utf-8")

            res = operations.ticket_move(
                root,
                "unblock",
                "T-999",
                "saipen-cli",
                payload="agent decided to unblock without operator",
            )
            self.assertFalse(res.ok)
            self.assertEqual(res.code, "WAIT_USER_DECISION")
            self.assertIn("unblocking requires verified operator authority", res.message)


if __name__ == "__main__":
    unittest.main()
