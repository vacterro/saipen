"""T-1577 SCOUT: every NON-canonical op id in the active log, with its E-id.

Read-only. Decides whether a validator FAIL on a malformed id is a live
finding or would red this repository's own history.
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path("tools").resolve()))
from saipen_engine.journal import resolvable_op_ids  # noqa: E402

PAT = re.compile(r"\[op: ([^\]]+)\]")
EID = re.compile(r"\[E-(\d+)\]")
GOOD = re.compile(r"^(checkpoint|transition|ticket|claim|finish|userreq|scope|"
                  r"stop|goal|retire|valve|supersede|convergence|converge_intent|"
                  r"reconcile|undo|refine|reload|receipt|pass)-[0-9a-f]{32}$")

root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
ledger = resolvable_op_ids(root)
events = []
for line in (root / ".saipen" / "LOG.md").read_text(
        encoding="utf-8", errors="replace").splitlines():
    op = PAT.search(line)
    if not op:
        continue
    eid = EID.search(line)
    events.append((int(eid.group(1)) if eid else 0, op.group(1),
                   op.group(1) in ledger, GOOD.match(op.group(1)) is not None, line))

floor = max((eid for eid, oid, res, _g, _l in events if res), default=None)
print("ledger size", len(ledger), "resolved_floor", floor, "events", len(events))
print("--- non-canonical op ids in the ACTIVE log ---")
for eid, oid, resolved, good, line in events:
    if not good:
        flag = "RESOLVES" if resolved else "no-record"
        print(f"E-{eid:<6} {flag:9} {oid[:70]}")
        print(f"        {line[:150]}")
