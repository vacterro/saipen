"""Check the restored scope against the exact pre-edit production snapshots."""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEST = Path(__file__).parent
def top(text):
    return {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(text).body
            if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
rows = []
for rel in ("tools/saipen_engine/intake.py", "tools/saipen.py"):
    old_raw = (DEST / (Path(rel).name + ".before")).read_bytes()
    new_raw = (ROOT / rel).read_bytes()
    old, new = top(old_raw.decode("utf-8-sig")), top(new_raw.decode("utf-8-sig"))
    changed = sorted(name for name in old.keys() & new.keys() if old[name] != new[name])
    added, removed = sorted(new.keys() - old.keys()), sorted(old.keys() - new.keys())
    if rel.endswith("intake.py"):
        assert changed == [] and removed == [], (changed, removed)
        assert added == ["_expand_receipt_range", "_plan_receipt_range_rewrite", "normalize_receipt_ranges"], added
    else:
        assert changed == ["_source", "main"] and added == [] and removed == [], (changed, added, removed)
    rows.append({"path": rel, "before_sha256": hashlib.sha256(old_raw).hexdigest(),
                 "after_sha256": hashlib.sha256(new_raw).hexdigest(),
                 "common_definition_changes": changed, "added": added, "removed": removed})
old_effect = json.loads((DEST / "COMMAND_EFFECTS.json.before").read_text(encoding="utf-8-sig"))
new_effect = json.loads((ROOT / "saipen/COMMAND_EFFECTS.json").read_text(encoding="utf-8-sig"))
old_effect["verbs"]["source"]["subcommands"]["normalize"] = "RECOVERY"
assert old_effect == new_effect
record = {"ok": True, "production": rows, "effect_delta": "only source.normalize=RECOVERY"}
(DEST / "scope-review.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps(record))
