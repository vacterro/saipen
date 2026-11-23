"""T-1648 real-contention A/B: one writer, N readers, no mocks.

Usage: python stress.py <tree root holding tools/saipen_engine> [writes] [readers]

The writer calls paths.safe_atomic_write_bytes in a loop while reader
processes open and read the same file the way a hook or a status poll does
(CPython's open: no delete-sharing). Prints one JSON line of counts.
"""
import json
import multiprocessing as mp
import os
import random
import shutil
import sys
import tempfile
import time
from pathlib import Path


def reader(target: str, stop, counts, hold: float, idle: float, seed: int) -> None:
    rng = random.Random(seed)
    reads = denied = other = 0
    while not stop.is_set():
        try:
            with open(target, "rb") as handle:
                handle.read()
                time.sleep(hold)  # a parse the size of a real one
            reads += 1
        except PermissionError:
            denied += 1
        except OSError:
            other += 1
        time.sleep(idle * rng.uniform(0.5, 1.5))
    counts.put({"reads": reads, "denied": denied, "other": other})


def main() -> int:
    tree = Path(sys.argv[1]).resolve()
    writes = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    readers = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    hold = float(sys.argv[4]) if len(sys.argv) > 4 else 0.002
    idle = float(sys.argv[5]) if len(sys.argv) > 5 else 0.02
    sys.path.insert(0, str(tree / "tools"))
    from saipen_engine import paths

    root = Path(tempfile.mkdtemp(prefix="saipen-t1648-stress-"))
    target = root / "STATE.md"
    target.write_bytes(b"seed\n" * 2000)
    stop = mp.Event()
    counts = mp.Queue()
    procs = [
        mp.Process(target=reader, args=(str(target), stop, counts, hold, idle, 1000 + n))
        for n in range(readers)
    ]
    for proc in procs:
        proc.start()
    time.sleep(0.5)
    failed = {}
    worst = 0.0
    started = time.perf_counter()
    for index in range(writes):
        begin = time.perf_counter()
        try:
            paths.safe_atomic_write_bytes(
                target, (f"write {index}\n" * 2000).encode(), kind="stress", ownership_root=root
            )
        except Exception as exc:  # the count IS the measurement
            key = f"{type(exc).__name__}:{getattr(exc, 'winerror', None)}"
            failed[key] = failed.get(key, 0) + 1
        worst = max(worst, time.perf_counter() - begin)
    elapsed = time.perf_counter() - started
    stop.set()
    reads = [counts.get(timeout=10) for _ in procs]
    for proc in procs:
        proc.join(10)
    leftovers = [p.name for p in root.iterdir() if p.name.endswith(".tmp")]
    shutil.rmtree(root, True)
    print(
        json.dumps(
            {
                "tree": tree.name,
                "writes": writes,
                "write_failures": failed,
                "failed_total": sum(failed.values()),
                "worst_write_s": round(worst, 3),
                "elapsed_s": round(elapsed, 2),
                "readers": readers,
                "hold_s": hold,
                "idle_s": idle,
                "reads": sum(r["reads"] for r in reads),
                "reader_denied": sum(r["denied"] for r in reads),
                "reader_other": sum(r["other"] for r in reads),
                "tmp_leftovers": len(leftovers),
                "platform": os.name,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
