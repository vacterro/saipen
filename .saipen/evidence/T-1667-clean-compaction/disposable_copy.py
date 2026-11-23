"""T-1667: the CLEAN compaction step on a disposable copy of this project.

Usage: disposable_copy.py <repo> <copy>

Copies the whole checkout (.git and .saipen included, caches excluded) with
robocopy, measures the operation journal, runs `operations.compact_journal`
-- the step `saipen transition CLEAN` runs -- from the copy's own engine, and
measures again. `validate.py --gate core` runs on the copy before and after.
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
env.update(PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")


def validate() -> list[str]:
    out = subprocess.run(
        [sys.executable, "-B", str(copy / "tools" / "validate.py"), "--gate", "core",
         "--project-root", str(copy)],
        cwd=str(copy), env=env, capture_output=True, timeout=1800, check=False,
    ).stdout.decode("utf-8", errors="replace")
    return [line for line in out.splitlines() if line.startswith("FAIL")]


def measure() -> dict:
    settled = copy / ".saipen" / "recovery" / "settled"
    total = staged = staged_files = dirs = 0
    for entry in os.scandir(settled):
        if entry.is_dir(follow_symlinks=False) and not entry.name.startswith("."):
            dirs += 1
        for path in Path(entry.path).rglob("*") if entry.is_dir(follow_symlinks=False) else ():
            if path.is_file():
                size = path.stat().st_size
                total += size
                if path.name.endswith(".staged"):
                    staged += size
                    staged_files += 1
    ops = copy / ".saipen" / "recovery" / "ops"
    return {
        "settled_dirs": dirs,
        "settled_bytes": total,
        "staged_files": staged_files,
        "staged_bytes": staged,
        "ops": len([p for p in ops.iterdir() if p.is_dir()]) if ops.is_dir() else 0,
    }


print("validate before:", len(validate()), "FAIL")
before = measure()
print("measured before:", json.dumps(before))
step = subprocess.run(
    [sys.executable, "-B", "-c",
     "import json,sys; sys.path.insert(0, sys.argv[1]);"
     "from saipen_engine.operations import compact_journal;"
     "print(json.dumps(compact_journal(sys.argv[2], 'saipen-cli').to_dict()))",
     str(copy / "tools"), str(copy)],
    cwd=str(copy), env=env, capture_output=True, timeout=900, check=False,
)
print("compact_journal:", step.stdout.decode("utf-8", errors="replace").strip()[:1500])
after = measure()
print("measured after: ", json.dumps(after))
print("validate after:", len(validate()), "FAIL")
again = subprocess.run(
    [sys.executable, "-B", "-c",
     "import json,sys; sys.path.insert(0, sys.argv[1]);"
     "from saipen_engine.operations import compact_journal;"
     "print(json.dumps(compact_journal(sys.argv[2], 'saipen-cli').to_dict()))",
     str(copy / "tools"), str(copy)],
    cwd=str(copy), env=env, capture_output=True, timeout=900, check=False,
)
print("second pass:", again.stdout.decode("utf-8", errors="replace").strip()[:600])
