"""Evaluate ordinary observations and one proposed write without executing them."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(r"V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN")
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import guard_events

projects = {
    "SAIPEN": ROOT,
    "AUDAPACK": Path(r"V:\___VAC\__K\__CODE\_PY\_AUDAPACK"),
    "PROBLIP": Path(r"V:\___VAC\__K\__CODE\_PY\_PROBLIP"),
}
results = []
for name, root in projects.items():
    paths = [root / ".saipen" / file for file in ("STATE.md", "BOARD.md", "LOG.md")]
    before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    for command in (
        "saipen status --json",
        "saipen permissions --json",
        "saipen explain-next --json",
        "node --version",
        "python --version",
    ):
        event = {
            "event": "before_tool", "host": "opencode", "cwd": str(root),
            "tool_name": "bash", "tool_input": {"command": command},
        }
        verdict = guard_events.evaluate_event(event)
        results.append({"project": name, "command": command, "verdict": verdict})
    proposed = root / "src086-proposed-write-only.txt"
    verdict = guard_events.evaluate_event({
        "event": "before_tool", "host": "opencode", "cwd": str(root),
        "tool_name": "write", "tool_input": {"file_path": str(proposed)},
    })
    results.append({"project": name, "command": "PROPOSED_WRITE_NOT_EXECUTED", "verdict": verdict})
    after = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    results.append({"project": name, "canonical_memory_unchanged": before == after})

out = Path(__file__).with_name("admission-observations.json")
out.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
for row in results:
    verdict = row.get("verdict")
    if verdict is None:
        print(json.dumps(row))
    else:
        print(json.dumps({
            "project": row["project"], "command": row["command"],
            "admitted": verdict.get("admitted"), "code": verdict.get("code"),
            "action": verdict.get("action"), "command_class": verdict.get("command_class"),
        }))
