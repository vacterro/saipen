"""Read-only census: which LOG events stand behind each ## DONE ticket?"""
import re, sys, collections
from pathlib import Path

EV = re.compile(r"^- \S+ \S+ \[E-(\d+)\](.*)$")
OP = re.compile(r"\[op: ([^\]]+)\]")
TK = re.compile(r"\[(T-\d+)\]")
CLOSE = re.compile(r"ticket (finished|done|deferred|superseded|retired|resolved|closed)|supersed|retire|resolve-external|external implementation|closure", re.I)

for proj in sys.argv[1:]:
    root = Path(proj) / ".saipen"
    board = (root / "BOARD.md").read_text(encoding="utf-8", errors="replace")
    section = None; done = []
    for line in board.splitlines():
        if line.startswith("## "): section = line.strip()
        m = re.match(r"^- \[(.)\] (T-\d+)", line)
        if m and section == "## DONE": done.append(m.group(2))
    files = sorted((root / "logs").glob("LOG-*.md")) if (root / "logs").is_dir() else []
    files.append(root / "LOG.md")
    events = []
    for f in files:
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            m = EV.match(line)
            if not m: continue
            op = OP.search(line); tk = TK.search(line)
            events.append((int(m.group(1)), op.group(1) if op else None, tk.group(1) if tk else None, line, f.name))
    events.sort(key=lambda e: e[0])
    first_op = next((e[0] for e in events if e[1]), None)
    by_ticket = collections.defaultdict(list)
    for e in events:
        if e[2]: by_ticket[e[2]].append(e)
    stats = collections.Counter(); closing_classes = collections.Counter(); bad = []
    for t in done:
        evs = by_ticket.get(t, [])
        if not evs: stats["no_events"] += 1; continue
        last = evs[-1][0]
        if first_op is None or last < first_op: stats["pre_boundary"] += 1; continue
        closers = [e for e in evs if e[1] and CLOSE.search(e[3])]
        if closers:
            stats["closure_op_event"] += 1
            closing_classes[closers[-1][1].split("-")[0]] += 1
        else:
            stats["NO_closure_op_event"] += 1
            bad.append((t, last, evs[-1][4], evs[-1][3][:150]))
    print(f"=== {proj}\n  DONE {len(done)}  first_op E-{first_op}  {dict(stats)}\n  closing op classes {dict(closing_classes)}")
    for b in bad[:12]: print("   BAD", b)
    if len(bad) > 12: print(f"   ... +{len(bad)-12} more")
