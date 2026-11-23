"""T-2108 REVIEW re-measurement: installed engine agent-status latency.

Times N samples of the installed (ProgramData machine runtime) engine running
`status --view agent --json` against a project root. Read-only; prints one
JSON object with per-sample wall milliseconds. Complements BASELINE.json
(cli_wall_ms.status_agent_installed_p50_ms).

Usage: python measure_installed_agent_status.py [samples] [project_root]  # cwd default
"""

import json
import subprocess
import sys
import time

LAUNCHER = r"C:\ProgramData\SAI\SAIPEN\bin\saipen.cmd"


def main() -> int:
    samples = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    cmd = ["cmd", "/c", LAUNCHER, "status", "--json"]
    rows = []
    for i in range(samples):
        t0 = time.perf_counter()
        p = subprocess.run(cmd, capture_output=True)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        try:
            payload = json.loads(p.stdout.decode("utf-8", "replace"))
            ok = payload.get("ok")
            phase = payload.get("phase")
        except Exception:
            ok, phase = None, None
        rows.append(
            {
                "sample": i + 1,
                "wall_ms": round(dt_ms, 1),
                "rc": p.returncode,
                "ok": ok,
                "phase": phase,
                "stdout_bytes": len(p.stdout),
                "stderr_bytes": len(p.stderr),
            }
        )
    walls = sorted(r["wall_ms"] for r in rows)
    p50 = walls[len(walls) // 2] if walls else None
    print(json.dumps({"launcher": LAUNCHER, "p50_ms": p50, "samples": rows}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
