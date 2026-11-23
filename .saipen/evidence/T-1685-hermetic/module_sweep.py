"""Run every module of the measured red set directly, with and without a
stand-in operator profile in CLAUDE_CONFIG_DIR, and prove the stand-in stays
empty. Never names a real profile."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[3] / "tools"
MODULES = [
    "test_t1685_profile_carrier", "test_hermetic_env", "test_t1442_family_env",
    "test_t1649_refusal_step", "test_t1635_claude_profiles", "test_host_authority_broker",
    "test_claude_stop_hook", "test_adapter_parity", "test_protocol_admission",
    "test_t1624_host_integration", "test_t1678_path_launcher",
]
results = {}
for label in ("unset", "stand-in"):
    with tempfile.TemporaryDirectory(prefix="saipen-t1685-sweep-") as tmp:
        operator = Path(tmp) / ".claude-operator"
        operator.mkdir()
        env = {k: v for k, v in os.environ.items()
               if k not in ("CLAUDE_CONFIG_DIR", "SAIPEN_CAPABILITY")}
        if label == "stand-in":
            env["CLAUDE_CONFIG_DIR"] = str(operator)
        proc = subprocess.run(
            [sys.executable, "-B", "-m", "unittest", *MODULES], cwd=TOOLS, env=env,
            stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=3000,
        )
        tail = [line for line in proc.stderr.splitlines() if line.startswith(("Ran ", "OK", "FAILED"))]
        written = sorted(str(p.relative_to(operator)) for p in operator.rglob("*"))
        results[label] = {"rc": proc.returncode, "summary": tail, "stand_in_written": written[:20]}
        (Path(__file__).parent / f"sweep-{label}.out.txt").write_text(proc.stderr, encoding="utf-8")
print(json.dumps(results, indent=1))
ok = all(r["rc"] == 0 and not r["stand_in_written"] for r in results.values())
print("SWEEP", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
