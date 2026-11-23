"""A long gate in flight binds the tree it tests; the agent keeps working (T-1575).

Defect classes this closes (SRC-151):

* IDLE WAIT. The declared core-unit family runs for many minutes; an agent that
  blocks on it, or sleep-polls it, spends that wall-clock doing nothing.
* WASTED RUN. The family's record is bound to the tree fingerprint (everything
  outside `.saipen/`). An agent that "uses the time" by editing that tree makes
  the record uncitable and forces a full re-run (measured 2026-09-23: two runs).

One owner answers both. The running gate writes a marker under the machine-local
`.saipen/cache/` namespace; `saipen continue|status` project the PARALLEL LANE
(what may be done meanwhile), and the admission guard refuses an in-root
mutation outside `.saipen/` while the marker is live (`TREE_UNDER_TEST`). A
marker is live only while the process that wrote it is running (pid plus its
creation time, so a reused pid never freezes a tree) and younger than
`MAX_AGE_S`; anything else is stale and ignored, so a crashed run never wedges
the project.
"""

from __future__ import annotations

import contextlib
import json
import os
import time
from pathlib import Path

MARKER_REL = ".saipen/cache/inflight/core-unit.json"
MAX_AGE_S = 6 * 3600
CODE_TREE_UNDER_TEST = "TREE_UNDER_TEST"

#: What an agent does while the tree is frozen, cheapest-first. Every item is
#: safe against the tested fingerprint: nothing here edits a path outside
#: `.saipen/` inside the project root.
PARALLEL_LANE = (
    "review the tested diff and draft the REVIEW evidence (read-only)",
    "write evidence and helper scripts under .saipen/evidence/",
    "SCOUT the next queued Work read-only (no claim while this seat holds a ticket)",
    "develop the next change in a scratch copy outside the project root",
    "update knowledge cards",
)
AWAIT_RULE = (
    "await the gate's completion through the host's background-job signal or one "
    "blocking wait on its process; never sleep-poll and never idle-wait"
)


def _process_created(pid: int) -> float | None:
    """The creation time of `pid` in epoch seconds, or None when unknowable."""
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, int(pid))  # QUERY_LIMITED
            if not handle:
                return None
            try:
                times = [wintypes.FILETIME() for _ in range(4)]
                if not kernel32.GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):
                    return None
                ticks = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
                return ticks / 10_000_000 - 11_644_473_600
            finally:
                kernel32.CloseHandle(handle)
        except (OSError, AttributeError, ValueError):
            return None
    try:
        stat = Path(f"/proc/{int(pid)}/stat").read_text(encoding="ascii")
        ticks = int(stat.rsplit(")", 1)[1].split()[19])
        boot = next(
            float(line.split()[1])
            for line in Path("/proc/stat").read_text(encoding="ascii").splitlines()
            if line.startswith("btime ")
        )
        return boot + ticks / os.sysconf("SC_CLK_TCK")
    except (OSError, ValueError, IndexError, StopIteration):
        return None


def _alive(pid: object) -> bool:
    from .core_unit import pid_alive

    return isinstance(pid, int) and not isinstance(pid, bool) and pid_alive(pid)


def begin(root: Path | str, ticket: str, command: str) -> Path:
    """Write this process's marker; a previous marker is replaced."""
    path = Path(root) / MARKER_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    now = time.time()
    record = {
        "schema": 1,
        "kind": "core-unit",
        "ticket": str(ticket or ""),
        "command": str(command or ""),
        "pid": os.getpid(),
        "pid_created": _process_created(os.getpid()),
        "started": now,
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
    }
    staging = path.with_name(path.name + f".{os.getpid()}.tmp")
    staging.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    os.replace(staging, path)
    return path


def end(root: Path | str) -> None:
    """Remove the marker when this process wrote it; never another's."""
    path = Path(root) / MARKER_REL
    with contextlib.suppress(OSError, ValueError):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("pid") == os.getpid():
            path.unlink()


@contextlib.contextmanager
def holding(root: Path | str, ticket: str, command: str):
    """The tree is frozen for exactly the lifetime of the block."""
    begin(root, ticket, command)
    try:
        yield
    finally:
        end(root)


def current(root: Path | str, now: float | None = None) -> dict | None:
    """The live in-flight record, or None (absent, unreadable or stale)."""
    path = Path(root) / MARKER_REL
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(record, dict) or record.get("schema") != 1:
        return None
    started = record.get("started")
    now = time.time() if now is None else now
    if not isinstance(started, (int, float)) or not 0 <= now - started <= MAX_AGE_S:
        return None
    if not _alive(record.get("pid")):
        return None
    created = record.get("pid_created")
    if isinstance(created, (int, float)):
        observed = _process_created(record["pid"])
        if observed is not None and abs(observed - created) > 2:
            return None  # the pid now names a different process
    return record


def frozen_targets(root: Path | str, relative_paths) -> list[str]:
    """In-root targets outside `.saipen/` that a live gate forbids editing."""
    paths = [str(p).replace("\\", "/").lstrip("/") for p in relative_paths or ()]
    inside = [p for p in paths if p and not p.lower().startswith(".saipen/") and p != ".saipen"]
    if not inside or current(root) is None:
        return []
    return inside


def frozen_owner(path: Path | str) -> str | None:
    """The project root whose live gate freezes an OUTSIDE-root `path`, or None.

    Measured 2026-09-30: an agent bound to another project edited this
    repository's `tools/improve.py` mid-run, the family re-snapshotted and ran
    twice. Every enclosing SAIPEN project is checked, not only the nearest, so a
    nested fixture project cannot hide the outer tree's gate.
    """
    target = Path(path)
    for ancestor in target.parents:
        if not (ancestor / ".saipen").is_dir():
            continue
        try:
            relative = target.relative_to(ancestor).as_posix()
        except ValueError:
            continue
        if relative.lower().startswith(".saipen/"):
            continue
        if current(ancestor) is not None:
            return str(ancestor)
    return None


def lane(root: Path | str) -> dict | None:
    """The turn-entry projection while a gate is in flight, else None."""
    record = current(root)
    if record is None:
        return None
    return {
        "kind": record.get("kind"),
        "ticket": record.get("ticket") or None,
        "pid": record.get("pid"),
        "since": record.get("started_utc"),
        "tree_frozen": True,
        "refusal_code": CODE_TREE_UNDER_TEST,
        "await": AWAIT_RULE,
        "parallel_lane": list(PARALLEL_LANE),
    }
