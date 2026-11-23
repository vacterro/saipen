"""T-1759 probe: can a typed head that also duplicates an id be recovered at all?

    python probe_deadlock.py <tools-dir-of-a-disposable-copy>

The T-1671 fixture, the lifecycle typed by hand, and one duplicated ticket id.
Drives the real CLI the way an executor would: `recover`, then the duplicate-id
decision it prints, then `recover` again. Prints each answer and whether the
canonical bytes moved. A route where every step refuses and nothing moves is a
deadlock: the reason an executor edited the engine instead.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

TOOLS = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(TOOLS))

import continuity_probes as probes  # noqa: E402
import test_t1671_lifecycle_authority as t1671  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

from saipen_engine.board import duplicate_records  # noqa: E402

DUPLICATE = (
    "- [ ] T-050 [P2] first record of the duplicated id | verify: probe\n"
    "- [ ] T-050 [P2] second record of the duplicated id | verify: probe\n"
)


def brief(answer: dict) -> dict:
    kept = {key: answer.get(key) for key in ("ok", "code", "next_action", "action")}
    kept["detail"] = str(answer.get("detail") or answer.get("message") or "")[:260]
    decision = answer.get("duplicate_id_decision")
    if decision:
        kept["duplicate_id_decision"] = {key: decision.get(key) for key in ("ticket", "choices")}
    plan = answer.get("plan") or answer.get("repair_plan")
    if plan:
        kept["plan"] = str(plan)[:200]
    for key in ("approval", "plan_id", "operator_action", "requires_approval", "repairs"):
        if answer.get(key):
            kept[key] = str(answer.get(key))[:240]
    return kept


def main() -> int:
    isolate_host_session()
    root = t1671._project()
    board = root / ".saipen" / "BOARD.md"
    text = board.read_text(encoding="utf-8")
    board.write_text(text.replace("## TODO\n", "## TODO\n" + DUPLICATE), encoding="utf-8",
                     newline="\n")
    t1671._type_the_lifecycle(root)
    records = duplicate_records(board.read_text(encoding="utf-8"), "T-050")
    out = {}
    steps = (
        ("1 recover", ("recover",)),
        ("2 duplicate-id decision", ("recover", "--resolve-duplicate-id", "T-050", "--keep",
                                     records[0]["digest"], "--reassign", records[1]["digest"])),
        ("3 recover again", ("recover",)),
        ("4 continue", ("continue",)),
    )
    for name, args in steps:
        before = t1671._bytes(root)
        answer = probes.cli(root, t1671.AGENT, *args)
        after = t1671._bytes(root)
        out[name] = brief(answer)
        out[name]["canonical_bytes_changed"] = sorted(k for k in before if before[k] != after[k])
    out["validator lifecycle FAIL lines at the end"] = len(t1671._lifecycle_fails(root))
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
