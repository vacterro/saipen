"""T-1669: a transition into terminal DONE commits the router's route.

Measured live (E-13182 / E-13186 / E-13187,
`.saipen/evidence/T-1640-live-clean/validate.exit.txt`): a conformant CLEAN run
made Work runnable before it exited, and `saipen transition DONE` then
persisted `next_action: "PHASE DONE"` -- a value that is not a route at all.
The validator read the contradiction correctly ("STATE.md audit route not
followed ... but next_action is 'PHASE DONE'"; the inbox routed
`PHASE SCOUT T-1304`), so the producer was the thing to repair, never the
detector.

DONE is terminal lifecycle state: what follows it is the SHARED router's
answer over the PROPOSED post-transition bytes, exactly as `ticket done`
already computes it (`operations._plan_finish_ticket`). Held here:

  * the exact incident -- CLEAN -> DONE over routed runnable Work commits
    `PHASE SCOUT <ticket>`, the operation's own report agrees with the bytes on
    disk, and `validate.py --gate core` is green BEFORE any Work is claimed
    (no later session may accidentally repair the field by claiming);
  * a RED control -- the pre-fix artifact (`PHASE DONE`) is red on that same
    fixture when it is driven through the real writer;
  * CLEAN -> DONE with nothing routed stays router-consistent and green;
  * non-DONE transitions keep their existing next_action contract.

Run standalone:
    python -B tools/test_t1669_clean_done_projection.py
"""

from __future__ import annotations

import datetime
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import audit_inbox  # noqa: E402
from saipen_engine.board import parse_board  # noqa: E402
from saipen_engine.operations import transition_phase  # noqa: E402
from saipen_engine.router import route_next  # noqa: E402
from saipen_engine.state import parse_state  # noqa: E402
from test_guard_hostile_matrix import fresh_project  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

AGENT = "test-agent"
VALIDATE_PY = TOOLS / "validate.py"
#: The layer number and the ticket the live incident measured.
AUDIT_LAYER = 16
TICKET = "T-1304"
AUDIT_BODY = "# audit 16\n\nfindings that CLEAN freed Work for\n"


def setUpModule() -> None:
    # An outer host session must never bind these disposable fixtures.
    isolate_host_session()


def _utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _board(*, doing: str = "", todo: str = "") -> str:
    lines = ["# Board", "## DOING"]
    if doing:
        lines.append(doing)
    lines.append("## TODO")
    if todo:
        lines.append(todo)
    lines += ["## DONE", "## BLOCKED"]
    return "\n".join(lines) + "\n"


def _state_text(root: Path) -> str:
    return (root / ".saipen" / "STATE.md").read_text(encoding="utf-8")


def _board_text(root: Path) -> str:
    return (root / ".saipen" / "BOARD.md").read_text(encoding="utf-8")


def _state(root: Path) -> dict:
    return parse_state(_state_text(root))


def _doing(root: Path) -> list[str]:
    tickets = parse_board(_board_text(root))["tickets"]
    return [tid for tid, t in tickets.items() if t["section"] == "## DOING"]


def _transition_from(root: Path, predecessor: str) -> None:
    """Point the fixture's history at a LEGAL predecessor of its phase.

    `fresh_project` always stamps `transition_from: SHIP`; the fast check
    validates the persisted pair, so a fixture in SCOUT has to say DONE.
    """
    path = root / ".saipen" / "STATE.md"
    path.write_text(
        re.sub(r"(?m)^transition_from:.*$", f"transition_from: {predecessor}", _state_text(root)),
        encoding="utf-8",
    )


def _bind_active_audit(root: Path, work: str) -> dict:
    """Layer 16 ACTIVE and bound to `work`, through the real inbox contract."""
    layer = root / "audit" / f"{AUDIT_LAYER}.md"
    layer.parent.mkdir(parents=True, exist_ok=True)
    layer.write_text(AUDIT_BODY, encoding="utf-8")
    rel = f"audit/{AUDIT_LAYER}.md"
    captured = audit_inbox.capture_layer(root, rel, work=work)
    assert captured["ok"], captured
    audit_inbox.bind_layer(
        root,
        rel,
        layer=AUDIT_LAYER,
        generation=1,
        file_sha256=captured["file_sha256"],
        size_bytes=len(AUDIT_BODY.encode("utf-8")),
        receipt_id=captured["receipt"],
        receipt_sha256=captured["file_sha256"],
        binding="exact",
        linked_work=work,
        state=audit_inbox.ACTIVE,
    )
    return audit_inbox.projection(root)


def _clean_project_with_runnable_work() -> tuple[Path, dict]:
    """The incident's shape: CLEAN with routed Work it just made runnable."""
    root = fresh_project(phase="CLEAN", task="none", next_action="PHASE CLEAN")
    (root / ".saipen" / "BOARD.md").write_text(
        _board(todo=f"- [ ] {TICKET} [P2] runnable once CLEAN exits | verify: proof"),
        encoding="utf-8",
    )
    return root, _bind_active_audit(root, TICKET)


def _core_findings(root: Path) -> list[str]:
    """Every FAIL/WARN line `validate.py --gate core` prints for `root`."""
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
    env["PYTHONUTF8"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", str(VALIDATE_PY), "--gate", "core"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        env=env,
        cwd=str(root),
        timeout=600,
        check=False,
    )
    text = proc.stdout.decode("utf-8", errors="replace")
    return [line for line in text.splitlines() if line.startswith(("FAIL", "WARN"))]


def _core_fails(root: Path) -> list[str]:
    return [line for line in _core_findings(root) if line.startswith("FAIL")]


class CleanExitProjectsTheRouter(unittest.TestCase):
    """The exact incident: CLEAN -> DONE over routed runnable Work."""

    def test_clean_to_done_commits_the_routed_scout_before_any_claim(self):
        root, projection = _clean_project_with_runnable_work()
        # The inbox's route and the shared router's pick are the same fact:
        # the layer's linked Work IS the topmost workable TODO, which is
        # exactly what "CLEAN made it runnable" means.
        self.assertEqual(projection["action"], f"PHASE SCOUT {TICKET}")
        self.assertEqual(projection["layer"], AUDIT_LAYER)

        result = transition_phase(root, "DONE", AGENT)
        self.assertTrue(result.ok, result.to_dict())

        state = _state(root)
        self.assertEqual(state["phase"], "DONE")
        self.assertEqual(state["task"], "none")
        self.assertEqual(state["next_action"], f"PHASE SCOUT {TICKET}")
        # The operation's report and the committed bytes are one fact.
        self.assertEqual(result.data.get("next_action"), state["next_action"])
        # ... and nothing has been claimed: the project must be valid as it
        # stands, without a later session repairing next_action by working.
        self.assertEqual(_doing(root), [])
        self.assertEqual(_core_fails(root), [])


class PreFixProjectionIsRed(unittest.TestCase):
    """RED control: the artifact T-1669 measured, driven through the writer."""

    def test_the_pre_fix_value_fails_the_same_fixture(self):
        root, _projection = _clean_project_with_runnable_work()
        # Pre-fix, `_plan_transition` persisted `PHASE DONE` without asking
        # anyone. Feeding that exact value back through the real writer
        # reproduces the measured artifact; the fixture is otherwise identical
        # to the green case above.
        with patch(
            "saipen_engine.router.route_next",
            return_value={"ok": True, "action": "PHASE DONE", "reason": "control"},
        ):
            result = transition_phase(root, "DONE", AGENT)
        self.assertTrue(result.ok, result.to_dict())
        self.assertEqual(_state(root)["next_action"], "PHASE DONE")

        fails = _core_fails(root)
        self.assertTrue(fails, "the pre-fix artifact must not validate")
        self.assertTrue(
            any("audit route not followed" in line for line in fails),
            fails,
        )
        self.assertTrue(any(f"PHASE SCOUT {TICKET}" in line for line in fails), fails)


class NoRoutedWorkStaysRouterConsistent(unittest.TestCase):
    """CLEAN -> DONE with nothing to start: the router's answer, verbatim."""

    def test_clean_to_done_without_routed_work_matches_the_router(self):
        root = fresh_project(phase="CLEAN", task="none", next_action="PHASE CLEAN")
        result = transition_phase(root, "DONE", AGENT)
        self.assertTrue(result.ok, result.to_dict())

        state = _state(root)
        self.assertEqual(state["phase"], "DONE")
        self.assertEqual(state["task"], "none")
        # No audit layer, no workable TODO: whatever the shared router
        # truthfully projects is the value, and it is never a stale PHASE DONE.
        routed = route_next(_state_text(root), _board_text(root), current_agent=AGENT)
        self.assertTrue(routed.get("ok"), routed)
        self.assertEqual(state["next_action"], routed["action"])
        self.assertNotEqual(state["next_action"], "PHASE DONE")
        self.assertEqual(result.data.get("next_action"), state["next_action"])
        self.assertEqual(_core_fails(root), [])


class NonDoneTransitionsKeepTheirContract(unittest.TestCase):
    """The repair is scoped to DONE; every other edge is untouched."""

    def _active_project(self, phase: str, task: str, next_action: str) -> Path:
        root = fresh_project(phase=phase, task=task, next_action=next_action)
        (root / ".saipen" / "BOARD.md").write_text(
            _board(
                doing=f"- [/] {task} [P1] ordinary Work | verify: proof "
                f"| owner: {AGENT} | claim_time: {_utc()}"
            ),
            encoding="utf-8",
        )
        return root

    def test_a_ticket_bearing_transition_still_names_the_ticket(self):
        root = self._active_project("SCOUT", "T-7", "PHASE SCOUT T-7")
        _transition_from(root, "DONE")
        planned = transition_phase(root, "BUILD", AGENT, "T-7", "regression", dry_run=True)
        self.assertTrue(planned.ok, planned.to_dict())
        self.assertEqual(planned.data.get("next_action"), "PHASE BUILD T-7")
        # The dry run wrote nothing, including no projection.
        self.assertEqual(_state(root)["next_action"], "PHASE SCOUT T-7")

    def test_a_nonterminal_phase_keeps_its_phase_route(self):
        root = self._active_project("BUILD", "T-7", "PHASE BUILD T-7")
        result = transition_phase(root, "VERIFY", AGENT, "T-7", "regression")
        self.assertTrue(result.ok, result.to_dict())
        state = _state(root)
        self.assertEqual(state["phase"], "VERIFY")
        self.assertEqual(state["next_action"], "PHASE VERIFY T-7")
        self.assertEqual(result.data.get("next_action"), state["next_action"])

    def test_a_non_ticket_destination_keeps_its_plain_phase_route(self):
        root = fresh_project(phase="DONE", task="none", next_action="saipen continue")
        result = transition_phase(root, "PLAN", AGENT)
        self.assertTrue(result.ok, result.to_dict())
        state = _state(root)
        self.assertEqual(state["phase"], "PLAN")
        self.assertEqual(state["next_action"], "PHASE PLAN")
        self.assertEqual(result.data.get("next_action"), state["next_action"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
