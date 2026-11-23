"""Read-only current-tree comparison for the actual completed family record."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import core_unit, inflight

relative = ".saipen/evidence/core-unit/f0679548f7e07395-20261012T164807Z.json"
record = json.loads((ROOT / relative).read_text(encoding="utf-8"))
fingerprint = core_unit.tree_fingerprint(ROOT)
body = {"record": relative, "record_keys": sorted(record),
        "current_fingerprint": fingerprint, "record_fingerprint": record.get("fingerprint"),
        "matches_current_tree": fingerprint == record.get("fingerprint"),
        "inflight": inflight.current(ROOT)}
target = Path(__file__).with_name("current-core-record-check.json")
target.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
print(json.dumps(body, indent=2))
