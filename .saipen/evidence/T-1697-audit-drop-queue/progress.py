"""Partial spool observations; never completion evidence."""
import collections
import datetime
import json
from pathlib import Path
import re
import tempfile

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
owner_path = ROOT / ".saipen/cache/inflight/core-unit.json"
if not owner_path.is_file():
    print("Runner owner settled; inspect its actual completion result.")
    raise SystemExit(0)
owner = json.loads(owner_path.read_text())
assert owner["ticket"] == "T-1697"
counts = collections.Counter()
completed = 0
for path in Path(tempfile.gettempdir()).glob("saipen-core-unit-*"):
    try:
        if json.loads((path / "owner.json").read_text()).get("pid") != owner["pid"]:
            continue
        data = (path / "spool/stderr").read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        continue
    counts.update(re.findall(
        r"\.\.\. (ok|FAIL|ERROR|skipped|expected failure|unexpected success)", data
    ))
    completed += bool(re.search(r"^Ran \d+ tests? in ", data, re.M))
record = {
    "observed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "partial_only": True,
    "result_lines": dict(counts),
    "completed_workers": completed,
}
with (OUT / "final-family-progress.jsonl").open("a", encoding="utf-8") as target:
    target.write(json.dumps(record) + "\n")
print(json.dumps(record))
