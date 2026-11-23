"""Read only the current gate's owned spools; no aggregate verdict yet."""
import json
from pathlib import Path
import re
import tempfile
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
marker_path = ROOT / ".saipen/cache/inflight/core-unit.json"
if not marker_path.exists():
    print(json.dumps({"state": "not_running", "verdict": "read native completion"}))
    raise SystemExit(0)
marker = json.loads(marker_path.read_bytes())
workers = []
for path in sorted(Path(tempfile.gettempdir()).glob("saipen-core-unit-*")):
    try:
        owner = json.loads((path / "owner.json").read_bytes())
        if owner.get("pid") != marker["pid"]:
            continue
        stderr = (path / "spool/stderr").read_text(encoding="utf-8", errors="replace")
        workers.append({"worker": path.name, "spool_bytes": len(stderr.encode("utf-8")),
                        "observed_bad_lines": len(re.findall(r"(?m)^test_.* \.\.\. (?:FAIL|ERROR)$", stderr)),
                        "summary": re.findall(r"Ran (\d+) tests in ([\d.]+)s", stderr)})
    except (OSError, ValueError):
        continue
record = {"ticket": marker["ticket"], "elapsed_seconds": round(time.time() - marker["started"]),
          "workers": workers, "scope": "telemetry only, aggregate pending"}
with (OUT / "family-progress.jsonl").open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(record) + "\n")
print(json.dumps(record))
