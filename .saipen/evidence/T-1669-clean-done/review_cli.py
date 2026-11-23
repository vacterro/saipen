"""REVIEW evidence for T-1669: the incident through the launcher, not in-process.

Usage: review_cli.py <repo>

The test module calls `operations.transition_phase` directly. Here the same
fixture (CLEAN, a routed audit layer whose Work is runnable) is driven through
`bin\\saipen.cmd` in a fresh cmd.exe process: `transition DONE`, then `status`
and `validate.py --gate core`, before anything is claimed.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(repo / "tools"))
import test_t1669_clean_done_projection as T  # noqa: E402

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


bad = 0
for label, build in (
    ("routed audit layer", lambda: T._clean_project_with_runnable_work()[0]),
    ("nothing routed", lambda: T.fresh_project(phase="CLEAN", task="none",
                                               next_action="PHASE CLEAN")),
):
    root = build()
    moved = launcher(root, "transition", "DONE")
    committed = T._state(root).get("next_action")
    status = launcher(root, "status")
    fails = T._core_fails(root)
    print(f"=== CLEAN -> DONE, {label}")
    print("  transition :", json.dumps({k: moved.get(k) for k in ("ok", "code", "phase",
                                                                 "next_action")}))
    print("  committed next_action:", committed)
    print("  status     :", json.dumps({k: status.get(k) for k in ("ok", "next_action",
                                                                 "computed_next_action")}))
    print("  validate --gate core FAIL lines:", len(fails), fails[:2])
    ok = (
        moved.get("ok") is True
        and moved.get("next_action") == committed
        and committed != "PHASE DONE"
        and status.get("ok") is True
        and status.get("computed_next_action") == committed
        and not fails
        and T._doing(root) == []
    )
    bad += 0 if ok else 1
    shutil.rmtree(root, ignore_errors=True)
print("cases that did not hold:", bad)
raise SystemExit(1 if bad else 0)
