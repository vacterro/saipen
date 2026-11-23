"""T-1682: the T-1619 E2E fixture against every live seat it can be copied in.

Usage: t1682_pair.py <repo> <copy>

The verifier is this driver: it copies the tree, writes the copy's own
`.saipen/STATE.md` as the live checkout's STATE re-seated at each phase and
`transition_from` a real run can hold, and runs test_t1619_iteration_boundary
there. The subject is tools/test_t1619_iteration_boundary.py: prefix/ holds
its pre-fix bytes.
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

HERE = Path(__file__).resolve()
SUBJECT = ("tools/test_t1619_iteration_boundary.py",)
#: (phase, transition_from) pairs a live checkout really sits at.
SEATS = (("SCOUT", "DONE"), ("BUILD", "SCOUT"), ("VERIFY", "BUILD"), ("REVIEW", "VERIFY"),
         ("SHIP", "REVIEW"), ("DONE", "SHIP"))
COMMAND = "python -B -m unittest test_t1619_iteration_boundary (per seat)"


def ignore(_directory, names):
    return [n for n in names if n in {"__pycache__", ".ruff_cache"} or n.endswith(".pyc")]


for part in ("tools", "tests", "saipen", "extensions", "bin", "bootstrap"):
    shutil.copytree(repo / part, copy / part, ignore=ignore)
shutil.copy2(repo / "VERSION", copy / "VERSION")
(copy / ".saipen").mkdir()
LIVE = (repo / ".saipen" / "STATE.md").read_text(encoding="utf-8-sig")


def seat(phase: str, source: str) -> None:
    text = re.sub(r"(?m)^phase:.*$", f"phase: {phase}", LIVE)
    text = re.sub(r"(?m)^transition_from:.*$", f"transition_from: {source}", text)
    (copy / ".saipen" / "STATE.md").write_text(text, encoding="utf-8")


def run_all(tree_subject: Path) -> list[tuple[str, int, list]]:
    shutil.copy2(tree_subject, copy / SUBJECT[0])
    results = []
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
    env["PYTHONUTF8"] = "1"
    for phase, source in SEATS:
        seat(phase, source)
        proc = subprocess.run(
            [sys.executable, "-B", "-m", "unittest", "test_t1619_iteration_boundary"],
            cwd=str(copy / "tools"), env=env, stdin=subprocess.DEVNULL, capture_output=True,
            timeout=900, check=False,
        )
        out = (proc.stdout + proc.stderr).decode("utf-8", errors="replace")
        red = sorted(set(re.findall(r"^(?:FAIL|ERROR): (test_\w+)", out, flags=re.MULTILINE)))
        results.append((f"{phase} from {source}", proc.returncode, red))
    return results


verifier = oracle.verifier_identity(COMMAND, (HERE.relative_to(repo).as_posix(),), repo)
before = run_all(HERE.parent / "prefix" / SUBJECT[0])
after = run_all(repo / SUBJECT[0])
print(f"command: {COMMAND}")
print(f"verifier:{verifier[:16]}  (this driver)")
for label, rows in (("FAIL", before), ("PASS", after)):
    tree = HERE.parent / "prefix" if label == "FAIL" else repo
    print(f"{label} subject:{oracle.oracle_digest(tree, SUBJECT)[:16]}")
    for seat_label, code, red in rows:
        print(f"  {seat_label:<18} exit {code}  red {len(red)}: {', '.join(red)}")
held = any(code for _s, code, _r in before) and not any(code for _s, code, _r in after)
shutil.rmtree(copy, ignore_errors=True)
print("held:", held)
raise SystemExit(0 if held else 1)
