"""Re-derive each session's refusal metrics from the host's OWN stored parts.

The sessions are not re-run: OpenCode's session store (read-only) still holds
every tool part, so the corrected extractor can be applied to exactly the
transcript the original measurement read. Prints recorded vs re-derived per
session and marks every session whose verdict changed.

    python rederive_measurements.py <polygon.json> [<polygon.json> ...]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools"))

import t1363_field_polygon as polygon  # noqa: E402


def main() -> int:
    changed = 0
    for path in sys.argv[1:]:
        report = json.loads(Path(path).read_text(encoding="utf-8"))
        print(f"== {Path(path).name}")
        for record in report["sessions"]:
            if record.get("measurement") != polygon.MEASURED:
                print(f"   {record['condition']:<22} {record.get('measurement')} (not re-derived)")
                continue
            parts = polygon._host_store_parts(
                Path(record["project"]), 0, record.get("session_id")
            )
            if not parts:
                print(f"   {record['condition']:<22} host store has no parts (not re-derived)")
                continue
            seen = polygon.measure(polygon._part_tool_events(parts), measured=True)
            before = (record.get("refusal_sequence"), record.get("repeated_refusal"))
            after = (seen["refusal_sequence"], seen["repeated_refusal"])
            mark = "   <-- changed" if before != after else ""
            changed += 1 if mark else 0
            print(
                f"   {record['condition']:<22} recorded repeated={before[1]} "
                f"re-derived repeated={after[1]}{mark}"
            )
            if mark:
                print(f"      recorded   refusals={before[0]}")
                print(f"      re-derived refusals={after[0]}")
    print(f"sessions whose metrics changed under the current extractor: {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
