"""Apply the T-1775 change under a given root.

    python -B apply_t1775.py <root> [--check]

1. tools/saipen_engine/continue_fallback.py gains `resume_action`: the next
   act on an ACTIVE cycle, read from the cycle, that never admits a seat.
2. tools/saipen.py's CONTINUE_IMPROVE_IN_FLIGHT emission names that act
   instead of the bare `saipen improve`, and its detail stops advising the
   bare form.

Refuses unless every anchor is found exactly once. Keeps line endings.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()

FALLBACK = ROOT / "tools/saipen_engine/continue_fallback.py"
FALLBACK_ANCHOR = "def source_identity_fields(root: Path) -> dict:\n"
FALLBACK_ADD = '''def resume_action(root: Path, cycle_id: str, agent: str) -> tuple[str, str]:
    """The next act on an ACTIVE cycle, as `(action, detail)`; never a new seat.

    T-1775 (SRC-248 R007). Bare `saipen improve` resumes only a seat of this
    agent's family whose report holds no audit content; otherwise it admits a
    NEW core seat (`improve.prepare_audit_seat`). Prescribed for a cycle in
    flight, it grew the roster with a zero-RUN draft whenever every seat had
    content -- measured in _SAIRELAY, where the one seat was complete and the
    cycle was waiting on its Core sweep. The act is read from the cycle:

    * an expected seat of this family whose report is not complete resumes by
      its session, `saipen improve --session <seat>` (idempotent);
    * an incomplete seat of another family is that agent's to resume, so the
      answer is the read-only status, never a takeover and never a new seat;
    * a roster whose expected reports are all complete goes to the Core sweep
      (`improve sweep-queue`), and to `improve cycle-complete` once the bar
      `improve verify` applies is met.

    An unreadable cycle answers the read-only status as well: the one thing
    this route never does is admit.
    """
    import re

    try:
        from improve import _field, _seat_blocks, derive_status, verify_cycle

        cycle = Path(root) / ".saipen" / "improve" / cycle_id
        roster = (cycle / "MANIFEST.md").read_text(encoding="utf-8-sig")
        sweep_path = cycle / "SWEEP.md"
        sweep = sweep_path.read_text(encoding="utf-8-sig") if sweep_path.is_file() else ""
        family = re.sub(r"[^A-Za-z0-9_-]", "-", agent or "").strip("-").lower() or "agent"
        own: list[str] = []
        foreign: list[str] = []
        for block in _seat_blocks(roster):
            if (_field(block, "availability") or "expected") != "expected":
                continue
            seat = _field(block, "seat_id")
            report = cycle / seat / _field(block, "report_path")
            text = report.read_text(encoding="utf-8-sig") if report.is_file() else ""
            status = derive_status(_field(block, "report_path"), roster, text, sweep, seat)
            if status["visible"] in ("expected", "draft"):
                (own if seat.startswith(family + "-") else foreign).append(seat)
        if own:
            return (
                f"saipen improve --session {own[0]}",
                f"improvement discovery cycle {cycle_id} is already active and seat "
                f"{own[0]} has not completed its report; resume that seat by its session",
            )
        if foreign:
            return (
                "saipen improve status",
                f"improvement discovery cycle {cycle_id} is already active and waits on "
                f"seat(s) {', '.join(foreign)} of another agent; they resume their own seats",
            )
        if verify_cycle(cycle):
            return (
                f"saipen improve sweep-queue {cycle_id}",
                f"improvement discovery cycle {cycle_id} is already active and every "
                "expected report is complete; the Core sweep of its findings is next",
            )
        return (
            f"saipen improve cycle-complete {cycle_id}",
            f"improvement discovery cycle {cycle_id} meets its bar; complete it",
        )
    except Exception as exc:  # any fault answers read-only; this route never admits
        return (
            "saipen improve status",
            f"improvement discovery cycle {cycle_id} is already active; its next act "
            f"could not be read ({type(exc).__name__}), so inspect it read-only",
        )


'''

CLI = ROOT / "tools/saipen.py"
CLI_IMPORT_OLD = (
    "    from saipen_engine.continue_fallback import (\n"
    "        active_cycle_status,\n"
    "        read_marker,\n"
)
CLI_IMPORT_NEW = (
    "    from saipen_engine.continue_fallback import (\n"
    "        active_cycle_status,\n"
    "        read_marker,\n"
    "        resume_action,\n"
)
CLI_EMIT_OLD = (
    "            # point rather than a second discovery.\n"
    "            _emit_result(\n"
    "                {\n"
    '                    "ok": True,\n'
    '                    "code": "CONTINUE_IMPROVE_IN_FLIGHT",\n'
    '                    "cycle_id": prior_cycle,\n'
    '                    "action": "saipen improve",\n'
    '                    "reason": "improve-in-flight",\n'
    '                    "dry_run": bool(dry_run),\n'
    '                    "detail": (\n'
    '                        "improvement discovery cycle "\n'
    '                        f"{prior_cycle} is already active; resume it "\n'
    '                        "(saipen improve) instead of preparing a duplicate"\n'
    "                    ),\n"
    "                }\n"
    "            )\n"
)
CLI_EMIT_NEW = (
    "            # point rather than a second discovery. T-1775: the point is read\n"
    "            # from the cycle; bare `saipen improve` admits a new seat whenever\n"
    "            # every seat has content, so it is never the resume point. The\n"
    "            # family is the one `improve` allocates seats under: STATE.agent.\n"
    "            _seat_state, _ = parse_state_or_error(codec.read_doc(_state_path(project_root)))\n"
    "            _resume, _resume_detail = resume_action(\n"
    "                project_root, prior_cycle, str((_seat_state or {}).get(\"agent\") or \"agent\")\n"
    "            )\n"
    "            _emit_result(\n"
    "                {\n"
    '                    "ok": True,\n'
    '                    "code": "CONTINUE_IMPROVE_IN_FLIGHT",\n'
    '                    "cycle_id": prior_cycle,\n'
    '                    "action": _resume,\n'
    '                    "reason": "improve-in-flight",\n'
    '                    "dry_run": bool(dry_run),\n'
    '                    "detail": _resume_detail,\n'
    "                }\n"
    "            )\n"
)


def _patch(path: Path, pairs: list[tuple[str, str]], marker: str, check: bool) -> int:
    raw = path.read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8").replace("\r\n", "\n")
    if marker in text:
        print(f"ALREADY_APPLIED: {path.name}")
        return 0
    for old, _new in pairs:
        if text.count(old) != 1:
            print(f"ABORT: {path.name}: anchor found {text.count(old)} times: {old.strip()[:60]!r}")
            return 1
    for old, new in pairs:
        text = text.replace(old, new)
    if check:
        print(f"CHECK OK: {path.name}")
        return 0
    path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
    print(f"patched {path}")
    return 0


def main() -> int:
    check = "--check" in sys.argv
    rc = _patch(
        FALLBACK,
        [(FALLBACK_ANCHOR, FALLBACK_ADD + FALLBACK_ANCHOR)],
        "def resume_action(",
        check,
    )
    if rc:
        return rc
    return _patch(
        CLI,
        [(CLI_IMPORT_OLD, CLI_IMPORT_NEW), (CLI_EMIT_OLD, CLI_EMIT_NEW)],
        "T-1775: the point is read",
        check,
    )


if __name__ == "__main__":
    sys.exit(main())
