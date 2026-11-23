"""Durably supervise the canonical family across host observation loss."""
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.inflight import current, _process_created  # noqa: E402


def write(name, data):
    path = HERE / name
    staging = path.with_suffix(".tmp")
    staging.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(staging, path)


live = current(ROOT)
if live:
    print(json.dumps({"action": "ADOPT_EXISTING", "inflight": live}))
    raise SystemExit(1)
marker = ROOT / ".saipen/cache/inflight/core-unit.json"
if marker.exists():
    previous = json.loads(marker.read_text(encoding="utf-8"))
    write("interrupted-first-run.json", {
        "observed_utc": datetime.now(timezone.utc).isoformat(),
        "host_handle": 72323,
        "host_observation": "Unknown process id 72323",
        "previous_marker": previous,
        "observed_process_creation": _process_created(previous["pid"]),
        "live_inflight": None,
        "result": "STOPPED_UNMEASURED",
        "limit": "No new full-family receipt exists; no test verdict is inferred.",
    })
command = [sys.executable, "-B", "tools/core_unit.py", "evidence", "T-1750",
           "--jobs", "6", "--timeout", "5400"]
with (HERE / "family.stdout.txt").open("wb") as out:
    with (HERE / "family.stderr.txt").open("wb") as err:
        child = subprocess.Popen(command, cwd=ROOT, stdout=out, stderr=err)
        state = {
            "ticket": "T-1750", "status": "RUNNING", "command": command,
            "supervisor_pid": os.getpid(), "supervisor_created": _process_created(os.getpid()),
            "child_pid": child.pid, "child_created": _process_created(child.pid),
            "started_utc": datetime.now(timezone.utc).isoformat(),
        }
        write("family-process.json", state)
        result = child.wait()
state.update(status="FINISHED", exit_code=result,
             finished_utc=datetime.now(timezone.utc).isoformat())
write("family-process.json", state)
raise SystemExit(result)
