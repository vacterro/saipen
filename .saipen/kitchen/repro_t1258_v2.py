#!/usr/bin/env python3
"""Reproduce T-1258 concurrent-load flake: heavy copytree + subprocess (parity's
pattern) while running the tight-timeout test class repeatedly."""
from __future__ import annotations
import os, subprocess, sys, threading, time, shutil, tempfile, json
from pathlib import Path

HOME = Path(__file__).resolve().parent.parent.parent
TRIALS = int(os.environ.get("TRIALS", "10"))
PY = sys.executable

def load_generator(stop_event):
    """Simulate audit_parity's IO/CPU load: copytree HOME + subprocess runs."""
    while not stop_event.is_set():
        ct = tempfile.mkdtemp(prefix="sim-parity-")
        try:
            shutil.copytree(HOME, ct / "tree", ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__"))
            # Simulate audit_checks subprocess: run a short Python script
            subprocess.run([PY, "-c", "import hashlib, os; [hashlib.sha256(os.urandom(1024)).hexdigest() for _ in range(1000)]"],
                          cwd=HOME, capture_output=True, timeout=60)
            # Write cache files (simulating parity's cache writes)
            (HOME / ".saipen" / "cache" / "sim_param.json").write_text(
                json.dumps({"key": "deadbeef", "when": time.time()}), "utf-8")
            time.sleep(0.5)
        except Exception:
            pass
        finally:
            shutil.rmtree(ct, ignore_errors=True)

def run_discover(discover_args: list[str], cwd: Path, timeout=300) -> dict:
    """Run discover, return results."""
    start = time.monotonic()
    p = subprocess.run([PY, "-m", "unittest", "discover"] + discover_args,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       text=True, cwd=cwd, timeout=timeout)
    elapsed = time.monotonic() - start
    out = p.stdout
    fails = [ln for ln in out.splitlines() if ln.startswith("FAIL:")]
    errors = [ln for ln in out.splitlines() if ln.startswith("ERROR:")]
    summary = None
    for ln in out.splitlines():
        if "Ran " in ln and " in " in ln:
            summary = ln.strip()
    return {"rc": p.returncode, "fails": fails, "errors": errors,
            "summary": summary, "elapsed": elapsed, "ok": p.returncode == 0}

def main():
    stop = threading.Event()
    loader = threading.Thread(target=load_generator, args=(stop,), daemon=True)
    loader.start()

    print(f"Load generator started. Running {TRIALS} discover trials...", flush=True)
    reds = []
    green = 0
    for t in range(1, TRIALS + 1):
        r = run_discover(["-s", "tools", "-v"], HOME)
        if not r["ok"] or r["fails"] or r["errors"]:
            reds.append((t, r))
            print(f"  trial {t}: RED rc={r['rc']} fails={len(r['fails'])} "
                  f"errors={len(r['errors'])} {r['summary']} [{r['elapsed']:.1f}s]", flush=True)
            for f in r["fails"]:
                print(f"    FAIL: {f}", flush=True)
            for e in r["errors"]:
                print(f"    ERROR: {e}", flush=True)
        else:
            green += 1
            print(f"  trial {t}: GREEN {r['summary']} [{r['elapsed']:.1f}s]", flush=True)

    stop.set()
    print(f"\nTRIALS={TRIALS}  GREEN={green}  RED={len(reds)}")
    for t, r in reds:
        print(f"  trial {t}: {r['fails']} {r['errors']}")
    return 0 if not reds else 1

if __name__ == "__main__":
    sys.exit(main())