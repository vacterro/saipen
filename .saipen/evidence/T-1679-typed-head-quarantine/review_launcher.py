"""REVIEW evidence for T-1679: the broken typed head through the launcher.

Usage: review_launcher.py <repo>

VERIFY drove `python tools/saipen.py`. Here the same fixture (a typed lifecycle
whose own line was replaced, STATE left malformed) goes through `bin\\saipen.cmd`
in fresh cmd.exe processes, the way an agent that reads the refusal would run
the two commands it names.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(repo / "tools"))
import test_t1679_typed_head_quarantine as T  # noqa: E402

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


def brief(answer: dict, *keys: str) -> str:
    keep = {k: answer.get(k) for k in ("ok", "code", "reason", *keys)}
    return json.dumps({k: v for k, v in keep.items() if v is not None}, ensure_ascii=False)[:300]


root = T._project()
T._type_the_lifecycle(root, keep_task=True)
T._replace_a_typed_line(root)
T._state_field(root, "transition_from", "REPAIR")
before = T._bytes(root)
first = launcher(root, "recover")
named = str(first.get("canonical_next_command") or "")
cut = launcher(root, *named.split()[1:]) if named else {}
blocked = launcher(root, "transition", "SCOUT", "next")
plan = launcher(root, "recover")
approved = str(plan.get("canonical_next_command") or "")
applied = launcher(root, *approved.split()[1:]) if approved else {}
after = launcher(root, "status")
print("recover          :", brief(first, "canonical_next_command", "terminal_disposition"))
print("named command    :", brief(cut, "journal_floor", "quarantined_lines"))
print("an ordinary verb :", brief(blocked), "|", str(blocked.get("message"))[:90])
print("recover          :", brief(plan))
print("approved command :", brief(applied, "event"))
print("status           :", brief(after, "top_workable_ticket"))
ok = (
    first.get("code") == "HISTORY_LEDGER_CORRUPT"
    and named == "saipen recover quarantine-log-tail"
    and cut.get("code") == "LOG_TAIL_QUARANTINED"
    and (root / cut["evidence_path"]).read_bytes() == before["LOG.md"]
    and blocked.get("ok") is False
    and plan.get("code") == "RECONCILE_REAUTH_REQUIRED"
    and applied.get("code") == "REPAIRED"
    and after.get("ok") is True
    and after.get("top_workable_ticket") == "T-001"
)
shutil.rmtree(root, ignore_errors=True)
print("held:", ok)
raise SystemExit(0 if ok else 1)
