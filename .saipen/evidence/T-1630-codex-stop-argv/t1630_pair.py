"""T-1630: the regression pair on one verifier, plus a red control per half.

Usage: t1630_pair.py <repo> <prefix-tree> <copy>

<prefix-tree> holds the pre-fix bytes of the two subject files (a copy of this
tree taken at 07:48 local on 2026-10-08, before another executor wrote the
repair in at 07:56). The copy is this tree with those two files restored; the
verifier (tools/test_codex_stop_hook.py) is byte-identical in both runs.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

repo, prefix, copy = (Path(arg).resolve() for arg in sys.argv[1:4])
assert not copy.exists(), copy
sys.path.insert(0, str(repo / "tools"))

from saipen_engine import oracle  # noqa: E402

GUARD = "extensions/adapters/codex/saipen-guard.py"
INSTALLER = "tools/install_host_guard.py"
SUBJECT = (GUARD, INSTALLER)
VERIFIER = ("tools/test_codex_stop_hook.py",)
TESTS = ["test_codex_stop_hook.CommandLineFaultTests",
         "test_codex_stop_hook.BrokenArtifactInstallTests"]
COMMAND = "python -B -m unittest " + " ".join(TESTS)


def ignore(_directory, names):
    return [n for n in names if n in {"__pycache__", ".ruff_cache"} or n.endswith(".pyc")]


for part in ("tools", "tests", "saipen", "extensions", "bin", "bootstrap"):
    shutil.copytree(repo / part, copy / part, ignore=ignore)
shutil.copy2(repo / "VERSION", copy / "VERSION")


def run(tree: Path, tests=TESTS) -> tuple[int, str]:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
    env["PYTHONUTF8"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", *tests], cwd=str(tree / "tools"), env=env,
        stdin=subprocess.DEVNULL, capture_output=True, timeout=1800, check=False,
    )
    return proc.returncode, (proc.stdout + proc.stderr).decode("utf-8", errors="replace")


def reds(out: str) -> list:
    return sorted(set(re.findall(r"^(?:FAIL|ERROR): (test_\w+)", out, flags=re.MULTILINE)))


assert (copy / VERIFIER[0]).read_bytes() == (repo / VERIFIER[0]).read_bytes()
verifier = oracle.verifier_identity(COMMAND, VERIFIER, repo)
code, out = run(copy)
print(f"CONTROL unmutated copy: exit {code}, {(re.search(r'Ran [0-9]+ tests', out) or [''])[0]}")
held = code == 0
for label, files in (("only the guard pre-fix", [GUARD]), ("only the installer pre-fix", [INSTALLER])):
    for rel in files:
        shutil.copy2(prefix / rel, copy / rel)
    code, out = run(copy)
    print(f"{label}: exit {code}, red {reds(out)}")
    held &= code != 0
    for rel in files:
        shutil.copy2(repo / rel, copy / rel)
for rel in SUBJECT:
    shutil.copy2(prefix / rel, copy / rel)
red_code, red_out = run(copy)
green_code, green_out = run(repo)
print(f"command: {COMMAND} (cwd tools/)")
print(f"verifier:{verifier[:16]}  ({VERIFIER[0]}, byte-identical in both trees)")
print(f"FAIL subject:{oracle.oracle_digest(copy, SUBJECT)[:16]}  exit {red_code}  red: {', '.join(reds(red_out))}")
print(f"PASS subject:{oracle.oracle_digest(repo, SUBJECT)[:16]}  exit {green_code}  "
      f"{(re.search(r'Ran [0-9]+ tests', green_out) or [''])[0]}")
held &= red_code != 0 and green_code == 0
shutil.rmtree(copy, ignore_errors=True)
print("held:", held)
raise SystemExit(0 if held else 1)
