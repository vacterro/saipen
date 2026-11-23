"""Preserve exact source and a stable read-only consumer checkpoint snapshot."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[3]
evidence = Path(__file__).resolve().parent
consumer = root.parent.parent / "__SAITULS"
files = {
    "audit.md": root / "audit" / "SAIHANDOFF_AGENT_PROTOCOL_DRIFT_AUDIT.md",
    "receipt.md": root / ".saipen" / "intake" / "active" / "SRC-197.md",
    "consumer-STATE.md": consumer / ".saipen" / "STATE.md",
    "consumer-BOARD.md": consumer / ".saipen" / "BOARD.md",
}
content = {name: path.read_bytes() for name, path in files.items()}
if any(path.read_bytes() != content[name] for name, path in files.items()):
    raise ValueError("source changed during snapshot; no evidence written")
if content["audit.md"] != content["receipt.md"]:
    raise ValueError("captured audit body differs from the requested file")
expected = "df983dc9ba85b05cba06672a3ae516f4d553aad0874a79bbd99fb6525f35cfa9"
if hashlib.sha256(content["audit.md"]).hexdigest() != expected:
    raise ValueError("audit generation moved")
snapshot = evidence / "snapshot"
snapshot.mkdir(exist_ok=True)
rows = []
for name, blob in content.items():
    (snapshot / name).write_bytes(blob)
    rows.append({"name": name, "origin": str(files[name]), "bytes": len(blob),
                 "sha256": hashlib.sha256(blob).hexdigest()})
(evidence / "snapshot.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
print(json.dumps(rows, indent=2))
