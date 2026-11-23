"""Record this Work's failed correction through the canonical checkpoint plan."""
from dataclasses import replace
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import codec, operations, plan
from saipen_engine.board import parse_board, set_ticket_field
from saipen_engine.result import Result

doc = codec.read_checkpoint_doc(ROOT, "BOARD.md")
ticket = parse_board(doc.text_norm)["tickets"]["T-1606"]
assert ticket["section"] == "## DOING"
assert ticket["fields"]["owner"] == "saipen-cli"
assert ticket["fields"].get("verify_attempts") == "1", "unexpected correction count"
prepared = operations._plan_checkpoint(
    ROOT, "saipen-cli", "RUN", "T-1606",
    "VERIFY accounting: verify_attempts 1->2 at the retry cap; current whole family 4908 ran "
    "and 7 new red, no leaked sandboxes. Preserve this candidate and restore only owned "
    "partial edits before another Work. The direct Unicode line-separator writer mismatch "
    "is also reproduced; no PASS or source closure is claimed.",
    operations._now(), operations._utc_iso(),
)
if isinstance(prepared, Result):
    raise SystemExit(json.dumps(prepared.to_dict()))
targets = []
found = False
for target in prepared.targets:
    if target.path == ".saipen/BOARD.md":
        found = True
        staged = codec.read_document(ROOT / target.path, raw=target.content)
        raw = parse_board(staged.text_norm)["tickets"]["T-1606"]["raw"]
        assert staged.text_norm.count(raw) == 1
        updated = staged.text_norm.replace(raw, set_ticket_field(raw, "verify_attempts", "2"), 1)
        targets.append(operations._target(doc, target.path, target.role, updated))
    else:
        targets.append(target)
assert found, "checkpoint did not own the current ticket's BOARD lease"
request = {
    **prepared.semantic_request, "owned_retry_ticket": "T-1606",
    "owned_retry_field": "verify_attempts", "before_attempts": 1, "after_attempts": 2,
}
owned = replace(
    prepared, targets=tuple(targets), semantic_request=request,
    semantic_payload_hash=plan.semantic_payload_hash(request),
)
result = plan.apply_plan(ROOT, owned)
print(json.dumps(result.to_dict()))
raise SystemExit(0 if result.ok else 1)
