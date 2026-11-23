"""T-1648 end to end: canonical checkpoints under a reader that holds LOG/STATE.

Usage: python e2e_journal.py <saipen home holding tools/> [checkpoints] [hold_s] [idle_s]

Builds a fixture project, keeps LOG.md and STATE.md open in a second thread
the way a hook or a status poll does (CPython open: no delete-sharing), and
runs real `saipen checkpoint` commands through the home's engine. Counts the
result codes; after a refused operation runs `saipen recover` so the next
checkpoint starts clean. Prints one JSON line.
"""
import json
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

home = Path(sys.argv[1]).resolve()
count = int(sys.argv[2]) if len(sys.argv) > 2 else 20
hold = float(sys.argv[3]) if len(sys.argv) > 3 else 0.03
idle = float(sys.argv[4]) if len(sys.argv) > 4 else 0.03
sys.path.insert(0, str(home / "tools"))

import test_t1614_future_gate as H  # noqa: E402
from test_hermetic_env import hermetic_env  # noqa: E402

base, project = H._project(intent="goal")
engine = str(home / "tools" / "saipen.py")
env = hermetic_env()
stop = threading.Event()
held = [0]


def holder() -> None:
    targets = [project / ".saipen" / "LOG.md", project / ".saipen" / "STATE.md"]
    while not stop.is_set():
        handles = []
        for target in targets:
            try:
                handles.append(open(target, "rb"))
            except OSError:
                pass
        held[0] += 1
        time.sleep(hold)
        for handle in handles:
            handle.close()
        time.sleep(idle)


def saipen(*args: str) -> dict:
    proc = subprocess.run(
        [sys.executable, "-B", engine, *args, "--project-root", str(project), "--json"],
        capture_output=True,
        env=env,
        timeout=120,
    )
    try:
        return json.loads(proc.stdout.decode("utf-8", "replace"))
    except ValueError:
        return {"code": f"UNPARSED rc={proc.returncode}", "detail": proc.stderr.decode("utf-8", "replace")[-300:]}


thread = threading.Thread(target=holder, daemon=True)
thread.start()
codes: dict = {}
details: list = []
recoveries = 0
for index in range(count):
    result = saipen("checkpoint", "DEC", f"note {index}")
    code = str(result.get("code"))
    codes[code] = codes.get(code, 0) + 1
    if not result.get("ok"):
        if len(details) < 2:
            details.append(str(result.get("detail"))[:160])
        recoveries += 1
        saipen("recover")
stop.set()
thread.join(5)
log_lines = (project / ".saipen" / "LOG.md").read_text(encoding="utf-8").count("\n")
shutil.rmtree(base, True)
print(
    json.dumps(
        {
            "home": home.name,
            "checkpoints": count,
            "codes": codes,
            "recoveries_needed": recoveries,
            "first_refusals": details,
            "holder_cycles": held[0],
            "hold_s": hold,
            "idle_s": idle,
            "log_lines": log_lines,
        }
    )
)
