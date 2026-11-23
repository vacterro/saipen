"""Bounded telemetry for the gate's own temporary spools; never a verdict."""
import json
from pathlib import Path
import re
import tempfile
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
marker_path = ROOT / ".saipen/cache/inflight/core-unit.json"
if not marker_path.exists():
    print(json.dumps({"state": "not_running", "scope": "read the host completion result for the verdict"}))
    raise SystemExit(0)
marker = json.loads(marker_path.read_text(encoding="utf-8"))
workers = []
for path in sorted(Path(tempfile.gettempdir()).glob("saipen-core-unit-*")):
    try:
        owner = json.loads((path / "owner.json").read_text(encoding="utf-8"))
        if owner.get("pid") != marker["pid"]:
            continue
        stderr = (path / "spool/stderr").read_text(encoding="utf-8", errors="replace")
        workers.append({"worker": path.name,
                        "completed_summary": re.findall(r"Ran (\d+) tests in ([\d.]+)s", stderr),
                        "observed_fail_or_error_lines": len(re.findall(r"(?m)^test_.* \.\.\. (?:FAIL|ERROR)$", stderr)),
                        "spool_bytes": len(stderr.encode("utf-8")),
                        "has_summary": "\nRan " in stderr})
    except (OSError, ValueError):
        continue
record = {"ticket": marker["ticket"], "elapsed_seconds": round(time.time() - marker["started"]),
          "workers": workers, "scope": "progress only; aggregate verdict remains pending"}
with (OUT / "family-progress.jsonl").open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(record) + "\n")
print(json.dumps(record))
