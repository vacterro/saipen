"""T-1474: a request `start` projects as NEW Work is a GOAL-01 Entry.

MAINTENANCE 2.4 makes any actionable request an Entry: `execution_intent:
goal`, `goal_waves: 0`, `goal_tickets: 0`. `start` reset the counters only for
a TRIPPED valve, so a new objective inherited the previous run's spend --
measured 2026-09-22 (E-8289..E-8299): SRC-107 (/goal) arrived at 1 wave / 18
tickets and would have tripped after two VERIFY passes, while the same request
at 20 got a full budget. E-8299 applied the Entry by hand.

Controls: new Work starts its run at 0 with a countable pivot line; an echo
bound to existing Work (T-1469) is not a new objective and touches nothing; a
tripped valve is still reauthorized. The previous run's spend is written into
the LOG as real increments, because reconciliation rebuilds the counters from
the LOG (CORE 1.5) and repairs a hand-set STATE value back to it.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import codec  # noqa: E402
from saipen_engine.state import parse_state  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_t1363_zero_manual_entry import cli, project, valve_project  # noqa: E402

TASK = "add a one-line docstring to the top of src/app.py"


def setUpModule() -> None:
    isolate_host_session()


def spent_log(waves: int, tickets: int) -> str:
    """A LOG whose previous run really spent `waves`/`tickets` of its budget."""
    lines = [
        "# Log",
        "- 14.09.26 00:00 [E-0001] [agent: test-agent] "
        "[op: transition-" + "a" * 32 + "] RUN: transition to SCOUT",
    ]
    texts = ["goal pivot -- the previous objective"]
    texts += [f"goal_waves {n}->{n + 1}" for n in range(waves)]
    texts += [f"goal_tickets {n}->{n + 1}" for n in range(tickets)]
    for index, text in enumerate(texts, start=2):
        lines.append(
            f"- 14.09.26 00:{index:02d} [E-{index:04d}] [parent: E-{index - 1:04d}] "
            f"[agent: test-agent] [op: checkpoint-{index:032d}] DEC: {text}"
        )
    return "\n".join(lines) + "\n"


def spent_project(case: unittest.TestCase, intent: str, waves: int, tickets: int) -> Path:
    return project(
        case,
        log=spent_log(waves, tickets),
        execution_intent=intent,
        goal_waves=waves,
        goal_tickets=tickets,
    )


def state_of(root: Path) -> dict:
    return parse_state(codec.read_doc(root / ".saipen" / "STATE.md"))


def log_of(root: Path) -> str:
    return (root / ".saipen" / "LOG.md").read_text(encoding="utf-8")


def counters(state: dict) -> tuple:
    return (
        state.get("execution_intent"),
        int(state.get("goal_waves") or 0),
        int(state.get("goal_tickets") or 0),
    )


class FixtureTests(unittest.TestCase):
    def test_the_spent_budget_survives_reconciliation(self):
        """Guard: without this the Entry tests would pass on a reset they never caused."""
        root = spent_project(self, "goal", 1, 18)
        code, _payload, text = cli(root, "status", "--json")
        self.assertEqual(code, 0, text)
        self.assertEqual(counters(state_of(root)), ("goal", 1, 18))


class NewWorkIsAnEntryTests(unittest.TestCase):
    def test_new_work_starts_its_run_at_zero_with_a_pivot_line(self):
        root = spent_project(self, "goal", 1, 18)
        code, payload, text = cli(root, "start", TASK, "--json")
        self.assertEqual(code, 0, text)
        self.assertEqual(payload["code"], "STARTED", text)
        self.assertEqual(counters(state_of(root)), ("goal", 0, 0))
        ticket = payload["ticket"]
        self.assertIn(f"DEC: goal pivot -- {ticket} ({payload['receipt']}): {TASK}", log_of(root))

    def test_a_project_with_no_intent_enters_goal(self):
        root = project(self)
        self.assertNotEqual(state_of(root).get("execution_intent"), "goal")
        code, payload, text = cli(root, "start", TASK, "--json")
        self.assertEqual(code, 0, text)
        self.assertEqual(counters(state_of(root)), ("goal", 0, 0))
        self.assertIn(f"DEC: goal pivot -- {payload['ticket']}", log_of(root))


class NotAnEntryTests(unittest.TestCase):
    def test_an_echo_of_existing_work_touches_no_counter(self):
        root = spent_project(self, "goal", 1, 5)
        code, first, text = cli(root, "start", TASK, "--json")
        self.assertEqual(code, 0, text)
        # The new run spends some of its own budget; reconciliation (inside the
        # next start) rebuilds STATE's counters from these LOG increments.
        for step in ("goal_waves 0->1", "goal_tickets 0->1", "goal_tickets 1->2"):
            code, _payload, text = cli(root, "checkpoint", "DEC", step, "--json")
            self.assertEqual(code, 0, text)
        pivots = log_of(root).count("DEC: goal pivot")
        code, again, text = cli(root, "start", TASK, "--json")
        self.assertEqual(code, 0, text)
        self.assertEqual(again["ticket"], first["ticket"], text)
        self.assertEqual(counters(state_of(root))[1:], (1, 2))
        self.assertEqual(log_of(root).count("DEC: goal pivot"), pivots)

    def test_a_tripped_valve_is_still_reauthorized(self):
        root = valve_project(self)
        code, payload, text = cli(root, "start", TASK, "--json")
        self.assertEqual(code, 0, text)
        self.assertTrue(payload["valve_reauthorized"], text)
        self.assertEqual(counters(state_of(root)), ("goal", 0, 0))


class ContinuationIsNotAnEntryTests(unittest.TestCase):
    """T-1566: a target-free continuation cannot preempt unfinished goal Work."""

    def active(self):
        root = spent_project(self, "goal", 1, 5)
        code, first, text = cli(root, "start", TASK, "--json")
        self.assertEqual(code, 0, text)
        code, _payload, text = cli(root, "transition", "BUILD", "--json")
        self.assertEqual(code, 0, text)
        for step in ("goal_waves 0->1", "goal_tickets 0->1"):
            code, _payload, text = cli(root, "checkpoint", "DEC", step, "--json")
            self.assertEqual(code, 0, text)
        code, _payload, text = cli(root, "status", "--json")
        self.assertEqual(code, 0, text)
        return root, first["ticket"]

    def test_target_free_continuations_preserve_work_phase_and_budget(self):
        from saipen_engine.board import parse_board

        phrases = (
            "continue", "keep improving", "go further",
            "Please continue improving the protocol logic and closing holes to the end.",
            "Хорошо, продолжи пожалуйста дальше улучшать логику протокола "
            "и закрывать мерзкие дыры до конца, Опус :)",
        )
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                root, work = self.active()
                before = parse_board(codec.read_doc(root / ".saipen" / "BOARD.md"))
                code, result, text = cli(root, "start", phrase, "--json")
                self.assertEqual(code, 0, text)
                self.assertEqual(result["ticket"], work, text)
                self.assertTrue(result["resumed"], text)
                self.assertEqual(result["phase"], "BUILD", text)
                self.assertIsNone(result["parked"], text)
                self.assertEqual(counters(state_of(root)), ("goal", 1, 1))
                after = parse_board(codec.read_doc(root / ".saipen" / "BOARD.md"))
                self.assertEqual(set(after["tickets"]), set(before["tickets"]))
                self.assertEqual(after["tickets"][work]["section"], "## DOING")
                # Retry of captured continuation must not create a second Work.
                code, again, text = cli(root, "start", "--receipt", result["receipt"], "--json")
                self.assertEqual(code, 0, text)
                self.assertEqual(again["ticket"], work, text)

    def test_a_concrete_target_after_continue_is_still_a_new_request(self):
        for phrase in (
            "continue, and add OAuth login", "keep improving the admission signer",
            "go further: repair src/app.py", "continue improving the protocol; add retries",
        ):
            with self.subTest(phrase=phrase):
                root, work = self.active()
                code, result, text = cli(root, "start", phrase, "--json")
                self.assertEqual(code, 0, text)
                self.assertNotEqual(result["ticket"], work, text)
                self.assertEqual(result["parked"]["ticket"], work, text)

    def test_without_active_goal_there_is_no_work_to_continue(self):
        root = project(self)
        code, result, text = cli(root, "start", "keep improving", "--json")
        self.assertEqual(code, 0, text)
        self.assertFalse(result["resumed"], text)

    def test_continuation_preview_matches_apply_and_writes_nothing(self):
        for door in ("start", "user-request"):
            with self.subTest(door=door):
                root, work = self.active()
                before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
                code, result, text = cli(root, door, "keep improving", "--dry-run", "--json")
                self.assertEqual(code, 0, text)
                self.assertTrue(result["continuation"], text)
                self.assertEqual(result["ticket"], work, text)
                after = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
                self.assertEqual(after, before)
                code, applied, text = cli(root, door, "keep improving", "--json")
                self.assertEqual(code, 0, text)
                self.assertEqual(applied["ticket"], work, text)

    def test_explicit_acceptance_metadata_is_not_swallowed_as_continuation(self):
        for door in ("start", "user-request"):
            with self.subTest(door=door):
                root, work = self.active()
                code, result, text = cli(
                    root, door, "continue", "--verify", "OAuth integration passes", "--json"
                )
                self.assertEqual(code, 0, text)
                self.assertNotEqual(result["ticket"], work, text)

    def test_helper_requires_an_executable_goal_without_independent_metadata(self):
        from saipen_engine.entry import continuation_work

        state = {"execution_intent": "goal", "task": "T-1", "phase": "BUILD"}
        tickets = {"T-1": {"section": "## DOING"}}
        self.assertEqual(continuation_work(state, tickets, "continue"), "T-1")
        for change in ({"execution_intent": "converge"}, {"phase": "BLOCKED"}, {"task": None}):
            self.assertIsNone(continuation_work({**state, **change}, tickets, "continue"))
        self.assertIsNone(continuation_work(state, {"T-1": {"section": "## TODO"}}, "continue"))
        for metadata in ({"needs": ["T-2"]}, {"supersedes": "SRC-001"}, {"verify": "new proof"}):
            self.assertIsNone(continuation_work(state, tickets, "continue", **metadata))

    def test_user_request_door_binds_continuation_without_forking_work(self):
        root, work = self.active()
        before = counters(state_of(root))
        code, result, text = cli(root, "user-request", "keep improving", "--json")
        self.assertEqual(code, 0, text)
        self.assertEqual(result["ticket"], work, text)
        self.assertEqual(state_of(root)["task"], work)
        self.assertEqual(state_of(root)["phase"], "BUILD")
        self.assertEqual(counters(state_of(root)), before)


if __name__ == "__main__":
    unittest.main()
