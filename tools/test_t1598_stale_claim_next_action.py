"""A stale foreign claim must not FAIL the pre-computed pick (T-1598).

The incident this ticket exists for: closing T-1596 (the BLOCKED drain)
released the single DOING seat, the Pick Rule recomputed
``next_action: "PHASE SCOUT T-1510"`` -- T-1507's continuation reservation
makes T-1510 the unique reserved child -- and ``saipen validate`` returned
``REFUSE CONFORMANCE_UNHEALTHY`` / ``CURRENT_FAIL`` with exactly one problem:

    STATE.md next_action names T-1510, claimed by 'astra' while this state's
    agent is 'saipen-cli' -- executing another agent's claim is the
    concurrency collision § 1.4 exists to prevent

Nothing about the board was wrong. T-1510's astra claim was 8.11 days old
against a 15-minute liveness window, so ``board.claim_status`` returned
``FOREIGN_STALE`` -- a claim CORE § 1.4 makes ADOPTABLE
(``ownership.ADOPTABLE == {UNCLAIMED, FOREIGN_STALE}``). Three canonical
owners already agreed it was not a collision:

  * ``board.ticket_is_workable`` treats a syntactically valid claim pair on a
    non-DOING ticket as INACTIVE history (hostile-regression, P1#5);
  * ``ownership.ownership_invariant_errors`` is deliberately scoped to the
    active ``## DOING`` ticket and returns ``[]`` here;
  * ``ownership.ADOPTABLE`` separates an adoptable stale claim from an
    untakeable live one.

``validate.py`` restated the ownership rule inline instead of consulting
``claim_status`` -- the exact drift
``test_core_ownership_routing.CommittedSplitTests.test_both_gates_use_the_same_predicate``
forbids ("the canonical validator must import the shared predicate, not
restate it"). The tree validated clean only while ``next_action`` happened to
name the drain's own DOING ticket; the first seat release exposed it.

The rule under repair: a persisted pick naming a TODO ticket whose foreign
claim has LAPSED is executable, because adopting it is a legal § 1.4 action.
Only a claim that is still LIVE, or an unreadable half pair, is a collision.
Both refusals survive the repair, and they must arrive through the one shared
predicate rather than a second rule.
"""

from __future__ import annotations

import datetime as dt
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402

from saipen_engine.board import CLAIM_LIVENESS_WINDOW, parse_board  # noqa: E402
from saipen_engine.state import parse_state  # noqa: E402

#: Comfortably INSIDE the § 1.4 liveness window.
LIVE = "live"
#: Comfortably OUTSIDE it -- another agent may adopt this one.
STALE = "stale"
#: No claim_time at all -- the unreadable half pair CORE § 1.4 fails closed.
NO_TIME = "none"

OWNER = "astra"
SEAT = "saipen-cli"


def _now() -> dt.datetime:
    """Read the clock HERE, never at import.

    T-1478: a module-level stamp is DISCOVERY time, and the family runs for tens
    of minutes -- a fixture stamped from it would age into a different claim
    class while the sweep was still going, which is the same
    history-is-not-current-truth defect this ticket exists to fix.
    """
    return dt.datetime.now(dt.timezone.utc)


def _claim_time(volley: str) -> str | None:
    age = CLAIM_LIVENESS_WINDOW / 3 if volley == LIVE else CLAIM_LIVENESS_WINDOW * 40
    return (_now() - age).strftime("%Y-%m-%dT%H:%M:%SZ")


class PickOwnershipFixture(unittest.TestCase):
    """A seat with NO active DOING ticket, whose pick names a TODO ticket.

    This is the post-seat-release shape the drain left behind: STATE.task is
    ``none``, so ``ownership_invariant_errors`` is silent by design and the
    ``next_action`` gate is the only thing left that can refuse.
    """

    def make_project(
        self,
        *,
        owner: str | None = OWNER,
        volley: str = STALE,
        task: str = "none",
        phase: str = "DONE",
        picked: str = "T-7",
    ) -> Path:
        base = Path(tempfile.mkdtemp(prefix="saipen-t1598-"))
        self.addCleanup(lambda: shutil.rmtree(base, ignore_errors=True))
        project = base / "project"
        (project / ".saipen").mkdir(parents=True)
        now = _now()
        claim = f" | owner: {owner}" if owner else ""
        claim_time = None if volley == NO_TIME else _claim_time(volley)
        if claim_time:
            claim += f" | claim_time: {claim_time}"
        todo = (
            f"- [ ] {picked} [P1] the reserved continuation | verify: proof{claim}\n"
            if picked
            else ""
        )
        (project / ".saipen" / "BOARD.md").write_text(
            "## DOING\n"
            f"## TODO\n{todo}"
            "## DONE\n- [x] T-1 [P1] finished | verify: proof\n"
            "## BLOCKED\n",
            encoding="utf-8",
        )
        (project / ".saipen" / "STATE.md").write_text(
            "---\n"
            f"phase: {phase}\n"
            f"task: {task}\n"
            f'next_action: "PHASE SCOUT {picked}"\n'
            'blocker: "none"\n'
            "transition_from: DONE\n"
            "saipen_version: 8\n"
            "schema_version: 3\n"
            "last_event: 1\n"
            f"style_contract: {CURRENT_STYLE_CONTRACT}\n"
            f'saipen_home: "{str(ROOT).replace(chr(92), chr(92) * 2)}"\n'
            f"agent: {SEAT}\n"
            "requires:\n  - filesystem\n  - python\n"
            f"mode: full\n"
            f'updated: "{now.strftime("%Y-%m-%dT%H:%M:%SZ")}"\n'
            "---\n",
            encoding="utf-8",
        )
        # Both ids carry a structured [T-###] event: CORE-003 / SRC-026:R003
        # demands allocation backing, and a T-7 with no event would FAIL the
        # validator for a reason unrelated to the ownership gate under test.
        stamp = now.strftime("%d.%m.%y %H:%M")
        (project / ".saipen" / "LOG.md").write_text(
            f"- {stamp} [E-001] [T-1] [agent: {SEAT}] RUN: done\n"
            f"- {stamp} [E-002] [{picked}] [agent: {SEAT}] RUN: ticket add\n",
            encoding="utf-8",
        )
        return project

    def validate(self, project: Path) -> subprocess.CompletedProcess:
        """The REAL canonical validator on a REAL installation."""
        ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
        shutil.copytree(TOOLS, project / "tools", ignore=ignore)
        shutil.copytree(ROOT / "saipen", project / "saipen", ignore=ignore)
        shutil.copytree(ROOT / "extensions", project / "extensions", ignore=ignore)
        (project / "VERSION").write_text("8.0.2\n", encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(project / "tools" / "validate.py"), "--gate", "core"],
            cwd=str(project),
            capture_output=True,
            text=True,
            errors="replace",
            timeout=600,
        )

    def ticket(self, project: Path, tid: str = "T-7") -> dict:
        return parse_board((project / ".saipen" / "BOARD.md").read_text(encoding="utf-8"))[
            "tickets"
        ][tid]


class StaleClaimIsAdoptableTests(PickOwnershipFixture):
    """THE REPAIR: a lapsed foreign claim on the pick must not FAIL."""

    def test_a_stale_foreign_claim_on_the_pick_validates_clean(self):
        """RED on the defect: the seat released onto an adoptable ticket FAILed.

        This is the whole incident in one assertion. Before the repair the
        canonical validator refused exactly this snapshot.
        """
        project = self.make_project()
        picked = self.ticket(project)
        self.assertEqual(picked["section"], "## TODO")
        self.assertEqual(picked["fields"].get("owner"), OWNER)
        proc = self.validate(project)
        output = proc.stdout + proc.stderr
        self.assertNotIn("executing another agent's claim", output)
        self.assertEqual(
            proc.returncode,
            0,
            f"a stale foreign claim is ADOPTABLE per CORE 1.4; the pick must "
            f"validate clean. Validator said:\n{output}",
        )

    def test_the_pick_is_not_the_active_seat_so_the_shared_rule_stays_silent(self):
        """The other two canonical owners already said this was not a collision.

        Recorded as an in-test control so the repair cannot be a lucky rewrite:
        if ``ownership_invariant_errors`` ever grew a say over the un-bound
        pick, this test would notice that the two gates had started to
        overlap.
        """
        from saipen_engine import ownership

        project = self.make_project()
        state = parse_state((project / ".saipen" / "STATE.md").read_text(encoding="utf-8"))
        board_text = (project / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
        self.assertEqual(state["task"], "none")
        self.assertEqual(
            ownership.ownership_invariant_errors(state, board_text, SEAT),
            [],
        )


class LiveAndInvalidClaimTests(PickOwnershipFixture):
    """SAME-ORACLE CONTROLS: the refusals that must survive the repair."""

    def test_a_live_foreign_claim_on_the_pick_still_fails(self):
        """A live foreign claim is a genuine collision -- adoption is not takeover."""
        project = self.make_project(volley=LIVE)
        proc = self.validate(project)
        output = proc.stdout + proc.stderr
        self.assertNotEqual(proc.returncode, 0, output)
        self.assertIn("executing another agent's claim", output)

    def test_an_invalid_half_claim_on_the_pick_still_fails_closed(self):
        """owner without claim_time is unreadable -- fail closed, never pick it.

        CORE § 1.4's both-or-neither rule: a half pair is not a lapsed claim,
        it is a corrupt one, and it may never be adopted on a guess.
        """
        project = self.make_project(owner=OWNER, volley=NO_TIME)
        picked = self.ticket(project)
        self.assertEqual(picked["fields"].get("owner"), OWNER)
        self.assertIsNone(picked["fields"].get("claim_time"))
        proc = self.validate(project)
        output = proc.stdout + proc.stderr
        self.assertNotEqual(proc.returncode, 0, output)

    def test_the_gate_uses_the_shared_predicate_not_a_second_rule(self):
        """The defect was a RESTATED rule; the repair imports the one authority.

        `claim_status` is the single expiry rule (ownership.py says so in its
        own docstring). A validator that compares raw owner strings cannot see
        liveness, which is exactly how the stale case came to FAIL.
        """
        source = (TOOLS / "validate.py").read_text(encoding="utf-8")
        self.assertIn("from saipen_engine.board import (", source)
        self.assertIn("claim_status", source)
        gate = source.split("next_action names {_named}, claimed by", 1)
        self.assertEqual(
            len(gate),
            2,
            "the next_action ownership gate no longer has its own wording",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()