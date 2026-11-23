"""Same-oracle reproducer: committed acceptance never resurrects a deleted target."""
from pathlib import Path
import hashlib
import json
import os
import sys
import unittest

ROOT = Path("V:/___VAC/__K/__CODE/_AI_STUFF_AGENTIC/_SAIPEN")
EVIDENCE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
from test_hermetic_env import hermetic_env, isolate_host_session

environment = hermetic_env(PYTHONDONTWRITEBYTECODE="1")
os.environ.clear()
os.environ.update(environment)
isolate_host_session()

from saipen_engine import accepted_debt as debt, journal
from test_t1851_debt_authority import NativeDecisionTests, tree_bytes


def snapshot(directory, files):
    for name, data in files.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def main():
    label = sys.argv[1]
    destination = EVIDENCE / ("debt-replay-" + label)
    destination.mkdir(exist_ok=False)
    case = NativeDecisionTests("test_committed_operation_does_not_report_a_missing_target_repaired")
    try:
        case.setUp()
        receipt = case.approval()
        first = case.apply(receipt)
        assert first["ok"], first
        target = case.root / debt.ACCEPTED_DEBT_DIR / (first["record_id"] + ".json")
        before = tree_bytes(case.root)
        original = target.read_bytes()
        operation = journal.Journal(case.root, first["journal_op_id"])
        manifest_before = operation.manifest.read_bytes()
        target.unlink()
        deleted = tree_bytes(case.root)
        second = case.apply(receipt)
        after = tree_bytes(case.root)
        report = {
            "fixture_kind": case.CATEGORY,
            "fixture_root": str(case.root),
            "first": first,
            "second": second,
            "target": target.relative_to(case.root).as_posix(),
            "target_existed_before": True,
            "target_absent_before_retry": target.relative_to(case.root).as_posix() not in deleted,
            "target_exists_after_retry": target.exists(),
            "restored_exact_original_bytes": target.exists() and target.read_bytes() == original,
            "journal_status": operation.read()["status"],
            "journal_bytes_unchanged": operation.manifest.read_bytes() == manifest_before,
            "changed_after_retry": sorted(name for name in set(deleted) | set(after)
                                          if deleted.get(name) != after.get(name)),
            "original_target_sha256": hashlib.sha256(original).hexdigest(),
            "production_sha256": {
                name: hashlib.sha256((ROOT / "tools/saipen_engine" / name).read_bytes()).hexdigest()
                for name in ("accepted_debt.py", "journal.py", "operator_origin.py")
            },
        }
        for stage, files in (("before", before), ("deleted", deleted), ("after", after)):
            snapshot(destination / stage, files)
        (destination / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2), flush=True)
        assert not second["ok"], second
        assert not target.exists(), "committed retry resurrected the deleted acceptance"
        assert deleted == after, "refused committed retry wrote files"
        return 0
    finally:
        case.doCleanups()
        unittest.doModuleCleanups()


if __name__ == "__main__":
    raise SystemExit(main())
