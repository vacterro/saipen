"""Which documented phase verbs does the guard admit from a shell, by state?"""
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
    "DONE, no Work": fresh_project(),
    "BUILD, own Work": active_project(),
}
commands = (
    "saipen clean", "saipen translate", "saipen hunt", "saipen markhunt", "saipen plan",
    "saipen validate", "saipen transition CLEAN", "saipen transition TRANSLATE",
)
for label, root in cases.items():
    for command in commands:
        code, data = GuardEventHarness.run(
            GuardEventHarness.tool_event(root, "bash", {"command": command})
        )
        event = data.get("event") or {}
        detail = str(data.get("detail") or data.get("reason") or "")[:120]
        print(
            f"{label:16s} {command:28s} admitted={data.get('admitted')!s:5s} "
            f"action={event.get('action')!s:9s} code={data.get('code')} :: {detail}"
        )
