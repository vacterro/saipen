import json
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "tools"))
import audit_checks as A

cases = [case for case in A.CASES if case[0] == "portable project identity becomes an external symlink"]
assert len(cases) == 1
lines = []
with tempfile.TemporaryDirectory(prefix="t1582-live-control-") as temporary:
    context = A.ProbeContext(Path(temporary), cases, frozenset({".saipen/IDENTITY.md"}))
    probe = A.Probe("owned-symlink-case", A.mutation_sweep_probe, "owned symlink case proven",
                    requires=("validator-baseline",))
    selected = [p for p in A.always_on_probes()
                if p.name in ("pristine-fixture", "validator-baseline")]
    assert len(selected) == 2
    verdicts = A.run_probes((*selected, probe), context, out=lines.append)
proof = {"scope": "one existing owned symlink mutation case; not the full audit",
         "verdicts": verdicts, "output": lines}
path = root / ".saipen/evidence/T-1582-sweep-live-control-20261001.json"
path.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
print(json.dumps(proof, indent=2))
sys.exit(0 if verdicts["owned-symlink-case"] in ("PASS", "UNPROVEN") else 1)
