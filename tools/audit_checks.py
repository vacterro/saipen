#!/usr/bin/env python3
"""Proves the canonical validator's checks can still go red.

`tools/audit_floor.py` does this for the 20 checks in the frozen portable
floor. Nothing did it for `tools/validate.py`, which now carries around 160
failure paths -- and measuring it is unpleasant reading: the inputs this
repository ships (its own `.saipen/` plus 14 executable fixtures) produce 17
distinct FAIL/WARN lines between them. Every other check rests on a hand test
from the day it was written.

That is not a hypothetical risk here. A check in this file lay dead from
`feae149` to v7.99.0 because its regex never matched a LOG line, and the first
draft of the portable-floor check could not go red at all. The repository's own
rule is that a hand test proves a check worked once and a fixture proves it
still works -- and the sixteen releases before this tool red-tested roughly
twenty-five checks in scratch directories that were deleted immediately after.
This is those tests, kept.

Each case breaks a known-good copy of this repository in exactly one way and
asserts the validator names that specific failure. A case that stops firing is
a check that has gone dead, and it fails here rather than being discovered
years later.

Exit 0 when every case still goes red, 1 otherwise.
"""
from __future__ import annotations

import io
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HOME = Path(__file__).resolve().parent.parent
IGNORE = shutil.ignore_patterns(".git", ".venv", "__pycache__", ".freebuff",
                                "node_modules")

STATE = ".saipen/STATE.md"
BOARD = ".saipen/BOARD.md"
LOG = ".saipen/LOG.md"
DIGEST = ".saipen/kitchen/digest.md"
MANIFEST = ".saipen/kitchen/markhunt_progress.md"
SUB = ".saipen/extensions/subs/saiwiki/STATE.md"


def sub_line(field: str, value: str):
    """Replace a whole frontmatter line."""
    return lambda t: re.sub(rf"^{field}:.*$", f"{field}: {value}", t, flags=re.MULTILINE)


def drop_line(field: str):
    return lambda t: re.sub(rf"^{field}:.*\n", "", t, flags=re.MULTILINE)


def add_after(anchor: str, text: str):
    return lambda t: t.replace(anchor, anchor + text, 1)


def replace(old: str, new: str):
    return lambda t: t.replace(old, new, 1)


UTF16 = "<rewrite as utf-16>"      # sentinel, not a mutation function
DELETE = "<delete the file>"
CREATE = "<create the file>"
SWAP = "<swap the last two log entries>"


def write_new(content: str):
    """A mutation that CREATES the file rather than editing it.

    Three markhunt cases skipped because this repository has no live manifest,
    and a case that skips on the machine where it matters is barely better than
    one that never fires.
    """
    return ("WRITE", content)


# (label, file, mutation, expected substring in the validator's output)
CASES: list[tuple[str, str, object, str]] = [
    # --- STATE shape -----------------------------------------------------
    ("STATE.md deleted", STATE, DELETE, "STATE.md missing"),
    ("STATE.md is UTF-16", STATE,
     UTF16, "not plain UTF-8"),
    ("phase not in the enum", STATE, sub_line("phase", "REFACTOR"),
     "not one of"),
    ("mode not in the enum", STATE, sub_line("mode", "yolo"),
     "field mode"),
    ("transition_from dropped", STATE, drop_line("transition_from"),
     "missing transition_from"),
    ("illegal transition", STATE, sub_line("transition_from", "BUILD"),
     "invalid phase transition"),
    ("updated not UTC", STATE, sub_line("updated", "2026-07-30 10:00"),
     "must be ISO-8601 UTC"),
    ("schema_version from the future", STATE, sub_line("schema_version", "99"),
     "only understands"),
    ("next_action has no prefix", STATE,
     sub_line("next_action", '"finish the thing"'),
     "does not start with"),
    ("WAIT with no category", STATE,
     sub_line("next_action", '"WAIT: need more context"'),
     "WAIT with no category token"),
    ("undefined saipen command", STATE, sub_line("next_action", '"saipen hunt"'),
     "does not define"),
    ("question outside a WAIT", STATE, sub_line("next_action", '"RUN: ship it?"'),
     "asks a question outside"),
    ("read-only in a writing phase", STATE,
     lambda t: sub_line("phase", "BUILD")(sub_line("mode", "read-only")(
         sub_line("transition_from", "SCOUT")(t))),
     "MUST NOT enter"),
    ("goal_mode true, counters absent", STATE,
     lambda s: drop_line("goal_tickets")(drop_line("goal_waves")(s)),
     "counter missing"),
    ("last_event above the log tail", STATE,
     add_after("schema_version: 1\n", "last_event: 999999\n"),
     "higher than the log"),
    ("requires: a capability nobody defines", STATE,
     replace("  - python", "  - pyhton"), "handshake vocabulary"),

    # --- BOARD -----------------------------------------------------------
    ("board heading removed", BOARD, replace("## BLOCKED\n", ""),
     "missing required section heading"),
    ("duplicate board heading", BOARD, lambda t: t + "\n## TODO\n",
     "duplicate section heading"),
    ("two tickets claimed at once", BOARD,
     add_after("## DOING\n", "- [/] T-801 a\n- [/] T-802 b\n"),
     "allows at most one per agent"),
    ("ticket field outside the closed list", BOARD,
     add_after("## TODO\n", "- [ ] T-803 a | assignee: me\n"),
     "unrecognized field"),
    ("needs: a ticket that does not exist", BOARD,
     add_after("## TODO\n", "- [ ] T-804 a | needs: T-9999\n"),
     "dangling needs: reference"),
    ("cyclic needs", BOARD,
     add_after("## TODO\n",
               "- [ ] T-805 a | needs: T-806\n- [ ] T-806 b | needs: T-805\n"),
     "cyclic needs: dependencies"),
    ("claim_time with no zone", BOARD,
     add_after("## DOING\n",
               "- [/] T-807 a | owner: x | claim_time: 2026-07-30T01:00:00\n"),
     "not ISO-8601 UTC"),
    ("review_passes over the cap", BOARD,
     add_after("## TODO\n", "- [ ] T-808 a | review_passes: 4\n"),
     "two passes"),
    ("ticket line that is not a ticket", BOARD,
     add_after("## TODO\n", "- [ ] fix this later\n"),
     "doesn't match RFC"),

    # --- LOG -------------------------------------------------------------
    # Appending a LOWER id cannot test this: E-### is contiguous, so any id
    # below the tail already exists and the duplicate check fires first,
    # `continue`s, and the monotonic branch is never reached. Swap the last two
    # entries instead -- ids go backwards with nothing duplicated.
    ("LOG event ids go backwards", LOG, SWAP, "increase monotonically"),
    ("LOG entry with no date", LOG,
     lambda t: t + "- [E-999999] RUN: undated\n", "has no DATE"),

    # --- kitchen ---------------------------------------------------------
    ("digest is not three lines", DIGEST, lambda t: "done: x\nremaining: y\n",
     "exactly three lines"),
    ("markhunt manifest half-written", MANIFEST,
     write_new("vectors: [1,2,3,4,5]\ncursor: done\n"), "is missing"),
    ("markhunt head pair mixed", MANIFEST,
     write_new("vectors: [1,2,3,4,5]\nsurface: x\nfindings: 0\n"
               "cursor: done\nhead_start: abc1234\nhead_end: no-git\n"),
     "never one"),
    ("markhunt done with a vector missing", MANIFEST,
     write_new("vectors: [1,2,4,5]\nsurface: x\nfindings: 0\n"
               "cursor: done\nhead_start: abc1234\nhead_end: abc1234\n"),
     "NOT exhausted"),

    # --- subSaipen -------------------------------------------------------
    ("sub keeps TEMPLATE's agent placeholder", SUB,
     sub_line("agent", "<name>"), "TEMPLATE's placeholder"),
    ("sub in a phase it cannot reach", SUB, sub_line("phase", "BUILD"),
     "unreachable for a subSaipen"),
    ("sub transition_from dropped", SUB, drop_line("transition_from"),
     "ninth required field"),
    ("sub updated not UTC", SUB, sub_line("updated", "2026-07-30 10:00"),
     "must be ISO-8601 UTC"),

    # --- home-repo drift -------------------------------------------------
    ("README badge behind VERSION", "README.md",
     lambda t: re.sub(r"\*\*v\d+\.\d+\.\d+\*\*", "**v1.0.0**", t, count=1),
     "badge doesn't match VERSION"),
    ("a phase doc disappears", "saipen/phases/hunt.md", DELETE,
     "phase enum"),
    ("shipped doc names the superseded palette", "README.md",
     replace("Vintage Golden", "Dark Golden Win95"), "palette-name"),
    ("BOOT drops the reply-language rule", "saipen/BOOT.md",
     replace("**Reply language, before any output**", "**Chat voice**"),
     "reply-language"),
    ("a locale loses its guide", "guides/GUIDE_UK.md", DELETE,
     "locale coverage"),
    # NOT tested here: the phantom-version check needs the TAG half of the
    # release ledger, and this harness copies the tree without .git on
    # purpose. Without tags the check correctly declines to run, so a case
    # for it could only ever match the WARN saying it was skipped -- which
    # is exactly how it scored as "always present". CI covers it, where the
    # checkout carries tags (fetch-depth: 0).

    (".saipen/ carries a copy of the protocol", ".saipen/RFC.md",
     CREATE, "§ 1.7"),
]


def apply_case(root: Path, rel: str, mutation) -> bool:
    """Returns False when the case cannot be set up (skip it loudly)."""
    p = root / rel
    if mutation == DELETE:
        if not p.exists():
            return False
        p.unlink()
        return True
    if mutation == CREATE:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("copied protocol\n", encoding="utf-8")
        return True
    if isinstance(mutation, tuple) and mutation[0] == "WRITE":
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(mutation[1], encoding="utf-8", newline="\n")
        return True
    if mutation == SWAP:
        lines = p.read_text(encoding="utf-8-sig").splitlines(True)
        idx = [i for i, ln in enumerate(lines) if ln.startswith("- ")]
        if len(idx) < 2:
            return False
        a, b = idx[-2], idx[-1]
        lines[a], lines[b] = lines[b], lines[a]
        p.write_text("".join(lines), encoding="utf-8", newline="\n")
        return True
    if mutation == UTF16:
        if not p.exists():
            return False
        text = p.read_text(encoding="utf-8-sig")
        p.write_bytes(text.encode("utf-16"))
        return True
    if not p.exists():
        return False
    text = p.read_text(encoding="utf-8-sig")
    p.write_text(mutation(text), encoding="utf-8", newline="\n")
    return True


def validator_output(root: Path) -> str:
    """Only the FAIL/WARN lines. Searching the whole output matched PASS text:
    "at most one", "cyclic" and "dangling needs" all appear in the lines that
    say those very checks PASSED, so five cases scored as proving nothing when
    the harness was the thing at fault."""
    r = subprocess.run([sys.executable, str(root / "tools" / "validate.py")],
                       cwd=root, capture_output=True, text=True,
                       errors="replace")
    keep = [ln for ln in (r.stdout + r.stderr).splitlines()
            if ln.startswith(("FAIL", "WARN", "Traceback")) or "Error" in ln]
    return "\n".join(keep)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="audit_checks_"))
    pristine = tmp / "pristine"
    shutil.copytree(HOME, pristine, ignore=IGNORE)

    # The control. Every expectation below must be ABSENT here, or the case
    # proves nothing -- a message that is always present is not evidence.
    control = validator_output(pristine)
    if "Traceback" in control:
        print("FAIL: the validator crashes on an unmodified copy -- fix that "
              "before trusting any case below")
        print(control[-800:])
        shutil.rmtree(tmp, ignore_errors=True)
        return 1

    dead, skipped, always = [], [], []
    for label, rel, mutation, expected in CASES:
        if expected in control:
            always.append((label, expected))
            continue
        work = tmp / "work"
        shutil.rmtree(work, ignore_errors=True)
        shutil.copytree(pristine, work)
        if not apply_case(work, rel, mutation):
            skipped.append(label)
            continue
        if expected not in validator_output(work):
            dead.append((label, expected))
    shutil.rmtree(tmp, ignore_errors=True)

    for label, expected in always:
        print(f"FAIL: {label!r} expects {expected!r}, which the UNMODIFIED "
              f"repository already prints -- the case proves nothing")
    for label in skipped:
        print(f"SKIP: {label} -- the file it mutates is absent here")
    for label, expected in dead:
        print(f"FAIL: {label} -- the validator did not report {expected!r}. "
              f"That check no longer goes red on its own condition")

    live = len(CASES) - len(dead) - len(skipped) - len(always)
    if dead or always:
        print(f"\n{len(dead) + len(always)} of {len(CASES)} case(s) are not "
              f"evidence any more.")
        return 1
    print(f"PASS: {live} of {len(CASES)} validator check(s) still go red on "
          f"their own condition"
          + (f" ({len(skipped)} skipped)" if skipped else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
