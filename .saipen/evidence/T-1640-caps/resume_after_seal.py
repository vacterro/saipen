"""REVIEW probe: does Work parked across a seal resume on its sealed evidence?

Usage: resume_after_seal.py <repo> <scratch-dir> <copy-name>

On a disposable copy of the real project: park the active ticket (its VERIFY
evidence is in the active LOG), enter CLEAN (the LOG is sealed, so that
evidence is now in a sealed segment), leave CLEAN, resume the ticket and ask
the gates that read cycle evidence. The repository is never written.
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
copy = scratch / sys.argv[3]
assert repo != copy and repo not in copy.parents


def _writable(function, path, _info):
    os.chmod(path, stat.S_IWRITE)
    function(path)


if copy.exists():
    shutil.rmtree(copy, onerror=_writable)
skip_tree = {".git", ".saipen", "__pycache__", ".pytest_cache", ".ruff_cache",
             ".workbuddy-ai", ".codenomad", ".freebuff", ".claude"}
shutil.copytree(
    repo, copy, ignore=lambda d, names: [n for n in names if n in skip_tree or n.endswith(".pyc")]
)
skip_memory = {"cache", "tmp", "saitranslate", "exchange", "locks"}
shutil.copytree(
    repo / ".saipen", copy / ".saipen",
    ignore=lambda d, names: [
        n for n in names
        if (Path(d) == repo / ".saipen" and n in skip_memory) or n == ".git"
        or n.endswith((".tmp", ".lock"))
    ],
)
env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
env["PWD"] = str(copy)
env["FORBID_SAIPEN_PROJECT_WRITE"] = str(repo)
env["PYTHONUTF8"] = "1"


def saipen(*words: str) -> dict:
    proc = subprocess.run(
        [sys.executable, "-B", str(copy / "tools" / "saipen.py"), "--project-root", str(copy),
         *words, "--json"],
        cwd=str(copy), env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=1800,
        check=False,
    )
    out = proc.stdout.decode("utf-8", errors="replace")
    try:
        return json.loads(out)
    except ValueError:
        return {"ok": False, "code": "UNPARSEABLE", "message": out[-500:]}


def say(label: str, answer: dict, *keys: str) -> None:
    shown = {k: answer.get(k) for k in ("ok", "code", *keys)}
    detail = str(answer.get("message") or answer.get("detail") or "")
    text = f"{label}: {json.dumps(shown)}" + (f" :: {detail[:260]}" if not answer.get("ok") else "")
    print(text.encode("ascii", "replace").decode("ascii"))


status = saipen("status")
ticket = status.get("claimed_ticket")
say("status before", status, "phase", "task")
assert ticket, status
say("park", saipen("ticket", "block", ticket, "ACTIVE -- parked so CLEAN can be entered"), "ticket")
entry = saipen("transition", "CLEAN")
say("transition CLEAN", entry, "phase")
say("  board_scrub", entry.get("board_scrub") or {}, "pruned_records")
say("  log_seal", entry.get("log_seal") or {}, "segment", "sealed_from", "sealed_to")
again = saipen("transition", "CLEAN")
say("transition CLEAN again", again, "phase")
print("  second entry reports a step:", [k for k in ("board_scrub", "log_seal") if k in again])
say("clean exit record", saipen("checkpoint", "RUN", "clean -> done @0000000"), "event_id")
say("transition DONE", saipen("transition", "DONE"), "phase")
say("unblock", saipen("ticket", "unblock", ticket, "CLEAN completed; the pause condition is met"), "ticket")
resumed = saipen("claim", ticket)
say("claim", resumed, "phase", "ticket")
status = saipen("status")
say("status after resume", status, "phase", "task")
tail = (copy / ".saipen" / "LOG.md").read_text(encoding="utf-8").splitlines()
print("active LOG lines after resume:", len(tail))
print("cycle evidence left in the active LOG:",
      sum(1 for line in tail if "verify -> PASS" in line or "CORE-UNIT-EVIDENCE" in line))
say("transition REVIEW on sealed VERIFY evidence",
    saipen("transition", "REVIEW", ticket, "VERIFY PASS"), "phase")
say("transition SHIP on the sealed family citation",
    saipen("transition", "SHIP", ticket, "core-unit PASS"), "phase")
say("status at the end", saipen("status"), "phase", "task")
