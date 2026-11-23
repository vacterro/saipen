"""Re-run exactly the modules the 110-failure record named, one subprocess each.

The same invocation shape the focused gate uses
(``python -B -m unittest discover -s tools -p <module>.py -v``), so a module that
is green here is green for the harness that reported it red, not for a weaker
proxy. Output: one JSON object on stdout with per-module status, count and the
failing test ids, plus the resolved state of every originally reported id.

    python -B .saipen/evidence/T-1882-regression-baseline/rerun_red_modules.py
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RECORD = ROOT / ".saipen/evidence/core-unit/9b10e579a60f9c79-20261024T100757701402Z.json"
PER_MODULE_TIMEOUT_S = 280

RAN_RE = re.compile(r"^Ran (\d+) tests? in ", re.M)
FAILED_RE = re.compile(r"^(?:FAILED|OK)\b.*$", re.M)
FAIL_LINE_RE = re.compile(r"^(?:FAIL|ERROR): (\S+)", re.M)


def module_of(test_id: str) -> str:
    return test_id.split(".", 1)[0]


def main() -> int:
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    red = list(record.get("red") or [])
    modules = sorted({module_of(t) for t in red})
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    results = []
    started = time.monotonic()
    for name in modules:
        begin = time.monotonic()
        command = [sys.executable, "-B", "-m", "unittest", "discover",
                   "-s", "tools", "-p", f"{name}.py", "-v"]
        try:
            proc = subprocess.run(command, cwd=str(ROOT), capture_output=True,
                                  text=True, encoding="utf-8", errors="replace",
                                  env=env, timeout=PER_MODULE_TIMEOUT_S)
            out = (proc.stdout or "") + (proc.stderr or "")
            status = "PASS" if proc.returncode == 0 else "FAIL"
            exit_code = proc.returncode
        except subprocess.TimeoutExpired as exc:
            out = (exc.stdout or "") + (exc.stderr or "")
            if isinstance(out, bytes):
                out = out.decode("utf-8", "replace")
            status, exit_code = "TIMEOUT", None
        ran = RAN_RE.search(out)
        results.append({
            "module": name,
            "status": status,
            "exit_code": exit_code,
            "ran": int(ran.group(1)) if ran else None,
            "failures": sorted(set(FAIL_LINE_RE.findall(out))),
            "tail": [ln for ln in FAILED_RE.findall(out)][-1:] or [None],
            "duration_s": round(time.monotonic() - begin, 3),
            "reported_red": sum(1 for t in red if module_of(t) == name),
        })
        print(f"{status:7s} {results[-1]['ran']:>4} {name} "
              f"({results[-1]['reported_red']} reported)", file=sys.stderr, flush=True)

    green = {r["module"] for r in results if r["status"] == "PASS"}
    unresolved = []
    for test_id in red:
        name = module_of(test_id)
        row = next(r for r in results if r["module"] == name)
        if row["status"] == "PASS":
            disposition = "NOW_PASS"
        elif test_id in row["failures"]:
            disposition = "STILL_FAIL"
        else:
            disposition = "MODULE_RED_TEST_NOT_REPORTED"
        unresolved.append({"test_id": test_id, "module": name,
                           "module_status": row["status"], "disposition": disposition})
    payload = {
        "schema": 1,
        "source_record": str(RECORD.relative_to(ROOT)),
        "invocation": "python -B -m unittest discover -s tools -p <module>.py -v",
        "modules": results,
        "green_modules": sorted(green),
        "reported_red_total": len(red),
        "now_pass": sum(1 for u in unresolved if u["disposition"] == "NOW_PASS"),
        "still_fail": [u for u in unresolved if u["disposition"] != "NOW_PASS"],
        "wall_s": round(time.monotonic() - started, 2),
    }
    print(json.dumps(payload, indent=1, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
