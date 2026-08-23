"""Regressions for the 2026-08-23 audit handoff (RUN acb-mt51rjib).

CORE-002..006, W2-002/003, PERF-001/004 against the ed1f86e8 baseline.
Focus on the shared attempt contract helpers and the public CLI reproductions
the audit described, so a fix cannot be undone by prose or a fixture tweak.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(TOOLS))

from saipen_engine import attempt as A  # noqa: E402
from saipen_engine import log as LOG  # noqa: E402
from saipen_engine import operations as OPS  # noqa: E402
from saipen_engine import state as S  # noqa: E402


def _project() -> Path:
    root = Path(tempfile.mkdtemp(prefix="saipen-audit-2026-08-23-"))
    fixture = ROOT / "tests/scenarios/done-wait-deadlock-goal-mode/.saipen"
    shutil.copytree(fixture, root / ".saipen")
    shutil.rmtree(root / ".saipen/recovery", ignore_errors=True)
    state_path = root / ".saipen/STATE.md"
    state_path.write_text(
        S.patch_state(
            state_path.read_text(encoding="utf-8"),
            {"saipen_home": str(ROOT.resolve())},
        ),
        encoding="utf-8",
        newline="\n",
    )
    return root


def _ev(event: int, ticket: str | None, tax: str, text: str, agent: str = "a1") -> dict:
    # `text` is the DEC payload only (parse_attempt_event reads ev["text"]
    # as the payload); event/agent/ticket ride as structured fields.
    return {"event": event, "ticket": ticket, "taxonomy": tax, "text": text, "agent": agent}


class Core002TicketAdmission(unittest.TestCase):
    def _records(self, events):
        return A.build_attempts(events)

    def test_later_interrupted_attempt_does_not_hide_candidate_obligation(self):
        events = [
            _ev(1, "T-001", "DEC", "attempt A-001 open"),
            _ev(2, "T-001", "DEC", "attempt A-001 close result candidate stop completed_execution"),
            _ev(3, "T-001", "DEC", "attempt A-002 open"),
            _ev(4, "T-001", "DEC", "attempt A-002 close result interrupted stop unknown"),
        ]
        records, errors = self._records(events)
        self.assertEqual(errors, [])
        err = A.ticket_admission_error("T-001", records, events)
        # A-001 closed candidate at E-2 with no VERIFY boundary after it; the
        # later interrupted A-002 must NOT erase that obligation.
        self.assertIsNotNone(err)
        self.assertIn("A-001", err)

    def test_candidate_then_verify_boundary_passes(self):
        events = [
            _ev(1, "T-001", "DEC", "attempt A-001 open"),
            _ev(2, "T-001", "DEC", "attempt A-001 close result candidate stop completed_execution"),
            _ev(3, "T-001", "RUN", "transition to VERIFY"),
        ]
        records, errors = self._records(events)
        self.assertEqual(errors, [])
        self.assertIsNone(A.ticket_admission_error("T-001", records, events))

    def test_no_candidate_attempt_has_no_obligation(self):
        events = [
            _ev(1, "T-001", "DEC", "attempt A-001 open"),
            _ev(2, "T-001", "DEC", "attempt A-001 close result failed stop validation_failure"),
        ]
        records, errors = self._records(events)
        self.assertEqual(errors, [])
        self.assertIsNone(A.ticket_admission_error("T-001", records, events))


class Core003WorkLocalSupersedes(unittest.TestCase):
    def test_predecessor_must_be_same_work(self):
        # The writer-side open path must select the predecessor only from the
        # same ticket. This is a structural regression on the max() selector.
        # We can't reach the writer easily, so we assert the shared contract
        # rejects a cross-ticket lineage, then rely on the writer fix's own
        # unit coverage in the operations module.
        events = [
            _ev(1, "T-001", "DEC", "attempt A-001 open"),
            _ev(2, "T-001", "DEC", "attempt A-001 close result failed stop validation_failure"),
            _ev(3, "T-002", "DEC", "attempt A-002 open"),  # T-002 episode
            _ev(4, "T-002", "DEC", "attempt A-002 close result interrupted stop unknown"),
        ]
        records, errors = A.build_attempts(events)
        self.assertEqual(errors, [])
        # A-002 (T-002) must not carry A-001 (T-001) as a predecessor.
        self.assertIsNone(records["A-002"].get("supersedes"))
        self.assertEqual(records["A-002"].get("ticket"), "T-002")


class Core004BidirectionalPointer(unittest.TestCase):
    def _contract(self, events, state_fields):
        return A.contract_errors(events, state_fields, known_ticket_ids={"T-001", "T-002"})

    def test_open_attempt_without_pointer_is_invalid(self):
        events = [
            _ev(1, "T-001", "DEC", "attempt A-001 open"),
        ]
        errors = self._contract(events, {"task": "T-001", "attempt": None})
        self.assertTrue(any("no attempt pointer" in e for e in errors), errors)

    def test_open_attempt_with_matching_pointer_is_valid(self):
        events = [
            _ev(1, "T-001", "DEC", "attempt A-001 open"),
        ]
        errors = self._contract(events, {"task": "T-001", "attempt": "A-001"})
        self.assertEqual(errors, [])

    def test_no_open_attempt_no_pointer_is_valid(self):
        events = []
        errors = self._contract(events, {"task": "T-001", "attempt": None})
        self.assertEqual(errors, [])


class Core005ExactCloseReplay(unittest.TestCase):
    def test_close_agent_preserved(self):
        events = [
            _ev(1, "T-001", "DEC", "attempt A-001 open", agent="a1"),
            _ev(2, "T-001", "DEC", "attempt A-001 close result interrupted stop unknown", agent="a2"),
        ]
        records, errors = A.build_attempts(events)
        self.assertEqual(errors, [])
        self.assertEqual(records["A-001"]["agent"], "a1")  # open owner
        self.assertEqual(records["A-001"]["close_agent"], "a2")  # close actor


class W2_003TNoneRejected(unittest.TestCase):
    def _contract(self, events, state_fields):
        return A.contract_errors(events, state_fields, known_ticket_ids={"T-001"})

    def test_attempt_on_t_none_is_invalid(self):
        events = [
            _ev(1, "T-none", "DEC", "attempt A-001 open"),
            _ev(2, "T-none", "DEC", "attempt A-001 close result interrupted stop unknown"),
        ]
        errors = self._contract(events, {"task": "T-001", "attempt": None})
        self.assertTrue(any("T-none" in e for e in errors), errors)

    def test_open_alone_on_t_none_is_invalid(self):
        events = [_ev(1, "T-none", "DEC", "attempt A-001 open")]
        errors = self._contract(events, {"task": "T-001", "attempt": "A-001"})
        self.assertTrue(any("T-none" in e for e in errors), errors)


class Perf001FusedMaxTicketId(unittest.TestCase):
    def test_fused_reader_reports_max_ticket_id(self):
        root = _project()
        logs_dir = root / ".saipen" / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        # A sealed segment carrying a historical high ticket.
        sealed = (
            "# Log\n"
            "- 22.08.23 00:00 [E-900] [parent: E-899] [T-900] DEC: historical work\n"
        )
        (logs_dir / "LOG-001.md").write_text(sealed, encoding="utf-8")
        # Active LOG continues past E-900.
        active = (
            "# Log\n"
            "- 22.08.23 00:00 [E-901] [parent: E-900] [T-901] DEC: current work\n"
        )
        (root / ".saipen" / "LOG.md").write_text(active, encoding="utf-8")
        plain = LOG.read_history_snapshot(root)
        fused, _digest = LOG.read_history_snapshot_and_logs_digest(root)
        self.assertEqual(plain.max_ticket_id, 901)
        self.assertEqual(fused.max_ticket_id, 901)


class Core006BriefFailsClosed(unittest.TestCase):
    def test_malformed_state_returns_structured_failure(self):
        from saipen_engine import context as CTX

        root = _project()
        # Tear the closing STATE frontmatter fence.
        state_text = root / ".saipen/STATE.md"
        state_text.write_text(
            "---\nphase: DONE\ntask: none\nagent: a1\n---\n", encoding="utf-8"
        )
        result = CTX.brief_projection(root)
        self.assertIsInstance(result, CTX.Result)
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "VALIDATION_FAILED")
        self.assertNotIn("AttributeError", str(result.message))

    def test_missing_pointer_open_attempt_rejected(self):
        from saipen_engine import context as CTX
        from saipen_engine import state as S

        root = _project()
        log_path = root / ".saipen/LOG.md"
        tail = log_path.read_text(encoding="utf-8").rstrip("\n")
        log_path.write_text(
            tail + "\n- 22.08.23 00:00 [E-9999] [T-001] [agent: a1] DEC: attempt A-001 open\n",
            encoding="utf-8",
        )
        # Set STATE.task = T-001 so brief sees an active Work with an open
        # attempt but no STATE.attempt pointer.
        state_path = root / ".saipen/STATE.md"
        st = S.patch_state(
            state_path.read_text(encoding="utf-8"),
            {"task": "T-001"},
        )
        state_path.write_text(st, encoding="utf-8")
        result = CTX.brief_projection(root)
        self.assertIsInstance(result, CTX.Result)
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "VALIDATION_FAILED")


class W2_001DeliveryInventory(unittest.TestCase):
    def test_builder_includes_untracked_non_ignored_files(self):
        import subprocess

        root = _project()
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        # Track one file so the repo is a real Git project.
        (root / "README.md").write_text("proj", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
            cwd=root,
            check=True,
        )
        # Untracked non-ignored implementation file + ignored garbage.
        (root / "NEW_REQUIRED_MODULE.py").write_text("def x(): pass\n", encoding="utf-8")
        (root / ".gitignore").write_text("__pycache__/\nignored_cache.bin\n", encoding="utf-8")
        (root / "ignored_cache.bin").write_text("junk", encoding="utf-8")
        # The builder's inventory must include the untracked module and exclude
        # ignored garbage.
        sys_path = list(__import__("sys").path)
        __import__("sys").path.insert(0, str(ROOT / "tools"))
        from build_handoff_archive import _delivery_inventory

        inv = _delivery_inventory(root)
        __import__("sys").path[:] = sys_path
        self.assertIn("NEW_REQUIRED_MODULE.py", inv)
        self.assertIn("README.md", inv)
        self.assertNotIn("ignored_cache.bin", inv)


if __name__ == "__main__":
    unittest.main(verbosity=2)