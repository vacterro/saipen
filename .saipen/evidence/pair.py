"""Red on the pre-fix subject, green on the tree, one byte-identical verifier.

Usage: pair.py <repo> <copy> <prefix-dir> <test-module> <subject-path>...

<prefix-dir> holds the pre-fix bytes of every <subject-path> (repository
relative), copied before the ticket's edits. The copy is the tree with those
files restored; the verifier tools/<test-module>.py is the same bytes in both
runs. Prints the verifier and both subject digests in the
REGRESSION-EVIDENCE vocabulary of saipen_engine.oracle.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

repo, copy, prefix = (Path(arg).resolve() for arg in sys.argv[1:4])
module = sys.argv[4]
subject = tuple(sys.argv[5:])
assert subject and not copy.exists(), (subject, copy)
sys.path.insert(0, str(repo / "tools"))

from saipen_engine import oracle  # noqa: E402

verifier_paths = (f"tools/{module}.py",)
command = f"python -B -m unittest {module}"
for rel in subject:
    assert (prefix / rel).is_file(), rel


def ignore(_directory, names):
    return [n for n in names if n in {"__pycache__", ".ruff_cache"} or n.endswith(".pyc")]


for part in ("tools", "tests", "saipen", "extensions", "bin", "bootstrap"):
    shutil.copytree(repo / part, copy / part, ignore=ignore)
shutil.copy2(repo / "VERSION", copy / "VERSION")


def run(tree: Path) -> tuple[int, str]:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
    env["PYTHONUTF8"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", module], cwd=str(tree / "tools"), env=env,
        stdin=subprocess.DEVNULL, capture_output=True, timeout=1800, check=False,
    )
    return proc.returncode, (proc.stdout + proc.stderr).decode("utf-8", errors="replace")


def reds(out: str) -> list:
    return sorted(set(re.findall(r"^(?:FAIL|ERROR): (\S+)", out, flags=re.MULTILINE)))


def ran(out: str) -> str:
    return (re.search(r"Ran [0-9]+ tests?", out) or [""])[0]


assert (copy / verifier_paths[0]).read_bytes() == (repo / verifier_paths[0]).read_bytes()
verifier = oracle.verifier_identity(command, verifier_paths, repo)
code, out = run(copy)
print(f"CONTROL unmutated copy: exit {code}, {ran(out)}")
held = code == 0
for rel in subject:
    shutil.copy2(prefix / rel, copy / rel)
red_code, red_out = run(copy)
green_code, green_out = run(repo)
print(f"command: {command} (cwd tools/)")
print(f"verifier:{verifier[:16]}  ({verifier_paths[0]}, byte-identical in both trees)")
print(f"FAIL subject:{oracle.oracle_digest(copy, subject)[:16]}  exit {red_code}  "
      f"red {len(reds(red_out))}: {', '.join(reds(red_out))}")
print(f"PASS subject:{oracle.oracle_digest(repo, subject)[:16]}  exit {green_code}  {ran(green_out)}")
held &= red_code != 0 and green_code == 0
shutil.rmtree(copy, ignore_errors=True)
print("held:", held)
raise SystemExit(0 if held else 1)
