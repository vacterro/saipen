"""Wave B: cProfile one source-layout capture against a frozen live-repo copy.

Builds the same frozen copy the test uses, then runs validate.py --gate core
under cProfile with per-module cumulative time. Read-only wrt the repository.
"""
import cProfile
import io
import json
import pstats
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
import test_validator_layout_parity as vlp
import profile_validator_layout_parity  # noqa: F401  (not used; avoid double patch)

def main():
    tmp = Path(tempfile.mkdtemp(prefix="saipen-vlp-cprof-"))
    frozen = tmp / "live-project"
    import test_validator_layout_parity as m
    ignore = m._ignore_runtime_state(m.HOME)
    print("copying frozen tree...", flush=True)
    shutil.copytree(m.HOME, frozen, ignore=ignore)
    print("frozen copy done", flush=True)
    home = tmp / "source-home"
    home.mkdir()
    m._build_home(home, flatten=False)
    out = tmp / "findings.json"

    argv = [
        sys.executable, str(home / "tools/validate.py"),
        "--gate", "core", "--project-root", str(frozen),
        "--findings-json", str(out), "--no-receipt",
    ]

    # Profile the validator as a subprocess via -m cProfile? cProfile must wrap
    # the target script; use runctx in-process instead: import validate as
    # module with sys.argv patched and cwd=frozen.
    old_argv, old_cwd = sys.argv, Path.cwd()
    sys.argv = [str(home / "tools/validate.py"), "--gate", "core",
                "--project-root", str(frozen), "--findings-json", str(out),
                "--no-receipt"]
    import os
    os.chdir(str(frozen))
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("validate_target", str(home / "tools/validate.py"))
        target = importlib.util.module_from_spec(spec)
        prof = cProfile.Profile()
        import contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            with contextlib.redirect_stderr(io.StringIO()):
                prof.enable()
                try:
                    spec.loader.exec_module(target)  # noqa -- module runs main()
                except SystemExit as exc:
                    prof.disable()
                    print("validator exit:", exc.code, flush=True)
                else:
                    prof.disable()
                    print("validator completed (no SystemExit)", flush=True)
    finally:
        sys.argv, _oldcwd = old_argv, None
        os.chdir(str(old_cwd))

    stats = pstats.Stats(prof)
    buf = io.StringIO()
    stats.stream = buf
    stats.sort_stats("cumulative").print_stats(40)
    print(buf.getvalue())
    buf2 = io.StringIO()
    stats.stream = buf2
    stats.sort_stats("tottime").print_stats(40)
    print(buf2.getvalue())
    print("artifact:", out.is_file(), flush=True)

main()
