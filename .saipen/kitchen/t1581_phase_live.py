import hashlib
import json
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "tools"))
import audit_checks as A

proof_file = root / ".saipen/evidence/T-1580-project-binding-20261001.md"
original = proof_file.read_bytes()
lines = []
with tempfile.TemporaryDirectory(prefix="t1581-phase-live-") as temporary:
    context = A.ProbeContext(Path(temporary), [], None)
    probes = [p for p in A.always_on_probes() if p.name in ("pristine-fixture", "phase-rename")]
    verdicts = A.run_probes(probes, context, out=lines.append)
assert proof_file.read_bytes() == original
proof = {"scope": "actual whole-tree phase rename probe, not the full audit",
         "verdicts": verdicts, "output": lines,
         "live_retirement_proof_sha256": hashlib.sha256(original).hexdigest()}
(root / ".saipen/evidence/T-1581-phase-live-20261001.json").write_text(
    json.dumps(proof, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(proof, indent=2))
sys.exit(0 if verdicts.get("phase-rename") == "PASS" else 1)
