"""The operator's own words survive the refusal that names their transport.

MEASURED, not imagined (T-1372, field run 2026-09-16). A routed model was
refused on a 520-byte, 12-line request -- the payload cannot survive one quoted
shell argument -- and was handed the exact transport that carries it:
``saipen start --file <path>``. It started a 179-byte paraphrase of its own
instead. The receipt that came out asserted mode ``exact`` with
``original_available`` true and a body digest matching its own meta, so it was
internally consistent, and BOARD title, coverage, closure and every downstream
gate read green over text the operator never wrote.

The defect class this ends: **a refusal that says which command to run next,
but not which BYTES that command owes.** Nothing compared what arrived with
what was refused, so rewording the request was the cheapest way past the gate.
`BOOT.md` already says "Never reword the user's task to get past a refusal";
this module is the measurement that makes the sentence enforceable.

The obligation lives in ``.saipen/recovery/`` because it is exactly what that
namespace is for: one operation in flight on this machine. It is deliberately
NOT canonical ledger state -- it is never exported, never archived, and it
outlives nothing but the next ingress.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

#: `.saipen/recovery/` is non-exportable and machine-local by contract; the
#: obligation belongs there and nowhere in the canonical ledger.
PENDING_REL = ("recovery", "pending-ingress.json")

SCHEMA_VERSION = 1

#: A pending obligation is about the NEXT ingress, not about the project's
#: life. Past this age the record is stale: the session that earned it is gone,
#: and holding a later operator to bytes nobody remembers refusing would be the
#: deadlock this module must not create.
MAX_AGE_SECONDS = 24 * 60 * 60

CODE_PARAPHRASE = "INGRESS_PARAPHRASE_REFUSED"
CODE_UNREADABLE = "INGRESS_PENDING_UNREADABLE"

#: The exact flag an operator uses to say the request itself changed.
SUPERSEDE_FLAG = "--supersede-ingress"


def pending_path(root: Path | str) -> Path:
    return Path(root).joinpath(".saipen", *PENDING_REL)


def ingress_digest(text: str) -> str:
    """One digest for one request, whatever transport spelled it.

    The shell payload carried `\\n` and no trailing newline; the file a host
    write tool produces carries `\\r\\n` and usually one. Those are the same
    request, and a digest that disagreed would refuse the operator's own bytes
    for arriving by the route the refusal demanded. Line endings and the outer
    whitespace are normalized; nothing inside the text is.
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _age_seconds(stamp: Any) -> float | None:
    if not isinstance(stamp, str):
        return None
    try:
        recorded = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - recorded).total_seconds()


def record(root: Path | str, payload: str, route: str) -> dict:
    """Remember which bytes a transport refusal refused. Never raises.

    The guard is a classifier: a failure to persist this obligation must not
    turn a refusal that was about transport into a crash about disk. A record
    that could not be written simply leaves the project where it was before.
    """
    root = Path(root)
    normalized = payload.replace("\r\n", "\n").replace("\r", "\n").strip()
    entry = {
        "schema_version": SCHEMA_VERSION,
        "digest": ingress_digest(payload),
        "bytes": len(normalized.encode("utf-8")),
        "route": route,
        "recorded": _now(),
        "preview": normalized[:160],
    }
    path = pending_path(root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        from .paths import safe_atomic_write_bytes

        safe_atomic_write_bytes(
            path,
            (json.dumps(entry, indent=2, ensure_ascii=False) + "\n").encode("utf-8"),
            kind="pending ingress",
            ownership_root=root,
        )
    except (OSError, ValueError):
        return {**entry, "recorded_to_disk": False}
    return {**entry, "recorded_to_disk": True}


def pending(root: Path | str) -> dict | None:
    """The obligation this project owes its next ingress, or None.

    An unreadable record returns ``{"malformed": True}`` rather than None: an
    obligation nobody can read is not an obligation nobody has, and silently
    treating it as absent would restore exactly the hole this module closes.
    A record older than ``MAX_AGE_SECONDS`` is stale and is not enforced.
    """
    path = pending_path(root)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError) as exc:
        return {"malformed": True, "detail": str(exc)}
    try:
        entry = json.loads(raw)
    except ValueError as exc:
        return {"malformed": True, "detail": str(exc)}
    if not isinstance(entry, dict) or not isinstance(entry.get("digest"), str):
        return {"malformed": True, "detail": "record declares no digest"}
    age = _age_seconds(entry.get("recorded"))
    if age is None:
        return {"malformed": True, "detail": "record declares no readable timestamp"}
    if age > MAX_AGE_SECONDS:
        return None
    return entry


def clear(root: Path | str, reason: str) -> bool:
    """Discharge the obligation. True when a record was actually removed."""
    path = pending_path(root)
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    except OSError:
        return False
    return bool(reason)


def enforce(root: Path | str, text: str, *, supersede: bool = False) -> dict | None:
    """None when this ingress may proceed; a refusal payload when it may not.

    Clearing is part of proceeding: bytes that answer the obligation discharge
    it, and so does an explicit operator supersede. What never proceeds is
    different text arriving silently while the refused bytes are still owed.
    """
    found = pending(root)
    if found is None:
        return None
    if found.get("malformed"):
        if supersede:
            clear(root, "operator superseded an unreadable pending ingress")
            return None
        return {
            "code": CODE_UNREADABLE,
            "detail": (
                "a pending ingress obligation exists but cannot be read ("
                + str(found.get("detail") or "unreadable")
                + "). The refused request's bytes cannot be compared, so this "
                "ingress is refused rather than believed. Carry the original "
                "request through --file/--hex, or, if the request itself "
                "changed, repeat this command with " + SUPERSEDE_FLAG
            ),
            "pending_ingress": {"malformed": True},
            "canonical_next_command": "saipen start --file <path>",
            "supersede_command": "saipen start " + SUPERSEDE_FLAG + " <task>",
        }
    if supersede:
        clear(root, "operator superseded the refused request")
        return None
    if ingress_digest(text) == found["digest"]:
        clear(root, "the refused bytes arrived through their own transport")
        return None
    route = str(found.get("route") or "saipen start --file <path>")
    return {
        "code": CODE_PARAPHRASE,
        "detail": (
            "this project owes its last refused ingress: "
            + str(found.get("bytes"))
            + " bytes, sha256 "
            + found["digest"]
            + ". The text supplied now has digest "
            + ingress_digest(text)
            + ", so it is not what was refused -- rewording a request to get "
            "past a transport refusal makes the receipt claim the operator's "
            "authority over the model's words. Carry the ORIGINAL bytes with "
            + route
            + ", or, if the operator genuinely changed the request, repeat "
            "this command with " + SUPERSEDE_FLAG
        ),
        "pending_ingress": {
            "digest": found["digest"],
            "bytes": found.get("bytes"),
            "recorded": found.get("recorded"),
            "route": route,
            "preview": found.get("preview"),
        },
        "supplied_digest": ingress_digest(text),
        "canonical_next_command": route,
        "supersede_command": "saipen start " + SUPERSEDE_FLAG + " <task>",
    }


__all__ = [
    "CODE_PARAPHRASE",
    "CODE_UNREADABLE",
    "MAX_AGE_SECONDS",
    "SCHEMA_VERSION",
    "SUPERSEDE_FLAG",
    "clear",
    "enforce",
    "ingress_digest",
    "pending",
    "pending_path",
    "record",
]
