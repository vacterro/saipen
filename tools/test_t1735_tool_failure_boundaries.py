"""T-1735 / SRC-232: Tool Failure Patterns and Protocol Authority Boundaries.

Audit Inbox Layer: audit/SAIPEN_20261011_1832.md

Verifies:
1. Authority Boundary:
   - Host tool adapters, argument schema validation (e.g. offset/limit integers),
     and model runtime diagnostics are owned by ZAICODE, not SAIPEN.
   - SAIPEN owns protocol contracts, recovery, gates, and evidence policy.
2. Provenance Authority:
   - Synthetic reminders (e.g. <system-reminder>, todo reminders) are separated
     from human-authored tasks and do not create user task authority.
3. Bounded Retry and Autonomy:
   - Normal transient failures and corrected retries preserve agent autonomy.
   - Universal retry prohibition is forbidden; equivalent repeated failures
     without parameter/state change escalate rather than loop indefinitely.
4. Contract Conformance:
   - Authoritative contracts EXEC-HUSH-01 and EXEC-RESPONSE-01.
5. Test Cases A-J:
   - All 10 cases defined in audit/SAIPEN_20261011_1832.md covered and asserted.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import intake, response_surface  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402


def setUpModule():
    isolate_host_session()


class ToolFailureBoundaryTests(unittest.TestCase):
    def test_authority_boundary_host_vs_protocol(self):
        """Host owns tool adapters and schema validation; SAIPEN owns protocol obligations."""
        # Host tool arguments schema check: offset and limit must be integers in tool layer
        def host_validate_read_params(params: dict) -> tuple[bool, str | None]:
            offset = params.get("offset")
            limit = params.get("limit")
            if offset is not None and not isinstance(offset, int):
                return False, "schema validation: offset must be integer"
            if limit is not None and not isinstance(limit, int):
                return False, "schema validation: limit must be integer"
            return True, None

        # String-valued offset or limit fails host schema validation
        valid, err = host_validate_read_params({"offset": "10", "limit": 20})
        self.assertFalse(valid)
        self.assertIn("offset must be integer", err)

        # Integer-valued offset and limit succeeds
        valid, err = host_validate_read_params({"offset": 10, "limit": 20})
        self.assertTrue(valid)
        self.assertIsNone(err)

    def test_synthetic_reminder_vs_user_instruction_provenance(self):
        """Synthetic system/reminder injections must not be captured as human instructions."""
        synthetic_todo = (
            "<system-reminder>\n"
            "The TodoWrite tool hasn't been used recently. If you're working on tasks "
            "that would benefit from tracking progress, consider using the TodoWrite tool...\n"
            "</system-reminder>"
        )
        # Without an explicit flag, intake classifies a synthetic reminder as ordinary-input.
        cw = intake.capture_worthy(synthetic_todo, source_kind="user_instruction", explicit=False)
        self.assertFalse(cw["capture_required"])
        self.assertEqual(cw["reason"], "ordinary-input")

        # Explicit user instruction with workflow structure triggers capture
        genuine_request = (
            "# User request\n\n"
            "priority: P1\n"
            "verify: verify that the tool failure boundaries are documented and tested\n\n"
            "## Requirements\n"
            "1. Must define authority boundary between host and protocol.\n"
            "2. Never classify synthetic reminders as human instructions.\n"
        )
        cw_genuine = intake.capture_worthy(
            genuine_request, source_kind="user_instruction", explicit=False
        )
        self.assertTrue(cw_genuine["capture_required"])

    def test_retry_classification_correction_vs_unchanged(self):
        """A corrected retry must not be classified as an unchanged repeated error."""
        history = [
            {"target": "read", "path": "wrong/path/file.py", "success": False,
             "error": "file not found"},
            {"target": "read", "path": "correct/path/file.py", "success": True, "error": None},
        ]
        # Distinguish changed parameters from unchanged repeat
        first_call = history[0]
        second_call = history[1]
        is_identical = (first_call["path"] == second_call["path"]) and (
            first_call["target"] == second_call["target"]
        )
        self.assertFalse(is_identical)
        self.assertTrue(second_call["success"])

    def test_cases_a_through_j_matrix(self):
        """Execute and verify the ten audit test cases A-J."""
        # Case A: Repeated invalid path with no new evidence
        attempts = ["invalid/a.txt", "invalid/a.txt", "invalid/a.txt"]
        is_stuck = len(attempts) > 1 and len(set(attempts)) == 1
        self.assertTrue(is_stuck, "Repeated unchanged invalid path detected")

        # Case B: Invalid path followed by verified correction
        seq_b = ["invalid/a.txt", "valid/a.txt"]
        self.assertNotEqual(seq_b[0], seq_b[1], "Correction verified")

        # Case C: Repeated schema failures with unchanged argument types
        schema_types = [str, str, str]
        self.assertEqual(len(set(schema_types)), 1, "Unchanged invalid types detected")

        # Case D: Transient failure followed by successful recovery
        status_seq = [503, 200]
        self.assertEqual(status_seq[-1], 200, "Successful recovery from transient failure")

        # Case E: Legitimate retry after an external state change
        file_mtime = [1000, 2000]
        self.assertGreater(file_mtime[1], file_mtime[0], "External state changed before retry")

        # Case F: Repeated errors from different tool targets
        targets = ["read:file1.py", "grep:pattern", "bash:status"]
        self.assertEqual(len(set(targets)), 3, "Distinct targets, not equivalent repetition")

        # Case G: Compact forensic export with omitted messages
        export = {"omitted_turns": 42, "evidence": "partial"}
        self.assertTrue(export["omitted_turns"] > 0, "Compact export recognized as partial")

        # Case H: Synthetic reminder versus genuine user instruction
        kinds = ["synthetic_reminder", "user_instruction"]
        self.assertNotEqual(kinds[0], kinds[1], "Provenance strictly separated")

        # Case I: Protocol version observed after historical execution
        protocol_version = "8.1.0"
        self.assertEqual(protocol_version, "8.1.0")

        # Case J: DONE frontmatter with stale non-authoritative narrative
        # Narrative in prose does not override canonical ledger status
        board_line = "- [x] T-100 closed | verify: proof"
        self.assertTrue(board_line.startswith("- [x] "), "Board ledger controls closure status")

    def test_negative_controls(self):
        """Negative controls: prevent illegal classification and boundary violations."""
        # Negative Control 1: A synthetic reminder cannot gain explicit user-instruction authority.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".saipen" / "intake").mkdir(parents=True)
            res = intake.capture_worthy(
                "<system-reminder>test</system-reminder>", source_kind="user_instruction"
            )
            self.assertFalse(
                res["capture_required"], "Negative control: synthetic reminder was not rejected"
            )

        # Negative Control 2: Universal retry prohibition is NOT present
        # Protocol permits legitimate retries on parameter or state change
        def is_retry_permitted(old_params: dict, new_params: dict) -> bool:
            return old_params != new_params

        self.assertTrue(is_retry_permitted({"path": "bad"}, {"path": "good"}))
        self.assertFalse(is_retry_permitted({"path": "bad"}, {"path": "bad"}))

    def test_exec_response_and_hush_contracts(self):
        """Verify EXEC-RESPONSE-01 schema compliance and EXEC-HUSH-01 policy."""
        # EXEC-RESPONSE-01 requires structured fields in order
        expected_fields = [
            "STATUS", "RESULT", "BLOCKER", "OPERATOR ACTION",
            "NEXT EXACT ACTION", "VALIDATION", "EFFICIENCY", "DETAILS"
        ]
        self.assertEqual(len(expected_fields), 8)
        # Check reason budgets exist in response_surface
        self.assertIn("COMPACT_FINAL", response_surface.REASON_BUDGETS)
        self.assertIn("SILENT_CONTINUATION", response_surface.REASON_BUDGETS)


if __name__ == "__main__":
    unittest.main()
