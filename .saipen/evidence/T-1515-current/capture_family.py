"""Retain real shard output before owned cleanup, including exact skip counts.

The canonical runner, discovery, subject, timeout and six-shard configuration
are unchanged. The wrapper only preserves files immediately before the existing
reclaim function removes this run's own sandbox.
"""
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import core_unit, inflight, operations
from saipen_engine.state import parse_state


def tally(text):
    ran = re.findall(r"^Ran (\d+) tests? in .*?$", text, re.MULTILINE)
    summaries = re.findall(r"^(OK|FAILED)(?: \(([^\n]*)\))?\s*$", text, re.MULTILINE)
    if not ran or not summaries:
        raise ValueError("the native unittest summary is incomplete")
    status, fields = summaries[-1]
    counts = dict((key, int(value)) for key, value in re.findall(
        r"(failures|errors|skipped|expected failures|unexpected successes)=(\d+)", fields))
    total = int(ran[-1])
    skipped = counts.get("skipped", 0)
    expected = counts.get("expected failures", 0)
    passed = total - skipped - expected if status == "OK" else None
    if passed is not None and passed < 0:
        raise ValueError("the native summary counts contradict its run count")
    return {"ran": total, "passed": passed, "skipped": skipped,
            "expected_failures": expected, "failures": counts.get("failures", 0),
            "errors": counts.get("errors", 0),
            "unexpected_successes": counts.get("unexpected successes", 0), "status": status}


def main():
    if "--control" in sys.argv:
        good = tally("Ran 4 tests in 0.1s\n\nOK (skipped=1)\n")
        assert good["passed"] == 3 and good["skipped"] == 1
        bad = tally("Ran 4 tests in 0.1s\n\nFAILED (failures=1, skipped=1)\n")
        assert bad["passed"] is None and bad["failures"] == 1
        native = b"native section \xa7\nRan 4 tests in 0.1s\n\nOK (skipped=1)\n"
        assert tally(native.decode("utf-8", errors="replace")) == good
        try:
            tally("....\n")
        except ValueError:
            print("summary controls: good skip preserved; failed not PASS; incomplete refused")
            return 0
        raise AssertionError("incomplete output was accepted")
    original_reclaim = core_unit.reclaim
    summaries = []

    def retain_then_reclaim(path):
        base = Path(path)
        try:
            owner = json.loads((base / core_unit.SANDBOX_OWNER).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            owner = {}
        stderr = base / "spool/stderr"
        if owner.get("pid") == os.getpid() and stderr.is_file():
            raw = stderr.read_bytes()
            # Match the canonical runner's decoder; preserve the exact raw bytes.
            counts = tally(raw.decode("utf-8", errors="replace"))
            destination = HERE / "shards" / base.name
            destination.mkdir(parents=True, exist_ok=True)
            for rel in ("owner.json", "spec.json", "manifest.json", "spool/stderr", "spool/stdout"):
                source = base / rel
                if source.is_file():
                    target = destination / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
            summaries.append({"sandbox": base.name, "stderr_sha256": hashlib.sha256(raw).hexdigest(),
                              **counts})
        return original_reclaim(path)

    core_unit.reclaim = retain_then_reclaim
    try:
        with inflight.holding(ROOT, "T-1515", "core_unit fresh evidence with output retention"):
            run = core_unit.run_family(ROOT, jobs=6, timeout=5400)
            written = core_unit.write_record(ROOT, run, run["fingerprint"])
            assert core_unit.tree_fingerprint(ROOT) == run["fingerprint"], "source tree drifted"
            assert len(summaries) == 6, "not every real shard summary was retained"
            assert sum(item["ran"] for item in summaries) == run["ran"]
            summary = {"family_record": written["path"], "fingerprint": run["fingerprint"],
                       "runner": "canonical core_unit.run_family", "jobs": 6, "timeout": 5400,
                       "verdict": written["record"]["verdict"], "shards": summaries}
            for key in ("ran", "skipped", "expected_failures", "failures", "errors", "unexpected_successes"):
                summary[key] = sum(item[key] for item in summaries)
            summary["passed"] = (sum(item["passed"] for item in summaries)
                                 if all(item["passed"] is not None for item in summaries) else None)
            (HERE / "family-counts.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
            state = parse_state((ROOT / ".saipen/STATE.md").read_text(encoding="utf-8"))
            result = operations.checkpoint(ROOT, state["agent"], "RUN", "T-1515",
                                           core_unit.evidence_line(written))
            print(json.dumps({key: summary[key] for key in (
                "family_record", "verdict", "ran", "passed", "skipped", "failures", "errors")}))
            return 0 if result.ok and summary["verdict"] == "PASS" else 1
    finally:
        core_unit.reclaim = original_reclaim


if __name__ == "__main__":
    raise SystemExit(main())
