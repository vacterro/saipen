"""SRC-026:R009 on this project's own bytes: before and after, wall clock.

Usage: r009_proof.py <live-repo> <scratch-dir> <old-engine-copy> <new-copy-name>

`old-engine-copy` is an existing disposable copy that still carries the engine
as it was before T-1304 (made earlier the same day). A fresh copy of the
repository with its project memory is made for the engine as it is now. Both
run their OWN tools with themselves as working directory and project root;
the repository is read and never written.
"""
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

live = Path(sys.argv[1]).resolve()
scratch = Path(sys.argv[2]).resolve()
old = scratch / sys.argv[3]
new = scratch / sys.argv[4]
assert live not in (old, new) and live not in new.parents and old.is_dir(), (old, new)


def _writable(function, path, _info):
    os.chmod(path, stat.S_IWRITE)
    function(path)


if new.exists():
    shutil.rmtree(new, onerror=_writable)
skip_tree = {".git", ".saipen", "__pycache__", ".pytest_cache", ".ruff_cache",
             ".workbuddy-ai", ".codenomad", ".freebuff", ".claude"}
shutil.copytree(
    live, new, ignore=lambda d, names: [n for n in names if n in skip_tree or n.endswith(".pyc")]
)
skip_memory = {"cache", "tmp", "saitranslate", "exchange", "locks"}
shutil.copytree(
    live / ".saipen", new / ".saipen",
    ignore=lambda d, names: [
        n for n in names
        if (Path(d) == live / ".saipen" and n in skip_memory) or n == ".git"
        or n.endswith((".tmp", ".lock"))
    ],
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:16]


def cli(copy: Path, *words: str) -> tuple[float, dict]:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
    env["PWD"] = str(copy)
    env["FORBID_SAIPEN_PROJECT_WRITE"] = str(live)
    env["PYTHONUTF8"] = "1"
    started = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, "-B", str(copy / "tools" / "saipen.py"), "--project-root", str(copy),
         *words, "--json"],
        cwd=str(copy), env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=1800,
        check=False,
    )
    elapsed = time.perf_counter() - started
    try:
        answer = json.loads(proc.stdout.decode("utf-8", errors="replace"))
    except ValueError:
        answer = {"ok": False}
    return elapsed, answer


def receipts(copy: Path) -> int:
    settled = copy / ".saipen" / "recovery" / "settled"
    return sum(1 for p in settled.iterdir() if p.is_dir() and not p.name.startswith("."))


for label, copy in (("BEFORE (engine as it was)", old), ("AFTER (engine as it is)", new)):
    engine = copy / "tools" / "saipen_engine"
    print(f"== {label}: journal.py {digest(engine / 'journal.py')}, "
          f"settled_projection.py {digest(engine / 'settled_projection.py')}, "
          f"settled receipts {receipts(copy)}")
    legacy = copy / ".saipen" / "recovery" / "settled" / ".receipt-index.json"
    print(f"   monolithic index: {legacy.stat().st_size if legacy.is_file() else 'absent'} bytes")
    times = []
    for step in range(1, 6):
        elapsed, answer = cli(copy, "checkpoint", "RUN", f"R009 wall-clock probe {step}")
        times.append(elapsed)
        assert answer.get("ok"), answer
    print("   five checkpoints, seconds:", " ".join(f"{t:.2f}" for t in times),
          f"| median {sorted(times)[2]:.2f}")
    for words in (("status",), ("continue", "--dry-run")):
        elapsed, answer = cli(copy, *words)
        print(f"   {' '.join(words):20s} {elapsed:.2f} s ok={answer.get('ok')}")
    print(f"   monolithic index after: {legacy.stat().st_size if legacy.is_file() else 'absent'}")

sys.path.insert(0, str(new / "tools"))
from saipen_engine import journal, settled_projection as SP  # noqa: E402

print("== the new copy, checked in-process")
print("projection state:", SP.state(new), "| deep validation:", SP.validate_projection_deep(new))
warm = journal.semantic_receipt_snapshot(new)
real = SP.record_memo
SP.record_memo = lambda root: {}
started = time.perf_counter()
strict = journal.semantic_receipt_snapshot(new)
strict_time = time.perf_counter() - started
SP.record_memo = real
started = time.perf_counter()
journal.semantic_receipt_snapshot(new)
warm_time = time.perf_counter() - started
print(f"whole-history snapshot: memo {warm_time:.2f} s, strict {strict_time:.2f} s, "
      f"{len(warm.records)} records; identical records: {list(warm.records) == list(strict.records)}; "
      f"identical digest: {warm.digest == strict.digest}; errors {len(warm.errors)}/{len(strict.errors)}")
operations = sorted({r.get("operation") for r in strict.records})
mismatch = []
slowest = (0.0, "")
for operation in operations:
    started = time.perf_counter()
    found = journal.semantic_receipts_for_operation(new, operation)
    elapsed = time.perf_counter() - started
    slowest = max(slowest, (elapsed, f"{operation} ({len(found)})"))
    if found != [r for r in strict.records if r.get("operation") == operation]:
        mismatch.append(operation)
started = time.perf_counter()
none = journal.semantic_receipts_for_operation(new, "no-such-operation")
zero_time = time.perf_counter() - started
print(f"operation queries: {len(operations)} operations, mismatches {mismatch}, "
      f"slowest {slowest[1]} {slowest[0]:.2f} s, zero-match {zero_time * 1000:.1f} ms -> {none}")
ok = (SP.state(new) == SP.STATE_CURRENT and SP.validate_projection_deep(new)[0]
      and list(warm.records) == list(strict.records) and warm.digest == strict.digest
      and not mismatch and not warm.errors)
print("RESULT:", "bounded settlement and reads agree with the strict answers" if ok else "NOT PROVEN")
sys.exit(0 if ok else 1)
