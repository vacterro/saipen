"""SRC-026:R009 measured on a disposable copy of the real project (10829 receipts).

Usage: r009_measure_after.py <copy> <live-repo>

Copies the two patched engine modules into the copy, then times real commands
through the copy's own CLI and compares the memo-backed snapshot with a strict
one. The repository is read, never written.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

copy = Path(sys.argv[1]).resolve()
live = Path(sys.argv[2]).resolve()
assert "scratchpad" in copy.as_posix() and copy != live
for name in ("journal.py", "settled_projection.py", "fast_check.py"):
    shutil.copyfile(live / "tools" / "saipen_engine" / name, copy / "tools" / "saipen_engine" / name)

env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
env["PWD"] = str(copy)
env["FORBID_SAIPEN_PROJECT_WRITE"] = str(live)
env["PYTHONUTF8"] = "1"


def cli(*words: str) -> tuple[float, dict]:
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
        answer = {"ok": False, "raw": proc.stdout.decode("utf-8", errors="replace")[-300:]}
    return elapsed, answer


settled = copy / ".saipen" / "recovery" / "settled"
legacy = settled / ".receipt-index.json"
print("settled receipts:", sum(1 for p in settled.iterdir() if p.is_dir() and not p.name.startswith(".")),
      "| retired index present before:", legacy.is_file())
for label in ("first checkpoint (projection rebuilds once)", "second checkpoint",
              "third checkpoint", "fourth checkpoint"):
    elapsed, answer = cli("checkpoint", "RUN", f"R009 timing probe: {label}")
    print(f"{label:46s} {elapsed:6.2f} s  ok={answer.get('ok')} {answer.get('code')}")
print("retired index present after:", legacy.is_file())
for words in (("status",), ("continue", "--dry-run")):
    elapsed, answer = cli(*words)
    print(f"{' '.join(words):46s} {elapsed:6.2f} s  ok={answer.get('ok')}")

sys.path.insert(0, str(copy / "tools"))
from saipen_engine import journal, settled_projection as SP  # noqa: E402

print("projection state:", SP.state(copy), "| deep valid:", SP.validate_projection_deep(copy))
started = time.perf_counter()
memo = SP.record_memo(copy)
print(f"record_memo: {len(memo)} entries in {time.perf_counter() - started:.2f} s")
started = time.perf_counter()
warm = journal.semantic_receipt_snapshot(copy)
warm_time = time.perf_counter() - started
real_memo = SP.record_memo
SP.record_memo = lambda root: {}
journal_memo = journal.semantic_receipt_snapshot
started = time.perf_counter()
strict = journal.semantic_receipt_snapshot(copy)
strict_time = time.perf_counter() - started
SP.record_memo = real_memo
print(f"snapshot with memo {warm_time:.2f} s ({len(warm.records)} records, {len(warm.errors)} errors); "
      f"strict {strict_time:.2f} s ({len(strict.records)} records, {len(strict.errors)} errors)")
print("records identical:", list(warm.records) == list(strict.records),
      "| digest identical:", warm.digest == strict.digest)
started = time.perf_counter()
digest = journal.semantic_receipt_digest(copy)
print(f"semantic_receipt_digest {time.perf_counter() - started:.2f} s, equals snapshot digest: {digest == warm.digest}")
for operation in ("checkpoint", "seal_log", "producer_integration", "no-such-operation"):
    started = time.perf_counter()
    found = journal.semantic_receipts_for_operation(copy, operation)
    bounded = time.perf_counter() - started
    expected = [r for r in strict.records if r.get("operation") == operation]
    print(f"semantic_receipts_for_operation({operation!r}): {len(found)} in {bounded:.3f} s, "
          f"equals the strict filter: {found == expected}")
