"""SAITULS-shaped fixture: execution DONE with real outstanding obligations.

T-1862 / SRC-294. This reproduces the reported state on a DISPOSABLE project:

    phase: DONE, task: none
    continuation_authority: operator_required, safety_valve_mode: hard_wait
    1 active external audit layer
    162 source clauses UNKNOWN
    7 BLOCKED tickets, 2 TODO tickets

The real SAITULS project is never written to. The fixture is built under a
temporary directory with the canonical helpers, its `status --json` is captured
both before and after the readiness projection, and the STATE/BOARD/LOG bytes
are compared to prove the projection is read-only.

Run standalone:
    python tools/fixture_t1862_saituls_shape.py [--json]
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

UNKNOWN_COUNT = 162
BLOCKED_COUNT = 7
TODO_COUNT = 2


def _state(**overrides) -> str:
    base = {
        "phase": "DONE",
        "task": "none",
        "next_action": "PHASE DONE",
        "blocker": "none",
        "transition_from": "SHIP",
        "agent": "fixture",
        "saipen_version": 8,
        "schema_version": 3,
        "last_event": 11,
        "updated": "2026-10-23T00:00:00Z",
        "style_contract": "ded-069a4c52",
        "saipen_home": str(ROOT).replace("\\", "/"),
        "mode": "full",
        "execution_intent": "goal",
        "goal_waves": 0,
        "goal_tickets": 0,
        "continuation_authority": "operator_required",
        "authority_source": "E-1",
        "authority_until": "budget",
        "safety_valve_mode": "hard_wait",
    }
    base.update(overrides)
    lines = ["---"]
    for key, value in base.items():
        if key in ("goal_waves", "goal_tickets", "last_event", "saipen_version",
                   "schema_version"):
            lines.append(f"{key}: {value}")
            continue
        lines.append(f'{key}: "{value}"' if isinstance(value, str) else f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def _board() -> str:
    lines = ["## DOING", "## TODO"]
    for number in range(1, TODO_COUNT + 1):
        lines.append(
            f"- [ ] T-9{number:03d} [P2] fixture follow-up {number} | "
            f"verify: it holds"
        )
    lines.append("## DONE")
    lines.append("- [x] T-001 [P1] the last shipped execution ticket | verify: it held")
    lines.append("## BLOCKED")
    for number in range(1, BLOCKED_COUNT + 1):
        lines.append(
            f"- [ ] T-8{number:03d} [P2] blocked fixture {number} | "
            f"blocker: BLOCKED_EXTERNAL -- vendor session required"
        )
    return "\n".join(lines) + "\n"


def _log() -> str:
    lines = ["# Log"]
    for number in range(1, 12):
        lines.append(
            f"- 01.10.26 00:0{number % 10} [E-{number}] [agent: fixture] DEC: seed {number}"
        )
    return "\n".join(lines) + "\n"


def _coverage(folder: Path, receipt: str, unknown: int) -> None:
    requirements = {}
    for index in range(unknown):
        requirements[f"{receipt}:R{index + 1:03d}"] = {
            "actionable": True,
            "class": "requirement",
            "disposition": "UNKNOWN",
            "text": f"fixture clause {index + 1}",
        }
    (folder / f"{receipt}.json").write_text(
        json.dumps({"schema_version": 1, "requirements": requirements}, indent=1),
        encoding="utf-8",
    )


def build() -> Path:
    root = Path(tempfile.mkdtemp(prefix="t1862-saituls-"))
    memory = root / ".saipen"
    memory.mkdir(parents=True)
    (memory / "STATE.md").write_text(_state(), encoding="utf-8")
    (memory / "BOARD.md").write_text(_board(), encoding="utf-8")
    (memory / "LOG.md").write_text(_log(), encoding="utf-8")

    # One active source receipt carrying the 162 UNKNOWN clauses.
    intake = memory / "intake"
    for name in ("active", "contracts", "coverage"):
        (intake / name).mkdir(parents=True)
    body = "\n".join(f"clause {index + 1}" for index in range(UNKNOWN_COUNT)) + "\n"
    (intake / "active" / "SRC-001.md").write_text(body, encoding="utf-8")
    (intake / "contracts" / "SRC-001.json").write_text(
        json.dumps({"schema_version": 1, "clauses": [], "kind": "request"}, indent=1),
        encoding="utf-8",
    )
    _coverage(intake / "coverage", "SRC-001", UNKNOWN_COUNT)
    import hashlib

    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    (intake / "active" / "SRC-001.meta.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "receipt_id": "SRC-001",
                "kind": "request",
                "source_sha256": digest,
                "linked_work": None,
                "captured_at": "2026-10-23T00:00:00Z",
                "agent": "fixture",
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    (intake / "index.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "next_id": 2,
                "active": {"SRC-001": {"linked_work": None, "source_sha256": digest}},
                "tombstones": {},
            },
            indent=1,
        ),
        encoding="utf-8",
    )

    # One ACTIVE audit layer. The inbox lives at `<project>/audit/` (a project
    # surface, not protocol memory), bound to the receipt by its digest so
    # classification can resolve it to a receipt without re-reading a body.
    audit = root / "audit"
    audit.mkdir()
    (audit / "1.md").write_text(
        "# fixture audit layer\n\nOne external audit finding awaiting consumption.\n",
        encoding="utf-8",
    )
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("code\n", encoding="utf-8")
    return root


def status(root: Path) -> tuple[int, dict | None, str]:
    env = dict(os.environ)
    env["SAIPEN_HOME"] = str(ROOT)
    proc = subprocess.run(
        [sys.executable, "-B", str(TOOLS / "saipen.py"), "status", "--json"],
        cwd=str(root), capture_output=True, text=True, encoding="utf-8", env=env, timeout=300,
    )
    try:
        return proc.returncode, json.loads(proc.stdout), proc.stdout
    except ValueError:
        return proc.returncode, None, (proc.stderr or proc.stdout)


def main() -> int:
    as_json = "--json" in sys.argv[1:]
    root = build()
    try:
        memory = root / ".saipen"
        before = {n: (memory / n).read_bytes() for n in ("STATE.md", "BOARD.md", "LOG.md")}
        code, payload, raw = status(root)
        after = {n: (memory / n).read_bytes() for n in ("STATE.md", "BOARD.md", "LOG.md")}
        if payload is None:
            print(raw[:4000])
            return 1
        ready = payload.get("readiness") or {}
        report = {
            "fixture": str(root),
            "exit_code": code,
            "execution_phase": payload.get("phase"),
            "execution_task": payload.get("task"),
            "top_workable_ticket": payload.get("top_workable_ticket"),
            "derived_status": ready.get("status"),
            "accepted": ready.get("accepted"),
            "ready": ready.get("ready"),
            "reasons": ready.get("reasons"),
            "dimensions": ready.get("dimensions"),
            "continuation_authority": payload.get("continuation_authority"),
            "safety_valve_mode": payload.get("safety_valve_mode"),
            "grants_authority": ready.get("grants_authority"),
            "memory_unchanged": before == after,
        }
        if as_json:
            print(json.dumps(report, indent=1))
        else:
            for key, value in report.items():
                if key == "dimensions" and isinstance(value, dict):
                    print(f"{key}:")
                    for name, detail in value.items():
                        print(f"  {name}: {json.dumps(detail)}")
                else:
                    print(f"{key}: {value}")
        # Two properties decide this fixture's usefulness. Both must hold.
        ok = (
            report["execution_phase"] == "DONE"
            and report["derived_status"] == "AUDIT_OUTSTANDING"
            and not report["ready"]
            and report["memory_unchanged"]
            and report["continuation_authority"] == "operator_required"
        )
        print("FIXTURE HOLDS" if ok else "FIXTURE BROKEN")
        return 0 if ok else 2
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
