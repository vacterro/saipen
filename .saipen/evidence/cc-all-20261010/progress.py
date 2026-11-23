"""Inspect this gate's live owner and its actual temporary sandbox root."""

import json
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import inflight
from saipen_engine.core_unit import SANDBOX_OWNER, parse_output

binding = inflight.current(ROOT)
if binding is None:
    print(json.dumps({"live": False, "next": "READ_COMPLETION_RECEIPT"}))
    raise SystemExit(0)

rows = []
temporary_root = Path(tempfile.gettempdir())
for candidate in sorted(temporary_root.glob("saipen-core-unit-*")):
    try:
        owner = json.loads((candidate / SANDBOX_OWNER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        continue
    if owner.get("pid") != binding["pid"]:
        continue
    try:
        manifest = json.loads((candidate / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        manifest = {}
    stream = candidate / "spool/stderr"
    body = stream.read_bytes().decode("utf-8", errors="replace").replace("\r\n", "\n") if stream.exists() else ""
    parsed = parse_output(body)
    rows.append({
        "sandbox": candidate.name,
        "selected": manifest.get("selected"),
        "discovered": manifest.get("discovered"),
        "observed_results": len(re.findall(r"^test_.*\.\.\. (?:ok|FAIL|ERROR|skipped.*)$", body, re.MULTILINE)),
        "completed_tally": parsed["ran"],
        "red_headers": parsed["red"],
        "stream_bytes": len(body.encode("utf-8")),
        "recent_lines": [line[:240] for line in body.splitlines()[-3:]],
    })
print(json.dumps({
    "live": True,
    "pid": binding["pid"],
    "ticket": binding["ticket"],
    "utc": datetime.now(timezone.utc).isoformat(),
    "temporary_root": str(temporary_root),
    "shards": rows,
    "verdict": "PENDING",
}, indent=2))
