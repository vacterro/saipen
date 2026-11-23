"""Consume only the proven closed SRC-216 generation through its native journal."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2].resolve(strict=True)
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import audit_inbox, intake, journal, operations

output = HERE / "source-audit-final.json"
assert not output.exists(), "preserve immutable closure evidence"
docs, state, board, _ = operations._read(ROOT)
assert board["tickets"]["T-1717"]["section"] == "## DONE"
source = intake.status(ROOT, "SRC-216")
assert source["ok"] and source["status"] == "CLOSED" and source["location"] == "archive", source
digest = "e272b73351028793fd0882ab77973bf3a22493956f4aa8cd0edd36560df60d15"
assert source["source_sha256"] == digest
assert source["coverage"]["terminal"] == source["coverage"]["actionable"] == 10
archived = ROOT / ".saipen/archive/source/SRC-216.md"
assert hashlib.sha256(archived.read_bytes()).hexdigest() == digest
relative = "audit/SAIPEN_20261010_1156.md"
target = ROOT / relative
assert target.resolve(strict=True).is_relative_to(ROOT) and target.is_file()
assert hashlib.sha256(target.read_bytes()).hexdigest() == digest

def other_generations():
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (ROOT / "audit").iterdir() if path.is_file() and path != target}

before = other_generations()
result = audit_inbox.consume_layer(ROOT, relative, "saipen-cli")
assert result["ok"] and result["code"] == "AUDIT_CONSUMED", result
assert not target.exists() and other_generations() == before
assert hashlib.sha256(archived.read_bytes()).hexdigest() == digest
pending, conflicts = journal.scan_pending(ROOT)
assert not pending and not conflicts, (pending, conflicts)
value = {"work": "T-1717", "source": source, "original_source_digest_retained": True,
         "consume": result, "consumed_only": relative, "other_generations": before,
         "other_generations_unchanged": True, "pending": pending, "conflicts": conflicts,
         "product_live_acceptance_claimed": False, "publication": False}
output.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"work": "T-1717", "source": source["status"], "clauses": 10,
                  "consume": result, "other_generations_unchanged": True,
                  "pending": pending, "conflicts": conflicts}))
