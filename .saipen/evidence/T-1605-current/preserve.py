"""Preserve exact pre-recovery production bytes without changing the subject."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
paths = ("tools/saipen_engine/operations.py", "tools/saipen.py",
         "saipen/COMMANDS.md", "saipen/OPS.md")
receipt = {}
for rel in paths:
    source = ROOT / rel
    data = source.read_bytes()
    target = HERE / "before" / rel
    if target.exists():
        assert target.read_bytes() == data, rel
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    receipt[rel] = hashlib.sha256(data).hexdigest()
(HERE / "before.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt))
