"""`saipen continue` -> `saipen improve` fallthrough (T-20260830_0842).

`saipen continue` must never terminate merely because there is no
immediately actionable queued Work. Once recovery, blocked/retryable,
queued and required-follow-up routing has been exhausted (the router's
idle-maintain verdict), continuation falls through ONCE to the
improvement-discovery path (`saipen improve` bare = the bounded audit
assignment PREPARE step). A marker keeps the fallback bounded across
invocations: an already-active prepared cycle is resumed, never duplicated.

A completed cycle frees a fresh discovery only when the SOURCE moved. The
marker records the source identity at admission, and an unchanged tree
yields a clean idle verdict instead of another cycle: a discovery keyed to
`git-delta-v1` that re-derives a verdict already held is not an audit, it is
churn, and each admitted cycle becomes immutable evidence.

This module is the deterministic decision + marker side. The actual
`saipen improve` invocation stays in the CLI so capability, handover and
writer-lock rules stay in their owning boundary.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path


FALLBACK_MARKER_REL = Path(".saipen") / "extensions" / "continue_fallback.json"

#: An in-flight cycle whose report has not completed in this many days is
#: stalled, not slow. A cycle that is NOT in flight (`archived`, `superseded`,
#: ...) with an unfinished report is stale by state alone -- the measured case
#: was exactly that, and it never needed a clock to be stale.
STALE_DRAFT_DAYS = 7

_FIELD_RE_TEMPLATE = r"(?m)^{key}:[ \t]*(.+?)[ \t]*$"
_RUN_HEADING_RE = re.compile(r"(?m)^## RUN\s+\d+\s*$")


def _marker_path(root: Path) -> Path:
    return Path(root) / FALLBACK_MARKER_REL


def read_marker(root: Path) -> dict:
    """The persisted continue-fallback marker, or {} when absent/malformed.

    Malformed bytes are treated as absent: a broken marker must never block
    continuation or fabrication-safe routing, and the next write overwrites
    it atomically.
    """
    path = _marker_path(root)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def active_cycle_status(root: Path, cycle_id: str) -> str:
    """The manifest `cycle_status:` of the named cycle, '' when absent.

    '' means no active cycle under that id: a fresh discovery may run.
    `complete`/`archived` seal the cycle and also allow a fresh discovery.
    Any other value (`active`) means the improvement discovery is already in
    flight -- resume, never prepare a duplicate.
    """
    manifest = Path(root) / ".saipen" / "improve" / cycle_id / "MANIFEST.md"
    try:
        text = manifest.read_text(encoding="utf-8")
    except OSError:
        return ""
    for line in text.splitlines():
        if line.startswith("cycle_status:"):
            return line.split(":", 1)[1].strip()
    return ""


def _manifest_field(text: str, key: str) -> str:
    """The `key:` value of a MANIFEST/report header line, '' when absent."""
    match = re.search(_FIELD_RE_TEMPLATE.format(key=re.escape(key)), text)
    return match.group(1) if match else ""


def cycle_liveness(root: Path, cycle_id: str) -> dict | None:
    """The assigned cycle's visible liveness, or None when the id is unknown.

    T-38, measured: `continue --json` named the marker's cycle id and answered
    `CONTINUE_IDLE_SOURCE_UNCHANGED`, while the genuinely unfinished audit
    (`imp-vacterro-saiwebsite-20261007-1`, archived with `draft-preserved`)
    sat one directory away carrying an age, a draft state and a submit route
    that the payload never mentioned -- seven days of unfinished work read as
    a clean idle verdict. The answer now carries them, so stale cycles become
    visible work (T-1434 already treats only `active` as in flight).

    Read-only and total: an unreadable manifest yields None, never a guess.
    """
    cycle_dir = Path(root) / ".saipen" / "improve" / cycle_id
    try:
        text = (cycle_dir / "MANIFEST.md").read_text(encoding="utf-8")
    except OSError:
        return None

    status = _manifest_field(text, "cycle_status")
    seat_id = _manifest_field(text, "seat_id")
    project = _manifest_field(text, "project_identity")
    report_path = _manifest_field(text, "report_path")
    created = _manifest_field(text, "created_at")

    report_text = ""
    if seat_id and report_path:
        try:
            report_text = (cycle_dir / seat_id / report_path).read_text(encoding="utf-8")
        except OSError:
            report_text = ""
    report_status = _manifest_field(report_text, "report_status") if report_text else ""
    runs = len(_RUN_HEADING_RE.findall(report_text))
    # `draft` is the report's own machine status; `no_run` catches the
    # header-only report that never even declared a status or a RUN block.
    draft = bool(report_status) and report_status != "complete"
    no_run = runs == 0

    age_days: int | None = None
    if created:
        try:
            born = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except ValueError:
            born = None
        if born is not None:
            if born.tzinfo is None:
                born = born.replace(tzinfo=timezone.utc)
            age_days = int((datetime.now(timezone.utc) - born).total_seconds() // 86400)

    stale = bool(draft or no_run) and (
        status != "active" or (age_days is not None and age_days >= STALE_DRAFT_DAYS)
    )
    submit = (
        f"saipen improve submit {cycle_id} {seat_id} {project} {seat_id}/{report_path}"
        if draft and seat_id and report_path
        else ""
    )
    result = {
        "cycle_id": cycle_id,
        "status": status,
        "seat_id": seat_id,
        "report_status": report_status,
        "has_report": bool(report_text),
        "runs": runs,
        "draft": draft,
        "no_run": no_run,
        "created_at": created,
        "age_days": age_days,
        "stale": stale,
        "submit_route": submit,
    }
    # A terminal manifest never proves that every historical finding was
    # adjudicated. Read every seat and the native successor instead of offering
    # submit/complete commands that are forbidden on the sealed original.
    from improve import TERMINAL_CYCLE_STATUSES, _field, _seat_blocks

    if status in TERMINAL_CYCLE_STATUSES:
        from .improve_retrospective import inspect_archive

        result.update(inspect_archive(cycle_dir))
        result["submit_route"] = ""
    else:
        unfinished = False
        for block in _seat_blocks(text):
            if (_field(block, "availability") or "expected") != "expected":
                continue
            path = cycle_dir / _field(block, "seat_id") / _field(block, "report_path")
            try:
                seat_text = path.read_text(encoding="utf-8")
            except OSError:
                seat_text = ""
            unfinished = unfinished or _manifest_field(seat_text, "report_status") != "complete"
            unfinished = unfinished or not _RUN_HEADING_RE.search(seat_text)
        result["stale"] = bool(unfinished and age_days is not None and age_days >= STALE_DRAFT_DAYS)
    return result


def _other_cycle_liveness(root: Path, exclude: str = "") -> list[dict]:
    """Every OTHER cycle in this project's registry whose liveness is stale.

    The assigned cycle and the genuinely unfinished one are different cycles
    in the measured case (the marker names the complete 20261013-1 cycle,
    while the archived `draft-preserved` 20261007-1 cycle is the work that was
    never submitted), so liveness scans the registry rather than trusting the
    marker to name the only interesting cycle. Oldest first, so the top of the
    list is the cycle that has waited longest.
    """
    improve = Path(root) / ".saipen" / "improve"
    try:
        entries = sorted(p for p in improve.iterdir() if p.is_dir())
    except OSError:
        return []
    stale = []
    for entry in entries:
        if entry.name == exclude:
            continue
        live = cycle_liveness(root, entry.name)
        if live is not None:
            stale.append(live)
    stale.sort(key=lambda item: (item["age_days"] is not None, item["age_days"] or 0), reverse=True)
    return stale


def stale_cycles(root: Path, exclude: str = "") -> list[dict]:
    return [item for item in _other_cycle_liveness(root, exclude) if item["stale"]]


def with_cycle_liveness(payload: dict, root: Path) -> dict:
    """Attach the assigned cycle's liveness to one continue answer (T-38).

    The assigned cycle is the payload's own `cycle_id`, else the marker's.
    One read-only merge, so it can sit on every outcome the fallback branch
    emits without a second decision; a missing cycle leaves the payload
    unchanged. A different, stale cycle still rides along under
    `improve_stale_cycles`, because the answer that names only the assigned
    cycle is what hid the measured one for seven days.
    """
    cycle_id = str(payload.get("cycle_id") or read_marker(root).get("cycle_id") or "")
    live = cycle_liveness(root, cycle_id) if cycle_id else None
    others = _other_cycle_liveness(root, cycle_id)
    stale = [item for item in others if item["stale"]]
    blocked = [item for item in others if item.get("blocked")]
    if live is None and not stale and not blocked:
        return payload
    answer = dict(payload)
    if live is not None:
        answer["improve_cycle"] = live
    if stale:
        answer["improve_stale_cycles"] = stale
    if blocked:
        answer["improve_blocked_cycles"] = blocked
    return answer


def resume_action(root: Path, cycle_id: str, agent: str) -> tuple[str, str]:
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
        cycle_errors = verify_cycle(cycle)
        if not cycle_errors:
            return (
                f"saipen improve cycle-complete {cycle_id}",
                f"improvement discovery cycle {cycle_id} meets its bar; complete it",
            )
        has_unswept = False
        for block in _seat_blocks(roster):
            if (_field(block, "availability") or "expected") != "expected":
                continue
            seat = _field(block, "seat_id")
            report_name = _field(block, "report_path")
            report = cycle / seat / report_name
            text = report.read_text(encoding="utf-8-sig") if report.is_file() else ""
            status = derive_status(report_name, roster, text, sweep, seat)
            if status.get("missing"):
                has_unswept = True
                break
        if has_unswept:
            return (
                f"saipen improve sweep-queue {cycle_id}",
                f"improvement discovery cycle {cycle_id} is already active and every "
                "expected report is complete; the Core sweep of its findings is next",
            )
        return (
            f"saipen improve abort {cycle_id}",
            f"improvement discovery cycle {cycle_id} is already active and every "
            "expected report is complete, but identity-stale with zero unswept findings; "
            "abort to archive the stale-complete evidence",
        )
    except Exception as exc:  # any fault answers read-only; this route never admits
        return (
            "saipen improve status",
            f"improvement discovery cycle {cycle_id} is already active; its next act "
            f"could not be read ({type(exc).__name__}), so inspect it read-only",
        )


def source_identity_fields(root: Path) -> dict:
    """The current source identity as marker-persisted strings, {} when unknown.

    An unmeasurable tree (no Git, unreadable, or a fingerprint that changed
    while it was being read) is `{}`: the caller then admits the discovery
    rather than guessing that nothing moved.
    """
    try:
        from freshness import compute_source_identity

        ident = compute_source_identity(root)
    except Exception:
        return {}
    return {
        "source_head": ident.source_head,
        "source_tree_fingerprint": ident.source_tree_fingerprint,
        "discovery_model": ident.discovery_model,
    }


def source_unchanged(root: Path, marker: dict) -> tuple[bool, str]:
    """(unchanged, detail) against the identity the marker recorded.

    True only when the marker carries a real identity AND the current tree
    still hashes to it. A marker written before this field existed, or one
    carrying no identity, returns False exactly once: the next admission
    records the identity and the gate becomes decisive from then on.
    """
    fields = source_identity_fields(root)
    if not fields:
        return False, "source identity is not measurable; discovery admitted"
    recorded_head = marker.get("source_head") or ""
    recorded_fp = marker.get("source_tree_fingerprint") or ""
    if not recorded_head or not recorded_fp:
        return False, "marker carries no recorded source identity; discovery admitted"
    if fields["source_head"] == recorded_head and fields["source_tree_fingerprint"] == recorded_fp:
        return True, (
            f"source unchanged since the last improve discovery "
            f"({fields['discovery_model']} head {fields['source_head'][:12]})"
        )
    return False, (
        f"source changed since the last improve discovery "
        f"({recorded_head[:12]} -> {fields['source_head'][:12]})"
    )


def write_marker(root: Path, cycle_id: str, agent: str) -> Path:
    """Persist the one marker record for this fallback cycle. Atomic replace."""
    path = _marker_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "cycle_id": cycle_id,
        "agent": agent,
        "prepared_at": _now_utc(),
    }
    payload.update(source_identity_fields(root))
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(payload, sort_keys=True), encoding="utf-8", newline="\n"
    )
    tmp.replace(path)
    return path


def _now_utc() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
