"""T-1663: the regression pair on one verifier, plus a red control per engine half.

Usage: t1663_pair.py <repo> <copy>

prefix/ beside this script holds the pre-fix bytes of every subject file,
copied before the T-1663 edits (iteration_verdict.py rebuilt by removing
exactly the inserted blocks). The copy is this tree with those files
restored; the verifier (tools/test_t1663_ticket_requires.py) is
byte-identical in both runs.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

repo, copy = (Path(arg).resolve() for arg in sys.argv[1:3])
assert not copy.exists(), copy
sys.path.insert(0, str(repo / "tools"))

from saipen_engine import oracle  # noqa: E402

PREFIX = Path(__file__).resolve().parent / "prefix"
VERDICT = "tools/saipen_engine/iteration_verdict.py"
VERB = ("tools/saipen_engine/operations.py", "tools/saipen.py")
SUBJECT = (
    VERDICT,
    *VERB,
    "tools/saipen_engine/journal.py",
    "tools/saipen_engine/board_compaction.py",
    "saipen/REGISTRY.json",
    "extensions/schemas/board.schema.json",
)
VERIFIER = ("tools/test_t1663_ticket_requires.py",)
TESTS = ["test_t1663_ticket_requires"]
COMMAND = "python -B -m unittest " + " ".join(TESTS)
for rel in SUBJECT:
    assert (PREFIX / rel).is_file(), rel


def ignore(_directory, names):
    return [n for n in names if n in {"__pycache__", ".ruff_cache"} or n.endswith(".pyc")]


for part in ("tools", "tests", "saipen", "extensions", "bin", "bootstrap"):
    shutil.copytree(repo / part, copy / part, ignore=ignore)
shutil.copy2(repo / "VERSION", copy / "VERSION")


def run(tree: Path) -> tuple[int, str]:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
    env["PYTHONUTF8"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", *TESTS], cwd=str(tree / "tools"), env=env,
        stdin=subprocess.DEVNULL, capture_output=True, timeout=1800, check=False,
    )
    return proc.returncode, (proc.stdout + proc.stderr).decode("utf-8", errors="replace")


def reds(out: str) -> list:
    return sorted(set(re.findall(r"^(?:FAIL|ERROR): (test_\w+)", out, flags=re.MULTILINE)))


def ran(out: str) -> str:
    return (re.search(r"Ran [0-9]+ tests?", out) or [""])[0]


assert (copy / VERIFIER[0]).read_bytes() == (repo / VERIFIER[0]).read_bytes()
verifier = oracle.verifier_identity(COMMAND, VERIFIER, repo)
code, out = run(copy)
print(f"CONTROL unmutated copy: exit {code}, {ran(out)}")
held = code == 0
for label, files in (("only the verdict pre-fix", (VERDICT,)), ("only the verb pre-fix", VERB)):
    for rel in files:
        shutil.copy2(PREFIX / rel, copy / rel)
    code, out = run(copy)
    print(f"{label}: exit {code}, red {len(reds(out))}: {reds(out)}")
    held &= code != 0
    for rel in files:
        shutil.copy2(repo / rel, copy / rel)
for rel in SUBJECT:
    shutil.copy2(PREFIX / rel, copy / rel)
red_code, red_out = run(copy)
green_code, green_out = run(repo)
print(f"command: {COMMAND} (cwd tools/)")
print(f"verifier:{verifier[:16]}  ({VERIFIER[0]}, byte-identical in both trees)")
print(f"FAIL subject:{oracle.oracle_digest(copy, SUBJECT)[:16]}  exit {red_code}  "
      f"red {len(reds(red_out))}: {', '.join(reds(red_out))}")
print(f"PASS subject:{oracle.oracle_digest(repo, SUBJECT)[:16]}  exit {green_code}  {ran(green_out)}")
held &= red_code != 0 and green_code == 0
shutil.rmtree(copy, ignore_errors=True)
print("held:", held)
raise SystemExit(0 if held else 1)
