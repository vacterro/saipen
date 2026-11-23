"""REVIEW evidence: the incident through the operator's entry point.

Usage: review_launcher.py <repo>

VERIFY drove `python tools/saipen.py` directly. An executor reaches the engine
through the repository launcher, in a fresh process started by a shell, so the
same typed lifecycle is driven here through `bin\\saipen.cmd` (cmd.exe) and
`bin/saipen` (sh) with nothing imported from the engine in this process except
the fixture builder.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(repo / "tools"))
import test_t1671_lifecycle_authority as T  # noqa: E402

T.setUpModule()
CMD = repo / "bin" / "saipen.cmd"
SH = repo / "bin" / "saipen"
BASH = shutil.which("bash")


def env_for(root: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
    env.update(PYTHONUTF8="1", PWD=str(root), FORBID_SAIPEN_PROJECT_WRITE=str(repo))
    return env


def through(kind: str, root: Path, *args: str) -> dict:
    tail = ["--project-root", str(root), "--agent", T.AGENT, "--json", *args]
    if kind == "cmd":
        argv = ["cmd.exe", "/d", "/c", str(CMD), *tail]
    else:
        argv = [BASH, str(SH), *tail]
    proc = subprocess.run(argv, cwd=str(root), env=env_for(root), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=600)
    blob = (proc.stdout or "") + (proc.stderr or "")
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        return {"ok": False, "code": "LAUNCHER_OUTPUT_NOT_JSON", "detail": blob[-400:]}


def brief(answer: dict) -> str:
    keep = {k: answer.get(k) for k in ("ok", "code", "reason", "action", "event",
                                        "top_workable_ticket", "canonical_next_command")}
    return json.dumps({k: v for k, v in keep.items() if v is not None}, ensure_ascii=False)[:330]


bad = 0
for kind in ("cmd", "sh"):
    if kind == "sh" and not BASH:
        print("sh: no bash on this host, skipped")
        continue
    root = T._project()
    T._type_the_lifecycle(root)
    before = T._bytes(root)
    status = through(kind, root, "status")
    refused = through(kind, root, "ticket", "done", "T-001", "--closure-mode", "own_patch")
    unchanged = T._bytes(root) == before
    plan = through(kind, root, "recover")
    route = str(plan.get("canonical_next_command") or "").split()[1:]
    applied = through(kind, root, *route) if route else {}
    after = through(kind, root, "status")
    print(f"=== bin/saipen{'.cmd via cmd.exe' if kind == 'cmd' else ' via sh'}")
    print("  status      :", brief(status))
    print("  ticket done :", brief(refused), "| canonical bytes unchanged:", unchanged)
    print("  recover     :", brief(plan))
    print("  approved    :", brief(applied))
    print("  status after:", brief(after))
    ok = (
        status.get("reason") == T.CLASS
        and T.CLASS in str(refused.get("message"))
        and unchanged
        and applied.get("code") == "REPAIRED"
        and after.get("ok") is True
        and after.get("top_workable_ticket") == "T-001"
    )
    bad += 0 if ok else 1
    shutil.rmtree(root, ignore_errors=True)
print("launcher paths that did not hold:", bad)
raise SystemExit(1 if bad else 0)
