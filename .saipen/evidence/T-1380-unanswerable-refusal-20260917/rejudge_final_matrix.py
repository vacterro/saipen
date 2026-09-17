"""Re-derive the final matrix's repeat metric from the host's own stored parts.

The sessions are not re-run and nothing about them changes: OpenCode's store
holds every part they produced, and this reads those bytes with the CURRENT
measurement. What changed is the metric -- T-1380 made the ATTEMPT part of a
refusal's identity, because a guard refusal is about the project's state and
reads byte-identical for every shell effect it stops, so two different commands
refused for one standing reason were scored as one refusal repeating with
nothing changed.

    python rejudge_final_matrix.py <polygon.json>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools"))

import t1363_field_polygon as polygon  # noqa: E402


def main() -> int:
    report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    changed = 0
    for session in report["sessions"]:
        parts = polygon._host_store_parts(
            Path(session["project"]), 0, session.get("session_id")
        )
        if not parts:
            print(f"{session['condition']:22s} no stored parts; recorded value kept")
            continue
        tools = polygon._part_tool_events(parts)
        fresh = polygon.measure(tools, measured=True)
        was = session.get("repeated_refusal")
        now = fresh["repeated_refusal"]
        mark = "" if was == now else "   <-- changed"
        changed += was != now
        print(f"{session['condition']:22s} recorded={was} rederived={now}{mark}")
    print(f"\nconditions whose repeat set changed under the corrected identity: {changed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
