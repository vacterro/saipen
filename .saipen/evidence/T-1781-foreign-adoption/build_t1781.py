"""T-1781: adopt the foreign T-36/T-37/T-38 engine edits, and fix T-37's guard.

    python -B build_t1781.py before <root> <out-dir>   # write the pre-foreign subjects
    python -B build_t1781.py fix <root> [--check]      # T-37 guard reads the latest BUILD

`before` reconstructs the subjects without the three foreign hunks (they left
no pre-edit bytes behind; zcode artifacts hold none for 14.10.26 12:30Z), by
removing exactly the blocks each hunk added. `fix` changes only T-37's guard:
the foreign version refused `own_patch` when ANY of the ticket's BUILD records
declared `implementation_delta none`, so a ticket whose later BUILD carried a
real patch could not close as its own patch. The latest BUILD record decides.
Every anchor must match exactly once; line endings are kept.
"""

from __future__ import annotations

import sys
from pathlib import Path

OPS = "tools/saipen_engine/operations.py"
FALLBACK = "tools/saipen_engine/continue_fallback.py"
CLI = "tools/saipen.py"

T37_HELPER_START = "#: A BUILD record that states plainly it carried no implementation delta.\n"
T37_HELPER_END = "            found.append(event)\n    return found\n\n\n"
T37_GUARD_START = "    # T-37 (vacterro-saiwebsite improve 20261013-1 IMP-003): an `own_patch`\n"
T37_GUARD_END = "            ticket=ticket_id,\n        )\n    # T-1162: a short BOARD title"
T38_FUNCS_START = "def _manifest_field(text: str, key: str) -> str:\n"
T38_FUNCS_END = "def resume_action(root: Path, cycle_id: str, agent: str) -> tuple[str, str]:\n"
T38_WIRING = (
    "        # T-38: every outcome of this fallthrough names the assigned cycle's\n"
    "        # liveness (age, draft/no-RUN state, submit route), so a stale cycle\n"
    "        # is visible work rather than a clean idle verdict.\n"
    "        from saipen_engine.continue_fallback import with_cycle_liveness\n"
    "\n"
    "        payload = with_cycle_liveness(payload, project_root)\n"
)
T36_PAIRS = [
    ('"transition <PHASE> [T-###] [text]|checkpoint <DEC|RUN> "', '"transition <PHASE> [T-###] [text]|checkpoint <TAXONOMY> "'),
    ('"detail": "checkpoint needs <DEC|RUN> [T-###] [text]",', '"detail": "checkpoint needs <TAXONOMY> [T-###] [text]",'),
]

GUARD_OLD = '    if _mode == "own_patch" and no_delta_build_events(ticket_id, docs["_history"].events):\n'
GUARD_NEW = (
    "    # T-1781: the LATEST BUILD record decides; a no-delta BUILD that a later\n"
    "    # BUILD with a real patch superseded no longer refuses own_patch.\n"
    '    if _mode == "own_patch" and latest_build_declares_no_delta(\n'
    '        ticket_id, docs["_history"].events\n'
    "    ):\n"
)
HELPER_ANCHOR = "            found.append(event)\n    return found\n"
HELPER_ADD = '''

def latest_build_declares_no_delta(ticket_id: str, events) -> bool:
    """Whether this ticket's most recent BUILD record declared no delta (T-1781).

    A BUILD record is an event of the ticket whose text opens with `build`
    (after an optional `RUN:`). Only the latest one describes the patch the
    closure asserts: an earlier no-delta BUILD superseded by a real one is
    history, not the current claim.
    """
    builds = [
        event
        for event in events
        if event.get("ticket") == ticket_id
        and re.match(r"(?:RUN:\\s*)?build\\b", str(event.get("text") or ""), re.IGNORECASE)
    ]
    return bool(builds) and bool(_NO_DELTA_BUILD_RE.search(str(builds[-1].get("text") or "")))
'''


def read(path: Path) -> tuple[str, bool]:
    raw = path.read_bytes()
    return raw.decode("utf-8").replace("\r\n", "\n"), b"\r\n" in raw


def write(path: Path, text: str, crlf: bool) -> None:
    path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))


def cut(text: str, start: str, end: str, *, keep_end: bool, name: str) -> str:
    if text.count(start) != 1 or text.count(end) != 1:
        raise SystemExit(f"ABORT: {name}: span anchors not unique")
    a = text.index(start)
    b = text.index(end) + (0 if keep_end else len(end))
    if b <= a:
        raise SystemExit(f"ABORT: {name}: span out of order")
    return text[:a] + text[b:]


def before(root: Path, out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    ops, ops_crlf = read(root / OPS)
    ops = cut(ops, T37_HELPER_START, T37_HELPER_END, keep_end=False, name="T-37 helper")
    ops = cut(ops, T37_GUARD_START, "    # T-1162: a short BOARD title", keep_end=True, name="T-37 guard")
    if "no_delta_build_events" in ops or "latest_build_declares_no_delta" in ops:
        raise SystemExit("ABORT: T-37 remains in the reconstructed operations.py")
    write(out / "operations.py", ops, ops_crlf)
    fallback, fb_crlf = read(root / FALLBACK)
    fallback = cut(fallback, T38_FUNCS_START, T38_FUNCS_END, keep_end=True, name="T-38 functions")
    write(out / "continue_fallback.py", fallback, fb_crlf)
    cli, cli_crlf = read(root / CLI)
    if cli.count(T38_WIRING) != 1:
        raise SystemExit("ABORT: T-38 wiring not unique")
    cli = cli.replace(T38_WIRING, "")
    for old, new in T36_PAIRS:
        if cli.count(old) != 1:
            raise SystemExit(f"ABORT: T-36 anchor not unique: {old}")
        cli = cli.replace(old, new)
    write(out / "saipen.py", cli, cli_crlf)
    print(f"before written to {out}")
    return 0


def fix(root: Path, check: bool) -> int:
    path = root / OPS
    text, crlf = read(path)
    if "def latest_build_declares_no_delta(" in text:
        print("ALREADY_APPLIED")
        return 0
    for old in (GUARD_OLD, HELPER_ANCHOR):
        if text.count(old) != 1:
            raise SystemExit(f"ABORT: anchor not unique: {old.strip()[:60]!r}")
    text = text.replace(GUARD_OLD, GUARD_NEW).replace(HELPER_ANCHOR, HELPER_ANCHOR + HELPER_ADD)
    if check:
        print("CHECK OK")
        return 0
    write(path, text, crlf)
    print(f"patched {path}")
    return 0


if __name__ == "__main__":
    mode, root = sys.argv[1], Path(sys.argv[2]).resolve()
    if mode == "before":
        sys.exit(before(root, Path(sys.argv[3]).resolve()))
    sys.exit(fix(root, "--check" in sys.argv))
