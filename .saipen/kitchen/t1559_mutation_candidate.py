"""Same mutation-sweep oracle before and after the bounded STYLE restoration."""
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import audit_checks as audit
from saipen_engine.state import patch_state, style_contract_token

labels = {"SKILL drops the reply-language precedence", "STYLE drops persistent caveman voice"}
cases = [case for case in audit.CASES if audit.case_parts(case)[0] in labels]
if len(cases) != 2:
    raise RuntimeError("STYLE mutation controls changed: " + repr([audit.case_parts(c)[0] for c in cases]))
out = ROOT / ".saipen/evidence/T-1559-style-candidate"
updated = (out / "STYLE.md").read_text(encoding="utf-8")
records = []
with tempfile.TemporaryDirectory(prefix="saipen-t1559-mutation-") as temporary:
    for label in ("original", "candidate"):
        folder = Path(temporary) / label
        folder.mkdir()
        context = audit.ProbeContext(folder, cases, None)
        setup = audit.build_pristine(context)
        if setup:
            raise RuntimeError(setup)
        if label == "candidate":
            (context.pristine / "saipen/STYLE.md").write_text(updated, encoding="utf-8", newline="")
            state_path = context.pristine / ".saipen/STATE.md"
            state_path.write_text(patch_state(state_path.read_text(encoding="utf-8"), {
                "style_contract": style_contract_token(updated),
            }), encoding="utf-8", newline="")
        baseline = audit.validator_baseline_probe(context)
        if baseline:
            raise RuntimeError("invalid " + label + " control: " + baseline)
        error = audit.mutation_sweep_probe(context)
        records.append({"variant": label, "baseline": "PASS", "ran": len(cases),
                        "verdict": "FAIL" if error else "PASS", "error": error})
record = {"scope": "the two owned STYLE/SKILL mutation controls only", "controls": records,
          "oracle_sha256": hashlib.sha256((ROOT / "tools/audit_checks.py").read_bytes()).hexdigest()}
(out / "mutation-controls.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps(record))
sys.exit(0 if records[0]["verdict"] == "FAIL" and records[1]["verdict"] == "PASS" else 1)
