"""T-1674: a `## DONE` row with a typed closure_mode has a recovery owner.

Measured on a copy of AUDAPACK (08.10.26): `T-282 ... | closure_mode:
duplicate_reconciled`, typed by an executor two days earlier. `board.py`
refuses the value, so every reader answered `checkpoint-invalid`; the
phantom-DONE and legacy-review classes skip any row that carries a
closure_mode at all, so `saipen recover` answered `RESIDUAL_DEFECTS` with no
command. The project could not move and the only exit was a hand edit of
BOARD.md -- the edit the protocol forbids.

The CLI half drives the operator's entry point on a project with real
allocations; the unit half pins which rows the class may and may not take.
"""

import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import continuity_probes as probes  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

from saipen_engine.board import CLOSURE_MODES, parse_board  # noqa: E402
from saipen_engine.reconcile import _board_lifecycle_repairs  # noqa: E402

AGENT = "buffy"
TYPED = "duplicate_reconciled"
CLASS = "typed-closure-mode"
CANON = ("STATE.md", "BOARD.md", "LOG.md")


def setUpModule() -> None:
    isolate_host_session()


def _project() -> tuple[Path, str]:
    """A git worktree whose two tickets were both allocated by real operations.

    The scenario fixture ships a hand-authored T-001; a board that mixes it
    with a canonical allocation is refused for that reason, which is not the
    defect under test, so the board starts empty.
    """
    root = probes.fresh_project("t1674")
    subprocess.run(["git", "init", "-q", "."], cwd=root, check=True)
    (root / ".saipen" / "BOARD.md").write_text(
        "# Board\n## DOING\n## TODO\n## DONE\n## BLOCKED\n", encoding="utf-8", newline="\n"
    )
    first = probes.cli(root, AGENT, "ticket", "add", "P2", "the widget", "--verify", "it works")
    assert first.get("ok"), first
    added = probes.cli(root, AGENT, "ticket", "add", "P3", "the same widget again",
                       "--verify", f"duplicate of {first['ticket']}")
    assert added.get("ok"), added
    return root, added["ticket"]


def _type_the_closure(root: Path, ticket: str) -> None:
    """Move the row under DONE by hand with a closure_mode nobody writes."""
    board = root / ".saipen" / "BOARD.md"
    text = board.read_text(encoding="utf-8")
    line = next(row for row in text.splitlines() if f" {ticket} " in row)
    text = text.replace(line + "\n", "")
    done = re.sub(r"^- \[.\]", "- [x]", line) + f" | closure_mode: {TYPED}"
    board.write_text(text.replace("## DONE\n", "## DONE\n" + done + "\n"),
                     encoding="utf-8", newline="\n")
    # The row models AUDAPACK's T-282, typed before any operation left a
    # terminal baseline (T-1673). With one present the lifecycle authority
    # names the same row first as a BOARD-only move -- test_t1673 owns that.
    (root / ".saipen" / "recovery" / "board-terminal.json").unlink(missing_ok=True)


def _bytes(root: Path) -> dict:
    return {name: (root / ".saipen" / name).read_bytes() for name in CANON}


class TypedClosureModeRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.root, self.ticket = _project()
        self.addCleanup(lambda: shutil.rmtree(self.root, ignore_errors=True))

    def cli(self, *args):
        return probes.cli(self.root, AGENT, *args)

    def test_recovery_names_one_approved_command_and_the_project_is_valid_after_it(self):
        _type_the_closure(self.root, self.ticket)
        before = _bytes(self.root)
        status = self.cli("status")
        self.assertFalse(status.get("ok"), status)
        self.assertIn(f"closure_mode '{TYPED}'", str(status.get("detail")), status)
        self.assertEqual(status.get("action"), "saipen recover", status)

        plan = self.cli("recover")
        self.assertEqual(plan.get("code"), "RECONCILE_REAUTH_REQUIRED", plan)
        self.assertIn(CLASS, str(plan.get("changed")), plan)
        route = str(plan.get("canonical_next_command") or "").split()
        self.assertEqual(route[:3], ["saipen", "recover", "--apply-approved-repair"], plan)
        # Bare recovery never reopens a row silently.
        self.assertEqual(_bytes(self.root), before)

        applied = self.cli(*route[1:])
        self.assertEqual(applied.get("code"), "REPAIRED", applied)
        row = parse_board(_bytes(self.root)["BOARD.md"].decode())["tickets"][self.ticket]
        self.assertEqual(row["section"], "## TODO", row)
        self.assertNotIn("closure_mode", row["fields"], row)
        after = self.cli("status")
        self.assertTrue(after.get("ok"), after)
        self.assertEqual(self.cli("recover").get("code"), "CLEAN")
        # The row is ordinary Work again: an operation may close it properly.
        self.assertTrue(self.cli("claim", self.ticket, "--explicit").get("ok"))


class WhichRowsTheClassTakesTests(unittest.TestCase):
    """`_board_lifecycle_repairs` over boards built for the case."""

    @staticmethod
    def atoms(board_text: str, state: dict | None = None) -> list[dict]:
        board = parse_board(board_text)
        return [
            atom for atom in _board_lifecycle_repairs(board, None, state)
            if atom.get("_class") == CLASS
        ]

    @staticmethod
    def board(*done_rows: str) -> str:
        return "# Board\n## DOING\n## TODO\n## DONE\n" + "".join(
            row + "\n" for row in done_rows
        ) + "## BLOCKED\n"

    def test_only_a_value_outside_the_closed_set_is_taken(self):
        rows = [
            f"- [x] T-{index} [P2] closed properly | verify: proof | closure_mode: {mode}"
            for index, mode in enumerate(CLOSURE_MODES, start=10)
        ]
        typed = f"- [x] T-5 [P3] typed | verify: duplicate of T-6 | closure_mode: {TYPED}"
        plain = "- [x] T-7 [P2] closed before the field existed | verify: proof"
        atoms = self.atoms(self.board(typed, plain, *rows))
        self.assertEqual([atom["ticket"] for atom in atoms], ["T-5"])
        atom = atoms[0]
        self.assertEqual((atom["kind"], atom["from_section"], atom["to_section"]),
                         ("section-move", "## DONE", "## TODO"))
        self.assertTrue(atom["requires_approval"])
        self.assertIn("closure_mode", atom["fields"])
        self.assertIn(TYPED, atom["reason"])

    def test_the_claim_is_dropped_with_the_closure(self):
        typed = (f"- [x] T-5 [P3] typed | verify: x | owner: buffy "
                 f"| claim_time: 2026-10-06T02:39:00Z | closure_mode: {TYPED}")
        atom = self.atoms(self.board(typed))[0]
        self.assertTrue({"closure_mode", "owner", "claim_time"} <= set(atom["fields"]), atom)

    def test_the_row_state_is_bound_to_is_left_to_the_current_done_classes(self):
        typed = f"- [x] T-5 [P3] typed | verify: x | closure_mode: {TYPED}"
        self.assertEqual(self.atoms(self.board(typed), {"task": "T-5", "phase": "DONE"}), [])
        self.assertEqual(len(self.atoms(self.board(typed), {"task": "none"})), 1)


if __name__ == "__main__":
    unittest.main()
