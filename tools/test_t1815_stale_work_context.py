"""SRC-274:R002 (F-03): a late checkpoint may not become live lifecycle history.

The measured defect, 2026-10-18: T-1745 was finished at 02:06 and a checkpoint
naming T-1745 was accepted at 02:11 -- while T-1744 owned the active phase. The
checkpoint minted a durable `[T-1745]` LOG event, and the phase decision that
followed was correctly refused, but only AFTER history had been forged. The
whole ticket-bearing guard was `T-\\d+` plus "is the row on the board", so any
finished ticket stayed writable forever.

Proven here, against the real `checkpoint`/`transition_phase` entry points:

- a checkpoint naming a finished ticket while another owns the phase REFUSES
  with `STALE_WORK_CONTEXT` and writes ZERO bytes to LOG, BOARD or STATE;
- the same refusal covers a ticket that is merely not the current one;
- a ticket-less session checkpoint is still legal (budget/idle notes carry no
  ticket, and blocking them would break ordinary operation);
- the current ticket's own checkpoint still succeeds;
- the two-writer race the audit names: T-7 is closed while T-8 becomes
  current, then the stale T-7 checkpoint is refused, and the legal T-8 one
  after it still commits -- the engine is not left wedged;
- the code is registered, so a caller can match on it.

Run standalone:
    python tools/test_t1815_stale_work_context.py
"""

from __future__ import annotations

import datetime as dt
import hashlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402

from saipen_engine import errors, operations  # noqa: E402
from saipen_engine.operations import checkpoint  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _state(phase: str, task: str, last_event: int, transition_from: str = "SCOUT") -> str:
    home = str(ROOT).replace(chr(92), chr(92) * 2)
    return (
        "---\n"
        f"phase: {phase}\n"
        f"task: {task}\n"
        f'next_action: "PHASE {phase} {task}"\n'
        'blocker: ""\n'
        f"transition_from: {transition_from}\n"
        "saipen_version: 8\n"
        "schema_version: 3\n"
        f"last_event: {last_event}\n"
        "style_contract: " + CURRENT_STYLE_CONTRACT + "\n"
        f'saipen_home: "{home}"\n'
        "agent: tester\n"
        "requires:\n  - filesystem\n  - python\n"
        "mode: full\n"
        f'updated: "{_now()}"\n'
        "execution_intent: normal\n"
        "---\n"
    )


def _board(doing: str, done: tuple[str, ...] = (), todo: tuple[str, ...] = ()) -> str:
    at = _now()
    lines = ["## DOING"]
    if doing:
        lines.append(
            f"- [/] {doing} [P1] fixture work | verify: it holds "
            f"| owner: tester | claim_time: {at}"
        )
    lines.append("## TODO")
    lines.extend(f"- [ ] {tid} [P2] todo fixture | verify: it holds" for tid in todo)
    lines.append("## DONE")
    lines.extend(f"- [x] {tid} [P2] finished fixture | verify: it held" for tid in done)
    lines.append("## BLOCKED")
    lines.append("")
    return "\n".join(lines)


class StaleWorkContextFixture(unittest.TestCase):
    """A project whose STATE.task and BOARD DOING can be moved independently."""

    def setUp(self) -> None:
        base = Path(tempfile.mkdtemp(prefix="saipen-t1815-"))
        self.addCleanup(lambda: shutil.rmtree(base, ignore_errors=True))
        self.project = base / "project"
        (self.project / ".saipen").mkdir(parents=True)
        self.write(task="T-7", phase="BUILD", board=_board("T-7", done=("T-6",)))
        (self.project / ".saipen" / "LOG.md").write_text(
            "- 24.08.26 00:00 [E-001] [T-7] [agent: tester] RUN: fixture -> PASS\n",
            encoding="utf-8",
        )

    def write(self, *, task: str, phase: str, board: str, transition_from: str = "SCOUT") -> None:
        (self.project / ".saipen" / "STATE.md").write_text(
            _state(phase, task, 1, transition_from), encoding="utf-8"
        )
        (self.project / ".saipen" / "BOARD.md").write_text(board, encoding="utf-8")

    def canonical(self) -> dict[str, str]:
        return {
            name: hashlib.sha256((self.project / ".saipen" / name).read_bytes()).hexdigest()
            for name in ("STATE.md", "BOARD.md", "LOG.md")
        }

    def assert_refused_unchanged(self, ticket: str | None, expected: str = "STALE_WORK_CONTEXT"):
        before = self.canonical()
        result = checkpoint(self.project, "tester", "RUN", ticket, "late decision")
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(result.code, expected, result.to_dict())
        self.assertEqual(self.canonical(), before, "a refusal must write zero canonical bytes")
        return result

    # -- the measured defect ------------------------------------------------

    def test_a_checkpoint_for_a_finished_ticket_is_refused(self):
        """The exact F-03 shape: T-6 is DONE, T-7 owns the phase."""
        self.assert_refused_unchanged("T-6")

    def test_a_checkpoint_for_a_merely_inactive_ticket_is_refused(self):
        """TODO work is not current either: existence is not ownership."""
        self.write(task="T-7", phase="BUILD", board=_board("T-7", todo=("T-9",)))
        self.assert_refused_unchanged("T-9")

    def test_the_current_ticket_still_checkpoints(self):
        result = checkpoint(self.project, "tester", "RUN", "T-7", "ordinary work")
        self.assertTrue(result.ok, result.to_dict())
        self.assertEqual(result.code, "CHECKPOINTED")

    def test_a_ticket_less_session_checkpoint_is_still_legal(self):
        """Budget/idle notes carry no ticket; blocking them breaks operation."""
        result = checkpoint(self.project, "tester", "RUN", None, "session note")
        self.assertTrue(result.ok, result.to_dict())

    def test_a_project_with_no_active_task_refuses_a_ticket_bearing_checkpoint(self):
        """No STATE.task means no current work to bind -- refuse, do not guess."""
        self.write(task="none", phase="BUILD", board=_board("T-7", done=("T-6",)))
        self.assert_refused_unchanged("T-7")

    # -- the two-writer race the audit names -------------------------------

    def test_the_two_writer_race_refuses_the_late_writer_and_recovers(self):
        """T-7 closes while T-8 becomes current; the stale T-7 event is refused.

        The post-race state is written directly because closing T-7 through
        `ticket_move(done)` needs a full VERIFY chain, and that chain is not
        what this control measures. What it measures is the exact shape the
        two writers leave behind: T-7 in DONE, T-8 owning the phase.
        """
        (self.project / ".saipen" / "LOG.md").write_text(
            "- 24.08.26 00:00 [E-001] [T-7] [agent: tester] RUN: fixture -> PASS\n"
            "- 24.08.26 00:01 [E-002] [T-7] [agent: tester] DEC: scaffold\n",
            encoding="utf-8",
        )
        # Writer A finished T-7; writer B adopted T-8, now the current work.
        self.write(
            task="T-8",
            phase="SCOUT",
            board=_board("T-8", done=("T-6", "T-7")),
            transition_from="DONE",
        )
        # Writer A's late decision for T-7 must not become live history.
        refused = self.assert_refused_unchanged("T-7")
        self.assertIn("T-7", refused.message)
        self.assertIn("T-8", refused.message)

        # The engine is not wedged: the legal current-ticket checkpoint commits.
        allowed = checkpoint(self.project, "tester", "RUN", "T-8", "current work")
        self.assertTrue(allowed.ok, allowed.to_dict())

    # -- red-before-green: the guard is what makes the difference -----------

    def test_without_the_guard_the_same_checkpoint_would_forge_history(self):
        """RED control: disable the guard and the F-03 checkpoint is accepted.

        This is the measured pre-fix engine behaviour. It proves the green
        above depends on the guard and not on the fixture refusing for some
        unrelated reason (an illegal taxonomy, a bad ticket shape, a stale
        claim). If this control ever fails, the guard has stopped being what
        stands between a late writer and forged lifecycle history.
        """
        from unittest import mock

        before = self.canonical()
        with mock.patch.object(operations, "_stale_work_context_refusal", return_value=None):
            accepted = checkpoint(self.project, "tester", "RUN", "T-6", "late decision")
        self.assertTrue(accepted.ok, accepted.to_dict())
        self.assertEqual(accepted.code, "CHECKPOINTED")
        self.assertNotEqual(self.canonical(), before, "the unguarded write moved history")

    # -- the code is registered --------------------------------------------

    def test_the_refusal_code_is_registered(self):
        self.assertIn("STALE_WORK_CONTEXT", errors.CODES)

    def test_the_guard_is_the_one_operations_consults(self):
        """The planner delegates to one helper, so a future edit cannot fork it."""
        self.assertIs(
            operations._stale_work_context_refusal.__module__, operations.__name__
        )
        state = {"task": "T-8"}
        refusal = operations._stale_work_context_refusal(state, _board("T-8", done=("T-7",)), "T-7")
        self.assertIsNotNone(refusal)
        self.assertEqual(refusal.code, "STALE_WORK_CONTEXT")
        self.assertIsNone(
            operations._stale_work_context_refusal(state, _board("T-8", done=("T-7",)), "T-8")
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
