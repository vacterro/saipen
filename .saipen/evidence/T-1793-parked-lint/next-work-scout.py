"""Read-only reconnaissance of already-queued T-1790 while the family runs."""

import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / "tools"))
from saipen_engine.closure_readiness import closure_readiness

decision = closure_readiness(root, "T-1767")
result = {
    "ticket_to_repair": "T-1790",
    "observed_work": "T-1767",
    "ready": decision["ready"],
    "code": decision["code"],
    "receipt": decision["receipt"],
    "open_clauses": len(decision["unresolved"]),
    "command_chars": len(decision["canonical_next_command"] or ""),
    "command_prefix": (decision["canonical_next_command"] or "")[:100],
    "first_three": decision["unresolved"][:3],
    "writes": 0,
    "implementation_owner": "tools/saipen_engine/closure_readiness.py:106-113",
    "existing_oracle": "tools/test_t1789_child_closure_route.py",
    "next_change": "Bound the explanatory clause/owner preview; retain complete unresolved truth and the same canonical block route.",
}
Path(__file__).with_name("next-work-scout.json").write_text(
    json.dumps(result, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(result))
