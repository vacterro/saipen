"""T-1382 VERIFY: measure the 13 previously-unmeasured core-unit modules.

The prior session's blocker was transport, not the modules: a live-host child
held the pipe and hung the invoking shell even under a timeout. Here every
module's stdout/stderr goes to its own FILE (no pipe to hold), the parent is
waited on with a per-module bound, and a kill on timeout cannot strand the
driver. Output lands beside the ticket's evidence; summary.json is rewritten
after each module so a killed driver still leaves partial results.
"""

import json
import os
import subprocess
import sys
import time

ROOT = r"V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN"
OUT = os.path.join(
    ROOT, ".saipen", "evidence", "T-1382-recovery-liveness-20260918", "modules"
)
os.makedirs(OUT, exist_ok=True)

MODS = {
    "test_ledger_gap": 240,
    "test_log_stamp_guard": 240,
    "test_narrative_authority": 240,
    "test_opencode_bound_launch_smoke": 600,
    "test_opencode_live_session": 600,
    "test_project_root_session_binding": 300,
    "test_reconcile_legacy_output_field": 240,
    "test_recovery_noop_targets": 240,
    "test_settled_projection": 240,
    "test_t1304_r004_transition": 300,
    "test_unknown_tool_fail_closed": 240,
    "test_validator_layout_parity": 300,
    "test_xpatch": 420,
}

env = dict(os.environ)
env["PYTHONUTF8"] = "1"

results = {}
for mod, tmo in MODS.items():
    out_path = os.path.join(OUT, mod + ".txt")
    t0 = time.time()
    rc = None
    verdict = "?"
    with open(out_path, "wb") as fh:
        proc = subprocess.Popen(
            [sys.executable, "-m", "unittest", "tools." + mod, "-v"],
            cwd=ROOT,
            stdout=fh,
            stderr=subprocess.STDOUT,
            env=env,
        )
        try:
            rc = proc.wait(timeout=tmo)
            verdict = "PASS" if rc == 0 else "FAIL"
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=30)
            except Exception:
                pass
            verdict = "TIMEOUT"
    results[mod] = {
        "verdict": verdict,
        "rc": rc,
        "seconds": round(time.time() - t0, 1),
        "bound_s": tmo,
    }
    with open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8") as sf:
        json.dump(results, sf, indent=1, sort_keys=True)

print(json.dumps(results, indent=1, sort_keys=True))
