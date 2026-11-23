#!/usr/bin/env python3
"""SAIPEN Operator Gateway - read-only status surface.

This gateway intentionally does not mint, renew, or approve authority. It only
displays the current project/ticket/phase/budget state and points the operator
to a trusted host hook for any real approval.

Security note: a process started by a model or shell is not an operator. Real
operator-origin authority can only be issued by a host hook that the separated
broker authenticates (for example, a Claude Code UserPromptSubmit hook). This
gateway therefore never calls issue_operator_origin and never writes a carrier.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from saipen_engine.state import parse_state


def _load_state(root: Path) -> dict:
    return parse_state((root / ".saipen" / "STATE.md").read_text(encoding="utf-8-sig"))


def status(root: Path) -> dict:
    state = _load_state(root)
    return {
        "ok": True,
        "code": "GATEWAY_STATUS",
        "project": str(root),
        "task": state.get("task"),
        "phase": state.get("phase"),
        "goal": state.get("goal_ingress"),
        "budget": state.get("authority_source"),
        "authority": "READ_ONLY",
        "real_approval_requires": "trusted host hook authenticated by the SAIPEN broker",
        "note": "This gateway does not mint or renew authority.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only SAIPEN operator status gateway")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = args.project_root.resolve()
    if not (root / ".saipen" / "STATE.md").is_file():
        result = {"ok": False, "code": "PROJECT_UNBOUND", "detail": "no SAIPEN project at this root"}
        print(json.dumps(result))
        return 1

    result = status(root)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Project: {result['project']}")
        print(f"Task: {result['task']}")
        print(f"Phase: {result['phase']}")
        print(f"Budget: {result['budget']}")
        print("Authority: READ_ONLY (no minting)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
