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
