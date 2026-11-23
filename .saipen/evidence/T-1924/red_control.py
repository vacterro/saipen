"""Red control for T-1924: make the measured record lie, watch each test fail.

Each case mutates exactly ONE field of `.saipen/evidence/T-1924/reconnect-control.json`
to a value that means something different from what was measured, reruns the
acceptance module, and restores the byte-identical original before the next
case. A green run for any case would mean that test does not actually depend
on its measurement.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RECORD = ROOT / ".saipen" / "evidence" / "T-1924" / "reconnect-control.json"

CASES = [
    ("red_arm", "defect_reproduced", False, "claim the red arm did not reproduce"),
    ("green_arm", "defect_reproduced", True, "claim the green arm still reproduced"),
    ("green_arm", "after_personal_appears", "bundled", "claim green chose bundled"),
    (None, "cache_isolates_cause", False, "claim the control isolates nothing"),
    (None, "cache_key_carries_personal_mode", True, "claim the key carries the mode"),
    (None, "live_configuration_written", True, "claim the control wrote the live profile"),
    (None, "fixture_audio_claimed_as_original", True, "claim fixtures are originals"),
]


def run_module() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "tools.test_t1924_src330_acceptance"],
        cwd=ROOT, capture_output=True, text=True,
    )
    tail = [line for line in proc.stderr.splitlines()
            if line.startswith(("FAILED", "OK", "Ran "))]
    return proc.returncode, " / ".join(tail)


def main() -> int:
    original = RECORD.read_bytes()
    backup = Path(tempfile.mkdtemp(prefix="t1924-red-")) / "record.json"
    shutil.copyfile(RECORD, backup)
    green_cases = []
    try:
        for parent, field, liar, description in CASES:
            data = json.loads(original.decode("utf-8"))
            target = data[parent] if parent else data
            old = target[field]
            target[field] = liar
            RECORD.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            code, tail = run_module()
            verdict = "RED (test caught the lie)" if code != 0 else "GREEN (NOT CAUGHT)"
            if code == 0:
                green_cases.append(f"{parent or ''}{field}")
            print(f"{field}: {old!r} -> {liar!r} | {description}")
            print(f"  {tail} | {verdict}")
            RECORD.write_bytes(original)
        RECORD.write_bytes(original)
        code, tail = run_module()
        print(f"\nrestored record, green rerun: {tail}")
        if code != 0:
            print("FAIL: the restored record does not pass")
            return 1
        if green_cases:
            print(f"FAIL: these mutations were not caught: {green_cases}")
            return 1
        print(f"PASS: all {len(CASES)} mutations were caught; record restored byte-identically")
        return 0
    finally:
        RECORD.write_bytes(original)


if __name__ == "__main__":
    raise SystemExit(main())
