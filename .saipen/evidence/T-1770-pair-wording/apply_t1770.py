"""Apply the T-1770 change to tools/saipen_engine/log.py under a given root.

    python -B apply_t1770.py <root> [--check]

Adds a fourth attribution scope to `_claims_failure`, beside T-1444 (foreign),
T-1620 (previous run) and T-1762 (red control): the red half of a measured
pair in the stage words `saipen work regression` records -- `before exit 1`
with its count -- when its green twin `after exit 0` follows. Additive only;
refuses unless every anchor is found exactly once. Keeps the file's line
endings.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
SUBJECT = ROOT / "tools/saipen_engine/log.py"

DEF_ANCHOR = (
    '    + r"(?:\\s*[,;][^()]{0,40})?\\s*\\)|\\b" + _CONTROL_SCOPE + r"\\b)",\n'
    "    re.IGNORECASE,\n"
    ")\n"
)
DEF_ADD = '''
# T-1770 (SRC-248 R005): the red half of a measured pair, in the stage words
# `saipen work regression` records (`stage`, `exit_code`, `ran`, `failed`), is
# evidence data, not this checkpoint's claim. The line the operator's mission
# cites (_sairelay T-8, its E-112) transcribes its receipt as `before exit 1
# (28 ran, 7 failed) / after exit 0 (28 passed)`; T-1762's vocabulary (red
# control, pre-fix) does not cover it, and the count vetoed the green cycle.
# `before` is an ordinary word, so the WORD is not the scope: the scope is the
# whole red half -- `before exit 1` and its count, nothing else -- and only
# when its green twin `after exit 0` follows it. A count outside that half,
# a red half with no green twin, and the twin's own counts are left in place
# and still claim.
_PAIR_OTHER_COUNT = r"\\d+\\s+(?:ran|passed|skipped)"
_PAIR_EXIT = r"\\s*:?\\s*exit\\s*(?:code\\s*)?[:=]?\\s*"
_PAIR_RED_HALF_RE = re.compile(
    r"\\bbefore" + _PAIR_EXIT + r"1\\b\\s*"
    r"(?:\\(\\s*(?:" + _PAIR_OTHER_COUNT + r"\\s*,\\s*)*\\d+\\s+FAIL(?:S|ED|URE|URES)?\\b"
    r"(?:\\s*,\\s*" + _PAIR_OTHER_COUNT + r")*\\s*\\)"
    r"|,\\s*(?:" + _PAIR_OTHER_COUNT + r"\\s*,\\s*)*\\d+\\s+FAIL(?:S|ED|URE|URES)?\\b)"
    r"(?=\\s*[/;,]?\\s*(?:and\\s+|then\\s+)?after" + _PAIR_EXIT + r"0\\b)",
    re.IGNORECASE,
)
'''

DOC_ANCHOR = (
    "    claim. The `verify -> PASS`/`verify -> FAIL` verdict token keeps owning\n"
    "    the current-state claim exactly as before.\n"
)
DOC_ADD = (
    "\n"
    "    T-1770 scopes them a fourth time: the red half of a measured pair in the\n"
    "    stage words of a regression receipt (`before exit 1 (28 ran, 7 failed)`),\n"
    "    when its green twin `after exit 0` follows it. The word `before` alone\n"
    "    attributes nothing.\n"
)

SUB_ANCHOR = "    scoped = _CONTROL_FAIL_RE.sub(\" \", scoped)\n"
SUB_ADD = (
    "    # T-1770: the red half of a measured pair, written in the receipt's own\n"
    "    # stage words and followed by its green twin, is evidence data too.\n"
    "    scoped = _PAIR_RED_HALF_RE.sub(\" \", scoped)\n"
)


def main() -> int:
    raw = SUBJECT.read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8").replace("\r\n", "\n")
    if "_PAIR_RED_HALF_RE" in text:
        print("ALREADY_APPLIED: tools/saipen_engine/log.py carries _PAIR_RED_HALF_RE")
        return 0
    for anchor in (DEF_ANCHOR, DOC_ANCHOR, SUB_ANCHOR):
        if text.count(anchor) != 1:
            print(f"ABORT: anchor not found exactly once: {anchor.strip()[:70]!r}")
            return 1
    text = text.replace(DEF_ANCHOR, DEF_ANCHOR + DEF_ADD)
    text = text.replace(DOC_ANCHOR, DOC_ANCHOR + DOC_ADD)
    text = text.replace(SUB_ANCHOR, SUB_ANCHOR + SUB_ADD)
    if "--check" in sys.argv:
        print("CHECK OK: three anchors match once; nothing written")
        return 0
    SUBJECT.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
    print(f"patched {SUBJECT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
