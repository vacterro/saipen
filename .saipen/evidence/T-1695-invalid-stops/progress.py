"""Partial spool observations, never a completed family verdict."""
import collections
import datetime
import json
from pathlib import Path
import re
import tempfile

OUT = Path(__file__).resolve().parent
workers = []
for path in Path(tempfile.gettempdir()).glob("saipen-core-unit-*"):
    try:
        owner = json.loads((path / "owner.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        continue
    if owner.get("pid") != 14868:
        continue
    try:
        raw = (path / "spool/stderr").read_bytes()
    except OSError:
        continue
    text = raw.decode("utf-8", errors="replace")
    statuses = collections.Counter(re.findall(
        r"\.\.\. (ok|FAIL|ERROR|skipped|expected failure|unexpected success)", text))
    workers.append({"sandbox": path.name, "output_bytes": len(raw),
                    "reported_result_lines": dict(statuses),
                    "summary_present": bool(re.search(r"^Ran \d+ tests? in ", text, re.M))})
record = {"observed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "partial_only": True, "workers": workers,
          "finished_result_lines": sum(sum(v["reported_result_lines"].values()) for v in workers)}
with (OUT / "family-progress.jsonl").open("a", encoding="utf-8") as target:
    target.write(json.dumps(record) + "\n")
print(json.dumps(record))
