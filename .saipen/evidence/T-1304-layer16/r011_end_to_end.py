"""SRC-026:R011 end to end: `audit_checks --changed <path>` that selects zero controls.

Usage: r011_end_to_end.py <repo> [changed-path]

Runs tools/audit_checks.py main() in this process with the real argv shape
`--changed <path>`, after replacing its ThreadPoolExecutor with a trap that
records every construction and raises. The run must exit 0, print the SCOPED
banner, and construct no executor. A second run with the trap removed is the
control that the same invocation exits 0 without the instrument.
"""

import io
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
changed = sys.argv[2] if len(sys.argv) > 2 else "tools/saipen_engine/fast_check.py"
sys.path.insert(0, str(repo / "tools"))

import audit_checks as A  # noqa: E402

selected = A.select_cases(A.CASES, frozenset({changed}))
print(f"selection for --changed {changed}: {len(selected)} of {len(A.CASES)} controls")

constructed: list[object] = []


class Trap:
    def __init__(self, *args, **kwargs):
        constructed.append(kwargs.get("max_workers", args[0] if args else None))
        raise AssertionError("ThreadPoolExecutor constructed for an empty selection")


def run(trap: bool) -> tuple[int, str, float]:
    real = A.ThreadPoolExecutor
    if trap:
        A.ThreadPoolExecutor = Trap
    argv = sys.argv
    sys.argv = ["audit_checks.py", "--changed", changed]
    out = io.StringIO()
    started = time.monotonic()
    try:
        with redirect_stdout(out):
            code = A.main()
    finally:
        sys.argv = argv
        A.ThreadPoolExecutor = real
    return code, out.getvalue(), time.monotonic() - started


code, text, took = run(trap=True)
scoped = [line for line in text.splitlines() if line.lstrip().startswith("SCOPED:")]
print(f"instrumented run: exit {code}, {took:.1f} s, executor constructions {len(constructed)}")
for line in scoped:
    print(f"  {line.strip()}")
print("  " + (text.strip().splitlines() or ["<no output>"])[-1])
ok = code == 0 and not constructed and bool(scoped) and not selected
code2, text2, took2 = run(trap=False)
print(f"control run without the trap: exit {code2}, {took2:.1f} s")
print("  " + (text2.strip().splitlines() or ["<no output>"])[-1])
print("R011 END-TO-END:", "PASS" if ok and code2 == 0 else "FAIL")
raise SystemExit(0 if ok and code2 == 0 else 1)
