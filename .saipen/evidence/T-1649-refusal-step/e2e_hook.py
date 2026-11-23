"""T-1649 end to end through the REAL hook artifact.

Usage: python e2e_hook.py <saipen home holding tools/ and extensions/>

A real authority service runs on a runtime root under a throwaway profile. The
home's own Claude hook artifact is then given one UserPromptSubmit event for a
bound fixture project, with that profile as its home. The hook starts the
home's engine, the engine asks the service, the service refuses this process
(it is not a host application's hook invocation) and the answer travels back.
Printed: what the hook answered and what it left in the health record.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

home_root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(home_root / "tools"))
tmp = Path(tempfile.mkdtemp(prefix="saipen-t1649-hook-"))
profile = tmp / "userprofile"
profile.mkdir()
os.environ.update(USERPROFILE=str(profile), HOME=str(profile), HOMEDRIVE="", HOMEPATH="")

from saipen_engine import host_authority_broker as broker  # noqa: E402

import test_t1614_future_gate as H  # noqa: E402

runtime = profile / ".saipen" / "authority"
hook = home_root / "extensions" / "adapters" / "claude" / "saipen-guard.py"
base, project = H._project()
out: dict = {"home": home_root.name}
started = broker.spawn(home_root, runtime=runtime, wait=20.0)
out["service_started"] = bool(started.get("ok"))
try:
    event = {
        "hook_event_name": "UserPromptSubmit",
        "session_id": "t1649-e2e",
        "cwd": str(project),
        "prompt": "hello",
    }
    proc = subprocess.run(
        [
            sys.executable, str(hook), "--host", "claude", "--saipen-root", str(home_root),
            "--home", str(profile), "--runtime", str(runtime),
        ],
        input=json.dumps(event).encode("utf-8"),
        capture_output=True,
        cwd=str(project),
        check=False,
        timeout=180,
        env={key: value for key, value in os.environ.items() if not key.startswith("SAIPEN_")},
    )
    text = proc.stdout.decode("utf-8", errors="replace")
    out["hook_rc"] = proc.returncode
    out["notice_names_step"] = "AUTHORITY_CLIENT_UNPROVEN/NOT_HOST_DESCENDANT" in text
    out["notice_has_code"] = "AUTHORITY_CLIENT_UNPROVEN" in text
    health = profile / ".saipen" / "health" / "claude.json"
    record = json.loads(health.read_text(encoding="utf-8")) if health.is_file() else {}
    out["health"] = {key: record.get(key) for key in ("event", "state", "code", "step")}
finally:
    try:
        broker.request({"op": "shutdown"}, runtime=runtime, timeout=10)
    except Exception as exc:
        out["shutdown"] = type(exc).__name__
    time.sleep(1.5)
log = broker.log_path(runtime)
lines = [line for line in log.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()] if log.is_file() else []
out["service_log_lines"] = len(lines)
out["service_log_steps"] = sorted({json.loads(line).get("step") for line in lines if line.startswith("{")})
print(json.dumps(out))
shutil.rmtree(tmp, True)
shutil.rmtree(base, True)
