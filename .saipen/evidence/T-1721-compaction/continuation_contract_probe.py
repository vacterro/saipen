"""Observe complete current contracts and refusal without lifecycle writes."""

import datetime
import hashlib
import json
import sys
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent
PROTOCOL = EVIDENCE.parents[2]
sys.path.insert(0, str(PROTOCOL / "tools"))

from saipen_engine import acceptance_contract, operations


def canonical_hashes(root):
    return {
        name: hashlib.sha256((root / ".saipen" / name).read_bytes()).hexdigest()
        for name in ("STATE.md", "BOARD.md", "LOG.md", "IDENTITY.md")
    }


observations = []
for root, work, expected_count in (
    (PROTOCOL, "T-1719", 9),
    (Path("V:/___VAC/__K/__CODE/_PY/_AUDAPACK_RECOVERY_20261010"), "T-2", 6),
):
    before = canonical_hashes(root)
    docs, state, board, _tail = operations._read(root)
    visible = board["tickets"][work]["fields"]["verify"]
    bindings = {}
    complete = acceptance_contract.resolve(root, work, visible, bindings)
    criteria = acceptance_contract.specs(complete)
    assert len(criteria) == expected_count, (work, list(criteria))
    _compatible, chain = acceptance_contract._chain(
        root, work, complete, docs["_history"].events, bindings
    )
    refusal = operations._acceptance_gate(docs, work)
    assert refusal is not None, (work, "unfinished outcomes must still refuse")
    after = canonical_hashes(root)
    assert before == after, (work, "canonical bytes changed during observation")
    observations.append({
        "root": str(root),
        "work": work,
        "phase": state["phase"],
        "state_task": state["task"],
        "visible_criteria": len(acceptance_contract.specs(visible)),
        "complete_criteria": len(criteria),
        "criteria": criteria,
        "contract_sha256": acceptance_contract.digest(complete),
        "journal_contracts": len(chain),
        "current_refusal": refusal,
        "authority_bindings": bindings,
        "canonical_hashes": before,
        "canonical_unchanged": True,
    })

result = {
    "observed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "compaction_resolution": "PASS",
    "product_completion": "NOT_CLAIMED",
    "observations": observations,
}
output = EVIDENCE / "continuation-contracts.json"
output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({
    "compaction_resolution": result["compaction_resolution"],
    "product_completion": result["product_completion"],
    "observations": [
        {key: row[key] for key in (
            "work", "visible_criteria", "complete_criteria", "journal_contracts",
            "current_refusal", "canonical_unchanged",
        )}
        for row in observations
    ],
    "evidence": str(output),
}))
