"""T-1446 / SRC-100: the bounded autonomy worker, as a real separate process.

`supervisor` decides; this runs. It is a separate module AND a separate
process on purpose: "the worker died" is the case the whole lease design
exists for, and a worker that is a function call in the supervisor's own
process cannot die without taking the supervisor with it. Every in-process
test of crash recovery is therefore a test of something else.

One slice is: prove the lease still admits mutation, refresh the heartbeat,
advance the durable checkpoint, repeat. The checkpoint is DERIVED runtime
state under `.saipen/cache/`, never canonical truth -- a replacement
generation reads it to learn where the dead generation stopped, and then
resolves what to do next through the canonical router like any cold worker.

`--die-after N` exits with `os._exit`, skipping every finally-block and
atexit hook, because a worker that gets to clean up after itself is not the
worker this protocol has to survive.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from pathlib import Path

from . import supervisor, watchdog
from .paths import safe_atomic_write_bytes

CHECKPOINT_REL = Path(".saipen") / "cache" / "autonomy-worker.json"
SCHEMA_VERSION = 1

#: Exit codes. A worker's exit status is the only thing a supervisor that did
#: not read its stdout can see, so each refusal gets its own number.
EXIT_OK = 0
EXIT_NO_AUTHORITY = 3
EXIT_STOPPED = 4
EXIT_FENCED = 5


def checkpoint_path(root: Path | str) -> Path:
    return Path(root).resolve() / CHECKPOINT_REL


def read_checkpoint(root: Path | str) -> dict | None:
    """The last durable slice a worker finished here, or None."""
    try:
        payload = json.loads(checkpoint_path(root).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        return None
    return payload


def write_checkpoint(root: Path | str, payload: dict) -> None:
    root = Path(root).resolve()
    body = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    safe_atomic_write_bytes(
        checkpoint_path(root),
        body,
        kind="autonomy worker checkpoint",
        ownership_root=root,
    )


def _utc(now: _dt.datetime | None = None) -> str:
    return watchdog._utc(now)


def take_authority(
    root: Path | str,
    worker_id: str,
    *,
    now: _dt.datetime | None = None,
    suspect_after: float = 30.0,
    expire_after: float = 120.0,
) -> dict:
    """Acquire, adopt or replace -- whichever the supervisor's verdict allows.

    Never a fourth option. A worker that decides for itself which of these it
    is doing is a worker that can take a live generation's seat.
    """
    verdict = supervisor.decide(
        root,
        now=now,
        worker_id=worker_id,
        suspect_after=suspect_after,
        expire_after=expire_after,
    )
    name = verdict["verdict"]
    if name == supervisor.ADOPT_WORKER:
        return {
            "ok": True,
            "code": "LEASE_ADOPTED",
            "generation": verdict["adopt_generation"],
            "verdict": name,
        }
    if name == supervisor.RUN_WORK:
        try:
            lease = watchdog.acquire_lease(root, worker_id, now=now)
        except RuntimeError as exc:
            return {"ok": False, "code": str(exc), "verdict": name}
        return {
            "ok": True,
            "code": "LEASE_ACQUIRED",
            "generation": lease["lease_generation"],
            "verdict": name,
        }
    if name == supervisor.REPLACE_WORKER:
        replaced = supervisor.replace_worker(
            root,
            worker_id,
            now=now,
            suspect_after=suspect_after,
            expire_after=expire_after,
        )
        if not replaced["ok"]:
            return {**replaced, "verdict": name}
        return {
            "ok": True,
            "code": "LEASE_REPLACED",
            "generation": replaced["lease"]["lease_generation"],
            "fenced_generation": replaced["fenced_generation"],
            "verdict": name,
        }
    return {"ok": False, "code": name, "reason": verdict["reason"], "verdict": name}


def run_slice(
    root: Path | str,
    worker_id: str,
    generation: int,
    *,
    index: int,
    work: str | None,
    now: _dt.datetime | None = None,
) -> dict:
    """One bounded unit: admission check, heartbeat, durable checkpoint."""
    if not watchdog.mutation_allowed(root, worker_id, generation, now=now):
        return {"ok": False, "code": "FENCED_LEASE_GENERATION"}
    watchdog.heartbeat(root, worker_id, generation, now=now)
    previous = read_checkpoint(root) or {}
    payload = {
        "schema_version": SCHEMA_VERSION,
        "worker_id": worker_id,
        "lease_generation": generation,
        "slice_index": index,
        "slices_total": int(previous.get("slices_total") or 0) + 1,
        "work": work,
        "at": _utc(now),
        "previous_worker": previous.get("worker_id"),
        "previous_generation": previous.get("lease_generation"),
    }
    write_checkpoint(root, payload)
    return {"ok": True, "code": "SLICE_DONE", "checkpoint": payload}


def serve(
    root: Path | str,
    worker_id: str,
    *,
    slices: int = 1,
    die_after: int | None = None,
    suspect_after: float = 30.0,
    expire_after: float = 120.0,
) -> dict:
    """Take authority, run bounded slices, report. Crashes hard on demand."""
    root = Path(root)
    authority = take_authority(
        root, worker_id, suspect_after=suspect_after, expire_after=expire_after
    )
    if not authority["ok"]:
        return authority
    generation = authority["generation"]
    picture = supervisor.observe(
        root, suspect_after=suspect_after, expire_after=expire_after
    )
    work = picture["active_work"] or picture["executable_work"]
    done = 0
    for index in range(1, int(slices) + 1):
        outcome = run_slice(root, worker_id, generation, index=index, work=work)
        if not outcome["ok"]:
            return {**outcome, "generation": generation, "slices_done": done}
        done = index
        if die_after is not None and done >= int(die_after):
            # A crash, not a shutdown: no finally, no atexit, no lease release.
            sys.stdout.flush()
            os._exit(9)
    return {
        "ok": True,
        "code": "WORKER_DONE",
        "generation": generation,
        "slices_done": done,
        "authority": authority["code"],
        "work": work,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SAIPEN bounded autonomy worker")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--slices", type=int, default=1)
    parser.add_argument("--die-after", type=int, default=None)
    parser.add_argument("--suspect-after", type=float, default=30.0)
    parser.add_argument("--expire-after", type=float, default=120.0)
    args = parser.parse_args(argv)
    result = serve(
        args.project_root,
        args.worker_id,
        slices=args.slices,
        die_after=args.die_after,
        suspect_after=args.suspect_after,
        expire_after=args.expire_after,
    )
    print(json.dumps(result, sort_keys=True))
    if result.get("ok"):
        return EXIT_OK
    if result.get("code") == supervisor.AMBIGUOUS_AUTHORITY:
        return EXIT_NO_AUTHORITY
    if result.get("code") == "FENCED_LEASE_GENERATION":
        return EXIT_FENCED
    return EXIT_STOPPED


if __name__ == "__main__":  # pragma: no cover - process entry point
    raise SystemExit(main())
