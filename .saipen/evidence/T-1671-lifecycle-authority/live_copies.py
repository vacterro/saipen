"""The repaired engine against copies of the three projects the incident reached.

Usage: live_copies.py <repo> <scratch> <project> [<project> ...]

Fixtures prove the mechanism; a copy of the real bytes proves it on the
projects that actually carry a hand-written lifecycle. Each project's
`.saipen` (ledger included; caches, locks and nested repositories left out) is
copied into a fresh git worktree under <scratch>. Nothing here writes to the
project itself: every call runs with cwd and PWD on the copy, --project-root
first, SAIPEN* variables stripped and FORBID_SAIPEN_PROJECT_WRITE naming this
repository.

For each copy: status, the bare recovery plan, the plan applied (the approved
command when one is named), then status and the validator's lifecycle line.
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
projects = [Path(p).resolve() for p in sys.argv[3:]]
SAIPEN = repo / "tools" / "saipen.py"
VALIDATE = repo / "tools" / "validate.py"
SKIP = {"cache", "tmp", "locks", "__pycache__", "shots", ".git", "exchange"}
CANON = ("STATE.md", "BOARD.md", "LOG.md")


def _clear(function, path, _info):
    os.chmod(path, stat.S_IWRITE)
    function(path)


def env_for(copy: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
    env.update(PYTHONUTF8="1", PWD=str(copy), FORBID_SAIPEN_PROJECT_WRITE=str(repo))
    return env


def cli(copy: Path, *args: str) -> dict:
    proc = subprocess.run(
        [sys.executable, "-B", str(SAIPEN), "--project-root", str(copy), "--json", *args],
        cwd=str(copy), env=env_for(copy), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=900,
    )
    blob = (proc.stdout or "") + (proc.stderr or "")
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        return {"ok": False, "code": "CLI_CRASH", "detail": blob[-600:]}


def brief(answer: dict) -> str:
    keep = {k: answer.get(k) for k in ("ok", "code", "reason", "action", "phase", "task",
                                        "event", "canonical_next_command")}
    authority = answer.get("lifecycle_authority")
    if authority:
        keep["floor"] = authority.get("floor")
        keep["head"] = authority.get("head")
        keep["findings"] = [
            (f.get("rule"), f.get("ticket") or f.get("last_event")) for f in authority["findings"]
        ]
    return json.dumps({k: v for k, v in keep.items() if v is not None}, ensure_ascii=False)


def lifecycle_line(copy: Path) -> str:
    proc = subprocess.run(
        [sys.executable, "-B", str(VALIDATE), "--project-root", str(copy)],
        cwd=str(repo), env=env_for(copy), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=1800,
    )
    lines = [line for line in (proc.stdout or "").splitlines()
             if line.startswith("FAIL") and "lifecycle authority" in line]
    return lines[0][:420] if lines else "no lifecycle-authority FAIL"


failures = 0
for project in projects:
    name = project.name
    copy = scratch / f"live-{name}"
    if copy.exists():
        shutil.rmtree(copy, onerror=_clear)
    shutil.copytree(
        project / ".saipen", copy / ".saipen",
        ignore=lambda _dir, names: [n for n in names if n in SKIP],
    )
    for args in (["init", "-q", "."], ["add", "-A"],
                 ["-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
                  "commit", "-qm", "copy of the live project memory"]):
        subprocess.run(["git", *args], cwd=copy, capture_output=True, check=False)
    live_before = {n: (project / ".saipen" / n).read_bytes() for n in CANON}
    before = {n: (copy / ".saipen" / n).read_bytes() for n in CANON}
    print(f"=== {name}")
    print("  status before  :", brief(cli(copy, "status")))
    print("  validator      :", lifecycle_line(copy))
    plan = cli(copy, "recover")
    print("  recover        :", brief(plan))
    for repair in (plan.get("changed") or {}).get("lifecycle") or plan.get("lifecycle") or []:
        if isinstance(repair, dict):
            print(f"      board  {repair.get('ticket')}: {repair.get('from_section')} -> "
                  f"{repair.get('to_section')} dropping {repair.get('fields')}")
    changed = plan.get("changed")
    for repair in (changed.get("state") if isinstance(changed, dict) else None) or []:
        print(f"      state  {repair.get('field')}: {repair.get('from')!r} -> {repair.get('to')!r}")
    command = str(plan.get("canonical_next_command") or "")
    if "<next-action>" in command:
        # A free-form legacy next_action is its own operator decision (T-1358);
        # the copy answers it with the idle route so the lifecycle repair can
        # be observed. On the live project the operator supplies the value.
        command = command.replace("<next-action>", "saipen-continue")
        print("  operator value : next_action answered on the copy as 'saipen continue'")
    if plan.get("code") == "RECONCILE_REAUTH_REQUIRED" and " recover " in command + " ":
        argv = ["saipen continue" if part == "saipen-continue" else part
                for part in command.split()[1:]]
        applied = cli(copy, *argv)
        print("  approved plan  :", brief(applied))
        if not applied.get("ok"):
            print("      detail:", str(applied.get("detail"))[:300])
    after = {n: (copy / ".saipen" / n).read_bytes() for n in CANON}
    appended = after["LOG.md"][len(before["LOG.md"]):].decode("utf-8", errors="replace")
    lf_before = before["LOG.md"].replace(b"\r\n", b"\n").rstrip(b"\n") + b"\n"
    lf_after = after["LOG.md"].replace(b"\r\n", b"\n")
    print("  LOG append-only: bytes", after["LOG.md"].startswith(before["LOG.md"]),
          "| lines (line ends folded)", lf_after.startswith(lf_before))
    appended = lf_after[len(lf_before):].decode("utf-8", errors="replace")
    for line in appended.splitlines():
        print("      +", line[:330])
    kept = copy / ".saipen" / "recovery" / "terminal-gap"
    if kept.is_dir():
        exact = {path.name.rsplit(".", 2)[-2]: path.read_bytes() for path in kept.iterdir()
                 if path.name.startswith("reconcile-2026100")}
        print("  original bytes kept under recovery/terminal-gap:",
              all(exact.get(n[:-3]) == before[n] for n in CANON) if exact else "none written")
    status = cli(copy, "status")
    print("  status after   :", brief(status))
    if not status.get("ok"):
        print("      detail:", str(status.get("detail"))[:300])
    line = lifecycle_line(copy)
    print("  validator after:", line)
    untouched = all((project / ".saipen" / n).read_bytes() == live_before[n] for n in CANON)
    print("  live project untouched by this run:", untouched)
    if "lifecycle authority" in line and line.startswith("FAIL"):
        failures += 1
    if str(status.get("reason")) == "UNAUTHORIZED_LIFECYCLE_WRITE":
        failures += 1
    shutil.rmtree(copy, onerror=_clear)
print(f"copies still unauthorized after recovery: {failures}")
raise SystemExit(1 if failures else 0)
