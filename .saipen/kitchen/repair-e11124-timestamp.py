"""Bounded CORE.md LOG timestamp repair through the journaled SAIOPS layer.

Only E-11124's known accidental 14:54 stamp may change. Its original bytes
are preserved, and the DEC names the inherited upper bound, never a measured
execution time. Run without --apply to inspect the immutable plan.
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine import operations as ops
from saipen_engine.log import parse_log_line
from saipen_engine.result import Result
from saipen_engine.plan import TargetPlan
from saipen_engine.journal import hash_bytes
from saipen_engine.state import patch_state


def main():
    snapshot = ops._read(ROOT)
    docs, state, _board, _tail = snapshot
    original = docs["log"].text_norm
    lines = original.splitlines(keepends=True)
    matches = [i for i, line in enumerate(lines) if "[E-11124]" in line]
    if len(matches) != 1:
        raise ValueError("E-11124 is not unique in the active LOG")
    position = matches[0]
    event = parse_log_line(lines[position])
    successor = parse_log_line(lines[position + 1])
    if not event or event["event"] != 11124 or not successor or successor["event"] != 11125:
        raise ValueError("The known E-11124 -> E-11125 evidence pair changed")
    old = "- 01.10.26 14:54 "
    new = "- 01.10.26 11:54 "
    if not lines[position].startswith(old) or not lines[position + 1].startswith(new):
        raise ValueError("The known original stamp or successor upper bound changed")
    lines[position] = new + lines[position][len(old):]
    repaired = "".join(lines)
    now, utc = ops._now(), ops._utc_iso()
    actor = state["agent"]
    op_id = "checkpoint-" + ops.uuid4_hex()
    evidence = f".saipen/recovery/timestamp-repair/{op_id}/LOG.md"
    original_bytes = (ROOT / ".saipen/LOG.md").read_bytes()
    digest = hashlib.sha256(original_bytes).hexdigest()
    if digest[:16] != docs["log"].raw_hash:
        raise ValueError("The LOG changed after the frozen snapshot")
    preserved = TargetPlan(evidence, "generic", original_bytes, "", hash_bytes(original_bytes))

    def mutate(text, event_id):
        return patch_state(text, {"last_event": event_id, "updated": utc, "agent": actor})

    plan = ops._state_only_plan(
        ROOT, "checkpoint", actor, mutate,
        "observed historical timestamp inversions -- repaired E-11124 accidental future stamp "
        "01.10.26 14:54 -> 01.10.26 11:54 UTC, inherited upper bound from successor E-11125 "
        "rather than measured execution time; original LOG preserved at " + evidence
        + " sha256:" + digest,
        {"ok": True, "code": "CHECKPOINTED", "timestamp_repair": "E-11124",
         "evidence_path": evidence, "evidence_sha256": digest},
        now, utc, {"last_event", "updated", "agent"},
        ticket_id=state.get("task"), extra_targets=[preserved], op_id=op_id,
        read_once=snapshot, log_text=repaired, repair=True,
    )
    if isinstance(plan, Result):
        result = plan
    elif "--apply" in sys.argv:
        result = ops.apply_plan(ROOT, plan)
    else:
        result = ops._render_plan(plan)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
