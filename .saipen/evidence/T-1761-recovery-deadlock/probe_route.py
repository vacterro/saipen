"""T-1761 probe: follow only the commands the engine prints, to the end.

    python probe_route.py <tools-dir-of-a-disposable-copy> [typed-duplicate]

The T-1671 fixture with the lifecycle typed by hand and one duplicated id.
Default shape: the duplicate (T-050, twice under TODO) is beside the typed
closure of T-001. `typed-duplicate`: the hand also typed a second T-001 record
under DONE, so the typed row is itself one of the duplicated records.

Each step runs the command the previous answer named. Prints, per step, the
answer code, which canonical files moved, and the lifecycle verdict after it.
"""

from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path

TOOLS = Path(sys.argv[1]).resolve()
SHAPE = sys.argv[2] if len(sys.argv) > 2 else "beside"
sys.path.insert(0, str(TOOLS))

import continuity_probes as probes  # noqa: E402
import test_t1671_lifecycle_authority as t1671  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

from saipen_engine.board import parse_board  # noqa: E402
from saipen_engine.operations import TYPED_HEAD_QUARANTINE_OBSERVABLE, _read  # noqa: E402

BESIDE = (
    "- [ ] T-050 [P2] first record of the duplicated id | verify: probe\n"
    "- [ ] T-050 [P2] second record of the duplicated id | verify: probe\n"
)


def verdict(root: Path) -> str:
    try:
        docs, _state, _board, _tail = _read(root, observe=TYPED_HEAD_QUARANTINE_OBSERVABLE)
    except Exception as exc:  # the probe reports, it never judges
        return f"UNREADABLE {getattr(exc, 'code', '')}: {str(exc)[:120]}"
    lifecycle = docs["_lifecycle"]
    rows = sorted({f.get("ticket") for f in lifecycle.get("findings") or () if f.get("ticket")})
    return f"{lifecycle['status']} rows={rows}"


def sections(root: Path) -> dict:
    board = parse_board((root / ".saipen" / "BOARD.md").read_text(encoding="utf-8"))
    return {
        "errors": [error[:70] for error in board["errors"]][:3],
        "tickets": {name: row.get("section") for name, row in sorted(board["tickets"].items())},
    }


def next_command(answer: dict) -> list | None:
    decision = answer.get("duplicate_id_decision") or {}
    choices = decision.get("choices") or []
    if choices:
        return shlex.split(choices[0])[1:]
    for key in ("canonical_next_command", "remediation_command", "approval_command", "command"):
        value = answer.get(key)
        if isinstance(value, str) and value.startswith("saipen "):
            return shlex.split(value)[1:]
    for value in answer.values():
        if isinstance(value, dict):
            found = next_command(value)
            if found:
                return found
    return None


def main() -> int:
    isolate_host_session()
    root = t1671._project()
    board = root / ".saipen" / "BOARD.md"
    text = board.read_text(encoding="utf-8")
    if SHAPE == "beside":
        board.write_text(text.replace("## TODO\n", "## TODO\n" + BESIDE), encoding="utf-8",
                         newline="\n")
        t1671._type_the_lifecycle(root)
    else:
        # The hand leaves the canonical T-001 row where it is and types a
        # second T-001 record under DONE, with the LOG lines and STATE to match.
        t1671._type_the_lifecycle(root)
        typed = board.read_text(encoding="utf-8")
        row = next(line for line in text.splitlines() if "T-001" in line)
        section = "## DOING\n" if "## DOING\n" in typed else "## TODO\n"
        board.write_text(typed.replace(section, section + row + "\n", 1), encoding="utf-8",
                         newline="\n")
    out = {"shape": SHAPE, "start": {"lifecycle": verdict(root), "board": sections(root)}}
    command = ["recover"]
    for step in range(1, 9):
        before = t1671._bytes(root)
        answer = probes.cli(root, t1671.AGENT, *command)
        after = t1671._bytes(root)
        out[f"{step} saipen {' '.join(command)[:70]}"] = {
            "code": answer.get("code"),
            "ok": answer.get("ok"),
            "detail": str(answer.get("detail") or answer.get("message") or "")[:200],
            "moved": sorted(name for name in before if before[name] != after[name]),
            "lifecycle": verdict(root),
        }
        if answer.get("ok") and answer.get("code") in ("CLEAN", "RECONCILED", "NOTHING_TO_RECOVER"):
            break
        follow = next_command(answer)
        if follow is None:
            follow = ["recover"] if command != ["recover"] else None
        if follow is None:
            out["stopped"] = "the last answer names no command"
            out["last_answer_keys"] = sorted(answer)[:40]
            break
        command = follow
    out["end"] = {"lifecycle": verdict(root), "board": sections(root),
                  "validator lifecycle FAIL lines": len(t1671._lifecycle_fails(root))}
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
