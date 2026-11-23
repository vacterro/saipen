"""Concrete read-only REVIEW hypothesis; disposable project only."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "tools"))
import improve
import test_t1803_archived_improve as fixtures
from saipen_engine.improve_retrospective import inspect_archive

fixtures.setUpModule()
case = fixtures.ArchivedImproveTests()
case.setUp()
try:
    root, cycle, seat = case._archived()
    improve.write_sweep_entry(cycle, case._entry(seat))
    successor = case._successor(cycle)
    original = successor.read_bytes()
    result = {"scope": "DISPOSABLE COPY ONLY", "valid_control": inspect_archive(cycle)}
    successor.write_bytes(original + b"[]\n")
    try:
        result["malformed_result"] = inspect_archive(cycle)
    except Exception as exc:
        result["exception"] = {"type": type(exc).__name__, "message": str(exc)}
    (HERE / "malformed-successor-observation.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"valid_control_blocked": result["valid_control"].get("blocked"),
                      "malformed_result": result.get("malformed_result"),
                      "exception": result.get("exception")}))
finally:
    case.doCleanups()
