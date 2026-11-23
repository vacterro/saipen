"""Capture documented read-only validator/recovery diagnostics outside AUDAPACK."""
from __future__ import annotations

import datetime
import hashlib
import json
import subprocess
import sys
from pathlib import Path

CASE = Path(__file__).resolve().parent
LOCATION = json.loads((CASE / "location.json").read_text())
ROOT = Path(LOCATION["root"])
HOME = CASE.parents[2]
CORE = ("STATE.md", "BOARD.md", "LOG.md", "MANIFEST.json")


def hashes():
    return {name: hashlib.sha256((ROOT / ".saipen" / name).read_bytes()).hexdigest() for name in CORE}


commands = [
    ("native-before", [sys.executable, str(HOME / "tools" / "validate.py"), "--project-root", str(ROOT), "--gate", "core", "--no-receipt"]),
    ("recover-preview-before", [str(HOME / "bin" / "saipen.cmd"), "recover", "--project-root", str(ROOT), "--dry-run", "--json"]),
]
before = hashes()
results = []
for label, argv in commands:
    start = datetime.datetime.now(datetime.timezone.utc).isoformat()
    proc = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="backslashreplace", timeout=300)
    output = proc.stdout + proc.stderr
    (CASE / (label + ".txt")).write_text(output, encoding="utf-8")
    results.append({"label": label, "argv": argv, "started_utc": start, "exit_code": proc.returncode,
                    "output_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(), "core_after": hashes()})
    print(json.dumps({"label": label, "exit_code": proc.returncode, "output_tail": output[-9000:]}, ensure_ascii=False))
after = hashes()
(CASE / "readonly-checks.json").write_text(json.dumps({"before": before, "after": after, "core_unchanged": before == after, "commands": results}, indent=2) + "\n", encoding="utf-8")
if before != after:
    raise SystemExit("Unexpected core drift during read-only diagnostics")
