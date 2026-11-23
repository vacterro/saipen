"""Disposable existing-fixture observations; no live project mutation."""
import hashlib
import json
import sys
from pathlib import Path

HOME = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(HOME / "tools"))
from saipen_engine import intake
from test_source_receipts import SourceReceiptTests

def tree(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}

results = []
for missing in (None, "meta.json", "contract.json", "coverage.json", "md"):
    fixture = SourceReceiptTests("test_src15_close_archives_and_removes_hot_body")
    fixture.setUp()
    try:
        receipt = fixture.capture("Disposable closure outcome control")["receipt"]
        fixture.normalized(receipt)
        fixture.resolve(receipt)
        first = intake.close_receipt(fixture.root, receipt, closure_event="E-9")
        assert first["ok"], first
        if missing:
            (fixture.root / f".saipen/archive/source/{receipt}.{missing}").unlink()
        before = tree(fixture.root)
        result = intake.close_receipt(fixture.root, receipt, closure_event="E-9")
        after = tree(fixture.root)
        status = intake.status(fixture.root, receipt)
        findings = intake.validate_project(fixture.root)
        results.append({"missing_archive_artifact": missing, "repeat_close": result,
                        "status_after": status, "validator_findings": findings,
                        "repeat_changed_files": sorted(k for k in set(before) | set(after)
                                                       if before.get(k) != after.get(k))})
    finally:
        assert fixture.root.parent.resolve() == Path(fixture.tmp.name).resolve()
        fixture.tearDown()

target = Path(__file__).with_name("closure-outcomes-before.json")
target.write_text(json.dumps({"scope": "existing engine and disposable native fixture; "
                             "read-only investigation of next parent Work", "cases": results},
                            indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
print(json.dumps([{"missing": r["missing_archive_artifact"],
                   "close_ok": r["repeat_close"].get("ok"),
                   "recovered": r["repeat_close"].get("recovered"),
                   "residue_removed": r["repeat_close"].get("residue_removed"),
                   "validation_problem_count": len(r["validator_findings"])} for r in results]))
