"""T-1751 SCOUT probe: do status, continue, recover, start and the digest agree
when recovery needs ONE operator approval?

Builds a disposable project whose only defect is a phantom `## DONE` row (no
closure_mode, owner, claim_time or verification evidence) beside a legal DOING
ticket, then asks every operator-facing surface of the live engine. Writes only
under its own temporary directory; prints one JSON document.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))

from saipen_engine.paths import identity_file_content, new_project_lineage  # noqa: E402
from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402

STATE = (
    "---\n"
    "phase: BUILD\n"
    "task: T-9000\n"
    'next_action: "PHASE BUILD T-9000"\n'
    'blocker: ""\n'
    "transition_from: SCOUT\n"
    "saipen_version: 8\n"
    "schema_version: 3\n"
    "last_event: 102\n"
    "style_contract: " + CURRENT_STYLE_CONTRACT + "\n"
    "mode: full\n"
    "updated: 2026-09-15T00:00:00Z\n"
    "agent: test-agent\n"
    "---\n"
)
BOARD = (
    "## DOING\n"
    "- [/] T-9000 legal active work | verify: resume | owner: test-agent"
    " | claim_time: 2026-09-15T00:00:00Z\n"
    "## TODO\n"
    "## DONE\n"
    "- [x] T-9003 phantom done | verify: reopened without evidence\n"
    "## BLOCKED\n"
)
LOG = (
    "- 15.09.26 00:00 [E-098] [T-9000] [agent: test-agent] "
    "[op: ticket-00000000000000000000000000000000] DEC: ticket added via SAIOPS\n"
    "- 15.09.26 00:00 [E-099] [T-9003] [agent: test-agent] "
    "[op: ticket-00000000000000000000000000000003] DEC: ticket added via SAIOPS\n"
    "- 15.09.26 00:00 [E-100] [parent: E-099] [T-9000] [agent: test-agent] "
    "[op: claim-00000000000000000000000000000004] DEC: claimed via SAIOPS -- owner test-agent\n"
    "- 15.09.26 00:00 [E-101] [parent: E-100] [T-9000] [agent: test-agent] "
    "[op: transition-00000000000000000000000000000005] RUN: transition to SCOUT\n"
    "- 15.09.26 00:00 [E-102] [parent: E-101] [T-9000] [agent: test-agent] "
    "[op: transition-00000000000000000000000000000006] RUN: transition to BUILD\n"
)


def run(root: Path, *args: str) -> dict:
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.upper().startswith("SAIPEN") and k != "CLAUDE_CONFIG_DIR"
    }
    env["PYTHONUTF8"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", str(TOOLS / "saipen.py"), "--project-root", str(root),
         "--agent", "test-agent", *args],
        capture_output=True, env=env, cwd=str(root), timeout=300, check=False,
    )
    text = proc.stdout.decode("utf-8", errors="replace")
    try:
        body = json.loads(text)
    except ValueError:
        body = {"raw": text[-1500:], "stderr": proc.stderr.decode("utf-8", "replace")[-800:]}
    return {"exit": proc.returncode, "body": body}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="saipen-t1751-") as raw:
        root = Path(raw)
        memory = root / ".saipen"
        memory.mkdir()
        (memory / "IDENTITY.md").write_text(
            identity_file_content(new_project_lineage()), encoding="utf-8"
        )
        (memory / "STATE.md").write_text(STATE, encoding="utf-8")
        (memory / "BOARD.md").write_text(BOARD, encoding="utf-8")
        (memory / "LOG.md").write_text(LOG, encoding="utf-8")
        before = {p: (memory / p).read_bytes() for p in ("STATE.md", "BOARD.md", "LOG.md")}
        status = run(root, "status", "--json")
        cont = run(root, "continue", "--json")
        recover = run(root, "recover", "--json")
        start = run(root, "start", "probe task", "--json", "--dry-run")
        digest = subprocess.run(
            [sys.executable, "-B", str(TOOLS / "saipen.py"), "response", "digest",
             "--project-root", str(root), "--reason", "status"],
            capture_output=True, timeout=300, check=False,
            env={k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")},
        )
        after = {p: (memory / p).read_bytes() for p in ("STATE.md", "BOARD.md", "LOG.md")}
        auto = (status["body"] or {}).get("automation") or {}
        print(json.dumps({
            "status": {"exit": status["exit"], "automation": auto,
                       "computed_next_action": status["body"].get("computed_next_action")},
            "continue": {"exit": cont["exit"],
                         **{k: cont["body"].get(k) for k in ("action", "reason", "code")}},
            "recover": {"exit": recover["exit"],
                        **{k: recover["body"].get(k) for k in
                           ("code", "operator_decision_available", "canonical_next_command")}},
            "start_dry_run": {"exit": start["exit"],
                              **{k: start["body"].get(k) for k in ("code", "next", "detail")}},
            "digest": digest.stdout.decode("utf-8", "replace"),
            "canonical_bytes_unchanged": before == after,
        }, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
