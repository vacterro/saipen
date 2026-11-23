"""T-1679 on a copy of the real bytes: the two-command chain, end to end.

Usage: live_chain.py <repo> <scratch> <project>

The project's `.saipen` (ledger included; caches, locks and nested
repositories left out) is copied into a fresh git worktree under <scratch>.
Nothing writes to the project: cwd and PWD are the copy, --project-root comes
first, SAIPEN* variables are stripped and FORBID_SAIPEN_PROJECT_WRITE names
this repository. The copy keeps the project's own `saipen_home`, which is this
repository, so the immutable-ledger contract is enforced as it is live.
"""
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
scratch = Path(sys.argv[2]).resolve()
project = Path(sys.argv[3]).resolve()
SAIPEN = repo / "tools" / "saipen.py"
SKIP = {"cache", "tmp", "locks", "__pycache__", "shots", ".git", "exchange"}
CANON = ("STATE.md", "BOARD.md", "LOG.md")


def _clear(function, path, _info):
    os.chmod(path, stat.S_IWRITE)
    function(path)


copy = scratch / f"chain-{project.name}"
if copy.exists():
    shutil.rmtree(copy, onerror=_clear)
shutil.copytree(project / ".saipen", copy / ".saipen",
                ignore=lambda _dir, names: [n for n in names if n in SKIP])
for args in (["init", "-q", "."], ["add", "-A"],
             ["-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
              "commit", "-qm", "copy of the live project memory"]):
    subprocess.run(["git", *args], cwd=copy, capture_output=True, check=False)
env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
env.update(PYTHONUTF8="1", PWD=str(copy), FORBID_SAIPEN_PROJECT_WRITE=str(repo))


def cli(*args: str) -> dict:
    proc = subprocess.run(
        [sys.executable, "-B", str(SAIPEN), "--project-root", str(copy), "--json", *args],
        cwd=str(copy), env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=900,
    )
    blob = (proc.stdout or "") + (proc.stderr or "")
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        return {"ok": False, "code": "CLI_CRASH", "detail": blob[-600:]}


def brief(answer: dict, *keys: str) -> str:
    keep = {k: answer.get(k) for k in ("ok", "code", "reason", "action", *keys)}
    return json.dumps({k: v for k, v in keep.items() if v is not None}, ensure_ascii=False)[:520]


live_before = {n: (project / ".saipen" / n).read_bytes() for n in CANON}
before = {n: (copy / ".saipen" / n).read_bytes() for n in CANON}
print(f"=== {project.name}: STATE as found")
for line in before["STATE.md"].decode("utf-8", errors="replace").splitlines():
    if line.split(":")[0] in ("phase", "task", "next_action", "transition_from", "last_event"):
        print("   ", line)
print("1 status         :", brief(cli("status")))
refused = cli("recover")
print("2 recover        :", brief(refused, "canonical_next_command", "terminal_disposition"))
print("    ", str(refused.get("detail"))[:160])
cut = cli("recover", "quarantine-log-tail")
print("3 quarantine     :", brief(cut, "journal_floor", "quarantined_lines", "claimed_ids"))
kept_ok = False
if cut.get("evidence_path"):
    kept_ok = (copy / cut["evidence_path"]).read_bytes() == before["LOG.md"].replace(b"\r\n", b"\n") \
        or (copy / cut["evidence_path"]).read_bytes() == before["LOG.md"]
print("    original LOG kept in the evidence copy:", kept_ok)
tail = (copy / ".saipen" / "LOG.md").read_text(encoding="utf-8").strip().splitlines()[-1]
print("    ", tail[:420])
print("4 status         :", brief(cli("status")))
plan = cli("recover")
print("5 recover        :", brief(plan, "canonical_next_command"))
changed = plan.get("changed") if isinstance(plan.get("changed"), dict) else {}
for repair in changed.get("lifecycle") or []:
    print(f"     board  {repair.get('ticket')}: {repair.get('from_section')} -> "
          f"{repair.get('to_section')}  [{repair.get('_class')}]")
for repair in changed.get("state") or []:
    print(f"     state  {repair.get('field')}: {str(repair.get('from'))[:44]!r} -> {repair.get('to')!r}")
command = str(plan.get("canonical_next_command") or "")
applied = cli(*command.split()[1:]) if "--apply-approved-repair" in command else {}
print("6 approved plan  :", brief(applied, "event"))
status = cli("status")
print("7 status         :", brief(status, "phase", "task", "top_workable_ticket"))
if not status.get("ok"):
    print("    ", str(status.get("detail"))[:300])
print("8 recover        :", brief(cli("recover")))
untouched = all((project / ".saipen" / n).read_bytes() == live_before[n] for n in CANON)
print("live project untouched by this run:", untouched)
shutil.rmtree(copy, onerror=_clear)
raise SystemExit(0 if status.get("ok") and untouched else 1)
