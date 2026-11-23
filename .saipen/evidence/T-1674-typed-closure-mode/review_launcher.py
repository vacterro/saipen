"""REVIEW evidence for T-1674: the typed closure_mode through the launcher.

Usage: review_launcher.py <repo>

VERIFY drove `python tools/saipen.py`. Here the same fixture goes through
`bin\\saipen.cmd` in fresh cmd.exe processes: status, bare recover, the approved
command, status again.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(repo / "tools"))
import test_t1674_typed_closure_mode as T  # noqa: E402

T.setUpModule()
CMD = repo / "bin" / "saipen.cmd"


def launcher(root: Path, *args: str) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
    env.update(PYTHONUTF8="1", PWD=str(root), FORBID_SAIPEN_PROJECT_WRITE=str(repo))
    proc = subprocess.run(
        ["cmd.exe", "/d", "/c", str(CMD), "--project-root", str(root), "--agent", T.AGENT,
         "--json", *args],
        cwd=str(root), env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=600,
    )
    blob = (proc.stdout or "") + (proc.stderr or "")
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        return {"ok": False, "code": "LAUNCHER_OUTPUT_NOT_JSON", "detail": blob[-400:]}


root, ticket = T._project()
T._type_the_closure(root, ticket)
before = T._bytes(root)
status = launcher(root, "status")
plan = launcher(root, "recover")
untouched = T._bytes(root) == before
route = str(plan.get("canonical_next_command") or "").split()[1:]
applied = launcher(root, *route) if route else {}
after = launcher(root, "status")
row = T.parse_board(T._bytes(root)["BOARD.md"].decode())["tickets"][ticket]
print("status      :", json.dumps({k: status.get(k) for k in ("ok", "code", "action")}),
      str(status.get("detail"))[:110])
print("recover     :", json.dumps({k: plan.get(k) for k in ("ok", "code")}),
      "| bytes untouched:", untouched)
print("approved    :", json.dumps({k: applied.get(k) for k in ("ok", "code", "event")}))
print("status after:", json.dumps({k: after.get(k) for k in ("ok", "top_workable_ticket")}))
print("row         :", row["section"], sorted(row["fields"]))
ok = (
    status.get("ok") is False
    and status.get("action") == "saipen recover"
    and plan.get("code") == "RECONCILE_REAUTH_REQUIRED"
    and untouched
    and applied.get("code") == "REPAIRED"
    and after.get("ok") is True
    and row["section"] == "## TODO"
    and "closure_mode" not in row["fields"]
)
shutil.rmtree(root, ignore_errors=True)
print("held:", ok)
raise SystemExit(0 if ok else 1)
