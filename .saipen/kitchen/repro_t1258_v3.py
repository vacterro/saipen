#!/usr/bin/env python3
"""Focused: run the tight-timeout test class under concurrent parity-style load."""
from __future__ import annotations
import os, subprocess, sys, threading, time, shutil, tempfile, json
from pathlib import Path

HOME = Path(__file__).resolve().parent.parent.parent
TRIALS = int(os.environ.get("TRIALS", "10"))
PY = sys.executable

def load_generator(stop_event):
    while not stop_event.is_set():
        ct = tempfile.mkdtemp(prefix="sim-parity-")
        try:
            shutil.copytree(HOME, ct / "tree", ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__"))
            subprocess.run([PY, "-c", "import hashlib, os; [hashlib.sha256(os.urandom(1024)).hexdigest() for _ in range(1000)]"],
                          cwd=HOME, capture_output=True, timeout=60)
            (HOME / ".saipen" / "cache" / "sim_param.json").write_text(
                json.dumps({"key": "deadbeef", "when": time.time()}), "utf-8")
            time.sleep(0.3)
        except Exception:
            pass
        finally:
            shutil.rmtree(ct, ignore_errors=True)

def main():
    stop = threading.Event()
    loader = threading.Thread(target=load_generator, args=(stop,), daemon=True)
    loader.start()
    # Target class with the 1.5s timeout
    module = "test_audit_2026_08_28_all3"
    target = f"tests.test_audit_2026_08_28_all3"  # placeholder, adjusted below
    reds = []
    for t in range(1, TRIALS + 1):
        p = subprocess.run(
            [PY, "-m", "unittest", "discover", "-s", "tools", "-p", f"{module}.py", "-v"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=HOME, timeout=900,
        )
        out = p.stdout
        fails = [ln for ln in out.splitlines() if ln.startswith("FAIL:")]
        errors = [ln for ln in out.splitlines() if ln.startswith("ERROR:")]
        summary = next((ln.strip() for ln in out.splitlines() if "Ran " in ln), None)
        if fails or errors:
            reds.append((t, fails, errors))
            print(f"  trial {t}: RED rc={p.returncode} {summary}", flush=True)
            for f in fails: print(f"    FAIL: {f}", flush=True)
            for e in errors: print(f"    ERROR: {e}", flush=True)
        else:
            print(f"  trial {t}: GREEN {summary}", flush=True)
    stop.set()
    print(f"\nTRIALS={TRIALS} RED={len(reds)}")
    for t, f, e in reds:
        print(f"  trial {t}: {f} {e}")
    return 0 if not reds else 1

if __name__ == "__main__":
    sys.exit(main())