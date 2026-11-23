"""T-1767 SCOUT: split the usage line into its top-level alternatives.

Usage: python split_usage.py <project-root>
Prints the first word of every alternative the line presents at depth 0
of its outer parenthesis, one per line, with the alternative itself.
"""
import json
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
out = subprocess.run(
    [sys.executable, str(root / "tools" / "saipen.py"), "help", "--json"],
    capture_output=True, text=True, cwd=root,
).stdout
usage = json.loads(out)["usage"]
body = usage[usage.index("(") + 1 :]
depth, cur, alts = 0, "", []
for ch in body:
    if ch in "([{<":
        depth += 1
    elif ch in ")]}>":
        if depth == 0:
            break
        depth -= 1
    if ch == "|" and depth == 0:
        alts.append(cur.strip())
        cur = ""
    else:
        cur += ch
alts.append(cur.strip())
for alt in alts:
    print(f"{alt.split()[0] if alt else '':22} {alt}")
