"""Run one engine or validator command against a disposable copy, never the repo.

Usage: copy_cli.py <copy> <live-repo> saipen <words...>
       copy_cli.py <copy> <live-repo> validate [args...]

The copy's OWN tools run with the copy as working directory and project root.
The repository's root is named in the write interlock, so a call that somehow
resolved it as its project would be refused instead of mutating it.
"""
import os
import subprocess
import sys
from pathlib import Path

copy = Path(sys.argv[1]).resolve()
live = Path(sys.argv[2]).resolve()
kind, words = sys.argv[3], sys.argv[4:]
assert copy != live and (copy / ".saipen" / "STATE.md").is_file(), copy
env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
env["PWD"] = str(copy)
env["FORBID_SAIPEN_PROJECT_WRITE"] = str(live)
env["PYTHONUTF8"] = "1"
if kind == "saipen":
    argv = [sys.executable, "-B", str(copy / "tools" / "saipen.py"), "--project-root", str(copy), *words]
elif kind == "validate":
    argv = [sys.executable, "-B", str(copy / "tools" / "validate.py"), *words]
else:
    raise SystemExit(f"unknown kind {kind!r}")
proc = subprocess.run(
    argv, cwd=str(copy), env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=1800,
    check=False,
)
sys.stdout.write(proc.stdout.decode("utf-8", errors="replace"))
sys.stderr.write(proc.stderr.decode("utf-8", errors="replace"))
sys.exit(proc.returncode)
