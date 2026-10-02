"""Capture a bounded, non-closing status with current-tree evidence limits."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import codec, inflight
from saipen_engine.core_unit import tree_fingerprint
from saipen_engine.state import parse_state

state = parse_state(codec.read_doc(ROOT / ".saipen/STATE.md"))
fingerprint = tree_fingerprint(ROOT)
records = []
for path in (ROOT / ".saipen/evidence/core-unit").glob("*.json"):
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("finished_utc", "") < "2026-10-01T08:00:00Z":
        continue
    records.append({"path": path.relative_to(ROOT).as_posix(),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    **{key: record.get(key) for key in
                       ("finished_utc", "status", "ran", "red", "fingerprint", "duration_s")},
                    "matches_current_tree": record.get("fingerprint") == fingerprint})
records.sort(key=lambda item: item["finished_utc"])
paths = ["saipen/REGISTRY.json", "saipen/INDEX.md", "saipen/COMMANDS.md", "saipen/STORAGE.md",
         "tools/saipen_engine/storage.py", "tools/saipen_engine/storage_artifacts.py",
         "tools/test_storage_policy.py", "tools/test_storage_artifacts.py"]
report = {"recorded_utc": datetime.now(timezone.utc).isoformat(),
          "objective_complete": False, "no_closure_or_publication_claimed": True,
          "state": {key: state.get(key) for key in ("phase", "task", "next_action", "last_event")},
          "storage_owned_paths": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths},
          "current_tree_fingerprint": fingerprint, "family_records": records,
          "inflight": inflight.current(ROOT),
          "focused_storage_registry_and_static": {"tests": 51, "status": "PASS", "skips": 1},
          "incoming_T1561_focused": {"tests": 64, "status": "PASS",
                                   "command": "python -B -m unittest tools.test_t1561_probe_fixture tools.test_warn_ownership_probe tools.test_check_inventory"},
          "shared_writer": {"identity": "UNKNOWN", "team_tree": "root only; no child agents spawned",
                            "events_not_written_by_this_thread": ["E-11098", "E-11099"],
                            "file": "tools/audit_checks.py", "observed_mtime_utc": "2026-10-01T09:23:43Z",
                            "before_sha256": "1b52cbc58da619cb259086bc28448347e17d0a4afb2887aabe1feaab8f4ffe39",
                            "observed_after_sha256": hashlib.sha256((ROOT / "tools/audit_checks.py").read_bytes()).hexdigest(),
                            "policy": "preserve incoming edits; no draft overwrite of the shared implementation"},
          "prepared_backlog": {
              "T-1560": {"path": ".saipen/evidence/T-1560-utf8-candidate/",
                         "sites": 224, "files": 29, "permanent_oracle": "same source red on implicit encoding, green in isolated candidate"},
              "T-1559": {"path": ".saipen/evidence/T-1559-style-candidate/",
                         "same_oracle": "STYLE/SKILL target warnings: old 2, candidate 0, voice-red 1, language-red 1",
                         "byte_delta": -15, "measurable_style_contract_changed": False}},
          "authority_boundary": {"ticket": "T-1580", "code": "RETIREMENT_AUTHORITY_REQUIRED",
                                 "proof": ".saipen/evidence/T-1580-retire-refused-20261001.md",
                                 "parent": "T-1579", "parent_resume": "BUILD",
                                 "question": "pending operator capsule; no authorization inferred from elapsed time"},
          "recovery": "SAILEARN durable HOME selected; source evidence absent; no fabricated reconstruction; SAIBUD-8 untouched",
          "saipal_report": ".saipen/evidence/T-1579-storage-safety/saipal-report.json"}
OUT = ROOT / ".saipen/evidence/T-1579-storage-safety/goal-handoff.json"
OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"state": report["state"], "records": [{"status": item["status"], "ran": item["ran"],
                  "red": len(item["red"] or []), "current": item["matches_current_tree"]} for item in records],
                  "inflight": bool(report["inflight"]), "path": OUT.relative_to(ROOT).as_posix()}))
