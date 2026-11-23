"""Wave B: which files does one validator capture actually READ?

Runs one source-layout capture over a frozen live copy, tracing every file
open (and a few stat families) through builtins/os/io. Buckets the reads so
the copy-vs-read dead-weight ratio is measurable. Read-only wrt the repo.
"""
import builtins
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
import test_validator_layout_parity as vlp  # noqa: E402

def bucket(path: str, root: str) -> str:
    p = os.path.abspath(path)
    r = os.path.abspath(root)
    if p.startswith(r):
        rel = os.path.relpath(p, r).replace("\\", "/")
        parts = rel.split("/")
        if rel.startswith(".saipen/"):
            return ".saipen/" + "/".join(parts[1:3]) if parts[0] == ".saipen" else ".saipen/" + parts[1]
        return parts[0] if len(parts) > 1 else "(root file)"
    return "<outside>"

def main():
    tmp = Path(tempfile.mkdtemp(prefix="saipen-trace-"))
    frozen = tmp / "live-project"
    print("copying frozen tree...", flush=True)
    t0 = time.perf_counter()
    shutil.copytree(vlp.HOME, frozen, ignore=vlp._ignore_runtime_state(vlp.HOME))
    print("frozen copy done", round(time.perf_counter() - t0, 1), "s", flush=True)
    home = tmp / "source-home"
    home.mkdir()
    vlp._build_home(home, flatten=False)
    out = tmp / "findings.json"

    reads = Counter()
    stats = Counter()
    real_open, real_stat, real_lstat, real_scandir = builtins.open, os.stat, os.lstat, os.scandir

    def traced_open(file, *a, **k):
        try:
            mode = k.get("mode") or (a[1] if len(a) > 1 and isinstance(a[1], str) else "r")
            if isinstance(file, (str, bytes, os.PathLike)) and mode.startswith("r"):
                reads[bucket(str(file), frozen)] += 1
        except Exception:
            pass
        return real_open(file, *a, **k)

    def traced_stat(p, *a, **k):
        try:
            stats[bucket(str(p), frozen)] += 1
        except Exception:
            pass
        return real_stat(p, *a, **k)

    def traced_lstat(p, *a, **k):
        try:
            stats[bucket(str(p), frozen)] += 1
        except Exception:
            pass
        return real_lstat(p, *a, **k)

    def traced_scandir(p=".", *a, **k):
        try:
            stats["(scandir) " + bucket(str(p), frozen)] += 1
        except Exception:
            pass
        return real_scandir(p, *a, **k)

    import io as _io
    builtins.open = traced_open
    _io.open = traced_open  # pathlib goes through io.open, not builtins
    os.stat, os.lstat, os.scandir = traced_stat, traced_lstat, traced_scandir
    os.chdir(str(frozen))
    old_argv = sys.argv
    sys.argv = [str(home / "tools/validate.py"), "--gate", "core",
                "--project-root", str(frozen), "--findings-json", str(out),
                "--no-receipt"]
    try:
        spec = importlib.util.spec_from_file_location("validate_target", str(home / "tools/validate.py"))
        target = importlib.util.module_from_spec(spec)
        t1 = time.perf_counter()
        so = open(tmp / "vstdout.txt", "w", encoding="utf-8", errors="replace")
        se = open(tmp / "vstderr.txt", "w", encoding="utf-8", errors="replace")
        with contextlib.redirect_stdout(so), contextlib.redirect_stderr(se):
            try:
                spec.loader.exec_module(target)
            except SystemExit as exc:
                pass
        so.flush(); se.flush()
        print("capture_s:", round(time.perf_counter() - t1, 1), flush=True)
    finally:
        builtins.open = real_open
        _io.open = real_open
        os.stat, os.lstat, os.scandir = real_stat, real_lstat, real_scandir
        sys.argv = old_argv
        os.chdir(str(REPO))

    print("=== READ (open for reading) per bucket ===")
    for name, n in reads.most_common(30):
        print(f"{n:8d}  {name}")
    print("=== STAT per bucket (top 25) ===")
    for name, n in stats.most_common(25):
        print(f"{n:8d}  {name}")
    doc = json.loads(out.read_text(encoding="utf-8"))
    print("problems:", len(doc.get("problems", [])))
    print("buckets_read:", sorted(reads))

main()
