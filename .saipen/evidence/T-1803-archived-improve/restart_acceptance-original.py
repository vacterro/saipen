"""Real historical copies, native CLI, honest unresolved dispositions only."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parents[2]
CONSUMER = Path("V:/___VAC/__K/__CODE/_PY/_AUDAPACK")
sys.path.insert(0, str(ENGINE / "tools"))
import test_t1803_archived_improve as control  # noqa: E402
from saipen_engine.continue_fallback import cycle_liveness  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    baseline = json.loads((HERE / "baseline-observation.json").read_text(encoding="utf-8"))
    protected = baseline["protected_before"]

    def current():
        return {name: sha(CONSUMER / name) if (CONSUMER / name).is_file() else "ABSENT"
                for name in protected}

    if current() != protected:
        raise RuntimeError("Consumer protected inputs changed since observation; acceptance stopped")
    control.setUpModule()  # isolate only this test process; never mint an operator carrier
    scratch = Path(tempfile.mkdtemp(prefix="T1803-historical-acceptance-")).resolve()
    results = []
    for number, original in enumerate(baseline["cycles"], 1):
        directory = scratch / ("case-" + str(number))
        directory.mkdir()
        case = control.ArchivedImproveTests()
        case._tmp = SimpleNamespace(name=str(directory))
        root = case._project()  # native model-supplied local fixture Work, new lineage
        cycle_id = original["cycle"]
        cycle = root / ".saipen/improve" / cycle_id
        shutil.copytree(CONSUMER / ".saipen/improve" / cycle_id, cycle)
        before = case._history(cycle)
        code, blocked = case._cli(root, "improve", "reconcile", cycle_id)
        assert code != 0 and len(blocked["pending_findings"]) == 3, blocked
        for seat in original["seats"]:
            for finding in seat["findings"]:
                code, result = case._cli(
                    root, "improve", "sweep", cycle_id, finding["ref"],
                    "NEEDS_EXTERNAL_EVIDENCE", "--report", seat["seat"] + "/" + seat["report"],
                    "--reproduced", "n", "--retrospective",
                )
                assert code == 0 and result.get("ok"), result
        code, queue = case._cli(root, "improve", "sweep-queue", cycle_id)
        assert code == 0 and len(queue["queue"]) == 3, queue
        code, blocked = case._cli(root, "improve", "reconcile", cycle_id)
        assert code != 0 and blocked["blocked"], blocked
        successor = case._successor(cycle).read_bytes()
        for _ in range(2):
            code, continuation = case._cli(root, "continue", "--dry-run")
            assert code == 0, continuation
            assert not any(item["cycle_id"] == cycle_id
                           for item in continuation.get("improve_stale_cycles", [])), continuation
            assert case._successor(cycle).read_bytes() == successor
        view = cycle_liveness(root, cycle_id)
        assert view["blocked"] and not view["stale"] and len(view["pending_findings"]) == 3
        assert case._history(cycle) == before
        assert not (cycle / "SWEEP.md").exists()
        results.append({"cycle": cycle_id, "original_history_unchanged": True,
                        "native_successor_created": True, "pending_findings": 3,
                        "retained_report_statuses": [item["report_status"] for item in view["seats"]],
                        "classification": "BLOCKED_EXTERNAL_EVIDENCE; NOT RESOLVED",
                        "repeated_native_continue_stale_advertisement": False,
                        "successor_sha256": hashlib.sha256(successor).hexdigest()})
    after = current()
    assert after == protected
    result = {"scope": "DISPOSABLE HISTORICAL COPIES; NO REAL FINDING RESOLUTION CLAIM",
              "consumer_read_only": True, "consumer_T311_closed": False,
              "consumer_protected_after": after, "scratch": str(scratch), "cycles": results}
    (HERE / "historical-restart-acceptance.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"consumer_read_only": True, "cycles": results, "scratch": str(scratch)}))


if __name__ == "__main__":
    main()
