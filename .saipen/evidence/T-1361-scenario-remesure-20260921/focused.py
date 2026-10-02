"""Run existing scenario entry points, retaining subprocess diagnostic evidence."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
import run_scenarios as scenarios


def main():
    names = sys.argv[1:]
    if not names or any(not name.startswith("run_") or not callable(getattr(scenarios, name, None)) for name in names):
        raise SystemExit("Supply existing run_scenarios run_* function names")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    destination = Path(__file__).parent / ("focused-" + stamp)
    destination.mkdir()
    original = subprocess.run
    calls = []

    def traced(*args, **kwargs):
        result = original(*args, **kwargs)
        argv = args[0] if args else kwargs.get("args")
        if result.returncode or "validate.py" in str(argv):
            calls.append({"argv": str(argv), "cwd": str(kwargs.get("cwd", "")), "exit": result.returncode,
                          "stdout": str(result.stdout or ""), "stderr": str(result.stderr or "")})
        return result

    result_set = []
    with scenarios.session_carrier_isolation(), tempfile.TemporaryDirectory(prefix="t1361-config-") as config:
        with mock.patch.dict(os.environ, {"SAIPEN_USER_CONFIG_HOME": config}), mock.patch.object(subprocess, "run", traced):
            with (destination / "console.txt").open("w", encoding="utf-8") as stream, contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                for name in names:
                    start = time.monotonic()
                    result = getattr(scenarios, name)()
                    failures, checked, skipped = scenarios._group_counts(result)
                    result_set.append({"function": name, "elapsed": time.monotonic() - start,
                                       "checked": checked, "skipped": skipped, "failures": failures})
    (destination / "subprocess.json").write_text(json.dumps(calls, indent=2), encoding="utf-8")
    metadata = {"command": subprocess.list2cmdline(sys.argv),
                "head": original(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
                "harness_sha256": hashlib.sha256((ROOT / "tools/run_scenarios.py").read_bytes()).hexdigest(),
                "results": result_set}
    (destination / "result.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(destination)
    for item in result_set:
        print(item["function"], item["checked"], "checks;", len(item["failures"]), "failures;", round(item["elapsed"], 2), "seconds")
    return int(any(item["failures"] for item in result_set))


if __name__ == "__main__":
    raise SystemExit(main())
