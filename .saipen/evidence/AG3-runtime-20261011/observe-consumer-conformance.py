"""Classify existing consumer validation receipts; execute no validator."""
import datetime
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUTPUT = HERE / "consumer-conformance-observation.json"
if OUTPUT.exists():
    raise SystemExit("Existing observation is immutable")
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.conformance import conformance_status
from saipen_engine.state import parse_state

consumer = Path("V:/___VAC/__K/__CODE/_TAMPERMONKEY/_SUNO_DOWNLOADER")
paths = {name: consumer / ".saipen" / name for name in ("STATE.md", "BOARD.md", "LOG.md", "IDENTITY.md")}
def hashes():
    return {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()}

before = hashes()
status = conformance_status(consumer, "core")
state = parse_state(paths["STATE.md"].read_text(encoding="utf-8-sig"))
log = paths["LOG.md"].read_text(encoding="utf-8-sig")
after = hashes()
result = {"observed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "consumer": str(consumer), "phase": state.get("phase"), "task": state.get("task"),
          "conformance": status, "recent_events": log.splitlines()[-18:],
          "before": before, "after": after, "canonical_bytes_unchanged": before == after,
          "validator_executions": 0, "canonical_writes": 0, "acl_mutations": 0,
          "limit": "Existing receipt is classified through its current reader; no AG3 token or causal access-repair attribution"}
OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"phase": result["phase"], "task": result["task"], "status": status["status"],
                  "receipt": (status.get("receipt") or {}).get("receipt_id"),
                  "reason": status.get("reason"), "unchanged": before == after}))
if before != after:
    raise SystemExit("Consumer changed during observation")
