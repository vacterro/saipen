"""Runtime-local watchdog and mutation-lease fencing (T-1448).

This module owns no protocol truth.  It records replaceable worker health under
``.saipen/cache`` and fails closed when the carrier is absent, corrupt, stale,
or belongs to an older lease generation.  Durable Work/checkpoint authority
remains STATE/BOARD/LOG and is deliberately not copied into this cache.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import functools
from dataclasses import dataclass
from pathlib import Path

from .paths import safe_atomic_write_bytes

CACHE_REL = Path(".saipen") / "cache" / "autonomy-watchdog.json"
SCHEMA_VERSION = 1
HEALTHY = "HEALTHY"
SUSPECT = "SUSPECT"
EXPIRED = "EXPIRED"
TERMINAL = "TERMINAL"
UNKNOWN = "UNKNOWN"
HEALTH_STATES = (HEALTHY, SUSPECT, EXPIRED, TERMINAL, UNKNOWN)
CLAIM_WITNESSES = ("claim_run", "claim_generation")
AUTONOMY_ENV = ("SAIPEN_AUTONOMY_RUN_ID", "SAIPEN_AUTONOMY_WORKER", "SAIPEN_LEASE_GENERATION")


def _serialized(fn):
    """Fence changes and canonical APPLY share the same project mutex."""

    @functools.wraps(fn)
    def wrapped(root, *args, **kwargs):
        import time
        from .lock import WriterLock

        lock = WriterLock(root)
        deadline = time.monotonic() + 5
        while True:
            try:
                lock.acquire()
                break
            except PermissionError as exc:
                if "WRITER_BUSY" not in str(exc):
                    raise
                if time.monotonic() >= deadline:
                    raise RuntimeError("WRITER_BUSY") from exc
                time.sleep(0.02)
        try:
            return fn(root, *args, **kwargs)
        finally:
            lock.release()

    return wrapped


def _binding(root: Path | str, run_id: str) -> dict:
    from .board import claim_session_digest
    from .paths import project_lineage_identity

    lineage = project_lineage_identity(root)
    return {
        "project_root": str(Path(root).resolve()),
        "project_lineage": lineage,
        "run_binding": claim_session_digest(lineage, run_id) if lineage else None,
    }


def carrier_present() -> bool:
    return any(name in os.environ for name in AUTONOMY_ENV)


def current_carrier(root: Path | str) -> dict | None:
    """Prove all presented runtime witnesses against the current healthy lease.

    Environment values are witnesses, never authentication. Missing, partial,
    cross-project and stale carriers cannot authorize a canonical mutation.
    """
    run_id, worker_id, raw_generation = (os.environ.get(key, "") for key in AUTONOMY_ENV)
    if not run_id or not worker_id or not raw_generation.isdecimal():
        return None
    generation = int(raw_generation)
    expected = _binding(root, run_id)
    if not expected["run_binding"]:
        return None
    for key, value in (
        ("SAIPEN_PROJECT_ROOT", expected["project_root"]),
        ("SAIPEN_PROJECT_LINEAGE", expected["project_lineage"]),
    ):
        presented = os.environ.get(key)
        if presented is not None:
            if key == "SAIPEN_PROJECT_ROOT":
                try:
                    if Path(presented).resolve() != Path(value):
                        return None
                except (OSError, ValueError):
                    return None
            elif presented != value:
                return None
    current = _load(root)
    if (
        not current
        or any(current.get(k) != v for k, v in expected.items())
        or not mutation_allowed(root, worker_id, generation)
    ):
        return None
    return current


def claim_witnesses(root: Path | str) -> dict[str, str]:
    current = current_carrier(root)
    if current is None:
        return {}
    return {
        "claim_run": current["run_binding"],
        "claim_generation": str(current["lease_generation"]),
    }


def can_continue_claim(root: Path | str, ticket: dict, session_id: str | None = None) -> bool:
    """One continuation predicate: healthy successor -> fenced predecessor -> claim."""
    from .board import host_session_binding, claim_session_digest, claim_status
    from .paths import project_lineage_identity
    from .state import parse_state_or_error, binding_brake

    current = current_carrier(root)
    fields = ticket.get("fields") or {}
    session = (
        claim_session_digest(project_lineage_identity(root), session_id)
        if session_id is not None
        else host_session_binding(root)
    )
    old_session = fields.get("claim_session")
    if (
        not current
        or ticket.get("section") != "## DOING"
        or claim_status(ticket) not in ("FOREIGN_LIVE", "FOREIGN_STALE")
        or not old_session
        or not session
        or session == old_session
        or fields.get("claim_run") != current["run_binding"]
    ):
        return False
    try:
        state, error = parse_state_or_error(
            (Path(root) / ".saipen/STATE.md").read_text(encoding="utf-8-sig")
        )
    except (OSError, UnicodeError):
        return False
    if (
        error
        or state.get("task") != ticket.get("id")
        or state.get("phase") not in ("SCOUT", "BUILD", "VERIFY", "REVIEW", "SHIP")
        or state.get("mode") == "read-only"
        or binding_brake(state) is not None
    ):
        return False
    old = str(fields.get("claim_generation", ""))
    if not old.isdecimal() or not 0 < int(old) < current["lease_generation"]:
        return False
    return any(
        record.get("lease_generation") == int(old)
        and record.get("run_binding") == fields["claim_run"]
        and record.get("project_root") == current["project_root"]
        and record.get("project_lineage") == current["project_lineage"]
        and _instant(record.get("fenced_at")) is not None
        for record in current.get("fenced_generations", [])
        if isinstance(record, dict)
    )


def _instant(value: str) -> _dt.datetime | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text.endswith("Z"):
        return None
    try:
        parsed = _dt.datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _utc(value: _dt.datetime | None = None) -> str:
    value = value or _dt.datetime.now(_dt.timezone.utc)
    return (
        value.astimezone(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )


@dataclass(frozen=True)
class WatchdogStatus:
    state: str
    worker_id: str | None
    lease_generation: int | None
    heartbeat_at: str | None
    age_seconds: float | None
    reason: str

    def as_dict(self) -> dict:
        return {
            "state": self.state,
            "worker_id": self.worker_id,
            "lease_generation": self.lease_generation,
            "heartbeat_at": self.heartbeat_at,
            "age_seconds": self.age_seconds,
            "reason": self.reason,
        }


def _contended(action, attempts: int = 50):
    """Retry a lease-file access that lost a Windows sharing race.

    Workers read the lease while the supervisor replaces it; Windows reports
    either side of that race as PermissionError. It is contention, never a
    missing or fenced lease, so it is retried briefly before it is believed.
    """
    import time

    for attempt in range(attempts):
        try:
            return action()
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.01)


def _path(root: Path | str) -> Path:
    return Path(root).resolve() / CACHE_REL


def _load(root: Path | str) -> dict | None:
    path = _path(root)
    try:
        payload = json.loads(_contended(lambda: path.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        return None
    if not isinstance(payload.get("lease_generation"), int) or payload["lease_generation"] < 1:
        return None
    if not isinstance(payload.get("worker_id"), str) or not payload["worker_id"].strip():
        return None
    if _instant(payload.get("heartbeat_at")) is None:
        return None
    records = payload.get("fenced_generations", [])
    if not isinstance(records, list) or any(not isinstance(r, dict) for r in records):
        return None
    return payload


def _save(root: Path | str, payload: dict) -> None:
    root = Path(root).resolve()
    body = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _contended(
        lambda: safe_atomic_write_bytes(
            _path(root),
            body,
            kind="autonomy watchdog runtime state",
            ownership_root=root,
        )
    )


@_serialized
def acquire_lease(
    root: Path | str, worker_id: str, *, now: _dt.datetime | None = None, run_id: str = ""
) -> dict:
    """Create generation 1 or advance the fenced generation.

    A live, healthy lease is never silently stolen.  Callers must observe and
    fence an unhealthy generation before invoking this replacement operation.
    """
    current = _load(root)
    if current is not None:
        status = observe(root, now=now)
        if status.state in (HEALTHY, SUSPECT):
            raise RuntimeError("LIVE_LEASE_PRESENT")
        generation = current["lease_generation"] + 1
    else:
        generation = 1
    payload = {
        "schema_version": SCHEMA_VERSION,
        "worker_id": str(worker_id),
        "lease_generation": generation,
        "heartbeat_at": _utc(now),
        "status": HEALTHY,
        **(_binding(root, run_id) if run_id else {}),
        "fenced_generations": list((current or {}).get("fenced_generations", [])),
    }
    _save(root, payload)
    return payload.copy()


# No project mutex here: a worker's canonical APPLY fails fast on
# WRITER_BUSY, so a beat holding it would kill the generation it serves.
# The supervisor that beats is the same thread that fences.
def heartbeat(
    root: Path | str,
    worker_id: str,
    lease_generation: int,
    *,
    now: _dt.datetime | None = None,
) -> dict:
    """Refresh only the current generation; stale workers are fenced."""
    current = _load(root)
    if current is None:
        raise RuntimeError("UNKNOWN_LEASE")
    if current["worker_id"] != worker_id or current["lease_generation"] != lease_generation:
        raise RuntimeError("FENCED_LEASE_GENERATION")
    if _is_fenced(current):
        # A fenced generation must not revive itself. Before T-1446 this
        # rewrote status back to HEALTHY, so a returning fenced worker
        # un-fenced its own lease with one heartbeat.
        raise RuntimeError("FENCED_LEASE_GENERATION")
    payload = {**current, "heartbeat_at": _utc(now), "status": HEALTHY}
    _save(root, payload)
    return payload.copy()


def _is_fenced(current: dict) -> bool:
    return current.get("status") == EXPIRED and bool(current.get("fenced_at"))


def observe(
    root: Path | str,
    *,
    now: _dt.datetime | None = None,
    suspect_after: float = 30.0,
    expire_after: float = 120.0,
) -> WatchdogStatus:
    """Reconstruct health after supervisor restart, failing closed on unknown."""
    current = _load(root)
    if current is None:
        return WatchdogStatus(UNKNOWN, None, None, None, None, "missing_or_corrupt_runtime_state")
    heartbeat_at = _instant(current["heartbeat_at"])
    observed_at = now or _dt.datetime.now(_dt.timezone.utc)
    age = max(0.0, (observed_at - heartbeat_at).total_seconds())
    if current.get("status") == TERMINAL:
        state, reason = TERMINAL, "worker_terminal"
    elif _is_fenced(current):
        # Fencing takes effect when it is written, not when the heartbeat
        # ages out: a fenced generation read as HEALTHY for up to
        # `expire_after`, still passed `mutation_allowed`, and blocked its own
        # replacement with LIVE_LEASE_PRESENT (measured 2026-09-22).
        state, reason = EXPIRED, "fenced"
    elif age >= expire_after:
        state, reason = EXPIRED, "heartbeat_timeout"
    elif age >= suspect_after:
        state, reason = SUSPECT, "heartbeat_late"
    else:
        state, reason = HEALTHY, "heartbeat_current"
    return WatchdogStatus(
        state,
        current["worker_id"],
        current["lease_generation"],
        current["heartbeat_at"],
        age,
        reason,
    )


@_serialized
def fence(
    root: Path | str, worker_id: str, lease_generation: int, *, now: _dt.datetime | None = None
) -> dict:
    """Fence exactly the observed generation; stale callers cannot fence a replacement."""
    current = _load(root)
    if current is None:
        raise RuntimeError("UNKNOWN_LEASE")
    if current["worker_id"] != worker_id or current["lease_generation"] != lease_generation:
        raise RuntimeError("FENCED_LEASE_GENERATION")
    records = list(current.get("fenced_generations", []))
    fenced_at = current.get("fenced_at") or _utc(now)
    if not any(r.get("lease_generation") == lease_generation for r in records):
        records.append(
            {
                key: current.get(key)
                for key in (
                    "worker_id",
                    "lease_generation",
                    "run_binding",
                    "project_root",
                    "project_lineage",
                )
            }
            | {"fenced_at": fenced_at}
        )
    payload = {**current, "status": EXPIRED, "fenced_at": fenced_at, "fenced_generations": records}
    _save(root, payload)
    return payload.copy()


def mutation_allowed(
    root: Path | str, worker_id: str, lease_generation: int, *, now: _dt.datetime | None = None
) -> bool:
    """Admission predicate: only current healthy generation may mutate."""
    current = _load(root)
    status = observe(root, now=now)
    return bool(
        current
        and status.state == HEALTHY
        and current.get("worker_id") == worker_id
        and current.get("lease_generation") == lease_generation
    )
