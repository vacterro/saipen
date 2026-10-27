"""T-1915 / SRC-325: a terminal checkpoint must not deadlock on advisory prose.

Measured field shape (_FREEBUFF_SAI, 2026-10-25): STATE held `phase: DONE`,
`task: none` and a descriptive `next_action`, BOARD carried a `[x]` row inside
`## DOING`, and STATE.last_event lagged the LOG tail. `saipen recover` refused on
`next_action` because the phase is not ticket-bearing, so that one unexecutable
field held the whole checkpoint -- including an already-authorized urgent
request -- behind an operator decision.

`next_action` is a ROUTING PROJECTION, not a decision record: decisions live in
the journal and in operator gates. When the shared router uniquely projects an
executable action from the same bytes, the replacement is deterministic and the
legacy prose survives in the archived pre-repair STATE. When routing itself
cannot proceed (a foreign live seat, a binding split, an operator gate), the
gate stays exactly as it was.
"""

from __future__ import annotations

import datetime
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402

from saipen_engine import reconcile  # noqa: E402
from saipen_engine.board import parse_board  # noqa: E402
from saipen_engine.paths import identity_file_content, new_project_lineage  # noqa: E402
from saipen_engine.state import parse_state  # noqa: E402

HOME = TOOLS.parent
LEGACY = "BOARD empty; producer packages SAIT-002 + W-002 ready - collect with eee"
TODO_ROW = "- [ ] T-70 [P1] finish the launcher repair | verify: test\n"
#: The reported presentation drift: a completed-looking checkbox in DOING with
#: no lifecycle evidence that the ticket ever finished.
DOING_UNPROVEN = "- [x] T-69 [P1] repair launcher | verify: test\n"


def _utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


#: A live foreign seat: routing itself cannot proceed without a decision.
DOING_FOREIGN = (
    "- [/] T-69 [P1] repair launcher | verify: test | owner: other-agent | "
    f"claim_time: {_utc()}\n"
)


def _state(next_action: str = LEGACY) -> str:
    return (
        "---\n"
        "phase: DONE\n"
        "task: none\n"
        f'next_action: "{next_action}"\n'
        'blocker: ""\n'
        "transition_from: SHIP\n"
        "saipen_version: 8\n"
        "schema_version: 3\n"
        "last_event: 91\n"
        "style_contract: " + CURRENT_STYLE_CONTRACT + "\n"
        f'saipen_home: "{HOME.as_posix()}"\n'
        "agent: tester\n"
        "mode: full\n"
        'updated: "2026-10-25T00:00:00Z"\n'
        "---\n"
    )


def _log() -> str:
    return (
        "# Log\n"
        "- 25.10.26 00:00 [E-90] [T-70] [agent: tester] [op: ticket-fixture] "
        "DEC: ticket added via SAIOPS\n"
        "- 25.10.26 00:00 [E-91] [T-69] [agent: tester] [op: ticket-fixture] "
        "DEC: ticket added via SAIOPS\n"
        "- 25.10.26 00:01 [E-92] [agent: tester] [op: checkpoint-fixture] RUN: seed\n"
        "- 25.10.26 00:02 [E-93] [agent: tester] [op: checkpoint-fixture] RUN: seed\n"
    )


def _board(*, doing: str = "", todo: str = "") -> str:
    return f"## DOING\n{doing}## TODO\n{todo}## DONE\n## BLOCKED\n"


def project(base: Path, *, doing: str = "", todo: str = TODO_ROW) -> Path:
    root = base / "freebuff-shaped"
    saipen = root / ".saipen"
    saipen.mkdir(parents=True)
    (saipen / "STATE.md").write_text(_state(), encoding="utf-8")
    (saipen / "BOARD.md").write_text(_board(doing=doing, todo=todo), encoding="utf-8")
    (saipen / "LOG.md").write_text(_log(), encoding="utf-8")
    (saipen / "IDENTITY.md").write_text(
        identity_file_content(new_project_lineage()), encoding="utf-8"
    )
    return root


class CompoundCheckpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="t1915-")
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name).resolve()

    def _state(self, root: Path) -> dict:
        return parse_state((root / ".saipen" / "STATE.md").read_text(encoding="utf-8"))

    def _next_action_repairs(self, record: dict) -> list[dict]:
        return [
            repair
            for repair in (record.get("changed") or {}).get("state") or []
            if repair.get("field") == "next_action"
        ]

    def test_the_pre_fix_contract_refuses_the_terminal_checkpoint(self) -> None:
        """Red control: without the terminal projection the field gates."""
        root = project(self.base)
        with mock.patch.object(reconcile, "_terminal_projection_allowed", lambda phase: False):
            record = reconcile.reconcile_protocol_state(root, "tester", dry_run=True)
        refusals = [r for r in self._next_action_repairs(record) if r.get("refuse")]
        self.assertEqual(len(refusals), 1, record)
        self.assertIn("cannot be projected", refusals[0]["reason"])
        self.assertEqual(
            refusals[0].get("classification"), "NEXT_ACTION_SEMANTICALLY_AMBIGUOUS"
        )
        self.assertEqual(
            refusals[0]["canonical_next_command"],
            "saipen recover resolve-next-action <SRC-###>",
        )

    def test_a_provable_terminal_route_repairs_without_an_operator(self) -> None:
        root = project(self.base)
        record = reconcile.reconcile_protocol_state(root, "tester", dry_run=True)
        repairs = self._next_action_repairs(record)
        self.assertEqual(len(repairs), 1, record)
        self.assertFalse(repairs[0].get("refuse"), repairs)
        self.assertEqual(repairs[0]["from"], LEGACY)
        self.assertTrue(repairs[0]["to"], repairs)
        self.assertIn("SAFE_CANONICAL_REPAIR", repairs[0]["reason"])
        self.assertEqual(
            repairs[0].get("classification"), "NEXT_ACTION_CANONICALLY_PROJECTABLE"
        )

        applied = reconcile.reconcile_protocol_state(root, "tester", dry_run=False)
        self.assertTrue(applied.get("ok"), applied)
        state = self._state(root)
        self.assertEqual(state.get("next_action"), repairs[0]["to"])
        # The marker binds to the LOG as the repair leaves it: the fast-forward
        # plus the repair's own appended event (L08/L09).
        tail = [
            line for line in (root / ".saipen" / "LOG.md").read_text(encoding="utf-8").splitlines()
            if line.startswith("- ")
        ][-1]
        tail_event = int(tail.split("[E-")[1].split("]")[0])
        self.assertEqual(int(str(state.get("last_event"))), tail_event)
        self.assertGreater(tail_event, 93)

    def test_the_field_compound_shape_reports_one_gate_not_two(self) -> None:
        """The reported bytes: [x] in DOING plus legacy prose plus a stale tail."""
        root = project(self.base, doing=DOING_UNPROVEN, todo="")
        record = reconcile.reconcile_protocol_state(root, "tester", dry_run=True)

        self.assertFalse(
            [r for r in self._next_action_repairs(record) if r.get("refuse")],
            "the advisory field must not add its own gate to this checkpoint",
        )
        board_repairs = (record.get("changed") or {}).get("board") or []
        self.assertTrue(
            any(r.get("checkbox") == "x" and r.get("expected") == "/" for r in board_repairs),
            board_repairs,
        )
        decisions = record.get("operator_decisions") or []
        self.assertEqual(len(decisions), 1, decisions)
        self.assertEqual(decisions[0]["field"], "board")
        self.assertIn("--apply-approved-repair", decisions[0]["command"])

    def test_the_repair_is_idempotent(self) -> None:
        root = project(self.base)
        first = reconcile.reconcile_protocol_state(root, "tester", dry_run=False)
        self.assertTrue(first.get("ok"), first)
        before = (root / ".saipen" / "STATE.md").read_bytes()
        second = reconcile.reconcile_protocol_state(root, "tester", dry_run=False)
        self.assertTrue(second.get("ok"), second)
        self.assertEqual((root / ".saipen" / "STATE.md").read_bytes(), before)
        self.assertFalse(self._next_action_repairs(second), second)

    def test_the_field_compound_commits_atomically_on_one_approval(self) -> None:
        """SRC-325 §6 (P0-003): one gate, one plan, no half-committed checkpoint.

        The remaining gate is the BOARD section move of an unclaimed DOING work
        (SRC-043 deliberately holds the lifecycle set as ONE approved plan).
        Everything else -- the stale marker, the advisory next_action and the
        `[x]` presentation -- travels in that same transaction, so the operator
        approves once instead of repainting the checkpoint field by field.
        """
        root = project(self.base, doing=DOING_UNPROVEN, todo="")
        before = (
            (root / ".saipen" / "STATE.md").read_bytes(),
            (root / ".saipen" / "BOARD.md").read_bytes(),
        )
        plan = reconcile.reconcile_protocol_state(root, "tester", dry_run=True)
        self.assertFalse(plan.get("ok"), plan)
        repair_id = plan["repair_id"]

        unapproved = reconcile.reconcile_protocol_state(root, "tester", dry_run=False)
        self.assertFalse(unapproved.get("ok"), unapproved)
        self.assertEqual(
            (
                (root / ".saipen" / "STATE.md").read_bytes(),
                (root / ".saipen" / "BOARD.md").read_bytes(),
            ),
            before,
            "an unapproved plan must write nothing at all",
        )

        applied = reconcile.reconcile_protocol_state(
            root, "tester", approved_repair_id=repair_id
        )
        self.assertTrue(applied.get("ok"), applied)
        self.assertNotEqual(self._state(root).get("next_action"), LEGACY)
        board = parse_board((root / ".saipen" / "BOARD.md").read_text(encoding="utf-8"))
        self.assertEqual(board["tickets"]["T-69"]["section"], "## TODO")

    def test_a_foreign_live_seat_keeps_the_operator_gate(self) -> None:
        root = project(self.base, doing=DOING_FOREIGN, todo="")
        record = reconcile.reconcile_protocol_state(root, "tester", dry_run=True)
        refusals = [r for r in self._next_action_repairs(record) if r.get("refuse")]
        self.assertEqual(len(refusals), 1, record)
        self.assertTrue(refusals[0].get("operator_decision_available"), refusals)
        self.assertEqual(
            refusals[0].get("canonical_next_command"),
            "saipen recover resolve-next-action <SRC-###>",
        )


if __name__ == "__main__":
    unittest.main()
