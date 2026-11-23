"""Record completed investigation outcomes; preserve foreign unresolved verdicts."""
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
proofs = [
    "Fresh 42-event/47-operand original-evidence readback proves the original LIVE contract, its changes and E-3486 actual evidence; bounded Incident A CONFIRMED gap, no actual product LIVE PASS claimed.",
    "REPORT.md Incident A six-answer table and full original/replacement comparison remain supported by freshly read original operands; retirement authority and surviving live outcome limitations are explicit.",
    "Canonical findings E-14504/E-14505 exist and corrective native T-1718 is DONE; E-3490 original history is unchanged, Wintage product-owner live obligations remain explicit.",
    "T-1718 amendment/preimage/operator-origin/mapping enforcement plus current T-1721 full compaction resolution preserve every original outcome; unchanged measured RED/GREEN, native controls and current whole family prove the correction without retrospectively accepting T-359.",
    "All five required native control classes remain in the current 6278-test family; T-1718 genuine red preimage and current T-1721 24-test before 22 failures/after 0, equivalent retirement/supersession and ordinary implementation controls retained.",
    "Fresh native receipt and 6162-file four-scope durable search finds no E-3286 carrier with two matching positive controls; both cited files absent, event and COMMITTED receipt survive, stale location and real omission distinguished.",
    "No trustworthy original payload found in inspected scopes; incomplete integrity and canonical E-14505 retained, no reconstruction/removal/recovery write, deletion cause and external backups remain UNRESOLVED.",
    "Current whole family 6278/0, unchanged red/green, source contracts 21/21, Ruff 0.16.0 and whitespace PASS; independent native local REVIEW core CURRENT_PASS 0/10; actual consumer native FAIL 4/57 and unchanged canonical/history hashes preserved.",
    "Direct reviewed child diffs and current observers prove bounded SAIPEN protocol/evidence work; no Wintage CSS, AUDAPACK patch for this omission, historical rewrite, raw canonical edit, publication or cross-owner product acceptance.",
    "REPORT.md plus FINAL-INVESTIGATION.md deliver exact A/B verdicts, causal limits, changed symbols, contract comparison, evidence disposition, current red/green/protocol results and remaining actual operator-only product/backup decisions.",
]

rows = []
for number, proof in enumerate(proofs, 1):
    argv = [str(ROOT / "bin/saipen.cmd"), "--json", "source", "disp", "SRC-216",
            f"R{number:03d}", "VERIFIED", "--work", "T-1717",
            "--evidence", "E-14614; .saipen/evidence/T-1717-review-20261012/FINAL-INVESTIGATION.md; " + proof,
            "--verification", "Fresh read-only original/receipt/native-consumer observers; preserved child native regression and whole-family evidence; scope and truthful residual verdicts independently checked."]
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True,
                            encoding="utf-8", check=False, timeout=60)
    payload = json.loads(result.stdout)
    rows.append({"clause": f"R{number:03d}", "exit_code": result.returncode,
                 "result": payload})
    if result.returncode or not payload.get("ok"):
        raise RuntimeError(json.dumps(rows[-1]))
(HERE / "source-dispositions.json").write_text(
    json.dumps({"scope": "completed investigation, not foreign product/evidence PASS",
                "work": "T-1717", "outcomes": rows}, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"verified_investigation_clauses": len(rows),
                  "Wintage_product_LIVE": "UNPROVED", "E3286_integrity": "INCOMPLETE",
                  "Source_or_parent_Work_closed": False}))
