"""Read only the already-bound incident project; save evidence in this project."""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HOME = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(HOME / "tools"))
from saipen_engine import accepted_debt, board, intake
from saipen_engine.log import history_paths, read_history_snapshot

root = Path("V:/___VAC/__K/__CODE/_PY/_SMART_VAC_MEDIA_COMPRESSOR").resolve()
pins = [root / ".saipen/STATE.md", root / ".saipen/BOARD.md",
        root / ".saipen/intake/index.json", *history_paths(root),
        *sorted((root / ".saipen/archive/source").glob("SRC-003.*")),
        root / ".saipen/recovery/conformance/accepted_debt/AD-000001.json"]
def hashes():
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in pins}
before = hashes()
parsed = board.parse_board((root / ".saipen/BOARD.md").read_text(encoding="utf-8-sig"))
history = read_history_snapshot(root)
record = accepted_debt.load_record(root, "AD-000001")
missing = [("E-371", file, raw) for file, _line, raw, event
           in accepted_debt._iter_history(root) if event["event"] == 371]
source = intake.read_body(root, record["authority"])
meta = source.get("meta") or {}
observation = {
    "observed_utc": datetime.now(timezone.utc).isoformat(),
    "external_root": str(root), "read_only": True,
    "board_errors": parsed["errors"],
    "tickets": {t: parsed["tickets"][t]["section"] for t in ("T-57", "T-62")},
    "source_003_status": intake.status(root, "SRC-003"),
    "event_371": [e for e in history.events if e.get("event") == 371],
    "accepted_debt": {
        "record_id": record["record_id"], "authority": record["authority"],
        "events": record["accepted_missing_events"],
        "current_reader": accepted_debt.evaluate_provenance(root, missing)},
    "authority_source": {
        "ok": source.get("ok"), "status": meta.get("status"),
        "request_provenance": meta.get("request_provenance"),
        "body": source.get("body")},
    "before_hashes": before,
    "observed_files_unchanged": before == hashes(),
    "limitation": "No validator execution, foreign write, new operator decision, "
                  "historical writer attribution or native host acceptance. "
                  "A current receipt reference does not prove historical consent.",
}
assert observation["observed_files_unchanged"]
target = Path(__file__).with_name("external-after-authority-fix.json")
target.write_text(json.dumps(observation, indent=2, ensure_ascii=False, default=str) + "\n",
                  encoding="utf-8")
print(json.dumps({"tickets": observation["tickets"],
                  "source_003_ok": observation["source_003_status"].get("ok"),
                  "source_003_status": observation["source_003_status"].get("status"),
                  "debt": observation["accepted_debt"]["current_reader"],
                  "observed_files_unchanged": observation["observed_files_unchanged"]}))
