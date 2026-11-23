"""Extract and integrity-check only the immutable XP receipt's source bytes."""
import ast
import base64
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEST = Path(__file__).resolve().parent
xp = ROOT / ".saipen/exchange/xpatch/XP-000001"
payload = json.loads((xp / "payload.json").read_text(encoding="utf-8-sig"))
intent = json.loads((xp / "intent.json").read_text(encoding="utf-8-sig"))
for rel, encoded in payload["contents"].items():
    raw = base64.b64decode(encoded, validate=True)
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == intent["paths"][rel]["after_sha256"], rel
    target = DEST / (Path(rel).name + ".xp.txt")
    target.write_bytes(raw)
    print(json.dumps({"path": rel, "sha256": digest, "bytes": len(raw)}))
    text = raw.decode("utf-8-sig")
    lines = text.splitlines()
    if rel.endswith("saipen.py"):
        for number, line in enumerate(lines, 1):
            if 'sub == "normalize"' in line:
                print("\n".join(f"{i + 1}: {lines[i]}" for i in range(max(0, number - 6), min(len(lines), number + 40))))
    else:
        for node in ast.parse(text).body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in {
                "normalize_receipt_ranges", "_expand_receipt_range",
                "_plan_receipt_range_rewrite", "ReceiptRangeNormalizationTests",
            }:
                print("\n".join(f"{i + 1}: {lines[i]}" for i in range(node.lineno - 1, node.end_lineno)))
