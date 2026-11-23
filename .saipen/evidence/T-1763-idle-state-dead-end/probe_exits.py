"""T-1763 SCOUT probe: does any existing canonical command leave the dead end?

    python probe_exits.py <tools-dir-of-a-disposable-copy>

The T-1671 fixture (T-001 claimed and moved to BUILD by operations), then a
hand idles STATE: phase DONE, transition_from SHIP, task none. Nothing else.
Each candidate runs on a FRESH fixture, so one answer never colours the next.
Prints the code, what moved, and the STATE and BOARD row afterwards. Reads and
reports only; it decides nothing.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

TOOLS = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(TOOLS))

import continuity_probes as probes  # noqa: E402
import test_t1671_lifecycle_authority as t1671  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

from saipen_engine.board import parse_board  # noqa: E402

CANDIDATES = (
    ("status",),
    ("recover",),
    ("recover", "--dry-run"),
    ("continue",),
    ("claim", "T-001"),
    ("claim", "T-001", "--explicit"),
    ("transition", "BUILD", "T-001", "resume"),
    ("validate",),
)


def idle_state(root: Path) -> None:
    for field, value in (("phase", "DONE"), ("transition_from", "SHIP"), ("task", "none"),
                         ("next_action", '"saipen continue"')):
        t1671._state_field(root, field, value)


def state_of(root: Path) -> dict:
    text = (root / ".saipen" / "STATE.md").read_text(encoding="utf-8")
    return {key: (re.search(rf"^{key}: (.*)$", text, re.MULTILINE) or [None, None])[1]
            for key in ("phase", "transition_from", "task", "next_action", "last_event")}


def main() -> int:
    isolate_host_session()
    out = {}
    for args in CANDIDATES:
        root = t1671._project()
        try:
            idle_state(root)
            before = t1671._bytes(root)
            answer = probes.cli(root, t1671.AGENT, *args)
            after = t1671._bytes(root)
            row = parse_board(after["BOARD.md"].decode("utf-8"))["tickets"].get("T-001", {})
            out["saipen " + " ".join(args)] = {
                "ok": answer.get("ok"),
                "code": answer.get("code"),
                "detail": str(answer.get("detail") or answer.get("message") or "")[:150],
                "names": answer.get("canonical_next_command") or answer.get("action"),
                "moved": sorted(k for k in before if before[k] != after[k]),
                "state_after": state_of(root),
                "row_section": row.get("section"),
            }
        finally:
            shutil.rmtree(root, ignore_errors=True)
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
