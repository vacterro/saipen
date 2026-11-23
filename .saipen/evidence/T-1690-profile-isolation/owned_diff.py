"""Review this ticket's delta against its preserved preimages."""
from __future__ import annotations

import difflib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
evidence = Path(__file__).resolve().parent
diff = []
summary = []
for old in sorted((evidence / "pre" / "tools").rglob("*.py")):
    relative = old.relative_to(evidence / "pre")
    before = old.read_text(encoding="utf-8").splitlines(keepends=True)
    after = (root / relative).read_text(encoding="utf-8").splitlines(keepends=True)
    delta = list(difflib.unified_diff(before, after, fromfile="pre/" + relative.as_posix(),
                                    tofile=relative.as_posix()))
    diff.extend(delta)
    summary.append({"path": relative.as_posix(),
                    "added": sum(line.startswith("+") and not line.startswith("+++")
                                 for line in delta),
                    "removed": sum(line.startswith("-") and not line.startswith("---")
                                   for line in delta)})
(evidence / "owned.diff").write_text("".join(diff), encoding="utf-8")
print(json.dumps(summary, indent=2))
print("".join(diff))
