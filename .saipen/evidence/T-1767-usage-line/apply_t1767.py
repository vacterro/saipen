"""Apply the T-1767 change to tools/saipen.py under a given root.

    python -B apply_t1767.py <root> [--check]

The usage line separates top-level commands with `|` and used the same `|`
between the subcommands of one family, so `test suite [status]|declare --
<command>|run [T-###]|withdraw` presented declare, run and withdraw as
commands of their own. Each family's subcommands are grouped in braces (or in
the existing optional bracket for `test suite`), so every top-level
alternative is a command the dispatcher answers. `fleet prepare` and the
top-level `prepare [<producer>]` were one ambiguous `prepare`; both are
spelled. Replacements only inside the usage literal; every anchor must match
exactly once. Keeps line endings.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
SUBJECT = ROOT / "tools/saipen.py"

PAIRS = [
    (
        '            "continue|status|storage status|classify|durable|ephemeral|scratch|"\n'
        '            "store|verify|promote|migrate|"\n'
        '            "response render|check --stdin|next|runtime "\n',
        '            "continue|status|storage {status|classify|durable|ephemeral|scratch|"\n'
        '            "store|verify|promote|migrate}|"\n'
        '            "response {render|check} --stdin|next|runtime "\n',
    ),
    (
        '            "validate|recover|fleet preflight|scan|prepare|collect <producer>|"\n',
        '            "validate|recover|fleet {preflight|scan|prepare}|prepare [<producer>]|"\n'
        '            "collect <producer>|"\n',
    ),
    (
        '            "[--project|--global|--effective]|userperson add|remove <text> "\n',
        '            "[--project|--global|--effective]|userperson {add|remove} <text> "\n',
    ),
    (
        '            "<candidate-home>|context cold|hot|audit|orient [--handoff JSON]|"\n'
        '            "acceptance <T-###>|test suite [status]|declare -- <command>|run [T-###]|withdraw|"\n',
        '            "<candidate-home>|context {cold|hot|audit|orient [--handoff JSON]}|"\n'
        '            "acceptance <T-###>|test suite [status|declare -- <command>|run [T-###]|"\n'
        '            "withdraw]|"\n',
    ),
    (
        '            "<STOP>|brief|focus [text]|build <directive>|knowledge "\n'
        '            "status|index|retrieve <objective>|future "\n'
        '            "status|list|refresh|next|refine <FG-####>|promote <FG-####>|add <title>|"\n'
        '            "launch <host> [-- HOST-ARGS]|host doctor|repair|mode [strict|degraded|default]|"\n',
        '            "<STOP>|brief|focus [text]|build <directive>|knowledge {"\n'
        '            "status|index|retrieve <objective>}|future {"\n'
        '            "status|list|refresh|next|refine <FG-####>|promote <FG-####>|add <title>}|"\n'
        '            "launch <host> [-- HOST-ARGS]|host {doctor|repair|mode [strict|degraded|default]}|"\n',
    ),
]

COMMENT_ANCHOR = '        usage_msg = (\n            "usage: saipen (init|"\n'
COMMENT_NEW = (
    "        # T-1767: `|` separates TOP-LEVEL commands here; a family's subcommands\n"
    "        # are grouped in braces (or its optional bracket) so no subcommand reads\n"
    "        # as a command of its own (`saipen run` was advertised and unknown).\n"
    '        usage_msg = (\n            "usage: saipen (init|"\n'
)


def main() -> int:
    raw = SUBJECT.read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8").replace("\r\n", "\n")
    if "# T-1767: `|` separates TOP-LEVEL" in text:
        print("ALREADY_APPLIED")
        return 0
    for old, _new in [*PAIRS, (COMMENT_ANCHOR, COMMENT_NEW)]:
        if text.count(old) != 1:
            print(f"ABORT: anchor found {text.count(old)} times: {old.strip()[:70]!r}")
            return 1
    for old, new in [*PAIRS, (COMMENT_ANCHOR, COMMENT_NEW)]:
        text = text.replace(old, new)
    if "--check" in sys.argv:
        print("CHECK OK: anchors match once; nothing written")
        return 0
    SUBJECT.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
    print(f"patched {SUBJECT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
