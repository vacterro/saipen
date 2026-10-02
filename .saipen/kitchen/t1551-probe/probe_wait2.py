"""Which fixture field breaks `status`?"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from test_hermetic_env import isolate_host_session  # noqa: E402

isolate_host_session()
from test_guard_hostile_matrix import fresh_project  # noqa: E402

cases = {
    "plain": {},
    "wait-only": {"next_action": "WAIT: manual verify"},
    "blocker-only": {"blocker": "HUMAN_DECISION -- choose disposition"},
    "both": {"next_action": "WAIT: manual verify", "blocker": "HUMAN_DECISION -- choose disposition"},
}
for tag, over in cases.items():
    project = fresh_project(**over)
    st = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "saipen.py"), "status", "--json", "--project-root", str(project)],
        capture_output=True, text=True, cwd=str(ROOT), check=False,
    )
    try:
        payload = json.loads(st.stdout or "{}")
    except json.JSONDecodeError:
        payload = {"raw": st.stdout[:200]}
    print(f"== {tag} rc={st.returncode} err={st.stderr.strip()[:200]!r}")
    print("   code=", payload.get("code"), "detail=", str(payload.get("detail"))[:200])
    print("   conformance=", (payload.get("conformance_status") or {}).get("status"),
          "automation=", (payload.get("automation") or {}).get("disposition"))
