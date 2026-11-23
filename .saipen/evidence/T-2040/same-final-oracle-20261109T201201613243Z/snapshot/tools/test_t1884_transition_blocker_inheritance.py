"""T-1884 (SRC-309): a transition must not inherit a blocker it never authored.

Measured defect. `_plan_transition` built its owned-field set as
`{phase, next_action, transition_from, last_event, updated, agent}` and never
touched `blocker`, so whatever a previous phase carried came along:

  * SHIP + `operator_required (continuation_authority) for REVIEW -> SHIP`
    transitioned to BUILD and kept the blocker;
  * BLOCKED + any blocker transitioned to SCOUT and kept the blocker.

`binding_brake` treats a non-empty blocker as a hard stop in EVERY phase, so
each successful transition left the project refusing every consequential verb.
The deadlock arrived one step after the agent-written prose instead of at it.

The rule under test reuses the ONE classifier `recover` trusts
(`_state_blocker_repairs`), so a transition and a recovery cannot disagree:

  * leaving BLOCKED clears that phase's own field;
  * a blocker proven stale in an ACTIVE phase is cleared -- requiring an
    operator to run `recover` first is the manual round trip the mission
    forbids;
  * a GENUINE gate (recognised class token, or a causally related `## BLOCKED`
    ticket) refuses the transition and keeps the field. A phase move must never
    launder real security authority away.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

SAIPEN_CLI = TOOLS / "saipen.py"

STALE = "operator_required (continuation_authority) for REVIEW -> SHIP"
HELD = "HELD -- operator must decide before ship"
EXTERNAL = "BLOCKED_EXTERNAL -- vendor cert pending"
ACTIVE = "T-1517"
UNRELATED = ("T-1469", "T-1480")


def setUpModule() -> None:
    isolate_host_session()


def _project(phase="SHIP", blocker="none", blocked=(), active_needs=()) -> Path:
    root = Path(tempfile.mkdtemp(prefix="t1884-transition-"))
    (root / ".saipen").mkdir(parents=True)
    from saipen_engine.state import running_home

    (root / ".saipen" / "STATE.md").write_text(
        "---\n"
        f"phase: {phase}\n"
        f"task: {ACTIVE}\n"
        f'next_action: "PHASE {phase} {ACTIVE}"\n'
        f'blocker: "{blocker}"\n'
        "transition_from: REVIEW\n"
        "saipen_version: 8\n"
        "schema_version: 3\n"
        f"last_event: {len(blocked) + 4}\n"
        "style_contract: " + CURRENT_STYLE_CONTRACT + "\n"
        "mode: full\n"
        "updated: 2026-10-24T00:00:00Z\n"
        "agent: tester\n"
        f"saipen_home: {running_home().as_posix()}\n"
        "---\n",
        encoding="utf-8",
    )
    needs = f" | needs: {', '.join(active_needs)}" if active_needs else ""
    rows = "".join(
        f"- [ ] {tid} [P2] parked external work | verify: external ack"
        " | blocker: vendor ack pending | blocker_scope: ticket\n"
        for tid in blocked
    )
    (root / ".saipen" / "BOARD.md").write_text(
        "## DOING\n"
        f"- [/] {ACTIVE} [P1] ship the release | verify: acceptance suite{needs}"
        " | owner: tester | claim_time: 2026-10-24T00:00:00Z\n"
        "## TODO\n## DONE\n## BLOCKED\n" + rows,
        encoding="utf-8",
    )
    events = [
        f"- 24.10.26 00:00 [E-004] [{ACTIVE}] [agent: tester] "
        f"[op: ticket-{int(ACTIVE.split('-')[1]):032d}] DEC: ticket added via SAIOPS\n"
    ]
    for offset, tid in enumerate(blocked, start=1):
        events.append(
            f"- 24.10.26 00:00 [E-{4 + offset:03d}] [{tid}] [agent: tester] "
            f"[op: ticket-{int(tid.split('-')[1]):032d}] DEC: ticket added via SAIOPS\n"
        )
    (root / ".saipen" / "LOG.md").write_text("# Log\n" + "".join(events),
                                            encoding="utf-8")
    return root


def _state_fields(root: Path) -> dict[str, str]:
    text = (root / ".saipen" / "STATE.md").read_text(encoding="utf-8")
    fields = {}
    for line in text.splitlines():
        match = re.match(r"^(phase|task|blocker):\s*(.*)$", line)
        if match:
            fields[match.group(1)] = match.group(2).strip().strip('"')
    return fields


class TransitionBlockerInheritanceTests(unittest.TestCase):
    def _run(self, root: Path, destination: str) -> tuple[int, dict]:
        env = dict(os.environ)
        env.pop("PWD", None)
        env.pop("OLDPWD", None)
        proc = subprocess.run(
            [sys.executable, str(SAIPEN_CLI), "transition", destination, ACTIVE,
             "T-1884 probe", "--project-root", str(root), "--agent", "tester",
             "--json"],
            cwd=str(root), capture_output=True, text=True, env=env, timeout=600,
        )
        try:
            import json

            return proc.returncode, json.loads(proc.stdout)
        except ValueError:
            self.fail(f"non-JSON reply: {proc.stdout[:400]!r} {proc.stderr[:300]!r}")

    def _root(self, **kwargs) -> Path:
        root = _project(**kwargs)
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        return root

    def test_e10_a_stale_blocker_is_not_inherited_by_the_next_phase(self):
        root = self._root(phase="SHIP", blocker=STALE)
        code, payload = self._run(root, "BUILD")
        self.assertEqual(code, 0, payload)
        self.assertTrue(payload.get("ok"), payload)
        after = _state_fields(root)
        self.assertEqual(after["phase"], "BUILD")
        self.assertIn(after["blocker"].lower(), ("none", '""'), after)

    def test_e11_leaving_blocked_clears_the_phase_own_blocker(self):
        root = self._root(phase="BLOCKED", blocker=HELD)
        code, payload = self._run(root, "SCOUT")
        self.assertEqual(code, 0, payload)
        after = _state_fields(root)
        self.assertEqual(after["phase"], "SCOUT")
        self.assertIn(after["blocker"].lower(), ("none", '""'), after)

    def test_a_held_gate_refuses_and_is_preserved(self):
        root = self._root(phase="SHIP", blocker=HELD)
        before = (root / ".saipen" / "STATE.md").read_bytes()
        code, payload = self._run(root, "BUILD")
        self.assertNotEqual(code, 0, payload)
        self.assertEqual(payload.get("code"), "OPERATOR_DECISION_REQUIRED", payload)
        self.assertEqual((root / ".saipen" / "STATE.md").read_bytes(), before,
                         "a refused transition wrote bytes")

    def test_a_recognised_class_token_refuses_and_is_preserved(self):
        root = self._root(phase="SHIP", blocker=EXTERNAL)
        code, payload = self._run(root, "BUILD")
        self.assertNotEqual(code, 0, payload)
        self.assertEqual(payload.get("code"), "OPERATOR_DECISION_REQUIRED", payload)
        self.assertEqual(_state_fields(root)["blocker"], EXTERNAL)

    def test_a_causally_related_blocked_ticket_refuses(self):
        root = self._root(phase="SHIP", blocker=STALE, blocked=(UNRELATED[0],),
                          active_needs=(UNRELATED[0],))
        code, payload = self._run(root, "BUILD")
        self.assertNotEqual(code, 0, payload)
        self.assertEqual(payload.get("code"), "OPERATOR_DECISION_REQUIRED", payload)
        self.assertEqual(_state_fields(root)["blocker"], STALE)

    def test_an_unrelated_blocked_ticket_does_not_block_the_transition(self):
        root = self._root(phase="SHIP", blocker=STALE, blocked=UNRELATED)
        code, payload = self._run(root, "BUILD")
        self.assertEqual(code, 0, payload)
        self.assertIn(_state_fields(root)["blocker"].lower(), ("none", '""'))

    def test_a_clean_project_transitions_as_before(self):
        root = self._root(phase="SHIP", blocker="none")
        code, payload = self._run(root, "BUILD")
        self.assertEqual(code, 0, payload)
        self.assertEqual(_state_fields(root)["phase"], "BUILD")


if __name__ == "__main__":
    unittest.main()
