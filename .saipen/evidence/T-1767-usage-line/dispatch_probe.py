"""Read-only: verbs the dispatcher in tools/saipen.py compares `command` with."""

import re
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
source = (root / "tools" / "saipen.py").read_text(encoding="utf-8")
verbs = set(re.findall(r'\bcommand == "([a-z][a-z0-9-]*)"', source))
for group in re.findall(r"\bcommand in \(([^)]*)\)", source):
    verbs.update(re.findall(r'"([a-z][a-z0-9-]*)"', group))
verbs.update(re.findall(r'\bargs\[0\] == "([a-z][a-z0-9-]*)"', source))
print(len(verbs))
print(sorted(verbs))
