"""Read-only admission and routing counterexample. No authority is synthesized."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine import goal_authority, operator_task, state  # noqa: E402
from saipen_engine.audit_inbox import projection  # noqa: E402
from saipen_engine.audit_route import route_violation  # noqa: E402
from saipen_engine.board import parse_board  # noqa: E402
from saipen_engine.journal import scan_pending  # noqa: E402
from saipen_engine.log import read_history_snapshot  # noqa: E402
from saipen_engine.reconcile import _derived_goal_counters  # noqa: E402
from saipen_engine.router import route_next  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    protected = (
        ".saipen/STATE.md", ".saipen/BOARD.md", ".saipen/LOG.md",
        ".saipen/evidence/T-1703-host-truth/REPORT.md",
        ".saipen/evidence/T-1703-host-truth/cap-audit-conflict.json",
        "tools/saipen_engine/goal_authority.py", "tools/saipen_engine/operations.py",
        "tools/saipen_engine/router.py", "tools/saipen_engine/audit_route.py",
        "tools/saipen_engine/state.py", "tools/validate.py",
    )
    before = {name: sha(ROOT / name) for name in protected}
    state_text = (ROOT / ".saipen/STATE.md").read_text(encoding="utf-8")
    board_text = (ROOT / ".saipen/BOARD.md").read_text(encoding="utf-8")
    current = state.parse_state(state_text)
    board = parse_board(board_text)
    inbox = projection(ROOT)
    pending, conflicts = scan_pending(ROOT)
    routed = route_next(
        state_text, board_text, pending_ops=pending, conflict_ops=conflicts,
        current_agent=current["agent"], audit_inbox=inbox,
    )
    doing = [key for key, value in board["tickets"].items()
             if value["section"] == "## DOING"]

    def violation(action: str):
        return route_violation(
            inbox, action, doing, tickets=board["tickets"], agent=current["agent"],
        )

    actual_violation = violation(current["next_action"])
    history = read_history_snapshot(ROOT, lean=True)
    status = subprocess.run(
        ["git", "-c", "core.safecrlf=false", "status", "--porcelain=v1", "--branch"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True,
    )
    evidence = {
        "project_root": str(ROOT),
        "git_status_command": "git -c core.safecrlf=false status --porcelain=v1 --branch",
        "git_status_exit_code": status.returncode,
        "checkpoint": current,
        "derived_counters": _derived_goal_counters(history.events),
        "pending_operations": pending,
        "conflicts": conflicts,
        "ingress_authority": operator_task.authority_for_receipt(ROOT, "SRC-206"),
        "declared_operator_carrier": operator_task.declared(),
        "persistent_authority": goal_authority.persistent(current),
        "binding_brake": state.binding_brake(current),
        "audit_projection": inbox,
        "router": routed,
        "audit_validator_violation": actual_violation,
        "controls": {
            "active_review_continuation_accepted": violation("PHASE REVIEW T-1703") is None,
            "scope_wait_refused": violation("WAIT: scope selection -- choose an audit") is not None,
            "pending_ingestion_accepted": violation("saipen audit ingest") is None,
        },
        "protected_sha256": before,
        "protected_bytes_unchanged": before == {name: sha(ROOT / name) for name in protected},
        "regression_green": actual_violation is None,
        "disposition": "Diagnostic only; canonical bounded WAIT remains binding.",
    }
    out = Path(__file__).resolve().parent
    (out / "counterexample.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    (out / "dirty-files.txt").write_text(status.stdout, encoding="utf-8")
    print(json.dumps({
        "regression": "RED" if actual_violation else "GREEN",
        "phase": current["phase"], "ticket": current["task"],
        "counters": evidence["derived_counters"],
        "pending_operations": len(pending), "conflicts": len(conflicts),
        "persistent_authority": evidence["persistent_authority"],
        "operator_carrier": evidence["declared_operator_carrier"],
        "protected_bytes_unchanged": evidence["protected_bytes_unchanged"],
        "controls": evidence["controls"],
    }, indent=2))
    return 1 if actual_violation else 0


if __name__ == "__main__":
    raise SystemExit(main())
