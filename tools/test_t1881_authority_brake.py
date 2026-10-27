"""T-1881 (SRC-306:R002): a binding brake refuses NEW authority, not old Work.

Measured on a real fixture before this module existed: with `STATE.blocker` set
-- an open operator decision -- `saipen ticket add` returned TICKET_ADDED and
`saipen claim` returned CLAIMED. The brake was enforced only by continuation
entry (`saipen continue`), so a session that went around the resume route could
manufacture the very authority the decision was waiting to grant. SRC-306 D-02
is the same defect observed live in the SMART VAC MEDIA COMPRESSOR session.

What this module pins, in both directions:

  * `ticket add`, `ticket unblock` and `claim` are refused with WAIT_BLOCKED
    while a brake binds, and the refusal names the brake's own exit route;
  * a phase move under a tripped safety VALVE still WORKS. That is not a
    tolerance: D-05 of the same audit records the opposite bug (a phase
    shortcut overwriting a tripped valve), and T-1880 fixed it by keeping the
    WAIT verbatim while letting the phase move. Refusing `transition` here
    would re-break the repair that audit asked for.

    A phase move under an OPEN OPERATOR DECISION is the other case, and this
    module originally asserted it moved too. T-1884 (same day, later: 15:13
    against this module's 12:29) deliberately reversed that half. Its measured
    defect was that `_plan_transition` never touched `blocker`, so a
    transition carried whatever it inherited into the next phase while
    `binding_brake` went on treating it as a hard stop -- the deadlock simply
    arrived one step later. T-1884's rule: a recognised gate class or a
    causally related `## BLOCKED` ticket REFUSES an ordinary phase move and
    keeps the field, because laundering real security authority away on a
    phase move is worse than the deadlock. The two tickets use the same
    literal (`BLOCKED_EXTERNAL`), so they cannot both hold; the later,
    narrower rule owns the behaviour, and the assertion below states it;
  * read-only diagnosis keeps working under the brake, and so does `--dry-run`,
    because a preview grants nothing;
  * the clean state is untouched: with no brake, every route above still works.

The red control is the first test: it asserts the refusal on the exact routes
that were measured green, so removing the gate turns this module red rather
than silently restoring the hole.

Run standalone:
    python tools/test_t1881_authority_brake.py
"""

from __future__ import annotations

import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from test_hermetic_env import isolate_host_session  # noqa: E402

SAIPEN_PY = TOOLS / "saipen.py"
VALVE_WAIT = "WAIT: safety valve reached (0 waves / 20 tickets) -- run 'cc' to continue"
DOING = "- [/] T-010 feature | owner: aleks | claim_time: 2020-01-01T00:00:00Z"
PENDING = "- [ ] T-011 [P1] pending work | verify: probe\n"


def setUpModule() -> None:
    isolate_host_session()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _project(tmp: Path, *, brake: str | None, task: str = "T-010",
             doing: str = DOING, todo: str = "", phase: str | None = None) -> Path:
    """One project whose ONLY variable is which brake, if any, is binding."""
    root = tmp / "p"
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    blocker = "BLOCKED_EXTERNAL -- vendor cert pending" if brake == "decision" else "none"
    if phase is None:
        phase = "BLOCKED" if brake == "blocked" else "BUILD"
    action = f"PHASE BUILD {task}" if task != "none" else "saipen continue"
    extra = "execution_intent: normal\n"
    if brake == "valve":
        action = VALVE_WAIT
        extra = "execution_intent: goal\ngoal_waves: 0\ngoal_tickets: 20\n"
    _write(
        root / ".saipen" / "STATE.md",
        "---\n"
        f"phase: {phase}\ntask: {task}\nnext_action: \"{action}\"\n"
        f"blocker: {blocker}\ntransition_from: {'SHIP' if phase == 'DONE' else 'SCOUT'}\n"
        f"saipen_version: 7\n"
        f"agent: aleks\nmode: full\nupdated: {now}\n{extra}---\n",
    )
    _write(
        root / ".saipen" / "BOARD.md",
        f"# Board\n## DOING\n{doing}\n## TODO\n{todo}## DONE\n## BLOCKED\n",
    )
    _write(
        root / ".saipen" / "LOG.md",
        "# Log\n\n- 01.01.20 00:00 [E-001] [T-010] [agent: aleks] RUN: build\n",
    )
    from saipen_engine.journal import ensure_project_lineage

    ensure_project_lineage(root)
    return root


def _cli(root: Path, *args: str) -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, str(SAIPEN_PY), "--project-root", str(root), "--json", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
        timeout=300,
    )
    try:
        payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except ValueError:
        payload = {"_unparseable_stdout": proc.stdout[:500]}
    return proc.returncode, payload


class BrakeRefusesNewAuthorityTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="t1881-authority-")
        self.addCleanup(shutil.rmtree, self._tmp, True)
        self.tmp = Path(self._tmp)

    def _case(self, *args: str, brake: str = "decision", **kw) -> tuple[int, dict]:
        root = _project(self.tmp / str(len(list(self.tmp.iterdir()))), brake=brake, **kw)
        return _cli(root, *args)

    def test_an_open_operator_decision_refuses_ticket_add(self):
        """The measured hole: this returned TICKET_ADDED before the gate."""
        _rc, payload = self._case("ticket", "add", "P1", "probe work", "--verify", "probe")
        self.assertFalse(payload.get("ok"), payload)
        self.assertEqual(payload.get("code"), "WAIT_BLOCKED", payload)
        self.assertEqual(payload.get("brake"), "blocker", payload)
        self.assertTrue(payload.get("canonical_next_command"), payload)

    def test_an_open_operator_decision_refuses_claim(self):
        """The second measured hole: this returned CLAIMED before the gate."""
        _rc, payload = self._case(
            "claim", "T-011", "--explicit", task="none", doing="", todo=PENDING
        )
        self.assertFalse(payload.get("ok"), payload)
        self.assertEqual(payload.get("code"), "WAIT_BLOCKED", payload)

    def test_an_open_operator_decision_refuses_ticket_unblock(self):
        """`unblock` is how a BLOCKED phase is answered -- it is authority."""
        _rc, payload = self._case("ticket", "unblock", "T-010", "carry on")
        self.assertFalse(payload.get("ok"), payload)
        self.assertEqual(payload.get("code"), "WAIT_BLOCKED", payload)

    def test_a_tripped_valve_refuses_ticket_add_too(self):
        """A valve is a bounded grant, not a licence to enlarge the backlog."""
        _rc, payload = self._case(
            "ticket", "add", "P1", "probe work", "--verify", "probe", brake="valve"
        )
        self.assertFalse(payload.get("ok"), payload)
        self.assertEqual(payload.get("code"), "WAIT_BLOCKED", payload)
        self.assertEqual(payload.get("brake"), "wait", payload)
        self.assertIn("continue", str(payload.get("canonical_next_command")), payload)

    def test_a_blocked_phase_refuses_claim(self):
        _rc, payload = self._case(
            "claim", "T-011", "--explicit", brake="blocked",
            task="none", doing="", todo=PENDING,
        )
        self.assertFalse(payload.get("ok"), payload)
        self.assertEqual(payload.get("code"), "WAIT_BLOCKED", payload)


class TheWorkAlreadyHeldStillMovesTests(unittest.TestCase):
    """The other half: refusing everything would re-break D-05's repair."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="t1881-transition-")
        self.addCleanup(shutil.rmtree, self._tmp, True)
        self.tmp = Path(self._tmp)
        self._n = 0

    def _root(self, brake: str) -> Path:
        self._n += 1
        return _project(self.tmp / str(self._n), brake=brake)

    def _state(self, root: Path) -> dict:
        from saipen_engine import codec
        from saipen_engine.state import parse_state

        return parse_state(codec.read_doc(root / ".saipen" / "STATE.md"))

    def test_a_transition_refuses_under_an_open_decision(self):
        """T-1884 supersedes the move half; the brake is the one truth.

        A phase move must not launder a recognised gate away: `binding_brake`
        reads the blocker as a hard stop in EVERY phase, so moving the phase
        while keeping it only relocates the deadlock. The refusal is therefore
        the correct outcome, it names its own exit route, and it writes no
        bytes.
        """
        root = self._root("decision")
        before = (root / ".saipen" / "STATE.md").read_bytes()
        _rc, payload = _cli(root, "transition", "VERIFY", "T-010", "probe")
        self.assertFalse(payload.get("ok"), payload)
        self.assertEqual(payload.get("code"), "OPERATOR_DECISION_REQUIRED", payload)
        self.assertTrue(payload.get("canonical_next_command"), payload)
        self.assertEqual(self._state(root).get("phase"), "BUILD")
        self.assertEqual((root / ".saipen" / "STATE.md").read_bytes(), before,
                         "a refused transition wrote bytes")

    def test_a_transition_still_moves_under_a_tripped_valve(self):
        """T-1880's repair: the phase moves, the WAIT survives verbatim."""
        root = self._root("valve")
        _rc, payload = _cli(root, "transition", "VERIFY", "T-010", "probe")
        self.assertTrue(payload.get("ok"), payload)
        self.assertEqual(payload.get("phase"), "VERIFY", payload)
        after = self._state(root)
        self.assertEqual(after.get("phase"), "VERIFY")
        self.assertEqual(after.get("next_action"), VALVE_WAIT)

    def test_diagnosis_and_preview_stay_available_under_a_brake(self):
        root = self._root("decision")
        rc, payload = _cli(root, "status")
        self.assertEqual(rc, 0, payload)
        self.assertTrue(payload.get("ok"), payload)

        # A preview writes nothing, so it grants no authority and is allowed.
        _rc, preview = _cli(root, "--dry-run", "ticket", "add", "P1", "probe", "--verify", "probe")
        self.assertTrue(preview.get("ok"), preview)
        board = (root / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
        self.assertNotIn("probe", board.replace("probe work", ""))


class InitPauseIsAnswerableTests(unittest.TestCase):
    """SRC-307 (T-1882): the `init` pause is a question whose answer IS Work.

    INIT ends at `WAIT: init -- provide the first project goal or raw backlog`.
    T-1881's gate refused `ticket add` there, so a copied runtime could `init`
    and then could not seed the ticket its own pause asks for -- measured as
    three reds in test_t1586_scenario_inputs and its dependants. The exemption
    is by closed category (`init`), never by wording.
    """

    INIT_WAIT = "WAIT: init -- provide the first project goal or raw backlog"

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="t1882-init-")
        self.addCleanup(shutil.rmtree, self._tmp, True)

    def _root(self) -> Path:
        root = _project(Path(self._tmp) / "p", brake=None, task="none", doing="", phase="PLAN")
        state = root / ".saipen" / "STATE.md"
        # Rewritten whole: `_project` seeds `next_action: "saipen continue"` for a
        # ticketless project, and a substring replace that silently missed would
        # leave no WAIT at all -- which is exactly how the first version of this
        # test passed with the exemption removed.
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        state.write_text(
            "---\n"
            "phase: PLAN\ntask: none\n"
            f'next_action: "{self.INIT_WAIT}"\n'
            "blocker: none\ntransition_from: INIT\nsaipen_version: 7\n"
            f"agent: aleks\nmode: full\nexecution_intent: normal\nupdated: {now}\n---\n",
            encoding="utf-8",
        )
        return root

    def test_ticket_add_answers_the_init_pause(self):
        root = self._root()
        rc, payload = _cli(root, "ticket", "add", "P1", "first goal", "--verify", "probe")
        self.assertEqual(rc, 0, payload)
        self.assertEqual(payload.get("code"), "TICKET_ADDED", payload)

    def test_a_real_brake_still_refuses_next_to_it(self):
        """The exemption is one category, not a hole in the gate."""
        root = _project(Path(self._tmp) / "q", brake="decision")
        rc, payload = _cli(root, "ticket", "add", "P1", "probe work", "--verify", "probe")
        self.assertEqual(rc, 1, payload)
        self.assertEqual(payload.get("code"), "WAIT_BLOCKED", payload)


class CleanStateIsUntouchedTests(unittest.TestCase):
    """No brake means no behaviour change -- the gate must not cost routes."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="t1881-clean-")
        self.addCleanup(shutil.rmtree, self._tmp, True)
        self.tmp = Path(self._tmp)
        self._n = 0

    def test_ticket_add_still_works_with_no_brake(self):
        self._n += 1
        root = _project(self.tmp / str(self._n), brake=None)
        _rc, payload = _cli(root, "ticket", "add", "P1", "probe work", "--verify", "probe")
        self.assertTrue(payload.get("ok"), payload)
        self.assertEqual(payload.get("code"), "TICKET_ADDED", payload)

    def test_claim_still_works_with_no_brake(self):
        self._n += 1
        root = _project(
            self.tmp / str(self._n), brake=None, task="none", doing="", todo=PENDING,
            phase="DONE",
        )
        _rc, payload = _cli(root, "claim", "T-011", "--explicit")
        self.assertTrue(payload.get("ok"), payload)
        self.assertEqual(payload.get("code"), "CLAIMED", payload)

    def test_transition_still_works_with_no_brake(self):
        self._n += 1
        root = _project(self.tmp / str(self._n), brake=None)
        _rc, payload = _cli(root, "transition", "VERIFY", "T-010", "probe")
        self.assertTrue(payload.get("ok"), payload)
        self.assertEqual(payload.get("phase"), "VERIFY", payload)


class TheGateReadsTheOneBrakeTests(unittest.TestCase):
    """The gate must not carry its own brake vocabulary (T-1322's lesson)."""

    def test_the_gate_asks_state_binding_brake(self):
        source = SAIPEN_PY.read_text(encoding="utf-8")
        start = source.index("def _authority_refusal(")
        end = source.index("\ndef _ensure_handover(", start)
        body = source[start:end]
        self.assertIn("binding_brake(", body)
        self.assertIn("_BRAKE_ROUTES", body)
        # A second brake vocabulary would drift from the router and the guard.
        for invented in ("safety valve reached (", "BLOCKED_EXTERNAL --"):
            self.assertNotIn(invented, body)

    def test_transition_and_ingress_are_deliberately_absent(self):
        source = SAIPEN_PY.read_text(encoding="utf-8")
        start = source.index("_AUTHORITY_GRANTING")
        end = source.index("def _authority_refusal(", start)
        declared = source[start:end]
        self.assertNotIn('("transition"', declared)
        self.assertNotIn('("start"', declared)
        self.assertNotIn('("user-request"', declared)
        self.assertNotIn('("recover"', declared)
        for present in ('("ticket", "add")', '("claim", None)'):
            self.assertIn(present, declared)


if __name__ == "__main__":
    unittest.main(verbosity=2)
