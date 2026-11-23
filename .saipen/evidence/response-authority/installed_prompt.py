"""A standalone installed Claude prompt probe; it grants no admission."""

from pathlib import Path
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
DEST = Path(__file__).parent / "installed-dogfood"
sys.path.insert(0, str(ROOT / "tools"))

from install_host_guard import install
from test_codex_stop_hook import wait_project
from test_hermetic_env import isolate_host_session


def main():
    isolate_host_session()
    observed = install("claude", Path.home(), ROOT, check=True)
    assert observed["current"] and observed["configured"], observed
    event = {
        "hook_event_name": "UserPromptSubmit",
        "session_id": "installed-claude-prompt-no-authority-grant",
        "cwd": str(wait_project()),
        "prompt": "saipen status",
    }
    run = subprocess.run(
        [sys.executable, "-B", observed["artifact"], "--host", "claude", "--saipen-root", str(ROOT)],
        input=json.dumps(event).encode("utf-8"),
        capture_output=True,
        timeout=90,
        env={k: v for k, v in os.environ.items() if not k.startswith("SAIPEN_")},
    )
    result = {
        "kind": "installed-standalone-synthetic-prompt",
        "event": event,
        "installation": observed,
        "returncode": run.returncode,
        "stdout": run.stdout.decode("utf-8", errors="replace"),
        "stderr": run.stderr.decode("utf-8", errors="replace"),
        "admission_granted": False,
        "live_host_execution": "NOT_PROVEN",
    }
    (DEST / "claude-prompt.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    verdict = json.loads(result["stdout"])
    assert run.returncode == 0 and verdict.get("decision") == "block", result
    assert "ADMISSION REFUSED" in verdict.get("reason", ""), result
    print(json.dumps({"ok": True, "decision": verdict["decision"], "record": str(DEST / "claude-prompt.json")}))


if __name__ == "__main__":
    main()
