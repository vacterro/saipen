"""RED control: a foreign LIVE owner does not stop an UNSEATED product mutation.

Field observation (T-1367 final matrix, condition `foreign_owner`): the model
ran no saipen command at all, the canonical ledger stayed byte-identical, and
`src/app.py` changed anyway. Seat theft did not happen; product mutation did.

This control is the narrow deterministic form of that run. It does not drive a
model. It asks the guard the exact question the host asks it before an edit:

    event: before_tool
    tool:  edit | write | bash
    cwd:   a project whose LIVE Work is owned by `codex`
    actor: ABSENT -- the arriving agent never declared a seat

Expected (the invariant section 8 names):
    every one of the three tools is REFUSED with OWNERSHIP_CONFLICT

Measured (the defect):
    admission inherits STATE.agent as the actor, so the arriving agent IS
    `codex` as far as ownership is concerned, and the mutation is admitted.

Run from the repository root:
    python <this file>
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve()
REPO = Path.cwd()
sys.path.insert(0, str(REPO / "tools"))

from saipen_engine import guard_events  # noqa: E402

import test_t1363_zero_manual_entry as fixtures  # noqa: E402


class _Case(unittest.TestCase):
    """Fixtures take a TestCase for its tmpdir/cleanup registration only."""

    def runTest(self) -> None:  # pragma: no cover - never executed as a test
        pass


def probe(project: Path, tool_name: str, tool_input: dict) -> dict:
    event = guard_events.load_event(
        json.dumps(
            {
                "event": "before_tool",
                "host": "opencode",
                "cwd": str(project),
                "tool_name": tool_name,
                "tool_input": tool_input,
                # actor ABSENT on purpose: this is the unseated arrival.
            }
        )
    )
    return guard_events.evaluate_event(event, None)


def main() -> int:
    case = _Case()
    case.setUp() if hasattr(case, "setUp") else None
    project = fixtures.foreign_owner_project(case)

    state = (project / ".saipen" / "STATE.md").read_text(encoding="utf-8")
    board = (project / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
    target = project / "src" / "app.py"
    before = target.read_bytes() if target.is_file() else b""

    print("## Fixture")
    print(f"project      : {project}")
    print(f"STATE.agent  : {[ln for ln in state.splitlines() if ln.startswith('agent:')]}")
    print(f"STATE.task   : {[ln for ln in state.splitlines() if ln.startswith('task:')]}")
    print(f"STATE.phase  : {[ln for ln in state.splitlines() if ln.startswith('phase:')]}")
    print(f"BOARD.DOING  : {[ln for ln in board.splitlines() if ln.startswith('- [/]')]}")
    print(f"target bytes : {len(before)}")
    print()

    probes = {
        "edit": {"filePath": str(target), "oldString": "def main", "newString": "def main2"},
        "write": {"filePath": str(target), "content": "# unseated write\n"},
        "bash": {"command": f'printf "x" >> "{target}"'},
    }

    print("## Guard verdicts for an UNSEATED arrival")
    reds = []
    for tool_name, tool_input in probes.items():
        verdict = probe(project, tool_name, tool_input)
        code = verdict.get("code")
        allowed = bool(verdict.get("ok")) and code not in ("OWNERSHIP_CONFLICT", "UNSEATED_MUTATION")
        print(f"{tool_name:<6} ok={verdict.get('ok')!s:<5} code={code!r} actor={verdict.get('actor')!r}")
        print(f"       detail={str(verdict.get('detail'))[:160]!r}")
        if allowed:
            reds.append(tool_name)
    print()

    print("## Verdict")
    if reds:
        print(f"RED: guard ADMITS unseated product mutation via {','.join(reds)}")
        print("expected: a refusal on all three -- a live foreign owner")
        print("          must block product bytes, not only the canonical ledger")
        return 1
    print("GREEN: every unseated product mutation refused (UNSEATED_MUTATION)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
