"""Campaign X Wave B: phase-level profiler for test_validator_layout_parity.

Runs the five tests in-process, wrapping the module's own helpers with
perf_counter timers. Reports per-test wall time and per-phase attribution
(home build / frozen copytree / validator capture / residual assertions).
Read-only with respect to the repository: no production file is touched.
"""
from __future__ import annotations

import io
import json
import shutil
import sys
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

import test_validator_layout_parity as vlp  # noqa: E402

timings: dict[str, list] = {}
current: dict = {"name": "<module>", "depth": 0}


def _record(phase: str, seconds: float, note: str = "") -> None:
    timings.setdefault(current["name"], []).append([phase, round(seconds, 3), note])


orig_build_home = vlp._build_home


def timed_build_home(destination, *, flatten):
    t0 = time.perf_counter()
    orig_build_home(destination, flatten=flatten)
    _record(
        "build_home",
        time.perf_counter() - t0,
        "flat" if flatten else "source",
    )


vlp._build_home = timed_build_home


class _CaptureCounter:
    calls = 0


orig_capture = vlp._capture_findings


def timed_capture(validator_root, project_root, out_path):
    _CaptureCounter.calls += 1
    t0 = time.perf_counter()
    completed = orig_capture(validator_root, project_root, out_path)
    _record("capture", time.perf_counter() - t0, str(validator_root.parent.name))
    return completed


vlp._capture_findings = timed_capture


orig_copytree = shutil.copytree


def timed_copytree(*args, **kwargs):
    src = str(args[0])
    live = str(REPO.resolve()) in str(Path(src).resolve())
    t0 = time.perf_counter()
    result = orig_copytree(*args, **kwargs)
    _record("copytree", time.perf_counter() - t0, "live-home" if live else "other")
    return result


shutil.copytree = timed_copytree


def main() -> dict:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromName("test_validator_layout_parity.InstalledValidatorLayoutParityTests"))
    suite.addTests(loader.loadTestsFromName("test_validator_layout_parity.RootStrayLocaleTests"))

    def flatten(suite) -> list:
        tests = []
        for item in suite:
            if isinstance(item, unittest.TestSuite):
                tests.extend(flatten(item))
            else:
                tests.append(item)
        return tests

    all_tests = flatten(suite)
    report = {"results": [], "timings": timings}
    t_module0 = time.perf_counter()
    for test in all_tests:
            name = f"{test.__class__.__name__}.{test._testMethodName}"
            current["name"] = name
            buf = io.StringIO()
            runner = unittest.TextTestRunner(stream=buf, verbosity=0)
            t0 = time.perf_counter()
            result = runner.run(unittest.TestSuite([test]))
            wall = time.perf_counter() - t0
            entry = {
                "test": name,
                "wall_s": round(wall, 3),
                "ok": bool(result.wasSuccessful()),
                "stdout_tail": buf.getvalue()[-400:],
                "skipped": [str(skipped[0]) for skipped in result.skipped],
            }
            report["results"].append(entry)
            print(json.dumps(entry), flush=True)
    report["module_wall_s"] = round(time.perf_counter() - t_module0, 3)
    report["capture_calls"] = _CaptureCounter.calls

    print("=== PHASE BREAKDOWN ===", flush=True)
    for name, events in timings.items():
        agg: dict[str, list] = {}
        for phase, seconds, note in events:
            agg.setdefault(phase, []).append(seconds)
        print(name, flush=True)
        for phase, values in agg.items():
            print(f"  {phase}: n={len(values)} total={sum(values):.3f}s", flush=True)
    print(json.dumps(report), flush=True)
    return report


if __name__ == "__main__":
    main()
