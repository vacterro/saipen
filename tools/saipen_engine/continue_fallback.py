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
from pathlib import Path


FALLBACK_MARKER_REL = Path(".saipen") / "extensions" / "continue_fallback.json"


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
