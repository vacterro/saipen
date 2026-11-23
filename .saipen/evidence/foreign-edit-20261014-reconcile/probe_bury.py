"""T-1759 probe: does resolve_duplicate_id build on an unauthorized head?

    python probe_bury.py <tools-dir-of-a-disposable-copy>

Builds a project with a real operation ledger (the T-1671 fixture), types the
lifecycle by hand the way that incident did, puts one duplicated ticket id on
the BOARD, then executes the duplicate-id decision. Prints what the function
answered, whether canonical bytes moved, and the lifecycle-authority verdict
before and after. Run it once per subject (with and without the foreign hunk).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

TOOLS = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(TOOLS))

import test_t1671_lifecycle_authority as t1671  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

from saipen_engine import lifecycle_authority, reconcile  # noqa: E402
from saipen_engine.board import duplicate_records  # noqa: E402
from saipen_engine.operations import TYPED_HEAD_QUARANTINE_OBSERVABLE, _read  # noqa: E402

DUPLICATE = (
    "- [ ] T-050 [P2] first record of the duplicated id | verify: probe\n"
    "- [ ] T-050 [P2] second record of the duplicated id | verify: probe\n"
)


def verdict(root: Path) -> str:
    docs, _state, _board, _tail = _read(root, observe=TYPED_HEAD_QUARANTINE_OBSERVABLE)
    lifecycle = docs["_lifecycle"]
    return f"{lifecycle['status']} findings={len(lifecycle.get('findings') or [])}"


def main() -> int:
    isolate_host_session()
    root = t1671._project()
    board = root / ".saipen" / "BOARD.md"
    text = board.read_text(encoding="utf-8")
    assert text.count("## TODO\n") == 1, text
    board.write_text(text.replace("## TODO\n", "## TODO\n" + DUPLICATE), encoding="utf-8",
                     newline="\n")
    t1671._type_the_lifecycle(root)
    records = duplicate_records(board.read_text(encoding="utf-8"), "T-050")
    assert len(records) == 2, records
    before = t1671._bytes(root)
    out = {
        "subject": str(TOOLS / "saipen_engine" / "reconcile.py"),
        "lifecycle_code": lifecycle_authority.CODE,
        "lifecycle_before": verdict(root),
        "validator_lifecycle_fails_before": len(t1671._lifecycle_fails(root)),
    }
    answer = reconcile.resolve_duplicate_id(
        root, t1671.AGENT, "T-050", records[0]["digest"], records[1]["digest"]
    )
    after = t1671._bytes(root)
    out.update(
        answer={key: answer.get(key) for key in ("ok", "code")},
        answer_detail=str(answer.get("detail") or "")[:300],
        canonical_bytes_changed=sorted(name for name in before if before[name] != after[name]),
        lifecycle_after=verdict(root),
        validator_lifecycle_fails_after=len(t1671._lifecycle_fails(root)),
    )
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
