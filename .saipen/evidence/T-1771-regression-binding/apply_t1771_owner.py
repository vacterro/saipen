"""Apply T-1771's ownership correction to the live tree, preserving line endings.

    python apply_t1771_owner.py <project-root> <corrected-copy-root>

The live pre-image of each file must equal the first cut preserved under
first-cut/ (byte for byte, after line-ending normalization); the corrected
text comes from the copy the mutation controls ran on and is written back in
the live file's own line-ending convention.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILES = {
    "tools/saipen_engine/regression_execution.py": "regression_execution.py",
    "tools/test_t1771_measure_then_finish.py": "test_t1771_measure_then_finish.py",
}


def lf(raw: bytes) -> str:
    return raw.decode("utf-8").replace("\r\n", "\n")


def main(argv: list[str]) -> int:
    root, copy = (Path(item).resolve() for item in argv[:2])
    for relative, preserved in FILES.items():
        live = root / relative
        raw = live.read_bytes()
        if lf(raw) != lf((HERE / "first-cut" / preserved).read_bytes()):
            raise SystemExit(f"{relative}: live pre-image is not the preserved first cut")
        corrected = lf((copy / relative).read_bytes())
        if corrected == lf(raw):
            raise SystemExit(f"{relative}: the copy carries no correction")
        crlf = b"\r\n" in raw
        live.write_bytes((corrected.replace("\n", "\r\n") if crlf else corrected).encode("utf-8"))
        print(f"{relative}: applied ({'CRLF' if crlf else 'LF'})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
