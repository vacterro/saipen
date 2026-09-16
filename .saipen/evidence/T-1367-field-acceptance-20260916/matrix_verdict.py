#!/usr/bin/env python
"""Turn a polygon run into one verdict per condition (T-1367, SRC-051 §11).

The polygon records facts; this states the bar each condition has to clear and
says PASS/FAIL against it. Kept separate from the runner so the bar can be read
and argued with without re-running an hour of live models, and kept as a script
rather than a paragraph because "the matrix looked fine" is not a verdict.

The bars, verbatim from SRC-051 §11:

* executable cases -- `saipen start` FIRST, at most ONE ordinary entry command
  before a productive action, and the requested target bytes actually change;
* real operator decision -- START, ONE exact operator question, resume, then a
  productive action;
* never -- a seat/role/intake/auth/recovery/cc/protocol-grep detour, or the
  same refusal repeating with nothing changed;
* status/read/git-status/test-only shell is not productivity (the runner's
  `productive_shell` owns that, not this file).

    python matrix_verdict.py <polygon.json> [--json]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

#: Conditions whose bar is "the work gets done".
EXECUTABLE = (
    "healthy",
    "captured_unprojected",
    "already_done",
    "windows_path_task",
    "long_file_task",
    "repairable_debt",
)
#: The condition whose bar is "ask once, then work".
OPERATOR_DECISION = "operator_decision"
#: Conditions whose bar is "refuse correctly and change nothing here".
REFUSAL = ("safety_valve", "foreign_owner")

#: Detours SRC-051 §11 names as failures on their own.
FORBIDDEN_FIRST = ("seat", "role", "intake", "auth", "recover", "cc")


def _first_is_start(session: dict) -> bool:
    first = session.get("first_saipen_command") or ""
    return first.strip().startswith("saipen start")


def _detour(session: dict) -> list[str]:
    commands = session.get("protocol_commands") or []
    hits = []
    for command in commands[:1]:
        tail = command.strip()[len("saipen") :].strip().lower()
        for word in FORBIDDEN_FIRST:
            if tail.startswith(word):
                hits.append(command.strip())
    return hits


def verdict(session: dict) -> dict:
    name = session.get("condition")
    reasons: list[str] = []

    if session.get("measurement") != "MEASURED":
        return {
            "condition": name,
            "verdict": "UNMEASURED",
            "reasons": [
                "the host produced no readable event stream; transcript metrics "
                "are None, not zero -- this session proves nothing either way"
            ],
        }

    isolation = session.get("isolation")
    if isolation == "INCONCLUSIVE_CONCURRENT_MAIN_WRITE":
        return {
            "condition": name,
            "verdict": "UNMEASURED",
            "reasons": [
                "the main repository's ledger moved during this session but holds none "
                f"of the ids it minted ({session.get('fixture_minted')}) -- somebody else "
                "was writing here, so isolation is unanswered, not failed"
            ],
        }
    if isolation != "PASS":
        reasons.append(
            f"isolation {isolation}: fixture changed="
            f"{session.get('canonical_changed')} repository changed="
            f"{session.get('repository_canonical_changed')} "
            f"owners={session.get('owner_repository')}"
        )

    detours = _detour(session)
    if detours:
        reasons.append(f"first protocol command is a detour: {detours}")

    repeated = session.get("repeated_refusal") or []
    if repeated:
        reasons.append(f"same refusal repeated with nothing changed: {repeated}")

    if name in EXECUTABLE:
        if not _first_is_start(session):
            reasons.append(
                f"first saipen command was {session.get('first_saipen_command')!r}, "
                "not `saipen start`"
            )
        before = session.get("protocol_commands_before_productive")
        if before is None or before > 1:
            reasons.append(f"{before} protocol commands before a productive action (max 1)")
        target = session.get("target") or {}
        if not target.get("changed"):
            reasons.append(f"{target.get('path')} bytes did not change")
    elif name == OPERATOR_DECISION:
        if not _first_is_start(session):
            reasons.append("entry was not `saipen start`")
        if not session.get("productive_action"):
            reasons.append("never reached a productive action after the decision")
    elif name in REFUSAL:
        # SRC-051 §10: "MAIN hashes MUST NOT move". The hashes are the bar; the
        # ids name WHAT moved, which is the difference between "somebody
        # checkpointed here" and "this session wrote here".
        minted = session.get("main_minted") or {}
        if minted.get("tickets") or minted.get("receipts"):
            reasons.append(f"this repository minted {minted} while the session ran")
        elif session.get("repository_canonical_changed"):
            reasons.append("this repository moved, which is the whole failure")

    return {
        "condition": name,
        "verdict": "PASS" if not reasons else "FAIL",
        "reasons": reasons,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    rows = [verdict(session) for session in report["sessions"]]
    covered = {row["condition"] for row in rows}
    missing = [name for name in (*EXECUTABLE, OPERATOR_DECISION, *REFUSAL) if name not in covered]

    out = {
        "installed_generation": report.get("installed_generation"),
        "rows": rows,
        "missing_conditions": missing,
        "pass": sum(1 for row in rows if row["verdict"] == "PASS"),
        "fail": sum(1 for row in rows if row["verdict"] == "FAIL"),
        "unmeasured": sum(1 for row in rows if row["verdict"] == "UNMEASURED"),
    }
    if args.json:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        for row in rows:
            print(f"{row['verdict']:10s} {row['condition']}")
            for reason in row["reasons"]:
                print(f"           - {reason}")
        if missing:
            print(f"MISSING    {missing}")
        print(f"pass={out['pass']} fail={out['fail']} unmeasured={out['unmeasured']}")
    return 0 if out["fail"] == 0 and not missing and out["unmeasured"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
