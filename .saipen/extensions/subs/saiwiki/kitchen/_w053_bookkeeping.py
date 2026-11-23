"""saiwiki W-053 producer bookkeeping.

Writes the producer surface for a package that is ALREADY published and already
re-verified fresh: the LOG line, the BOARD DONE row and the STATE checkpoint.
The OUTBOX entry is written by hand in the same pass and validated here rather
than re-inserted. Nothing here re-publishes or touches a payload page, the main
tree, or any remote.

Every edit is an exact, single-match, byte-level replacement: an anchor that
matches zero or two times is a hard failure, and `edit` is idempotent so a
re-run reports `already` instead of rewriting. Re-running this script must be a
no-op.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
NS = ROOT / ".saipen" / "extensions" / "subs" / "saiwiki"
OUTBOX = NS / "kitchen" / "OUTBOX.md"
LOG = NS / "LOG.md"
BOARD = NS / "BOARD.md"
STATE = NS / "STATE.md"

APPLIED: list[str] = []
ALREADY: list[str] = []


def edit(path: Path, old: str, new: str, label: str, *, gone: str | None = None) -> None:
    """Byte-exact single-match replacement, idempotent for insertions and deletions."""
    text = path.read_bytes().decode("utf-8")
    if new:
        if new in text:
            ALREADY.append(label)
            return
    elif old not in text:
        if gone is None:
            raise AssertionError(f"{label}: a deletion edit needs a `gone` postcondition")
        if gone in text:
            raise AssertionError(
                f"{label}: anchor gone but the removed row's token {gone!r} is still present"
            )
        ALREADY.append(label)
        return
    if not old:
        raise AssertionError(f"{label}: empty anchor")
    hits = text.count(old)
    if hits != 1:
        raise AssertionError(f"{label}: anchor matched {hits} times in {path.name}, expected 1")
    path.write_bytes(text.replace(old, new, 1).encode("utf-8"))
    APPLIED.append(label)


def edit_state_field(key: str, new_value: str) -> None:
    """Replace one `key: "value"` line of STATE.md, preserving its CRLF endings."""
    text = STATE.read_bytes().decode("utf-8")
    lines = [
        line for line in text.replace("\r\n", "\n").split("\n") if line.startswith(f"{key}: ")
    ]
    if len(lines) != 1:
        raise AssertionError(f"STATE.{key}: {len(lines)} matching lines, expected 1")
    edit(STATE, lines[0] + "\r\n", f'{key}: "{new_value}"\r\n', f"STATE: {key}")


LOG_MARKER = "[W-053] [parent: W-052] RUN: prepare saiwiki -> done"

LOG_LINE = (
    "- {stamp} [W-053] [parent: W-052] RUN: prepare saiwiki -> done -- FORCE-FRESH re-bind: the "
    "pending v8.2.0 release batch moved the version surfaces in the working tree (VERSION, README "
    "badge, CHANGELOG top entry dated 2026-11-03) and one commit (66ef622a, T-1950) landed past "
    "W-052's binding (HEAD b152e6de -> 66ef622a, tree b580f1f6 -> 27711c51). 3 pages corrected "
    "(Home badge+Key features heading to v8.2.0 with a host-acceptance bullet mirroring the "
    "CHANGELOG split T-2011 and the inventory re-measured on today's bytes 572/8311/276 -> "
    "617/8962/276; _Footer to v8.2.0; SubSaipen rebind W-053), 6 byte-identical; Scenarios rows "
    "corrected=0 and its marker already equalled the corpus digest f46193d66010358e, so the mirror "
    "was verified rather than rebuilt. Strict READY sha256:bc0d96eb at epoch 15 with 55 read deps "
    "and 9 payload entries; _refresh_w053.py re-run a no-op; W-052 retired stale; no integration, "
    "commit, tag, push or remote write."
)

BOARD_ROW = (
    "- [x] W-053 FORCE-FRESH re-bind past W-052 -- the pending v8.2.0 release batch moved the "
    "canonical version surfaces in the working tree (VERSION, README badge, CHANGELOG top entry "
    "dated 2026-11-03) and one commit (66ef622a, T-1950) landed past the binding (HEAD b152e6de -> "
    "66ef622a, tree b580f1f6 -> 27711c51); 3 pages corrected, 6 byte-identical: Home badge+Key "
    "features heading to v8.2.0 with a host-acceptance bullet mirroring the CHANGELOG split "
    "(T-2011) and the inventory re-measured on today's bytes (572/8311/276 -> 617/8962/276), "
    "_Footer to v8.2.0 and SubSaipen rebound to W-053 | verify: READY sha256:bc0d96eb at epoch 15 "
    "with 55 read deps and 9 payload entries, _refresh_w053.py idempotent (6 applied then 0), "
    "Scenarios rows corrected=0 at marker f46193d66010358e; no integration or push"
)


def main() -> int:
    # 0. The OUTBOX entry is hand-written in this pass; assert it is the current
    #    one rather than silently proceeding from a different package.
    outbox_text = OUTBOX.read_bytes().decode("utf-8")
    if "## W-053: FORCE-FRESH re-bind past W-052" not in outbox_text:
        raise AssertionError("OUTBOX carries no W-053 entry; write it before bookkeeping")
    ready_w053 = outbox_text.split("## W-053", 1)[1].split("## W-052", 1)[0]
    if "- **status:** ready" not in ready_w053:
        raise AssertionError("W-053 OUTBOX entry is not `status: ready`")
    ALREADY.append("OUTBOX: W-053 entry present and ready")

    # 1. LOG: append one line.
    text = LOG.read_bytes().decode("utf-8")
    if LOG_MARKER in text:
        ALREADY.append("LOG: W-053 line")
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        stamp = datetime.now(timezone.utc).strftime("%d.%m.%y %H:%M")
        LOG.write_bytes((text + LOG_LINE.format(stamp=stamp) + "\n").encode("utf-8"))
        APPLIED.append("LOG: W-053 line")

    # 2. BOARD: its own DONE row, above W-052.
    edit(
        BOARD,
        "## DONE\n- [x] W-052 FORCE-FRESH re-bind past W-051",
        "## DONE\n" + BOARD_ROW + "\n- [x] W-052 FORCE-FRESH re-bind past W-051",
        "BOARD: W-053 DONE row",
    )

    # 3. STATE: the checkpoint the prepare cycle ends on. The voice marker is
    #    DERIVED from the STYLE.md this pass actually read (PROTOCOL.md § 8: a
    #    sub STATE carries Core's shape), never typed from memory.
    edit_state_field(
        "next_action",
        "WAIT: user brake -- prepare done: W-053 ready at 66ef622a/27711c51, not integrated or pushed",
    )
    edit_state_field("updated", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    style_text = (ROOT / "saipen" / "STYLE.md").read_text(encoding="utf-8")
    marker = re.search(r"`style_contract:\s*(ded-[0-9a-f]{8})`", style_text)
    if marker is None:
        raise AssertionError("saipen/STYLE.md carries no `style_contract: ded-########` marker")
    edit_state_field("style_contract", marker.group(1))

    print(json.dumps({"applied": APPLIED, "already": ALREADY}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
