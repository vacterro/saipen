"""What does a clone of this repository read where git-ignored evidence stood?

Usage: clone_shape_probe.py <copy-with-memory> <live-repo>

`git check-ignore` is asked in the live repository which stores under
.saipen/recovery are ignored; the same stores are then moved aside in the
disposable copy and its validator and engine are asked what they see.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

copy = Path(sys.argv[1]).resolve()
live = Path(sys.argv[2]).resolve()
assert copy != live and live not in copy.parents

recovery = copy / ".saipen" / "recovery"
stores = sorted(p.name for p in (live / ".saipen" / "recovery").iterdir() if p.is_dir())
ignored = []
for name in stores:
    probe = f".saipen/recovery/{name}/probe"
    code = subprocess.run(
        ["git", "-C", str(live), "check-ignore", "-q", "--", probe],
        stdin=subprocess.DEVNULL, capture_output=True, check=False,
    ).returncode
    tracked = subprocess.run(
        ["git", "-C", str(live), "ls-files", "--", f".saipen/recovery/{name}"],
        stdin=subprocess.DEVNULL, capture_output=True, check=False,
    ).stdout.count(b"\n")
    print(f"{name:28s} ignored={code == 0!s:5s} tracked_files={tracked}")
    if code == 0:
        ignored.append(name)

env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
env["PWD"] = str(copy)
env["FORBID_SAIPEN_PROJECT_WRITE"] = str(live)
env["PYTHONUTF8"] = "1"


def findings() -> tuple[int, list[str]]:
    proc = subprocess.run(
        [sys.executable, "-B", str(copy / "tools" / "validate.py"), "--gate", "core"],
        cwd=str(copy), env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=1800,
        check=False,
    )
    out = proc.stdout.decode("utf-8", errors="replace")
    return proc.returncode, [l for l in out.splitlines() if re.match(r"^(FAIL|WARN)", l)]


code_before, before = findings()
aside = copy / ".saipen" / "recovery.aside"
aside.mkdir(exist_ok=True)
moved = []
for name in ("board-compaction", "board-compaction-lineage"):
    if name in ignored and (recovery / name).is_dir():
        (recovery / name).rename(aside / name)
        moved.append(name)
print("moved aside in the copy:", moved)
code_after, after = findings()
print("validator before:", code_before, len(before), "findings; after:", code_after, len(after))
for line in after:
    if line not in before:
        print("  NEW:", line[:330].encode("ascii", "replace").decode("ascii"))

sys.path.insert(0, str(copy / "tools"))
from saipen_engine.board import parse_board  # noqa: E402
from saipen_engine.board_compaction import resolve_detail  # noqa: E402

tickets = parse_board((copy / ".saipen" / "BOARD.md").read_text(encoding="utf-8"))["tickets"]
cited = {tid: t["fields"]["detail_ref"] for tid, t in tickets.items() if t["fields"].get("detail_ref")}
broken = 0
first = ""
for tid, ref in cited.items():
    try:
        resolve_detail(copy, ref, expected_ticket_id=tid)
    except (OSError, ValueError) as exc:
        broken += 1
        first = first or f"{tid}: {exc}"
print(f"BOARD rows citing a detail_ref: {len(cited)}; unresolvable after the move: {broken}")
print("first:", first[:260].encode("ascii", "replace").decode("ascii"))
for name in moved:
    (aside / name).rename(recovery / name)
print("restored in the copy")
