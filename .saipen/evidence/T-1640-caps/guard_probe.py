"""How does the guard judge `saipen clean` typed in a shell, by project state?"""
import json
import sys
from pathlib import Path

TOOLS = Path(sys.argv[1]) / "tools"
sys.path.insert(0, str(TOOLS))

from test_hermetic_env import isolate_host_session  # noqa: E402

isolate_host_session()

from test_guard_hostile_matrix import (  # noqa: E402
    GuardEventHarness,
    active_project,
    fresh_project,
)

cases = {
    "DONE, no ticket": fresh_project(),
    "CLEAN, no ticket": fresh_project(phase="CLEAN", next_action="PHASE CLEAN"),
    "BUILD, own ticket": active_project(),
}
for label, root in cases.items():
    for command in ("saipen transition CLEAN", "bin/saipen transition CLEAN", "saipen translate", "saipen transition DONE"):
        code, data = GuardEventHarness.run(
            GuardEventHarness.tool_event(root, "bash", {"command": command})
        )
        event = data.get("event") or {}
        print(
            f"{label:18s} {command:18s} exit={code} admitted={data.get('admitted')} "
            f"action={event.get('action')} code={data.get('code')} "
            f"detail={str(data.get('detail') or data.get('reason') or '')[:110]}"
        )
