"""Which widget test file hangs?

The full widget suite finishes in ~225 s when it finishes at all, and the runs
that do not finish leave every worker idle. A per-file probe bounds the blast
radius: each file gets its own node process and its own timeout, so one leaked
handle is named instead of silently stalling the whole gate.
"""

import pathlib
import subprocess
import time

FILES = sorted(pathlib.Path("tests/widget").glob("*.test.js"))
LIMIT = 90

slow, hung, bad = [], [], []
for path in FILES:
    started = time.time()
    try:
        run = subprocess.run(
            ["node", "--test", "--test-force-exit", "--test-reporter=spec", str(path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=LIMIT)
    except subprocess.TimeoutExpired:
        hung.append(path.name)
        print(f"HANG  {path.name}", flush=True)
        continue
    took = time.time() - started
    if run.returncode != 0:
        bad.append((path.name, run.returncode))
        print(f"FAIL  {path.name} rc={run.returncode}", flush=True)
    elif took > 30:
        slow.append((path.name, round(took)))
        print(f"SLOW  {path.name} {took:.0f}s", flush=True)
    else:
        print(f"ok    {path.name} {took:.0f}s", flush=True)

print(f"\nfiles={len(FILES)} hung={hung} failed={bad} slow={slow}")