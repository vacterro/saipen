"""Read progress from this run's owner-stamped sandboxes; never infer PASS."""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.core_unit import SANDBOX_OWNER, parse_output  # noqa: E402

marker = ROOT / ".saipen/cache/inflight/core-unit.json"
if not marker.exists():
    print(json.dumps({"inflight": False, "verdict": "READ_COMPLETION_RECEIPT"}))
    sys.exit(0)
binding = json.loads(marker.read_text(encoding="utf-8"))
rows = []
for candidate in sorted(Path(os.environ["TEMP"]).glob("saipen-core-unit-*")):
    try:
        owner = json.loads((candidate / SANDBOX_OWNER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        continue
    if owner.get("pid") != binding.get("pid"):
        continue
    try:
        manifest = json.loads((candidate / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        manifest = {}
    stream = candidate / "spool/stderr"
    body = stream.read_bytes().decode("utf-8", errors="replace").replace("\r\n", "\n") if stream.exists() else ""
    parsed = parse_output(body)
    rows.append({"sandbox": candidate.name, "discovered": manifest.get("discovered"),
                 "selected": manifest.get("selected"), "stream_bytes": stream.stat().st_size
                 if stream.exists() else 0,
                 "observed_result_lines": len(re.findall(
                     r"^test_.*\.\.\. (?:ok|FAIL|ERROR|skipped.*)$", body, re.MULTILINE)),
                 "complete_tally": parsed["ran"], "red_headers": parsed["red"]})
print(json.dumps({"inflight": True, "ticket": binding["ticket"], "pid": binding["pid"],
                  "utc": datetime.now(timezone.utc).isoformat(), "shards": rows,
                  "observed_result_lines": sum(row["observed_result_lines"] for row in rows),
                  "selected": sum(row["selected"] or 0 for row in rows),
                  "verdict": "PENDING"}, indent=2))
