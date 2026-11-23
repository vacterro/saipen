"""The FAIL and PASS halves of the T-1672 regression pair, one verifier.

Usage: regression_pair.py <repo> <copy>

VERIFY-ORACLE-01: the SAME unchanged verifier must be red against the pre-fix
subject and green against the post-fix one. The verifier is
tools/test_t1671_lifecycle_authority.py with its command; its bytes are copied
verbatim. The pre-fix subject is a disposable copy of the tree with the repair
UNWIRED and the law restored: the loader gate, the status surface, the
validator finding, the reconcile repairs, and the two sentences that licensed
the hand-written lifecycle. The detector module stays in the copy because the
verifier imports it; nothing calls it there.

Prints the two digests the REGRESSION-EVIDENCE records carry.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
copy = Path(sys.argv[2]).resolve()
assert repo != copy and repo not in copy.parents and not copy.exists(), copy
sys.path.insert(0, str(repo / "tools"))

from saipen_engine import oracle  # noqa: E402

ROOT_ONLY = {".git", ".saipen", ".workbuddy-ai", ".codenomad", ".freebuff", ".claude",
             "future_gate", "audit", "locales", "guides"}
ANYWHERE = {"__pycache__", ".pytest_cache", ".ruff_cache"}
COMMAND = "python -B -m unittest test_t1671_lifecycle_authority"
VERIFIER = ("tools/test_t1671_lifecycle_authority.py",)
SUBJECT = (
    "tools/saipen_engine/operations.py",
    "tools/saipen_engine/reconcile.py",
    "tools/saipen_engine/lifecycle_authority.py",
    "tools/saipen.py",
    "tools/validate.py",
    "saipen/OPS.md",
    "saipen/ACTIVATION_BLOCK.md",
)

UNWIRE = [
    ("tools/saipen_engine/operations.py",
     'if lifecycle["status"] == _lifecycle_authority.UNAUTHORIZED:\n', "if False:\n"),
    ("tools/saipen.py",
     'if _lifecycle["status"] == _lifecycle_authority.UNAUTHORIZED:\n        _emit(\n',
     "if False:\n        _emit(\n"),
    ("tools/validate.py",
     'if _lifecycle["status"] == _lifecycle_authority.UNAUTHORIZED:\n            fail(\n',
     "if False:\n            fail(\n"),
    ("tools/saipen_engine/reconcile.py",
     '    if not verdict or verdict.get("status") != _la.UNAUTHORIZED:\n        return plan\n',
     "    if True:\n        return plan\n"),
    ("saipen/OPS.md",
     "Covered maintenance MUST use SAIOPS; a structural edit by hand is never a\n"
     "fallback, whatever reason it records (§ 8).\n",
     "In `mode: full` with Python available, covered maintenance MUST use SAIOPS;\n"
     "manual structural editing is FALLBACK / RECOVERY ONLY and must record why the\n"
     "mechanical path was unavailable.\n"),
    ("saipen/OPS.md",
     "None (SRC-192: an executor without `saipen` typed STATE, BOARD and LOG by\n"
     "hand and readers accepted them). No `saipen` -> BOOT's launcher, then the\n"
     "machine runtime, else stop: `SAIPEN_HOST_RUNTIME_UNAVAILABLE` (RUNTIME.md).\n"
     "State above the newest journaled event is UNAUTHORIZED_LIFECYCLE_WRITE:\n"
     "operations refuse it, `saipen recover` reopens it. Files stay readable\n"
     "without an engine.\n",
     "Python is the preferred mechanical path under `mode: full`. If Python is\n"
     "genuinely unavailable, use the documented manual protocol as compatibility\n"
     "fallback, state that mechanical enforcement was unavailable, and run available\n"
     "validation afterwards. A repository must remain readable without an executable\n"
     "environment: canonical files are the cold truth, never a cache or engine state.\n"),
    ("saipen/ACTIVATION_BLOCK.md",
     "Memory: .saipen/ at project root - read .saipen/STATE.md before work; STATE,\n"
     "BOARD, LOG change only via `saipen`. No route to it: stop, report\n"
     "SAIPEN_HOST_RUNTIME_UNAVAILABLE; no hand edit, DONE, commit or push.\n",
     "Memory: .saipen/ at project root - read .saipen/STATE.md before work;\n"
     "checkpoint BOARD + STATE after every ticket, LOG line after every run.\n"),
]


def ignore(directory: str, names: list[str]) -> list[str]:
    at_root = Path(directory).resolve() == repo
    return [n for n in names
            if n in ANYWHERE or n.endswith(".pyc") or (at_root and n in ROOT_ONLY)]


def run(tree: Path) -> tuple[int, str]:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
    env["PYTHONUTF8"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", "test_t1671_lifecycle_authority"],
        cwd=str(tree / "tools"), env=env, stdin=subprocess.DEVNULL, capture_output=True,
        timeout=1800, check=False,
    )
    return proc.returncode, (proc.stdout + proc.stderr).decode("utf-8", errors="replace")


def summary(out: str) -> str:
    ran = re.search(r"Ran \d+ tests", out)
    verdict = re.search(r"^(OK.*|FAILED \(.*\))$", out, flags=re.MULTILINE)
    reds = sorted(set(re.findall(r"^(?:FAIL|ERROR): (test_\w+)", out, flags=re.MULTILINE)))
    return (f"{ran.group(0) if ran else '?'}, {verdict.group(1) if verdict else '?'}"
            + (f"; red: {', '.join(reds)}" if reds else ""))


shutil.copytree(repo, copy, ignore=ignore)
for rel, old, new in UNWIRE:
    target = copy / rel
    raw = target.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8")
    old, new = old.replace("\n", newline), new.replace("\n", newline)
    assert text.count(old) == 1, (rel, text.count(old), old[:60])
    target.write_bytes(text.replace(old, new).encode("utf-8"))

assert (copy / VERIFIER[0]).read_bytes() == (repo / VERIFIER[0]).read_bytes()
verifier = oracle.verifier_identity(COMMAND, VERIFIER, repo)
assert verifier == oracle.verifier_identity(COMMAND, VERIFIER, copy)
red_code, red_out = run(copy)
green_code, green_out = run(repo)
print(f"command: {COMMAND} (cwd tools/)")
print(f"verifier:{verifier[:16]}  ({VERIFIER[0]}, byte-identical in both trees)")
print(f"FAIL subject:{oracle.oracle_digest(copy, SUBJECT)[:16]}  exit {red_code}  {summary(red_out)}")
print(f"PASS subject:{oracle.oracle_digest(repo, SUBJECT)[:16]}  exit {green_code}  {summary(green_out)}")
print("subject paths:", ", ".join(SUBJECT))
raise SystemExit(0 if red_code != 0 and green_code == 0 else 1)
