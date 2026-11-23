"""T-1666: the closing route on a disposable copy of this project.

Usage: disposable_copy.py <repo> <copy>

Copies the whole checkout with robocopy, parks the copy's own DOING ticket
(the CLEAN steps refuse while Work is in DOING), enters CLEAN through the
copy's engine and measures ACTIVE receipts, closable receipts and the BOARD
before and after; validate --gate core runs on the copy before and after.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

repo, copy = (Path(arg).resolve() for arg in sys.argv[1:3])
assert not copy.exists(), copy
proc = subprocess.run(
    ["robocopy", str(repo), str(copy), "/E", "/MT:16", "/NFL", "/NDL", "/NJH", "/NJS", "/NP",
     "/XD", "__pycache__", ".ruff_cache"],
    capture_output=True, check=False,
)
assert proc.returncode < 8, proc.stdout[-2000:]
env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
env.update(PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", SAIPEN_CAPABILITY="no-publish")
sys.path.insert(0, str(copy / "tools"))
from saipen_engine import intake  # noqa: E402
from saipen_engine.board import parse_board  # noqa: E402


def cli(*args: str) -> dict:
    out = subprocess.run(
        [sys.executable, "-B", str(copy / "tools" / "saipen.py"), "--project-root", str(copy),
         "--json", *args],
        cwd=str(copy), env=env, capture_output=True, timeout=1800, check=False,
    ).stdout.decode("utf-8", errors="replace")
    try:
        return json.loads(out)
    except ValueError:
        return {"ok": False, "raw": out[-600:]}


def validate() -> list[str]:
    out = subprocess.run(
        [sys.executable, "-B", str(copy / "tools" / "validate.py"), "--gate", "core",
         "--project-root", str(copy)],
        cwd=str(copy), env=env, capture_output=True, timeout=1800, check=False,
    ).stdout.decode("utf-8", errors="replace")
    return [line for line in out.splitlines() if line.startswith("FAIL")]


def measure() -> dict:
    board = (copy / ".saipen" / "BOARD.md").read_bytes()
    tickets = parse_board(board.decode("utf-8"))["tickets"]
    index = json.loads((copy / ".saipen" / "intake" / "index.json").read_text(encoding="utf-8"))
    return {
        "active_receipts": len(index.get("active", {})),
        "closable": len(intake.closable_receipts(copy)),
        "board_bytes": len(board),
        "done_rows": sum(1 for t in tickets.values() if t["section"] == "## DONE"),
    }


fails = validate()
print("validate before:", len(fails), "FAIL", fails[:3])
print("measured before:", json.dumps(measure()))
parked = cli("ticket", "block", "T-1666", "disposable copy: parked so CLEAN may run")
print("park T-1666:", parked.get("ok"), parked.get("code"))
entry = cli("transition", "CLEAN")
closed = entry.get("source_closed") or {}
scrub = entry.get("board_scrub") or {}
print("enter CLEAN:", entry.get("ok"), entry.get("code"),
      "| closed", len(closed.get("closed") or []), "refused", closed.get("refused"),
      "| scrub", scrub.get("ok"), scrub.get("code"), "pruned", scrub.get("pruned_records"))
print("measured after: ", json.dumps(measure()))
fails = validate()
print("validate after:", len(fails), "FAIL", fails[:3])
