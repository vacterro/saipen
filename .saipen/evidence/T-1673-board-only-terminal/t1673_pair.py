"""T-1673: the regression pair on one verifier, plus a red control per half.

Usage: t1673_pair.py <repo> <copy>

The copy is this tree with the T-1673 engine edits taken back out: every
(old, new) anchor patch_t1673.py applied to an engine file is reversed, and
each reversal asserts its anchor occurs exactly once. The verifier
(tools/test_t1673_board_only_terminal.py) is byte-identical in both runs.
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

HERE = Path(__file__).resolve().parent
LIFECYCLE = "tools/saipen_engine/lifecycle_authority.py"
PLAN = "tools/saipen_engine/plan.py"
RECONCILE = "tools/saipen_engine/reconcile.py"
NAMESPACE = "tools/saipen_engine/runtime_namespace.py"
SUBJECT = (LIFECYCLE, PLAN, RECONCILE, NAMESPACE)
VERIFIER = ("tools/test_t1673_board_only_terminal.py",)
TESTS = ["test_t1673_board_only_terminal"]
COMMAND = "python -B -m unittest " + " ".join(TESTS)

# Collect the edits patch_t1673.py declares without applying any of them.
EDITS: dict[str, list[tuple[str, str]]] = {}
source = (HERE / "patch_t1673.py").read_text(encoding="utf-8")
source = source.replace("def patch(", "def _declared_patch(", 1)
namespace = {"__name__": "t1673_edits", "patch": lambda rel, edits: EDITS.setdefault(rel, []).extend(edits)}
saved_argv = sys.argv
sys.argv = ["patch_t1673.py", str(copy)]
exec(compile(source, "patch_t1673.py", "exec"), namespace)
sys.argv = saved_argv
assert set(SUBJECT) <= set(EDITS), sorted(EDITS)


def ignore(_directory, names):
    return [n for n in names if n in {"__pycache__", ".ruff_cache"} or n.endswith(".pyc")]


for part in ("tools", "tests", "saipen", "extensions", "bin", "bootstrap"):
    shutil.copytree(repo / part, copy / part, ignore=ignore)
shutil.copy2(repo / "VERSION", copy / "VERSION")


def unpatch(tree: Path, rel: str) -> None:
    path = tree / rel
    raw = path.read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8").replace("\r\n", "\n")
    for old, new in reversed(EDITS[rel]):
        assert text.count(new) == 1, (rel, text.count(new), new[:80])
        text = text.replace(new, old)
    path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))


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
for label, rel in (("only lifecycle_authority pre-fix", LIFECYCLE), ("only plan pre-fix", PLAN)):
    unpatch(copy, rel)
    code, out = run(copy)
    print(f"{label}: exit {code}, red {reds(out)}")
    held &= code != 0
    shutil.copy2(repo / rel, copy / rel)
for rel in SUBJECT:
    unpatch(copy, rel)
red_code, red_out = run(copy)
green_code, green_out = run(repo)
print(f"command: {COMMAND} (cwd tools/)")
print(f"verifier:{verifier[:16]}  ({VERIFIER[0]}, byte-identical in both trees)")
print(f"FAIL subject:{oracle.oracle_digest(copy, SUBJECT)[:16]}  exit {red_code}  red: {', '.join(reds(red_out))}")
print(f"PASS subject:{oracle.oracle_digest(repo, SUBJECT)[:16]}  exit {green_code}  {ran(green_out)}")
held &= red_code != 0 and green_code == 0
shutil.rmtree(copy, ignore_errors=True)
print("held:", held)
raise SystemExit(0 if held else 1)
