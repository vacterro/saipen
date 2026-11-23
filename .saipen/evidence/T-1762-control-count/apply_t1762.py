"""Apply the T-1762 change: the proposing session's own bytes, one token narrowed.

    python -B <this file> [--check]

Run from the repository root. The subject becomes the proposal as its author
wrote it (kept at PROPOSAL below; live file plus additions, no removals), with
two edits made here and stated in the build record:

  * the scope word requires its separator: `pre-fix` or `pre fix`. The
    proposal's `pre[- ]?fix` also spelled the ordinary word `prefix`, and a
    current count beside that word was read as a red control (measured in
    judge-proposal.txt);
  * the comment says so, and names this ticket beside the author's.

Refuses unless the live file is still the bytes the proposal was cut against.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path.cwd()
SUBJECT = ROOT / "tools/saipen_engine/log.py"
BEFORE = ROOT / ".saipen/evidence/T-1762-control-count/before/log.py"
PROPOSAL = ROOT / (
    ".saipen/evidence/foreign-edit-20261014-reconcile/freeze-kept/"
    "20261013T231034Z/tools/saipen_engine/log.py"
)

SCOPE_OLD = '_CONTROL_SCOPE = r"(?:red[- ]?controls?|pre[- ]?fix)"\n'
SCOPE_NEW = '_CONTROL_SCOPE = r"(?:red[- ]?controls?|pre[- ]fix)"\n'

NOTE_OLD = (
    "# current nonzero count beside the control still claim and a real failure\n"
    "# cannot be talked past.\n"
)
NOTE_NEW = (
    "# current nonzero count beside the control still claim and a real failure\n"
    "# cannot be talked past. Landed here as T-1762 (SRC-248) with one narrowing:\n"
    "# the scope word keeps its separator, because `prefix` is an ordinary word\n"
    "# and a current count beside it is nobody's red control.\n"
)


def lf(raw: bytes) -> str:
    return raw.decode("utf-8").replace("\r\n", "\n")


def main() -> int:
    live = SUBJECT.read_bytes()
    if hashlib.sha256(live).hexdigest() != hashlib.sha256(BEFORE.read_bytes()).hexdigest():
        print("ABORT: the live subject moved since the rollback copy was taken; nothing written")
        return 1
    text = lf(PROPOSAL.read_bytes())
    removed = [line for line in lf(live).split("\n") if line and line not in text.split("\n")]
    if removed:
        print(f"ABORT: the proposal removes {len(removed)} line(s) of the live subject")
        return 1
    for old in (SCOPE_OLD, NOTE_OLD):
        if text.count(old) != 1:
            print(f"ABORT: anchor not found exactly once: {old.strip()[:70]!r}")
            return 1
    text = text.replace(SCOPE_OLD, SCOPE_NEW).replace(NOTE_OLD, NOTE_NEW)
    if "--check" in sys.argv:
        print("CHECK OK: proposal is additive, both anchors match once, live subject unmoved")
        return 0
    crlf = b"\r\n" in live
    SUBJECT.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
    print("patched tools/saipen_engine/log.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
