"""Retain the initial report and append a separately measured live observation."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
HOME = HERE.parents[2]
TARGET = Path("V:/___VAC/__K/__CODE/_AI_STUFF_AGENTIC/_ZAICODE")
sys.path.insert(0, str(HOME / "tools"))
from saipen_engine import log

later = json.loads((HERE / "live-later.json").read_text(encoding="utf-8"))
assert later["inputs_stable"] and not later["snapshot"]["contract_errors"]
captured = HERE / "captured-project"
original = log.read_history_snapshot(captured)
current = log.read_history_snapshot(TARGET)
assert current.hash == later["snapshot"]["hash"], "live history changed since the later probe"
fields = ("date", "event", "parent", "ticket", "agent", "op_id", "taxonomy", "text")
old_events = [{k: event.get(k) for k in fields} for event in original.events]
new_events = [{k: event.get(k) for k in fields} for event in current.events]
semantic_prefix = new_events[:len(old_events)] == old_events
old_active = (captured / ".saipen/LOG.md").read_bytes()
live_active = (TARGET / ".saipen/LOG.md").read_bytes()
byte_prefix = live_active.startswith(old_active)
sealed = {}
for path in (captured / ".saipen/logs").glob("LOG-*.md"):
    relative = path.relative_to(captured)
    sealed[path.name] = path.read_bytes() == (TARGET / relative).read_bytes()
result = {"observed_utc": later["observed_utc"], "initial_events": len(old_events),
          "later_events": len(new_events), "later_tail": current.tail,
          "original_events_exact_semantic_prefix": semantic_prefix,
          "original_active_bytes_exact_prefix": byte_prefix, "sealed_bytes_unchanged": sealed,
          "new_event_ids": [e["event"] for e in current.events[len(old_events):]],
          "actor_attribution": "new durable T-321 records observed; their initiating host/authorization was not identified by this inspector",
          "target_mutations_by_inspection": 0}
assert semantic_prefix and byte_prefix and all(sealed.values()), result
(HERE / "prefix-retention.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
report = HERE / "REPORT.md"
initial = HERE / "REPORT.initial.md"
if not initial.exists():
    shutil.copyfile(report, initial)
body = initial.read_text(encoding="utf-8")
notice = (
    "# Observation revision\n\n"
    f"The main report below records the initial 5050-event observation. A later read-only probe at "
    f"{later['observed_utc']} finds {len(new_events)} legal events, tail {current.tail}, with zero "
    "contract errors. The original active-log bytes are an exact prefix; every original parsed "
    "event and all four sealed files are unchanged. STATE/BOARD/active LOG advanced through "
    "durable T-321 records after the first capture. This inspection did not initiate those "
    "operations and has not established their separate host authorization.\n\n"
    "See live-later.json, later-revalidation.json and prefix-retention.json. The initial "
    "report is preserved byte-for-byte as REPORT.initial.md. No target recovery or continuation "
    "was invoked here; original failure mechanism remains unknown, and SRC-238 stays unresolved.\n\n"
)
report.write_text(notice + body, encoding="utf-8")
print(json.dumps(result))
