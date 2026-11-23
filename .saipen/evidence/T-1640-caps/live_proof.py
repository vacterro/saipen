"""The T-1640 route, run end to end on a disposable copy of the real project.

Usage: live_proof.py <repo> <scratch-dir> <copy-name>

Copies the repository with its project memory, runs the copy's own validator,
parks the active ticket, enters CLEAN through the copy's own CLI, checks the
moved bytes against the bytes saved before the entry, and validates again.
Prints one report. The repository is never written: every command runs with
the copy as working directory and project root, and the repository's root is
named in the write interlock.
"""
import hashlib
import json
import os
import re
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
    repo / ".saipen",
    copy / ".saipen",
    ignore=lambda d, names: [
        n
        for n in names
        if (Path(d) == repo / ".saipen" and n in skip_memory)
        or n == ".git"
        or n.endswith((".tmp", ".lock"))
    ],
)

env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
env["PWD"] = str(copy)
env["FORBID_SAIPEN_PROJECT_WRITE"] = str(repo)
env["PYTHONUTF8"] = "1"


def run(*argv: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-B", *argv], cwd=str(copy), env=env, stdin=subprocess.DEVNULL,
        capture_output=True, timeout=1800, check=False,
    )
    return proc.returncode, proc.stdout.decode("utf-8", errors="replace")


def saipen(*words: str) -> dict:
    code, out = run(str(copy / "tools" / "saipen.py"), "--project-root", str(copy), *words, "--json")
    try:
        return json.loads(out)
    except ValueError:
        raise SystemExit(f"saipen {' '.join(words)} -> exit {code}: {out[-800:]}")


def findings() -> tuple[int, dict[str, list[str]]]:
    code, out = run(str(copy / "tools" / "validate.py"), "--gate", "core")
    found: dict[str, list[str]] = {}
    for line in out.splitlines():
        match = re.match(r"^(FAIL|WARN)(?: \[([a-z0-9-]+)\])?: (.*)$", line)
        if match:
            found.setdefault(f"{match.group(1)} {match.group(2) or match.group(3)[:50]}", []).append(
                match.group(3)
            )
    return code, found


def say(text: str) -> None:
    print(text.encode("ascii", "replace").decode("ascii"))


memory = copy / ".saipen"
head = subprocess.run(
    ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"], capture_output=True, check=False
).stdout.decode().strip()
say(f"subject: copy of {repo.name} at HEAD {head} with its uncommitted tree and project memory")
code_before, before = findings()
say(f"validator before: exit {code_before}, findings {sorted(before)}")
for key in ("WARN board-soft-cap", "WARN log-soft-cap"):
    for text in before.get(key, []):
        say(f"    {key}: {text}")

state = saipen("status")
if state.get("claimed_ticket"):
    parked = saipen(
        "ticket", "block", state["claimed_ticket"],
        "ACTIVE -- parked in a disposable copy so CLEAN can be entered",
    )
    say(f"parked {state['claimed_ticket']}: {parked.get('code')}")
board_before = (memory / "BOARD.md").read_bytes()
log_before = (memory / "LOG.md").read_bytes()
answer = saipen("transition", "CLEAN")
say(f"transition CLEAN: {answer.get('code')} phase {answer.get('phase')}")
scrub, seal = answer.get("board_scrub") or {}, answer.get("log_seal") or {}
say("board_scrub: " + json.dumps({k: v for k, v in scrub.items() if k not in ("pruned", "changed_files")}))
say("log_seal: " + json.dumps({k: v for k, v in seal.items() if k != "changed_files"}))
assert scrub.get("ok") and seal.get("ok"), (scrub, seal)

board_after = (memory / "BOARD.md").read_bytes()
evidence = (copy / scrub["evidence_path"]).read_bytes()
pruned_lines = evidence.splitlines(keepends=True)
before_lines = board_before.splitlines(keepends=True)
drop = set(pruned_lines)
checks = {
    "evidence digest is the recorded one": hashlib.sha256(evidence).hexdigest() == scrub["evidence_sha256"],
    "evidence holds one physical BOARD line per pruned record": len(pruned_lines) == scrub["pruned_records"] == len(drop),
    "every evidence line was a BOARD line, in BOARD order": pruned_lines == [l for l in before_lines if l in drop],
    "BOARD after == BOARD before minus exactly those lines": b"".join(l for l in before_lines if l not in drop) == board_after,
}
segment = (copy / seal["segment"]).read_bytes()
tail = (memory / "LOG.md").read_bytes().decode("utf-8").splitlines()
checks.update({
    "segment digest is the recorded one": hashlib.sha256(segment).hexdigest() == seal["sealed_sha256"],
    "segment begins with the whole LOG saved before the entry": segment.startswith(log_before),
    "the entry added only its own events before the seal": [
        re.search(r"\[op: ([a-z-]+)-[0-9a-f]+\]", l).group(1)
        for l in segment[len(log_before):].decode("utf-8").splitlines()
    ] == ["transition", "board-scrub"],
    "fresh tail is the heading and the seal's own event": len(tail) == 2 and "DEC: log sealed --" in tail[1],
})
sys.path.insert(0, str(copy / "tools"))
from saipen_engine.fast_check import validate_project  # noqa: E402
from saipen_engine.log import read_history_snapshot, snapshot_contract_errors  # noqa: E402

snapshot = read_history_snapshot(copy)
checks["complete ledger passes the immutable-ledger contract"] = snapshot_contract_errors(snapshot) == []
checks["write gate passes on the result"] = validate_project(copy) == []
for label, held in checks.items():
    say(f"    {'PASS' if held else 'FAIL'}  {label}")
say(f"bytes: BOARD {len(board_before)} -> {len(board_after)}, active LOG {len(log_before)} -> "
    f"{(memory / 'LOG.md').stat().st_size}, events in ledger {len(snapshot.events)}")

code_after, after = findings()
say(f"validator after: exit {code_after}, findings {sorted(after)}")
say(f"gone: {sorted(set(before) - set(after))}")
say(f"new: {sorted(set(after) - set(before))}")
for key in sorted(set(after) - set(before)):
    for text in after[key]:
        say(f"    {key}: {text[:300]}")
ok = all(checks.values()) and code_after == 0 and not any(k.startswith("FAIL") for k in after) \
    and not any("soft-cap" in k for k in after)
say("RESULT: " + ("the named route clears both findings and breaks nothing" if ok else "NOT PROVEN"))
sys.exit(0 if ok else 1)
