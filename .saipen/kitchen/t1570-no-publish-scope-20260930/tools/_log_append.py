"""Retired: the raw LOG line appender. It writes nothing, ever.

Usage: python tools/_log_append.py [anything]   -> refusal, exit 2
       python tools/_log_append.py --help       -> this notice, exit 0

This was the one writer that took a caller-formed line: the caller typed the
stamp, the event id, the parent edge and the op id, and the tool appended the
bytes to whatever `.saipen/LOG.md` sat under the current directory -- no
writer lock, no STATE binding, no project identity, and only the stamp was
checked. Two classes came through it:

* hand-typed stamps in ISO order (E-2068 `26.08.05`, E-5171 `26.09.01`), which
  is why a stamp guard was bolted on (T-1261);
* on 29.09.26, an agent working in ANOTHER project ran it from this project's
  root. `--help` was appended as a LOG line, then three of that agent's own
  events -- E-2602..E-2604, ids this ledger had spent months earlier, with a
  parent edge into its old history. The stamps were fine, so the guard passed
  them, and every verb in this project refused HISTORY_LEDGER_CORRUPT until
  `saipen recover quarantine-log-tail` cut them off.

A stamp guard cannot fix that, and neither can an id guard: the defect is that
the caller forms ledger identity at all. `saipen checkpoint <TAXONOMY> [T-###]
<text>` forms the stamp, id, parent and op under the writer lock, binds the
project by its identity, and records STATE in the same transaction. Use it.
"""
from __future__ import annotations

import sys

NOTICE = (
    "tools/_log_append.py is retired and writes nothing. A LOG line is formed "
    "by the engine, never by the caller: run\n"
    "    saipen checkpoint <RUN|DEC|...> [T-###] <text>\n"
    "which allocates the stamp, event id, parent and op under the writer lock "
    "and binds the project by its identity."
)


def main(argv: list[str]) -> int:
    if argv[1:] in (["--help"], ["-h"]):
        print(NOTICE)
        return 0
    print("REFUSED -- nothing appended. " + NOTICE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
