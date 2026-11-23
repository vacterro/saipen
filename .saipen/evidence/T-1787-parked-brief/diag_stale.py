"""Read-only: which regression-execution input moved since the recorded pair."""

import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
record = Path(sys.argv[2])
sys.path.insert(0, str(root / "tools"))

from saipen_engine import regression_execution as rx  # noqa: E402

value = json.loads((root / record).read_text(encoding="utf-8"))
material = rx._load(root, root / value["contract_path"])
checks = {
    "verifier": (material["verifier"], value["after"]["verifier"]),
    "contract_sha256": (rx._sha(material["contract_raw"]), value.get("contract_sha256")),
    "before_subject": (rx._sha(rx._json(rx._manifest(material["prior"]))), value["before"]["subject"]),
    "context_digest": (rx._sha(rx._json(rx._manifest(material["context"]))), value["context_digest"]),
    "after_subject": (rx._sha(rx._json(rx._manifest(material["current"]))), value["after"]["subject"]),
}
for name, (now, then) in checks.items():
    print(f"{name}: {'same' if now == then else 'MOVED'} now={str(now)[:16]} recorded={str(then)[:16]}")

if checks["context_digest"][0] != checks["context_digest"][1]:
    manifest = rx._manifest(material["context"])
    print("context entries now:", len(manifest) if hasattr(manifest, "__len__") else type(manifest))
