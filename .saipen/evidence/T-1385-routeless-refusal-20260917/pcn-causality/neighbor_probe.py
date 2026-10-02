"""Two PCN shapes the causality proof exposed that T-1385 does NOT own.

Run on current bytes, against a started fixture, through the same
`guard_events.evaluate_event` path the OpenCode adapter spawns:

1. scratch asymmetry: the write tool may create `.saipen/kitchen/<file>`, and
   the shell may then neither run nor delete that file (T-1385 smoke,
   long_file_task, calls QW1971 and GI5745);
2. checkpoint prose: `saipen checkpoint RUN T-1 '<text>'` is not in the guard's
   canonical grammar (quoted payloads are admitted for start/user-request
   only), so it is judged as an ordinary shell line, and a text that mentions
   `.saipen` is refused PROTECTED_CANONICAL_NAMESPACE (T-1380 re-run,
   windows_path_task, three reworded checkpoints).

    python neighbor_probe.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[4] / "tools"
sys.path.insert(0, str(TOOLS))

import test_t1363_zero_manual_entry as fixtures  # noqa: E402
from saipen_engine import guard_events  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402


class _Case:
    def addCleanup(self, *_args, **_kwargs):
        return None


def verdict(root: Path, tool: str, tool_input: dict) -> dict:
    event = {
        "event": "before_tool",
        "host": "opencode",
        "cwd": str(root),
        "tool_name": tool,
        "tool_input": tool_input,
        "session_id": "ses_probe",
    }
    return guard_events.evaluate_event(guard_events.load_event(json.dumps(event)), None)


def main() -> int:
    isolate_host_session()
    root = Path(fixtures.healthy(_Case()))
    code, payload, text = fixtures.cli(root, "start", "add a docstring to src/app.py", "--json")
    assert code == 0 and payload["code"] == "STARTED", text
    script = root / ".saipen" / "kitchen" / "review_check.py"
    probes = [
        ("write", {"filePath": str(script), "content": "print('ok')\n"}),
        ("bash", {"command": f'python "{script}"'}),
        ("bash", {"command": f'Remove-Item -LiteralPath "{script}"'}),
        ("bash", {"command": "saipen checkpoint RUN T-1 'src/app.py and .saipen memory'"}),
        ("bash", {"command": "saipen checkpoint RUN T-1 'diff limited to src/app.py'"}),
    ]
    for tool, tool_input in probes:
        seen = verdict(root, tool, tool_input)
        shown = tool_input.get("command") or f"{tool} {tool_input.get('filePath')}"
        print(
            f"{tool:5} admitted={seen.get('admitted')!s:5} code={seen.get('code')} "
            f"action={(seen.get('event') or {}).get('action')} "
            f"route={seen.get('canonical_next_command')} :: {shown}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
