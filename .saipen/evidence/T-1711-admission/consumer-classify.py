"""Classify the live consumer through the existing read-only evidence owners."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import log
from saipen_engine.operations import _read

output = HERE / "consumer-classification.json"
if output.exists():
    raise SystemExit("Consumer classifier evidence already exists")
consumer = Path("V:/___VAC/__K/__CODE/_HTML/_SAI_WEBSITE")
paths = [consumer / ".saipen" / name for name in ("STATE.md", "BOARD.md", "LOG.md", "IDENTITY.md")]
before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
try:
    docs, state, board, tail = _read(consumer)
    events = docs["_history"].events
    result = {"state_task": state.get("task"), "state_phase": state.get("phase"),
              "tail": tail,
              "verification": log.verification_evidence("T-31", events),
              "regression": log.regression_evidence("T-31", events),
              "candidate_evidence": [ev for ev in events if ev.get("ticket") == "T-31" and any(
                  word in ev.get("text", "") for word in ("REGRESSION", "verifier:", "verify ->", "verify PASS"))]}
except Exception as exc:
    result = {"classification_unavailable": type(exc).__name__, "detail": str(exc)}
after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
result.update({"root": str(consumer), "before": before, "after": after,
               "canonical_bytes_unchanged": before == after,
               "mutations": 0, "limit": "Current source classifier; no foreign transition or evidence admission attempted"})
output.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
print(json.dumps({k: v for k, v in result.items() if k not in ("candidate_evidence", "before", "after")}, indent=2))
