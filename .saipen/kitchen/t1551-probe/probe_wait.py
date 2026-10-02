"""Repro: wait fixture + classify / hook."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from test_hermetic_env import isolate_host_session  # noqa: E402

isolate_host_session()

from test_guard_hostile_matrix import fresh_project  # noqa: E402

project = fresh_project(
    next_action="WAIT: manual verify",
    blocker="HUMAN_DECISION -- choose disposition",
)
print("project:", project)

for tag, cwd in (("cwd=ROOT", ROOT), ("cwd=project", project)):
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "saipen.py"), "response", "check", "--stdin",
         "--json", "--classify", "--auto-eligibility", "--project-root", str(project)],
        input="Everything is fine.", capture_output=True, text=True, cwd=str(cwd), check=False,
    )
    print(tag, "rc=", proc.returncode, "out=", proc.stdout.strip()[:300], "err=", proc.stderr.strip()[:300])

st = subprocess.run(
    [sys.executable, str(ROOT / "tools" / "saipen.py"), "status", "--json", "--project-root", str(project)],
    capture_output=True, text=True, cwd=str(ROOT), check=False,
)
print("status rc=", st.returncode, "err=", st.stderr.strip()[:300])
payload = json.loads(st.stdout or "{}")
print("status keys ok, conformance:", (payload.get("conformance_status") or {}).get("status"),
      "automation:", (payload.get("automation") or {}).get("disposition"))

hook = ROOT / "extensions" / "adapters" / "codex" / "saipen-guard.py"
event = {"hook_event_name": "Stop", "cwd": str(project), "session_id": "s", "turn_id": "t",
         "stop_hook_active": False, "last_assistant_message": "Everything is fine."}
proc = subprocess.run(
    [sys.executable, str(hook), "--host", "codex", "--saipen-root", str(ROOT)],
    input=json.dumps(event), capture_output=True, text=True, cwd=str(ROOT), check=False,
)
print("hook rc=", proc.returncode, "out=", proc.stdout.strip()[:400], "err=", proc.stderr.strip()[:200])
