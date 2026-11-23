"""Apply the reviewed T-1629 candidate only over the exact inherited bytes.

Rollback: copy pre/<path> back for each of the eight paths.
"""

import hashlib
import json
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
root = here.parents[2]
baseline = json.loads((here / "baseline.json").read_text(encoding="utf-8"))
candidate = json.loads((here / "candidate.json").read_text(encoding="utf-8"))


def digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


problems = []
for relative, expected in baseline.items():
    if digest(root / relative) != expected:
        problems.append(f"live {relative} is not the inherited baseline")
    saved = here / "pre" / relative
    if expected is not None and digest(saved) != expected:
        problems.append(f"pre/{relative} does not hold the inherited baseline")
    if digest(here / "candidate" / relative) != candidate[relative]:
        problems.append(f"candidate/{relative} does not match candidate.json")
if problems:
    print("\n".join(problems))
    sys.exit(1)
for relative in candidate:
    (root / relative).write_bytes((here / "candidate" / relative).read_bytes())
applied = {relative: digest(root / relative) for relative in candidate}
assert applied == candidate, applied
print(json.dumps({"applied": sorted(candidate)}, indent=2))
