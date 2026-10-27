"""SRC-026:R005 (T-1304): a verifier prerequisite that fails is reported, not dereferenced.

The clause: "a verifier prerequisite failure must not be converted into None
and then dereferenced". The journal half was repaired earlier -- `_run_verifier`
turns a raising verifier into a refusal (RaisingVerifierTests) -- and that
repair hid the other half instead of fixing it: `fast_check.validate_project`
still caught a history it could not read, set it to None, and handed None to
the ledger contract. Measured before this change: an active LOG carrying a
BOM, or a `.saipen/logs` that is a file, raised `AttributeError: 'NoneType'
object has no attribute 'illegal_lines'`; through the journal the operator was
told a verifier raised AttributeError, and never why.

Held here: the post-write verifier returns the cause as a finding; the journal
boundary carries that finding; an operation that meets it after APPLY settles
on a structured CONFLICT that names it; and once the cause is gone, recovery
finishes the same operation.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import journal as journal_mod  # noqa: E402
from saipen_engine import log as log_mod  # noqa: E402
from saipen_engine.fast_check import validate_project  # noqa: E402
from saipen_engine.journal import auto_recover_pending, scan_pending  # noqa: E402
from saipen_engine.operations import checkpoint  # noqa: E402
from test_guard_hostile_matrix import fresh_project  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

AGENT = "test-agent"


def setUpModule() -> None:
    isolate_host_session()


def _bom(root: Path) -> None:
    log = root / ".saipen" / "LOG.md"
    log.write_bytes(b"\xef\xbb\xbf" + log.read_bytes())


def _logs_is_a_file(root: Path) -> None:
    (root / ".saipen" / "logs").write_bytes(b"not a directory")


UNREADABLE = {
    "the active LOG carries a BOM": _bom,
    "the sealed-log container is a file": _logs_is_a_file,
}


class UnreadableHistoryTests(unittest.TestCase):
    def test_the_verifier_reports_the_cause_and_dereferences_nothing(self):
        for label, damage in UNREADABLE.items():
            with self.subTest(label):
                root = fresh_project()
                self.assertEqual(validate_project(root), [])
                damage(root)
                errors = validate_project(root)  # must return, never raise
                unreadable = [e for e in errors if "complete history unreadable" in e]
                self.assertEqual(len(unreadable), 1, errors)
                self.assertIn("HistoryOwnershipError", unreadable[0])
                self.assertNotIn("AttributeError", " ".join(errors))

    def test_the_journal_boundary_carries_the_cause(self):
        for label, damage in UNREADABLE.items():
            with self.subTest(label):
                root = fresh_project()
                damage(root)
                errors = journal_mod._run_verifier(root, [], "core_fast")
                self.assertTrue(errors)
                self.assertTrue(any("complete history unreadable" in e for e in errors), errors)
                self.assertFalse(any("raised" in e for e in errors), errors)

    def test_a_readable_history_is_still_judged_by_the_ledger_contract(self):
        # The repair must not turn the contract off: a parent newer than its
        # event is still a finding of the complete ledger.
        root = fresh_project()
        log = root / ".saipen" / "LOG.md"
        log.write_text(
            "- 12.09.26 00:00 [E-99] [parent: E-100] [agent: test-agent] RUN: before\n"
            + log.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        errors = validate_project(root)
        self.assertTrue(any("E-99" in e and "parent" in e for e in errors), errors)


class AfterApplyTests(unittest.TestCase):
    """The history turns unreadable between APPLY and the post-write verifier."""

    def interrupted(self, root: Path):
        real = log_mod.read_history_snapshot
        failure = log_mod.HistoryOwnershipError("history node LOG.md unreadable (injected)")

        def unreadable(*args, **kwargs):
            raise failure

        with patch.object(log_mod, "read_history_snapshot", unreadable):
            result = checkpoint(root, AGENT, "RUN", None, "an event the verifier cannot check")
        self.assertIs(log_mod.read_history_snapshot, real)
        return result

    def test_the_operation_settles_on_a_structured_conflict_that_names_the_cause(self):
        root = fresh_project()
        result = self.interrupted(root)
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(result.code, "CONFLICT")
        self.assertTrue(result.recovery_required)
        self.assertIn("complete history unreadable", result.message)
        self.assertIn("injected", result.message)
        self.assertNotIn("AttributeError", result.message)
        pending, conflicts = scan_pending(root)
        # One operation, reported as unresolved and as a conflict; never APPLYING.
        self.assertEqual({op.get("op_id") for op in (*pending, *conflicts)}, {result.op_id})
        self.assertEqual({op.get("status") for op in (*pending, *conflicts)}, {"CONFLICT"})

    def test_recovery_finishes_the_same_operation_once_the_cause_is_gone(self):
        root = fresh_project()
        result = self.interrupted(root)
        self.assertEqual(result.code, "CONFLICT")
        recovered = auto_recover_pending(root)
        self.assertTrue(recovered["ok"], recovered)
        self.assertEqual(scan_pending(root), ([], []))
        self.assertEqual(validate_project(root), [])
        tail = (root / ".saipen" / "LOG.md").read_text(encoding="utf-8").splitlines()[-1]
        self.assertIn("an event the verifier cannot check", tail)

    def test_recovery_under_the_same_condition_answers_and_strands_nothing(self):
        root = fresh_project()
        self.interrupted(root)
        failure = log_mod.HistoryOwnershipError("history node LOG.md unreadable (injected)")

        def unreadable(*args, **kwargs):
            raise failure

        with patch.object(log_mod, "read_history_snapshot", unreadable):
            still = auto_recover_pending(root)  # must answer, never raise
        self.assertIsInstance(still, dict)
        pending, conflicts = scan_pending(root)
        self.assertNotIn("APPLYING", [op.get("status") for op in (*pending, *conflicts)])
        self.assertTrue(auto_recover_pending(root)["ok"])
        self.assertEqual(scan_pending(root), ([], []))


if __name__ == "__main__":
    unittest.main()
