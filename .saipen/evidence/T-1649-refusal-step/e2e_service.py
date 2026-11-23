"""T-1649 end to end: a REAL authority service refuses a REAL client; what is left?

Usage: python e2e_service.py <saipen home holding tools/>

Starts the home's own `authority_service.py serve` as the detached process the
hook would start, on a runtime root under a throwaway profile (never the
operator's), asks it twice for an admission from this script -- which is not a
host hook, so the operating-system proof refuses it -- stops the service and
prints what its log file holds. Nothing is mocked.
"""
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

home = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(home / "tools"))
tmp = Path(tempfile.mkdtemp(prefix="saipen-t1649-e2e-"))
profile = tmp / "userprofile"
profile.mkdir()
os.environ.update(USERPROFILE=str(profile), HOME=str(profile), HOMEDRIVE="", HOMEPATH="")

from saipen_engine import host_authority_broker as broker  # noqa: E402

runtime = profile / ".saipen" / "authority"
out: dict = {"home": home.name}
started = broker.spawn(home, runtime=runtime, wait=20.0)
out["spawned"] = bool(started.get("ok"))
try:
    replies = []
    for _ in range(2):
        reply = broker.request(
            {"op": "admission", "host": "claude", "session": "e2e", "project": str(home)},
            runtime=runtime,
            timeout=15,
        )
        replies.append((reply.get("ok"), reply.get("code"), (reply.get("identity") or {}).get("reason")))
    out["replies"] = replies
    status = broker.request({"op": "status"}, runtime=runtime, timeout=10)
    out["refused_requests"] = status.get("refused_requests")
finally:
    try:
        broker.request({"op": "shutdown"}, runtime=runtime, timeout=10)
    except Exception as exc:  # the answer below is the log either way
        out["shutdown"] = type(exc).__name__
    time.sleep(1.5)
log = broker.log_path(runtime)
text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
lines = [line for line in text.splitlines() if line.strip()]
out["log_bytes"] = len(text.encode("utf-8"))
out["log_lines"] = len(lines)
records = []
for line in lines:
    try:
        records.append(json.loads(line))
    except ValueError:
        records.append({"unparsed": line[:120]})
out["log_records"] = [
    {key: record.get(key) for key in ("event", "op", "code", "step", "host", "chain") if key in record}
    for record in records
]
print(json.dumps(out))
shutil.rmtree(tmp, True)
