#!/usr/bin/env python3
"""Race repro: launch audit_parity once, then run unittest discover in foreground.
Repeat and capture failing test cases. Bounded trials."""
from __future__ import annotations
import os, subprocess, sys, threading, time, queue, json
from pathlib import Path

HOME = Path(__file__).resolve().parent.parent.parent
TOOLS = HOME / "tools"
PARITY = TOOLS / "audit_parity.py"
TRIALS = int(os.environ.get("TRIALS", "5"))

def run_one(trial):
    py = sys.executable
    # Clear caches to force the parity runner past its hit-and-exit
    for nm in ("audit_parity_cache.json", "audit_checks_cache.json"):
        p = HOME / ".saipen" / "cache" / nm
        if p.exists():
            try: p.unlink()
            except OSError: pass
    # Start parity in background
    parity = subprocess.Popen([py, str(PARITY)],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, cwd=str(HOME))
    # Give it a beat to begin its cache write
    time.sleep(0.4)
    # Run unittest discover; capture full output (cwd=HOME so -s tools resolves)
    print(f"[trial {trial}] running discover cwd={HOME} exists={HOME.exists()} tools={(HOME / 'tools').exists()}", flush=True)
    ut = subprocess.run([py, "-m", "unittest", "discover", "-s", "tools", "-v"],
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, cwd=HOME, timeout=900)
    out = ut.stdout
    rc = ut.returncode
    Path(f"repro_t1258_trial{trial}.log").write_text(out, encoding="utf-8")
    # drain parity
    try:
        p_stdout, _ = parity.communicate(timeout=60)
    except subprocess.TimeoutExpired:
        parity.kill()
        p_stdout, _ = parity.communicate()
    fails = [ln for ln in out.splitlines() if ln.startswith("FAIL:")]
    errs = [ln for ln in out.splitlines() if ln.startswith("ERROR:")]
    summary = None
    for ln in out.splitlines():
        if "Ran " in ln and " in " in ln:
            summary = ln.strip()
    ok = (rc == 0)
    return {
        "trial": trial, "rc": rc, "ok": ok, "fails": fails,
        "errors": errs, "summary": summary,
        "parity_rc": parity.returncode,
    }

def main():
    rows = []
    for t in range(1, TRIALS + 1):
        r = run_one(t)
        rows.append(r)
        print(f"trial {t}: rc={r['rc']} parity_rc={r['parity_rc']} fails={len(r['fails'])} errors={len(r['errors'])} summary={r['summary']}")
        for f in r["fails"]:
            print(f"  {f}")
        for e in r["errors"]:
            print(f"  {e}")
    red = [r for r in rows if r["fails"] or r["errors"]]
    print()
    print(f"TRIALS={TRIALS}  red={len(red)}")
    for r in red:
        print(f"  trial {r['trial']}: {r['fails']} {r['errors']}")
    return 0 if not red else 1

if __name__ == "__main__":
    sys.exit(main())