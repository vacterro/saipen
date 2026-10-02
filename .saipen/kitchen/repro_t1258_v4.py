#!/usr/bin/env python3
"""Reproduce T-1258: run full discover under audit_parity-style load matching its
real pattern: 2 copytrees + ThreadPoolExecutor(2) workers running floor+validate per case."""
from __future__ import annotations
import os, subprocess, sys, threading, time, shutil, tempfile, json, hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HOME = Path(__file__).resolve().parent.parent.parent
TRIALS = int(os.environ.get("TRIALS", "5"))
PY = sys.executable
AC_HOME = HOME / "tools" / "audit_checks.py"

def simulate_parity_work(stop_event):
    """Replicate audit_parity's exact load pattern."""
    # Phase 1: copytree (like audit_parity line 144)
    # Phase 2: canonical audit_checks subprocess (like line 247)
    # Phase 3: ThreadPoolExecutor(2) workers running floor + validate (like lines 285-322)
    while not stop_event.is_set():
        tmp = Path(tempfile.mkdtemp(prefix="t1258-sim-"))
        try:
            # Phase 1: copytree HOME → pristine (like audit_parity line 144)
            pristine = tmp / "pristine"
            shutil.copytree(HOME, pristine, ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", "node_modules"))
            # Phase 2: run a subprocess that does its own copytree + work (simulating audit_checks)
            # Instead of running audit_checks (which takes 900s), run a script that does copytree + heavy work
            heavy_code = ("""
import sys, shutil, tempfile, hashlib, os
from pathlib import Path
d = Path(tempfile.mkdtemp(prefix="t1258-sim-ac-"))
try:
    shutil.copytree(Path(sys.argv[1]), d / "ac", ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", "node_modules"))
    # Simulate 227 mutation cases: heavy loops
    expected = "deadbeef"
    found = False
    for i in range(500):
        h = hashlib.sha256(f"case-{i}".encode()).hexdigest()
        if h == expected:
            found = True
    # Spawn a subprocess (simulating floor/validate)
    subprocess.run([sys.executable, "-c", "import hashlib; [hashlib.sha256(b'x'*4096).hexdigest() for _ in range(500)]"],
                   capture_output=True, timeout=30)
finally:
    shutil.rmtree(d, ignore_errors=True)
""")
            subprocess.run([PY, "-c", heavy_code, str(HOME)], cwd=HOME, capture_output=True, timeout=300)

            # Phase 3: ThreadPoolExecutor(2) workers doing floor + validate
            def worker_work(worker_id):
                root = tmp / f"parity-{worker_id:02d}"
                shutil.copytree(pristine, root, copy_function=os.link)
                # Simulate floor: run a subprocess
                subprocess.run([PY, "-c", "import hashlib; [hashlib.sha256(b'x'*4096).hexdigest() for _ in range(200)]"],
                              cwd=root, capture_output=True, timeout=30)
                # Simulate validate: run a subprocess
                subprocess.run([PY, "-c", "import hashlib; [hashlib.sha256(b'x'*4096).hexdigest() for _ in range(200)]"],
                              cwd=root, capture_output=True, timeout=30)
                return worker_id

            cases = list(range(41))  # 41 cases like parity's BASELINE
            chunks = [cases[i::2] for i in range(2)]
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(worker_work, i) for i in range(2)]
                for f in as_completed(futures):
                    f.result()

            # Write cache files (like parity lines 267, 381)
            (HOME / ".saipen" / "cache" / "sim_audit_checks_cache.json").write_text(
                json.dumps({"key": hashlib.sha256(b"sim").hexdigest()[:16]}), "utf-8")
            (HOME / ".saipen" / "cache" / "sim_audit_parity_cache.json").write_text(
                json.dumps({"key": hashlib.sha256(b"sim").hexdigest()[:16], "caught": 11}), "utf-8")
            time.sleep(5)
        except Exception as e:
            pass
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

def main():
    stop = threading.Event()
    loader = threading.Thread(target=simulate_parity_work, args=(stop,), daemon=True)
    loader.start()
    print(f"Load generator started. Running {TRIALS} x full discover...", flush=True)
    reds = []
    for t in range(1, TRIALS + 1):
        p = subprocess.run(
            [PY, "-m", "unittest", "discover", "-s", "tools", "-v"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=HOME, timeout=1200,
        )
        out = p.stdout
        fails = [ln for ln in out.splitlines() if ln.startswith("FAIL:")]
        errors = [ln for ln in out.splitlines() if ln.startswith("ERROR:")]
        summary = next((ln.strip() for ln in out.splitlines() if "Ran " in ln), None)
        extra = extract_import_errors(out)
        if fails or errors or extra:
            reds.append((t, fails, errors, extra))
            print(f"  trial {t}: RED rc={p.returncode} {summary}", flush=True)
            for f in fails: print(f"    FAIL: {f}", flush=True)
            for e in errors: print(f"    ERROR: {e}", flush=True)
            for x in extra: print(f"    IMPORT: {x}", flush=True)
        else:
            print(f"  trial {t}: GREEN {summary} [{len(fails)}f {len(errors)}e]", flush=True)
    stop.set()
    print(f"\nTRIALS={TRIALS} RED={len(reds)}")
    for t, f, e, x in reds:
        print(f"  trial {t}: fails={f} errors={e} import={x}")
    return 0 if not reds else 1

def extract_import_errors(out):
    lines = out.splitlines()
    return [ln for ln in lines if "ImportError" in ln or "ModuleNotFoundError" in ln]

if __name__ == "__main__":
    sys.exit(main())