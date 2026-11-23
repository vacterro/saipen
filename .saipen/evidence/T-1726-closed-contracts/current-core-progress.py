"""Bounded read-only progress for the one owner-stamped active core run."""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import core_unit, inflight

marker = inflight.current(ROOT)
rows = []
if marker:
    for directory in Path(tempfile.gettempdir()).glob(core_unit.SANDBOX_PREFIX + "*"):
        try:
            owner = json.loads((directory / core_unit.SANDBOX_OWNER).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if owner.get("pid") != marker["pid"]:
            continue
        stderr = directory / "spool/stderr"
        tail = ""
        if stderr.is_file():
            with stderr.open("rb") as handle:
                handle.seek(max(0, stderr.stat().st_size - 8192))
                tail = handle.read(8192).decode("utf-8", errors="replace")
        tests = [line for line in tail.splitlines() if line.startswith("test_")]
        rows.append({"sandbox": directory.name, "test_output_present": stderr.exists(),
                     "summary_present": "\nRan " in tail,
                     "last_test": tests[-1][:180] if tests else None})
        if len(rows) >= 6:
            break
print(json.dumps({"running": bool(marker), "pid": marker.get("pid") if marker else None,
                  "shards": rows}, indent=2))
