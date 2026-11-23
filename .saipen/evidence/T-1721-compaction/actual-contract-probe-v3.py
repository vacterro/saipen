"""Read-only actual acceptance admission on two intact compacted contracts."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOME = HERE.parents[2]
sys.path.insert(0, str(HOME / "tools"))
from saipen_engine import acceptance_contract, operations
from saipen_engine.board import parse_board
from saipen_engine.board_compaction import resolve_detail

output = HERE / "compaction-probe-v3.json"
assert not output.exists()
rows = []
for root, work in [(HOME, "T-1719"), (Path("V:/___VAC/__K/__CODE/_PY/_AUDAPACK_RECOVERY_20261010"), "T-2")]:
    def protected():
        return {name: hashlib.sha256((root / ".saipen" / name).read_bytes()).hexdigest()
                for name in ("STATE.md", "BOARD.md", "LOG.md", "IDENTITY.md")}
    before = protected()
    docs, state, board, tail = operations._read(root)
    ticket = board["tickets"][work]
    visible = ticket["fields"]["verify"]
    detail = resolve_detail(root, ticket["fields"]["detail_ref"], expected_ticket_id=work)
    restored = parse_board("## TODO\n" + detail["original_record"].decode("utf-8") + "\n")
    full = restored["tickets"][work]["fields"]["verify"]
    full_chain_error = None
    try:
        compatible, chain = acceptance_contract._chain(root, work, full, docs["_history"].events, {})
    except ValueError as error:
        full_chain_error = str(error)
        chain = []
    actual = operations._acceptance_gate(docs, work)
    assert before == protected()
    rows.append({"root": str(root), "work": work, "state": state,
                 "visible_criteria": len(acceptance_contract.specs(visible)),
                 "preserved_criteria": len(acceptance_contract.specs(full)),
                 "full_journal_chain_positive": full_chain_error is None,
                 "full_journal_chain_error": full_chain_error, "committed_contract_count": len(chain),
                 "native_acceptance_gate_error": actual, "canonical_unchanged": True,
                 "detail_sha256": detail["sha256"],
                 "meaning": "Actual current native result; compare preserved criteria and journal chain without assuming a failure class."})
output.write_text(json.dumps({"observations": rows, "production_changed": False}, indent=2) + "\n", encoding="utf-8")
print(json.dumps(rows))

