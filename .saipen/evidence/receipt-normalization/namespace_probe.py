"""Independently observe both files and empty directories in a real preview."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEST = Path(__file__).parent
sys.path.insert(0, str(ROOT / "tools"))
from test_source_receipts import SourceReceiptTests
from saipen_engine import intake

case = SourceReceiptTests("test_src01_capture_is_verbatim_and_digest_covers_body_only")
case.setUp()
try:
    board = case.root / ".saipen/BOARD.md"
    board.write_text(board.read_text(encoding="utf-8").replace(
        "## TODO\n", "## TODO\n- [ ] T-099 range | source_receipts: SRC-009..SRC-029\n",
    ), encoding="utf-8")
    def snapshot():
        return {p.relative_to(case.root).as_posix():
                ("directory" if p.is_dir() else hashlib.sha256(p.read_bytes()).hexdigest())
                for p in case.root.rglob("*")}
    before = snapshot()
    result = intake.normalize_receipt_ranges(case.root, dry_run=True)
    after = snapshot()
    assert result["ok"] and result["code"] == "RECEIPT_RANGE_PLAN", result
    assert result["rewrites"] == 1 and len(result["expanded"]["T-099"]) == 21, result
    assert after == before, {"before": before, "after": after}
    record = {"oracle": "actual strict range preview; all directory names and file hashes unchanged",
              "result": result, "before": before, "after": after, "root": str(case.root)}
    (DEST / "namespace-dry-run.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "rewrites_planned": 1, "expanded_ids": 21,
                      "files_and_directories": len(before), "changed": []}))
finally:
    case.tearDown()
