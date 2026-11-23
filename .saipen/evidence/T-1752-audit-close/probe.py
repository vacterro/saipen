"""Reproduce the audit-source closure gap in a canonical disposable project."""

import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / "tools"))
from test_t1666_receipt_close import _Receipts  # noqa: E402
from saipen_engine import audit_inbox, intake  # noqa: E402

case = _Receipts()
try:
    project = case.make_project()
    layer = project / "audit/1.md"
    layer.parent.mkdir()
    layer.write_text("# audit\n\nRepair one bounded existing workflow.\n", encoding="utf-8")
    ingested = case.cli(project, "audit", "ingest")
    assert ingested.get("ok"), ingested
    work, receipt = ingested["work"], ingested["receipt"]
    added = intake.add_requirement(project, receipt, rid="R1", text="repair the workflow")
    assert added.get("ok"), added
    case.settle(project, receipt, work)
    case.ready_to_finish(project, work)
    finished = case.cli(project, "continue") if "--continue" in sys.argv else case.finish(project, work)
    missing_result = None
    if "--missing" in sys.argv:
        layer.unlink()
        missing_result = case.cli(project, "audit", "ingest")
    layers = audit_inbox.classify(project)["layers"]
    print(json.dumps({
        "finish_ok": finished.get("ok"),
        "finish_code": finished.get("code"),
        "continue_trace": finished.get("continue_trace"),
        "source_status": intake.status(project, receipt),
        "layer_states": [item["state"] for item in layers],
        "binding_state": audit_inbox.read_binding(project)["layers"]["audit/1.md"]["state"],
        "layer_preserved": layer.is_file(),
        "missing_ingest": missing_result,
        "retained_works": sorted(intake.active_receipt_works(project)[1]),
    }, indent=2))
finally:
    case.doCleanups()
