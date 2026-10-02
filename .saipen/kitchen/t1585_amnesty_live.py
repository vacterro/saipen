import json
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "tools"))
import audit_checks as A

cases = [case for case in A.CASES if case[0] == "an amnesty demoted to prose stops suppressing"]
assert len(cases) == 1
lines = []
with tempfile.TemporaryDirectory(prefix="t1585-amnesty-live-") as temporary:
    context = A.ProbeContext(Path(temporary), cases, frozenset({".saipen/LOG.md"}))
    probe = A.Probe("owned-amnesty-case", A.mutation_sweep_probe, "owned amnesty case proven",
                    requires=("validator-baseline",))
    selected = [p for p in A.always_on_probes()
                if p.name in ("pristine-fixture", "validator-baseline")]
    verdicts = A.run_probes((*selected, probe), context, out=lines.append)
proof = {"scope": "one current amnesty mutation against the real validator; not the full audit",
         "verdicts": verdicts, "output": lines}
(root / ".saipen/evidence/T-1585-amnesty-live-20261001.json").write_text(
    json.dumps(proof, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(proof, indent=2))
sys.exit(0 if verdicts["owned-amnesty-case"] == "PASS" else 1)
