"""T-1578: CURRENT_DONE_JOURNAL_GAP restores the execution seat, never transfers it.

T-1572 reopens the broken DONE row into `## DOING` while its preserved
historical owner stays on the row. The recovery proposal then wrote the
RECOVERY ACTOR into `STATE.agent`, so the committed pair read

    BOARD DOING T-261 owner auda   STATE.agent <recovery actor>

which is exactly the split `ownership_invariant_errors` exists to refuse -- the
approved plan therefore could not commit and the gap stayed stranded. The
repair must RESTORE the existing owner of the ticket it reopens (STATE.agent
becomes the row's owner) and must never TRANSFER ownership to whoever executed
the recovery. The LOG event keeps the real actor: provenance is not rewritten.

Matrix: A mismatch + no other DOING, B same owner, C a live foreign DOING
still refuses, D a distinct operator actor, E replay, F original-byte evidence.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import test_t1572_ticket_scoped_recovery as t1572
from test_hermetic_env import isolate_host_session

SAIPEN_CLI = t1572.SAIPEN_CLI

#: T-262 is a genuinely live foreign claim: a second DOING row with its own
#: owner. A broken DONE row must never displace it.
_FOREIGN_DOING_BOARD = (
    "## DOING\n"
    "- [/] T-262 [P1] a live foreign claim | verify: still running "
    "| owner: buffy | claim_time: 2026-09-29T12:04:00Z\n"
    "## TODO\n"
) + t1572._GAP_BOARD_TEXT


def setUpModule() -> None:
    isolate_host_session()


def _project(state_agent: str, board_text: str | None = None) -> Path:
    from saipen_engine.journal import ensure_project_lineage

    root = Path(tempfile.mkdtemp(prefix="saipen-t1578-")) / "AUDAPACK"
    (root / ".saipen").mkdir(parents=True)
    text = t1572._gap_state_text("saipen continue").replace(
        "agent: auda", f"agent: {state_agent}", 1
    )
    (root / ".saipen" / "STATE.md").write_text(
        text.format(home=str(t1572._HOME).replace(chr(92), chr(92) * 2)),
        encoding="utf-8",
    )
    (root / ".saipen" / "BOARD.md").write_text(
        board_text or t1572._GAP_BOARD_TEXT, encoding="utf-8"
    )
    (root / ".saipen" / "LOG.md").write_text(t1572._GAP_LOG, encoding="utf-8")
    ensure_project_lineage(root)
    subprocess.run(["git", "init"], cwd=str(root), capture_output=True)
    return root


class RestoreTheExistingOwner(unittest.TestCase):
    def setUp(self) -> None:
        self.root = _project("recovery-seat")
        self.addCleanup(lambda: shutil.rmtree(self.root.parent, ignore_errors=True))

    def cli(self, *args) -> dict:
        from saipen_engine.paths import unbound_environment

        run = subprocess.run(
            [sys.executable, str(SAIPEN_CLI), *args, "--json"],
            cwd=str(self.root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=unbound_environment(),
            timeout=600,
        )
        try:
            return json.loads(run.stdout or "{}")
        except json.JSONDecodeError:
            return {"_raw": (run.stdout + run.stderr)[:400], "rc": run.returncode}

    def route(self) -> list[str]:
        answer = self.cli("recover")
        self.assertFalse(answer.get("ok"), answer)
        route = answer.get("canonical_next_command")
        self.assertTrue(
            route, f"recover named no route out of the seat-mismatch gap: {answer}"
        )
        self.assertEqual(route.split()[:3],
                         ["saipen", "recover", "--apply-approved-repair"])
        return route.split()[1:]

    def committed(self) -> tuple[str, str]:
        return (
            (self.root / ".saipen" / "STATE.md").read_text(encoding="utf-8"),
            (self.root / ".saipen" / "BOARD.md").read_text(encoding="utf-8"),
        )

    # -- A ------------------------------------------------------------------
    def test_matrix_A_the_gap_restores_the_row_owner_and_converges(self):
        route = self.route()
        applied = self.cli(*route)
        self.assertTrue(applied.get("ok"), applied)
        self.assertEqual(applied.get("code"), "REPAIRED", applied)

        state, board = self.committed()
        # The ticket's OWN lifecycle is restored (T-1572's guarantees, intact).
        self.assertIn("phase: VERIFY", state)
        self.assertIn("transition_from: BUILD", state)
        self.assertIn("task: T-261", state)
        self.assertIn("PHASE VERIFY T-261", state)
        # T-1578: the SEAT is restored to the row's existing owner.
        self.assertIn("agent: auda", state)
        self.assertNotIn("agent: recovery-seat", state)

        row = [line for line in board.splitlines() if "T-261" in line]
        self.assertEqual(len(row), 1, board)
        self.assertTrue(row[0].startswith("- [/] "), board)
        self.assertIn("owner: auda", row[0], board)
        lines = board.splitlines()
        self.assertTrue(lines.index("## DOING") < lines.index(row[0]) < lines.index("## TODO"),
                        board)

        self.assertEqual(self.cli("validate").get("structural_gate"), "pass")
        clean = self.cli("recover")
        self.assertTrue(clean.get("ok"), clean)
        self.assertFalse(clean.get("changed"), clean)

    # -- B ------------------------------------------------------------------
    def test_matrix_B_an_already_coherent_seat_is_untouched(self):
        self.setUp()
        self.root = _project("auda")
        self.addCleanup(lambda: shutil.rmtree(self.root.parent, ignore_errors=True))
        route = self.route()
        self.assertTrue(self.cli(*route).get("ok"))
        state, board = self.committed()
        self.assertIn("agent: auda", state)
        self.assertNotIn("handover", state + board)

    # -- C ------------------------------------------------------------------
    def test_matrix_C_a_live_foreign_doing_is_never_displaced(self):
        before = self.committed()
        self.root = _project("recovery-seat", _FOREIGN_DOING_BOARD)
        self.addCleanup(lambda: shutil.rmtree(self.root.parent, ignore_errors=True))
        before = self.committed()
        answer = self.cli("recover")
        self.assertFalse(answer.get("ok"), answer)
        self.assertFalse(answer.get("canonical_next_command"), answer)
        self.assertEqual(self.committed(), before)

    # -- D ------------------------------------------------------------------
    def test_matrix_D_the_journal_keeps_the_real_actor(self):
        self.root = _project("operator-x")
        self.addCleanup(lambda: shutil.rmtree(self.root.parent, ignore_errors=True))
        applied = self.cli(*self.route())
        self.assertTrue(applied.get("ok"), applied)
        state, board = self.committed()
        self.assertIn("agent: auda", state)
        self.assertIn("owner: auda", board)
        log = (self.root / ".saipen" / "LOG.md").read_text(encoding="utf-8")
        self.assertIn("operator-x", log, log[-400:])

    # -- E ------------------------------------------------------------------
    def test_matrix_E_replay_is_refused_and_writes_nothing(self):
        route = self.route()
        self.assertTrue(self.cli(*route).get("ok"))
        before = self.committed()
        replay = self.cli(*route)
        self.assertFalse(replay.get("ok"), replay)
        self.assertEqual(self.committed(), before)

    # -- F ------------------------------------------------------------------
    def test_matrix_f_the_original_bytes_are_preserved(self):
        self.assertTrue(self.cli(*self.route()).get("ok"))
        kept = [
            path for path in (self.root / ".saipen" / "recovery").rglob("*")
            if path.is_file()
        ]
        self.assertTrue(kept, list((self.root / ".saipen").iterdir()))


if __name__ == "__main__":
    unittest.main()
