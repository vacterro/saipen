"""Continuation liveness projection (T-1159).

Durable memory for exactly one fact across CLI invocations: the fingerprint
of the last actionable crew/continuation carrier handed to the agent, so an
identical actionable answer twice in a row is surfaced as CREW_STALLED
instead of silently re-polled (CORE § 1.10 "EXECUTE, DO NOT EXPLAIN").

This is a PROJECTION stored under `.saipen/cache/`: rebuildable, never
canonical authority, never read by the validator as project truth. A missing
or corrupt carrier degrades to "no history" (first observation), never to a
failure. Read-only sessions and `--dry-run` invocations never write it.
"""

from __future__ import annotations

import hashlib
import json
from contextlib import suppress
from pathlib import Path

CACHE_REL = Path(".saipen") / "cache" / "continuation-liveness.json"

# The second consecutive identical actionable carrier means the previous one
# did NOT produce a qualifying state change: that is a stall, not progress.
STALL_THRESHOLD = 2


def action_fingerprint(
    *,
    stage: object = None,
    role: object = None,
    action: object = None,
    reason: object = None,
    source: object = None,
) -> str:
    """Deterministic identity of an actionable carrier's semantic content.

    Two carriers with the same fingerprint describe the same unresolved state:
    same stage, same role, same action, same unsatisfied-stage reasons, same
    source-tree identity. Any real progress (fresh evidence, replan, source
    change) changes at least one input and therefore the fingerprint.
    """
    payload = json.dumps(
        {
            "stage": stage,
            "role": role,
            "action": action,
            "reason": reason,
            "source": source,
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _cache_path(project_root: Path | str) -> Path:
    return Path(project_root) / CACHE_REL


def _load(path: Path) -> dict:
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except OSError:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def record_actionable(project_root: Path | str, fingerprint: str) -> dict:
    """Record one actionable carrier and classify repetition.

    Returns ``{"stalled": bool, "stall_repeats": int}``. The stalled verdict
    is deterministic: the same fingerprint observed ``STALL_THRESHOLD`` times
    in a row. A write failure degrades to a first observation -- liveness is
    best-effort projection and must never become a new failure surface.
    """
    path = _cache_path(project_root)
    data = _load(path)
    if data.get("fingerprint") == fingerprint and isinstance(data.get("repeats"), int):
        repeats = data["repeats"] + 1
    else:
        repeats = 1
    doc = {"schema_version": 1, "fingerprint": fingerprint, "repeats": repeats}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    except OSError:
        return {"stalled": False, "stall_repeats": 1}
    return {"stalled": repeats >= STALL_THRESHOLD, "stall_repeats": repeats}


def clear(project_root: Path | str) -> None:
    """Forget the last actionable carrier (real progress happened)."""
    with suppress(OSError):
        _cache_path(project_root).unlink()
