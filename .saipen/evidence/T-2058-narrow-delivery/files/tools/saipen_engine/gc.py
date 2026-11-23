"""Provenance-safe garbage collection (T-2049).

The collector that ran on 2026-11-12 01:16 deleted 738 canonical evidence
records, classified ``SUPERSEDED_BY_LOG``, because a LOG line cited them. A
citation is not a replacement artifact: the SHIP gate and the digest read the
JSON record itself, so the engine destroyed proof it claimed to compact. This
module is the reimplementation and it is built around that failure:

* a class is a claim about WHO can still prove the artifact's content. Anything
  the collector cannot prove is ``UNKNOWN_OWNERSHIP`` and is kept;
* ``.saipen/**`` is canonical proof for a gate that reads the record, not the
  LOG line, so no budget and no citation may delete it. An over-budget evidence
  tree is a reported blocker, never a deletion;
* only trees whose content is rebuilt by a tool that owns them (``__pycache__``,
  ``.pytest_cache``, ``.ruff_cache``, compiled bytecode) and generated builds an
  OWNERSHIP MANIFEST proves superseded are reclaimable;
* protecting a path's exact identity does not protect its descendants: a
  directory target is refused whole if ANY descendant is tracked, staged,
  dirty, linked, hard-linked, nested-Git or of unknown ownership. The
  ``work/__pycache__/tracked.pyc`` case is the regression that names this rule;
* a Git probe that cannot COMPLETE is a refusal, not an empty protection set:
  git missing, a timeout, a nonzero exit, an invalid repository, a mismatched
  toplevel and malformed output all produce ``GIT_GUARD_FAILED`` and no plan;
* a symlink, junction or reparse point anywhere on the path is a refusal, never
  a traversal -- a Windows junction under a build tree once pointed at a
  canonical directory;
* the plan is recomputed UNDER the writer lock and every target is re-audited
  immediately before mutation, so a plan cannot outlive the bytes it named;
* the journal names PLANNED / PREPARED / DELETE_STARTED / PARTIAL /
  DELETE_CONFIRMED / COMMITTED / RECONCILE_REQUIRED per target, and recovery
  credits ONLY observed ``DELETE_CONFIRMED`` bytes. A missing path is never
  booked as reclaimed storage;
* a malformed ``GC_STATE.json`` refuses destructive work, preserves the bad
  bytes and repairs only from independently validated canonical completion
  history (``finish`` events in the active and sealed LOG), never by resetting
  to zero and never from the current BOARD projection alone;
* the trigger is a durable counter of DISTINCT committed closures, so a
  duplicate DONE, a replayed VERIFY, a BOARD scrub or a re-imported snapshot
  cannot schedule extra work and cannot lose history.

The collector never writes the ledger. Its whole output is
``.saipen/GC_STATE.json``, its run records under ``.saipen/gc/runs/`` and the
deletions it proves.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .paths import safe_atomic_write_bytes

SCHEMA = 1
STATE_REL = ".saipen/GC_STATE.json"
RUNS_REL = ".saipen/gc/runs"
CORRUPT_REL = ".saipen/gc/corrupt"
REPAIR_REL = ".saipen/gc/repair"
PROGRESS_SUFFIX = ".progress.jsonl"
BOARD_REL = ".saipen/BOARD.md"
LOG_REL = ".saipen/LOG.md"
SEALED_LOG_REL = ".saipen/logs"
MANIFEST_REL = ".saipen/gc/build-manifest.json"
SETTLEMENT_REL = ".saipen/gc/settlement.jsonl"
FAILURE_REL = ".saipen/gc/maintenance-failures.jsonl"

#: Budget targets, not deletion authority (T-2049 acceptance).
DEFAULTS: dict = {
    "enabled": True,
    "interval_done": 20,
    "initial_scan": True,
    "budget_trigger": True,
    "evidence_budget_gib": 2.0,
    "generated_build_budget_gib": 10.0,
    "raw_success_grace_hours": 24,
    "raw_failure_grace_days": 7,
    "retain_current_build": True,
    "retain_verified_rollback": True,
    "unknown_policy": "KEEP",
}

#: Trees whose content a owning tool regenerates. Nothing else is reclaimable
#: by name: the list is deliberately small and is not a glob over build output,
#: because a `dist*` pattern is how a release artefact gets collected.
EPHEMERAL_DIR_NAMES = frozenset(
    {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".hypothesis"}
)
EPHEMERAL_SUFFIXES = (".pyc", ".pyo")

#: Subtrees the walk never enters. `.saipen/**` is canonical memory; the rest
#: are foreign-owned installed trees whose contents we cannot prove.
PRUNE_DIR_NAMES = frozenset({".git", "node_modules", ".venv", "venv", ".tox", ".nox"})

#: Canonical carriers. A collector that can name any of these is a collector
#: that can destroy proof, so the prefix lookup runs before any classification.
PROTECTED_PREFIXES = (
    ".git/",
    ".saipen/",
    "saipen/",
    "extensions/",
    "bootstrap/",
)

#: Retention classes. The first block is refusals: they exist so a report can
#: say WHY a path was kept instead of leaving it unexplained.
PROTECTED_LEDGER = "PROTECTED_LEDGER"
PROTECTED_GIT = "PROTECTED_GIT"
PROTECTED_LINK = "PROTECTED_LINK"
UNKNOWN_OWNERSHIP = "UNKNOWN_OWNERSHIP"
EPHEMERAL_REPRODUCIBLE = "EPHEMERAL_REPRODUCIBLE"
GENERATED_BUILD_SUPERSEDED = "GENERATED_BUILD_SUPERSEDED"
BUILD_CURRENT = "BUILD_CURRENT"
BUILD_DEPLOYED = "BUILD_DEPLOYED"
BUILD_ROLLBACK = "BUILD_ROLLBACK"
BUILD_REFERENCED = "BUILD_REFERENCED"
BUILD_UNVERIFIED = "BUILD_UNVERIFIED"

KEEP_CLASSES = frozenset(
    {
        PROTECTED_LEDGER,
        PROTECTED_GIT,
        PROTECTED_LINK,
        UNKNOWN_OWNERSHIP,
        BUILD_CURRENT,
        BUILD_DEPLOYED,
        BUILD_ROLLBACK,
        BUILD_REFERENCED,
        BUILD_UNVERIFIED,
    }
)

#: Journal states. `RECONCILE_REQUIRED` is the only one a crash may produce
#: that is not proof of an outcome.
PLANNED = "PLANNED"
PREPARED = "PREPARED"
DELETE_STARTED = "DELETE_STARTED"
PARTIAL = "PARTIAL"
DELETE_CONFIRMED = "DELETE_CONFIRMED"
COMMITTED = "COMMITTED"
RECONCILE_REQUIRED = "RECONCILE_REQUIRED"

#: Durable maintenance-debt states (T-2059). Every state is written into
#: `GC_STATE.json`'s `maintenance` block, so a restart, a replay, a BOARD scrub
#: or a LOG seal cannot lose what maintenance still owes. `GC_SETTLED` is the
#: ONLY state that means the debt was honestly paid: a run that reclaimed zero
#: bytes against protected canonical proof stays an open blocked state.
DEBT_DUE = "GC_DUE"
DEBT_RUNNING = "GC_RUNNING"
DEBT_PARTIAL = "GC_PARTIAL"
DEBT_BLOCKED_NO_SAFE_CANDIDATES = "GC_BLOCKED_NO_SAFE_CANDIDATES"
DEBT_BLOCKED_PROTECTED_BUDGET = "GC_BLOCKED_PROTECTED_BUDGET"
DEBT_FAILED = "GC_FAILED"
DEBT_SETTLED = "GC_SETTLED"

#: Debt states that still owe a real collection. A fingerprint that matches the
#: last zero-progress attempt against one of these suppresses the identical
#: expensive retry; a changed fingerprint reactivates it.
OPEN_DEBT_STATES = frozenset(
    {DEBT_DUE, DEBT_RUNNING, DEBT_PARTIAL, DEBT_BLOCKED_NO_SAFE_CANDIDATES,
     DEBT_BLOCKED_PROTECTED_BUDGET, DEBT_FAILED}
)
ZERO_PROGRESS_DEBT_STATES = frozenset(
    {DEBT_PARTIAL, DEBT_BLOCKED_NO_SAFE_CANDIDATES, DEBT_BLOCKED_PROTECTED_BUDGET}
)

#: A `finish-*` operation is the atomic canonical closure; its event carries the
#: ticket tag and survives BOARD scrub, LOG seal and re-import verbatim.
_FINISH_OP = re.compile(r"\[op:\s*finish-[^\]]*\]")
_TICKET_TAG = re.compile(r"\[(T-\d+)\]")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _norm(path: str) -> str:
    return path.replace(os.sep, "/").replace("\\", "/")


def _new_run_id() -> str:
    return time.strftime("%Y%m%dT%H%M%S", time.gmtime()) + "-" + uuid.uuid4().hex[:8]


def _sha(text: bytes) -> str:
    return hashlib.sha256(text).hexdigest()


def _default_state() -> dict:
    return {
        "schema": SCHEMA,
        "counted_done": [],
        "runs": [],
        "config": dict(DEFAULTS),
        "closure_sources": {"sealed": []},
        "maintenance": {
            "state": DEBT_SETTLED,
            "reason": None,
            "fingerprint": None,
            "last_attempt_fingerprint": None,
            "blockers": [],
            "protected_bytes": 0,
            "updated": None,
        },
    }


# --------------------------------------------------------------------------- state


def state_path(root: Path | str) -> Path:
    return Path(root) / STATE_REL


def read_state(root: Path | str) -> dict:
    """The durable counter and a typed verdict on the bytes that carry it.

    ``status`` is ``ok``, ``missing``, ``unreadable`` or ``corrupt``. A corrupt
    document is NEVER silently replaced by a default: the caller decides, and
    every destructive route refuses until ``repair`` has proved a replacement.
    """
    path = state_path(root)
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return {"status": "missing", "state": _default_state(), "detail": None}
    except OSError as exc:
        return {
            "status": "unreadable",
            "state": _default_state(),
            "detail": f"{path}: {exc}",
            "raw": None,
        }
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        return {
            "status": "corrupt",
            "state": _default_state(),
            "detail": f"{path}: not a JSON document ({exc})",
            "raw": raw,
        }
    if not isinstance(document, dict):
        return {
            "status": "corrupt",
            "state": _default_state(),
            "detail": f"{path}: document is {type(document).__name__}, not an object",
            "raw": raw,
        }
    if document.get("schema") != SCHEMA:
        return {
            "status": "corrupt",
            "state": _default_state(),
            "detail": f"{path}: schema {document.get('schema')!r} is not {SCHEMA}",
            "raw": raw,
        }
    counted = document.get("counted_done")
    if counted is None:
        counted = []
    if not isinstance(counted, list) or any(not isinstance(item, str) for item in counted):
        return {
            "status": "corrupt",
            "state": _default_state(),
            "detail": f"{path}: counted_done is not a list of ticket identities",
            "raw": raw,
        }
    document["counted_done"] = list(dict.fromkeys(counted))
    runs = document.get("runs")
    if not isinstance(runs, list) or any(not isinstance(entry, dict) for entry in runs):
        return {
            "status": "corrupt",
            "state": _default_state(),
            "detail": f"{path}: runs is not a list of run records",
            "raw": raw,
        }
    document["runs"] = list(runs)
    config = dict(DEFAULTS)
    if isinstance(document.get("config"), dict):
        config.update(document["config"])
    elif document.get("config") is not None:
        return {
            "status": "corrupt",
            "state": _default_state(),
            "detail": f"{path}: config is not an object",
            "raw": raw,
        }
    document["config"] = config
    sources = document.get("closure_sources")
    if not isinstance(sources, dict) or not isinstance(sources.get("sealed"), list):
        return {
            "status": "corrupt",
            "state": _default_state(),
            "detail": f"{path}: closure_sources has no sealed-segment list",
            "raw": raw,
        }
    maintenance = document.get("maintenance")
    if maintenance is not None and not isinstance(maintenance, dict):
        return {
            "status": "corrupt",
            "state": _default_state(),
            "detail": f"{path}: maintenance is not an object",
            "raw": raw,
        }
    return {"status": "ok", "state": document, "detail": None, "raw": raw}


def load_state(root: Path | str) -> dict:
    """The counter document. A corrupt carrier keeps its verdict on the result."""
    health = read_state(root)
    state = health["state"]
    if health["status"] in ("corrupt", "unreadable"):
        state["_corrupt"] = True
        state["_corrupt_detail"] = health["detail"]
    return state


def save_state(root: Path | str, state: dict) -> None:
    root = Path(root)
    payload = dict(state)
    payload.pop("_corrupt", None)
    payload.pop("_corrupt_detail", None)
    payload["schema"] = SCHEMA
    text = json.dumps(payload, indent=1, sort_keys=True) + "\n"
    safe_atomic_write_bytes(
        state_path(root),
        text.encode("utf-8"),
        kind="GC state",
        ownership_root=root,
    )


# ------------------------------------------------------------------ canonical history


def board_done_identities(root: Path | str) -> list[str]:
    """Distinct closed ticket identities the CURRENT BOARD projection holds."""
    from .board import parse_board

    try:
        text = (Path(root) / BOARD_REL).read_text(encoding="utf-8-sig")
    except OSError:
        return []
    parsed = parse_board(text)
    seen: dict[str, None] = {}
    for ticket_id, ticket in (parsed.get("tickets") or {}).items():
        if ticket.get("section") != "## DONE":
            continue
        seen.setdefault(str(ticket_id), None)
    return list(seen)


def _finish_identities(text: str) -> list[str]:
    found: list[str] = []
    for line in text.splitlines():
        if not _FINISH_OP.search(line):
            continue
        match = _TICKET_TAG.search(line)
        if match:
            found.append(match.group(1))
    return list(dict.fromkeys(found))


def sealed_logs(root: Path | str) -> list[Path]:
    directory = Path(root) / SEALED_LOG_REL
    if not directory.is_dir():
        return []
    return sorted(path for path in directory.glob("LOG-*.md") if path.is_file())


def canonical_closures(root: Path | str, state: dict | None = None) -> dict:
    """Committed closure identities from canonical history, never one projection.

    The active LOG tail, every sealed LOG segment and the BOARD DONE rows are
    unioned. A sealed segment is read once per state generation and remembered
    by name, so a routine checkpoint after a closure does not re-parse 6 MB of
    immutable history.
    """
    root = Path(root)
    state = state if state is not None else load_state(root)
    already = set((state.get("closure_sources") or {}).get("sealed") or [])
    seen: dict[str, None] = {}
    sources: dict[str, int] = {}
    try:
        active = (root / LOG_REL).read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        active = ""
    for ticket in _finish_identities(active):
        seen.setdefault(ticket, None)
    sources["active_log"] = len(seen)
    for path in sealed_logs(root):
        if path.name in already:
            continue
        try:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        for ticket in _finish_identities(text):
            seen.setdefault(ticket, None)
        sources[path.name] = len(seen)
    sources["sealed_segments"] = len(sealed_logs(root))
    for ticket in board_done_identities(root):
        seen.setdefault(ticket, None)
    sources["union"] = len(seen)
    return {"identities": list(seen), "sources": sources}


def canonical_total(root: Path | str, state: dict | None = None) -> dict:
    """Zero-write union of the recorded counter and canonical closure history."""
    state = state if state is not None else load_state(root)
    recorded = list(state.get("counted_done") or [])
    closures = canonical_closures(root, state)
    union = list(dict.fromkeys(recorded + closures["identities"]))
    return {
        "recorded": len(recorded),
        "canonical": len(closures["identities"]),
        "union": union,
        "pending": [tid for tid in union if tid not in set(recorded)],
        "sources": closures["sources"],
    }


def sync_counter(root: Path | str) -> dict:
    """Record every committed closure once. Replays cannot advance the counter."""
    root = Path(root)
    health = read_state(root)
    state = health["state"]
    if health["status"] in ("corrupt", "unreadable"):
        return {
            "ok": False,
            "code": "CORRUPT_GC_STATE",
            "detail": health["detail"],
            "counted": len(state["counted_done"]),
            "added": [],
        }
    total = canonical_total(root, state)
    counted = total["union"]
    added = total["pending"]
    closures = canonical_closures(root, state)
    sealed_seen = list((state.get("closure_sources") or {}).get("sealed") or [])
    sealed_seen.extend(
        path.name for path in sealed_logs(root) if path.name not in set(sealed_seen)
    )
    state["counted_done"] = counted
    state["closure_sources"] = {"sealed": sealed_seen}
    if added or sealed_seen != list((health["state"].get("closure_sources") or {}).get("sealed") or []):
        save_state(root, state)
    return {
        "ok": True,
        "code": "COUNTER_SYNCED",
        "counted": len(counted),
        "added": added,
        "next_threshold": next_threshold(len(counted), state["config"]),
        "sources": closures["sources"],
    }


def next_threshold(total: int, config: dict) -> int:
    interval = int(config.get("interval_done") or DEFAULTS["interval_done"])
    if interval <= 0:
        return 0
    return ((total // interval) + 1) * interval


def _interval_consumed(counted: int, interval: int) -> int:
    """Interval capacity a completed run has already paid for.

    A run that lands at 21 closures consumes the 20-closure interval, so 39
    closures is not due and 40 is. Anchoring to thresholds, not to the exact
    total at run time, is what makes the cadence survive a late or an early run.
    """
    if interval <= 0:
        return 0
    return (counted // interval) * interval


def protocol_digest(root: Path | str) -> str:
    """Digest of the canonical closure sources a reconstruction was built from."""
    root = Path(root)
    parts: list[bytes] = []
    for path in [root / LOG_REL, *sealed_logs(root), root / BOARD_REL]:
        try:
            parts.append(path.read_bytes())
        except OSError:
            parts.append(b"")
    return _sha(b"".join(parts))


# -------------------------------------------------------------------------- budgets


def _tree_bytes(path: Path) -> int:
    total = 0
    for base, _dirs, files in os.walk(path, followlinks=False):
        for name in files:
            try:
                total += os.lstat(os.path.join(base, name)).st_size
            except OSError:
                continue
    return total


def _file_bytes(node: Path) -> int:
    try:
        return os.lstat(node).st_size
    except OSError:
        return 0


def budget_report(root: Path | str, state: dict | None = None) -> dict:
    """Measured storage facts. A budget overrun is a report, never a warrant."""
    root = Path(root)
    state = state if state is not None else load_state(root)
    config = state["config"]
    evidence = root / ".saipen/evidence"
    evidence_bytes = _tree_bytes(evidence) if evidence.is_dir() else 0
    evidence_budget = int(float(config.get("evidence_budget_gib") or 0) * (1024**3))
    manifest = load_manifest(root)
    build_bytes = sum(
        _tree_bytes(root / entry["path"])
        for entry in manifest["builds"]
        if entry.get("path") and (root / entry["path"]).is_dir()
    )
    build_budget = int(float(config.get("generated_build_budget_gib") or 0) * (1024**3))
    blockers = []
    if evidence_budget and evidence_bytes > evidence_budget:
        blockers.append(
            {
                "code": "EVIDENCE_BUDGET_EXCEEDED",
                "detail": (
                    f"canonical evidence {evidence_bytes} bytes exceeds the "
                    f"{evidence_budget} byte budget; no compact replacement is verified "
                    "by every consumer, so it is KEPT and reported"
                ),
                "protected_bytes": evidence_bytes,
            }
        )
    if build_budget and build_bytes > build_budget:
        blockers.append(
            {
                "code": "GENERATED_BUILD_BUDGET_EXCEEDED",
                "detail": (
                    f"manifest-owned generated builds {build_bytes} bytes exceed the "
                    f"{build_budget} byte budget; eligible superseded builds are reclaimed first"
                ),
                "measured_bytes": build_bytes,
            }
        )
    return {
        "evidence_bytes": evidence_bytes,
        "evidence_budget_bytes": evidence_budget,
        "generated_build_bytes": build_bytes,
        "generated_build_budget_bytes": build_budget,
        "blockers": blockers,
    }


# -------------------------------------------------------------------------- manifest


def manifest_path(root: Path | str) -> Path:
    return Path(root) / MANIFEST_REL


def load_manifest(root: Path | str) -> dict:
    """The project-scoped generated-artifact ownership manifest, or an empty one.

    The manifest is the ONLY route by which a build directory becomes a target.
    A `dist*` or `recovery*` wildcard is never a class by itself.
    """
    path = manifest_path(root)
    empty = {"status": "missing", "builds": [], "problems": [], "raw": None}
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return empty
    except OSError as exc:
        return {"status": "unreadable", "builds": [], "problems": [str(exc)], "raw": None}
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        return {
            "status": "corrupt",
            "builds": [],
            "problems": [f"{path}: not a JSON document ({exc})"],
            "raw": raw,
        }
    if not isinstance(document, dict) or document.get("schema") != SCHEMA:
        return {
            "status": "corrupt",
            "builds": [],
            "problems": [f"{path}: schema is not {SCHEMA}"],
            "raw": raw,
        }
    builds = document.get("builds")
    if not isinstance(builds, list):
        return {
            "status": "corrupt",
            "builds": [],
            "problems": [f"{path}: builds is not a list"],
            "raw": raw,
        }
    clean: list[dict] = []
    problems: list[str] = []
    for index, entry in enumerate(builds):
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            problems.append(f"build entry {index} has no string path")
            continue
        relative = _norm(entry["path"]).strip("/")
        if (
            not relative
            or relative.startswith("/")
            or ".." in relative.split("/")
            or ":" in relative
        ):
            problems.append(f"build entry {index} path {entry['path']!r} is not project-relative")
            continue
        clean.append({**entry, "path": relative})
    return {"status": "ok", "builds": clean, "problems": problems, "raw": raw}


def _build_entry_class(
    root: Path, entry: dict, by_id: dict[str, dict], guard: dict
) -> tuple[str, str, bool]:
    """Classify one manifest build. Third value says the path is a deletion target."""
    if not str(entry.get("owner") or "").strip():
        return BUILD_UNVERIFIED, "no owner: no tool is accountable for rebuilding it", False
    if not str(entry.get("inventory_sha256") or "").strip():
        return (
            BUILD_UNVERIFIED,
            "no declared inventory digest: the bytes on disk cannot be proven to be this build",
            False,
        )
    if entry.get("deployed"):
        return BUILD_DEPLOYED, "the manifest marks this build deployed in production", False
    if entry.get("current") or (entry.get("retain_current") and entry.get("current_build")):
        return BUILD_CURRENT, "the manifest marks this build current/selected", False
    if entry.get("rollback"):
        return BUILD_ROLLBACK, "the manifest marks this build the verified rollback copy", False
    references = entry.get("references")
    if isinstance(references, list) and references:
        return (
            BUILD_REFERENCED,
            f"{len(references)} live reference(s) name this build: " + ", ".join(map(str, references[:4])),
            False,
        )
    if not str(entry.get("recipe") or "").strip():
        return BUILD_UNVERIFIED, "no reproduction recipe: the content cannot be proven rebuildable", False
    successor_id = str(entry.get("superseded_by") or "").strip()
    if not successor_id:
        return BUILD_UNVERIFIED, "no verified successor names this build as superseded", False
    successor = by_id.get(successor_id)
    if successor is None:
        return (
            BUILD_UNVERIFIED,
            f"successor {successor_id!r} is not an entry in this manifest",
            False,
        )
    successor_path = str(successor.get("path") or "")
    if successor_path == entry.get("path"):
        return BUILD_UNVERIFIED, "successor names the same path", False
    successor_problems = _structural_audit(root, successor_path, guard)
    if successor_problems:
        return (
            BUILD_UNVERIFIED,
            f"successor {successor_id!r} is not a safe local replacement: "
            + "; ".join(successor_problems[:3]),
            False,
        )
    if not (root / successor_path).exists():
        return (
            BUILD_UNVERIFIED,
            f"successor {successor_id!r} has no bytes on disk, so the replacement is unproven",
            False,
        )
    successor_digest = str(successor.get("inventory_sha256") or "").strip()
    if not successor_digest or inventory_digest(root, successor_path) != successor_digest:
        return (
            BUILD_UNVERIFIED,
            f"successor {successor_id!r} does not match its declared inventory digest",
            False,
        )
    if not (successor.get("verified") or successor.get("verified_evidence")):
        return (
            BUILD_UNVERIFIED,
            f"successor {successor_id!r} carries no verification evidence",
            False,
        )
    return (
        GENERATED_BUILD_SUPERSEDED,
        f"superseded by verified {successor_id}",
        True,
    )


# ------------------------------------------------------------------------- git guard


class _GitProbeError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _git(root: Path, argv: list[str], *, timeout: int = 120) -> str:
    if shutil.which("git") is None:
        raise _GitProbeError("GIT_UNAVAILABLE", "git is not resolvable on this host")
    try:
        done = subprocess.run(
            ["git", "-C", str(root), *argv],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise _GitProbeError("GIT_TIMEOUT", f"git {' '.join(argv)} exceeded {timeout}s") from exc
    except FileNotFoundError as exc:
        raise _GitProbeError("GIT_UNAVAILABLE", str(exc)) from exc
    except OSError as exc:
        raise _GitProbeError("GIT_EXEC_FAILED", f"git {' '.join(argv)}: {exc}") from exc
    if done.returncode != 0:
        raise _GitProbeError(
            "GIT_COMMAND_FAILED",
            f"git {' '.join(argv)} exited {done.returncode}: {(done.stderr or '').strip()[:400]}",
        )
    if done.stdout is None:
        raise _GitProbeError("GIT_MALFORMED_OUTPUT", f"git {' '.join(argv)} produced no stream")
    return done.stdout


def _split_z(stdout: str, argv: str) -> list[str]:
    if "\x00" not in stdout and stdout.strip():
        raise _GitProbeError(
            "GIT_MALFORMED_OUTPUT",
            f"git {argv} output carries no NUL separator: {stdout[:120]!r}",
        )
    entries: list[str] = []
    for raw in stdout.split("\x00"):
        if not raw:
            continue
        entry = _norm(raw)
        if "\n" in entry or "\r" in entry:
            raise _GitProbeError(
                "GIT_MALFORMED_OUTPUT",
                f"git {argv} entry carries a line break: {entry[:120]!r}",
            )
        entries.append(entry)
    return entries


def git_guard(root: Path | str) -> dict:
    """Proof of what Git owns right now, or a fail-closed refusal.

    An empty protection set is only ever returned for a repository Git proved.
    Every incomplete probe (missing binary, timeout, nonzero exit, unmatched
    toplevel, malformed stream) yields ``ok: False`` and the reason, and no
    deletion plan can be built from it.
    """
    root = Path(root)
    guard = {
        "ok": False,
        "code": "GIT_GUARD_FAILED",
        "detail": None,
        "tracked": set(),
        "staged": set(),
        "dirty": set(),
        "nested": set(),
        "guarded": set(),
        "unborn": False,
        "toplevel": None,
    }
    try:
        inside = _git(root, ["rev-parse", "--is-inside-work-tree"]).strip()
        if inside != "true":
            raise _GitProbeError(
                "GIT_NOT_A_WORKTREE",
                f"{root}: rev-parse --is-inside-work-tree answered {inside!r}",
            )
        toplevel = _git(root, ["rev-parse", "--show-toplevel"]).strip()
        if not toplevel:
            raise _GitProbeError("GIT_MALFORMED_OUTPUT", "rev-parse --show-toplevel was empty")
        resolved_toplevel = os.path.normcase(os.path.realpath(toplevel))
        resolved_root = os.path.normcase(os.path.realpath(str(root)))
        if resolved_toplevel != resolved_root:
            raise _GitProbeError(
                "GIT_ROOT_MISMATCH",
                f"{root} is inside the worktree {resolved_toplevel}, not its root: "
                "nested Git ownership is not supported by this collector",
            )
        guard["toplevel"] = _norm(toplevel)
        tracked = _split_z(_git(root, ["ls-files", "-z"]), "ls-files")
        staged_entries = _split_z(
            _git(root, ["diff", "-z", "--name-only", "--cached"]), "diff --cached"
        )
        index_entries = _git(root, ["ls-files", "-s", "-z"])
        nested: set[str] = set()
        for record in index_entries.split("\x00"):
            if not record:
                continue
            fields = record.split(" ", 3)
            if len(fields) >= 4 and fields[0] == "160000":
                nested.add(_norm(fields[3]))
        try:
            _git(root, ["rev-parse", "--verify", "HEAD"])
            unborn = False
        except _GitProbeError as exc:
            detail = exc.detail.lower()
            if exc.code == "GIT_COMMAND_FAILED" and any(
                marker in detail
                for marker in (
                    "unknown revision",
                    "ambiguous argument",
                    "needed a single revision",
                    "bad revision",
                    "unknown rev",
                )
            ):
                unborn = True
            else:
                raise
        dirty: set[str] = set()
        if not unborn:
            dirty = set(
                _split_z(_git(root, ["diff", "-z", "--name-only", "HEAD"]), "diff HEAD")
            )
    except _GitProbeError as exc:
        guard["code"] = exc.code
        guard["detail"] = exc.detail
        return guard
    guard["ok"] = True
    guard["code"] = "GIT_GUARD_OK"
    guard["tracked"] = set(tracked)
    guard["staged"] = set(staged_entries)
    guard["dirty"] = dirty
    guard["nested"] = nested
    guard["unborn"] = unborn
    guard["guarded"] = set(tracked) | set(staged_entries) | set(dirty) | set(nested)
    return guard


# ----------------------------------------------------------------------- classify


def _is_link(node: Path) -> bool:
    try:
        info = os.lstat(node)
    except OSError:
        return False
    if stat.S_ISLNK(info.st_mode):
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _linked_ancestor(root: Path, relative: str) -> str | None:
    parts = relative.split("/")
    current = root
    for part in parts[:-1]:
        current = current / part
        if _is_link(current):
            return _norm(current.relative_to(root).as_posix())
    return None


def _nested_git_ancestor(root: Path, relative: str) -> str | None:
    """The nearest ancestor directory that is itself a Git worktree.

    An untracked nested repository is an ownership boundary the outer index
    never names: deleting its caches destroys another project's rebuild state
    from inside ours, so a candidate below one is refused.
    """
    parts = [part for part in relative.split("/")[:-1] if part]
    current = Path(root)
    for part in parts:
        current = current / part
        if (current / ".git").exists():
            return _norm(current.relative_to(root).as_posix())
    return None


def _ancestor_problems(root: Path, relative: str) -> list[str]:
    """Why the PATH to this candidate is unsafe, whatever the candidate holds.

    A link or a nested repository ABOVE a target is invisible to a content
    audit: a junctioned build parent points outside the project and a nested
    worktree belongs to someone else. Both refuse the whole target.
    """
    problems: list[str] = []
    linked = _linked_ancestor(root, relative)
    if linked:
        problems.append(
            f"{linked}: linked/reparse ancestor is on the path; never traversed"
        )
    nested = _nested_git_ancestor(root, relative)
    if nested:
        problems.append(f"{nested}: ancestor is a nested Git ownership boundary")
    return problems


def _protected(relative: str) -> bool:
    normal = _norm(relative).strip("/")
    for prefix in PROTECTED_PREFIXES:
        base = prefix.rstrip("/")
        if normal == base or normal.startswith(base + "/"):
            return True
    return False


def _guarded_hit(relative: str, guarded: set[str]) -> str | None:
    """A guarded path at, above or BELOW this node. Descendants count.

    Compared through ``os.path.normcase``: on a case-insensitive host a
    Git-owned descendant whose on-disk name differs only in case owns the very
    bytes the candidate would delete, so an exact-string match would let tracked
    content through.
    """
    normal = _norm(relative).strip("/")
    folded = os.path.normcase(normal)
    prefix = os.path.normcase(normal + "/")
    for entry in guarded:
        candidate = os.path.normcase(_norm(entry).strip("/"))
        if candidate == folded or candidate.startswith(prefix):
            return entry
    return None


def audit_target(root: Path | str, relative: str, guard: dict) -> list[str]:
    """Every reason this exact target is not safe to delete. Empty means safe.

    A directory is judged by its CONTENTS, not its name: a cache-named directory
    that holds user data, a tracked child, a staged child, a nested repository,
    a link or a hard link is refused whole. Deleting the parent of a protected
    descendant is exactly the defect this function exists to prevent.
    """
    root = Path(root)
    relative = _norm(relative).strip("/")
    node = root / relative
    problems: list[str] = _ancestor_problems(root, relative)
    if problems:
        return problems
    if not guard.get("ok"):
        return [f"GIT_GUARD_FAILED: {guard.get('detail')}"]
    try:
        info = os.lstat(node)
    except FileNotFoundError:
        return [f"{relative}: no longer exists"]
    except OSError as exc:
        return [f"{relative}: cannot be inspected ({exc})"]
    if _is_link(node):
        return [f"{relative}: is a link/reparse point; never followed"]
    if _protected(relative):
        return [f"{relative}: canonical carrier"]
    hit = _guarded_hit(relative, guard["guarded"])
    if hit is not None:
        return [f"{relative}: Git owns it (or {hit} below it): {hit}"]
    if stat.S_ISREG(info.st_mode):
        leaf = relative.rsplit("/", 1)[-1]
        if not leaf.endswith(EPHEMERAL_SUFFIXES):
            problems.append(f"{relative}: a regular file that no owning tool rebuilds")
        if getattr(info, "st_nlink", 1) > 1:
            problems.append(f"{relative}: {info.st_nlink} hard links; ownership is not proven")
        return problems
    if not stat.S_ISDIR(info.st_mode):
        return [f"{relative}: not a regular file or directory"]
    problems.extend(_structural_audit(root, relative, guard))
    for base, _dirs, files in os.walk(node, followlinks=False):
        base_path = Path(base)
        for name in sorted(files):
            child = base_path / name
            child_relative = _norm(child.relative_to(root).as_posix())
            if not name.endswith(EPHEMERAL_SUFFIXES):
                problems.append(f"{child_relative}: user/unknown content inside a cache-named tree")
    return problems


def _structural_audit(root: Path | str, relative: str, guard: dict) -> list[str]:
    """Shape checks shared by cache trees and manifest-proven build trees.

    No link is ever traversed, no nested repository is ever entered, and a
    guarded descendant refuses the whole ancestor. Hard links are refused
    because a second name for the bytes means the owner is not proven.
    """
    root = Path(root)
    relative = _norm(relative).strip("/")
    node = root / relative
    problems: list[str] = _ancestor_problems(root, relative)
    if problems:
        return problems
    if not guard.get("ok"):
        return [f"GIT_GUARD_FAILED: {guard.get('detail')}"]
    if _is_link(node):
        return [f"{relative}: is a link/reparse point; never followed"]
    if _protected(relative):
        return [f"{relative}: canonical carrier"]
    hit = _guarded_hit(relative, guard["guarded"])
    if hit is not None:
        return [f"{relative}: Git owns it (or {hit} below it): {hit}"]
    if node.is_file():
        info = os.lstat(node)
        if getattr(info, "st_nlink", 1) > 1:
            problems.append(f"{relative}: {info.st_nlink} hard links")
        return problems
    for base, dirs, files in os.walk(node, followlinks=False):
        base_path = Path(base)
        for name in sorted(dirs):
            child = base_path / name
            child_relative = _norm(child.relative_to(root).as_posix())
            if name == ".git":
                problems.append(f"{child_relative}: nested Git ownership; never descended")
                dirs.remove(name)
                continue
            if _is_link(child):
                problems.append(f"{child_relative}: linked/reparse directory; never descended")
                dirs.remove(name)
                continue
            hit = _guarded_hit(child_relative, guard["guarded"])
            if hit is not None:
                problems.append(f"{child_relative}: Git owns it ({hit})")
                dirs.remove(name)
                continue
            if _protected(child_relative):
                problems.append(f"{child_relative}: canonical carrier")
                dirs.remove(name)
        for name in sorted(files):
            child = base_path / name
            child_relative = _norm(child.relative_to(root).as_posix())
            if name == ".git":
                problems.append(f"{child_relative}: nested Git ownership")
                continue
            if _is_link(child):
                problems.append(f"{child_relative}: link/reparse point")
                continue
            hit = _guarded_hit(child_relative, guard["guarded"])
            if hit is not None:
                problems.append(f"{child_relative}: Git owns it ({hit})")
                continue
            if _protected(child_relative):
                problems.append(f"{child_relative}: canonical carrier")
                continue
            try:
                child_info = os.lstat(child)
            except OSError as exc:
                problems.append(f"{child_relative}: cannot be inspected ({exc})")
                continue
            if not stat.S_ISREG(child_info.st_mode):
                problems.append(f"{child_relative}: not a regular file")
                continue
            if getattr(child_info, "st_nlink", 1) > 1:
                problems.append(f"{child_relative}: {child_info.st_nlink} hard links")
    return problems


def inventory_digest(root: Path | str, relative: str) -> str:
    """Digest of the target's file inventory (path, size, mtime). Never reads bytes."""
    root = Path(root)
    node = root / relative
    digest = hashlib.sha256()
    if node.is_file():
        info = os.lstat(node)
        digest.update(f"{_norm(relative)}:{info.st_size}:{info.st_mtime_ns}\n".encode())
        return digest.hexdigest()
    for base, _dirs, files in os.walk(node, followlinks=False):
        base_path = Path(base)
        for name in sorted(files):
            child = base_path / name
            try:
                info = os.lstat(child)
            except OSError:
                continue
            digest.update(
                f"{_norm(child.relative_to(root).as_posix())}:{info.st_size}:{info.st_mtime_ns}\n".encode()
            )
    return digest.hexdigest()


def classify(relative: str, *, guard: dict, linked: str | None) -> tuple[str, str]:
    """The typed retention class for one relative path and why it got it."""
    normal = _norm(relative).strip("/")
    if linked:
        return PROTECTED_LINK, f"a linked/reparse ancestor ({linked}) is on the path; never traversed"
    if _protected(normal):
        return PROTECTED_LEDGER, "canonical carrier a gate or consumer reads"
    if _guarded_hit(normal, guard.get("guarded") or set()) is not None:
        return PROTECTED_GIT, "Git owns the path: index, staged set or working-tree delta"
    leaf = normal.rsplit("/", 1)[-1]
    parent = normal.rsplit("/", 1)[0] if "/" in normal else ""
    if leaf in EPHEMERAL_DIR_NAMES or normal.endswith(EPHEMERAL_SUFFIXES):
        return EPHEMERAL_REPRODUCIBLE, f"owning tool rebuilds it ({leaf if leaf in EPHEMERAL_DIR_NAMES else 'bytecode'})"
    if parent.rsplit("/", 1)[-1] in EPHEMERAL_DIR_NAMES:
        return EPHEMERAL_REPRODUCIBLE, f"inside a tool-owned cache directory ({parent.rsplit('/', 1)[-1]})"
    return UNKNOWN_OWNERSHIP, "no proven owner and no rebuild path; KEEP"


def _candidates(root: Path) -> list[str]:
    """Every cache-named tree and loose bytecode file the walk is allowed to see."""
    found: list[str] = []
    for base, dirs, files in os.walk(root, followlinks=False):
        base_path = Path(base)
        relative_base = _norm(base_path.relative_to(root).as_posix())
        if relative_base == ".":
            relative_base = ""
        keep_dirs = []
        for name in sorted(dirs):
            relative = f"{relative_base}/{name}" if relative_base else name
            if name in PRUNE_DIR_NAMES or _protected(relative):
                continue
            if name in EPHEMERAL_DIR_NAMES:
                found.append(relative)
                # A cache directory is reclaimed whole; never descend and
                # double-count its files against its own directory size.
                continue
            keep_dirs.append(name)
        dirs[:] = keep_dirs
        for name in sorted(files):
            if name.endswith(EPHEMERAL_SUFFIXES):
                found.append(f"{relative_base}/{name}" if relative_base else name)
    return found


def _fingerprint(root: Path, relative: str) -> str:
    """Identity of the target's CURRENT contents: a plan cannot outlive it."""
    node = root / relative
    digest = hashlib.sha256()
    try:
        info = os.lstat(node)
    except OSError:
        return ""
    if stat.S_ISREG(info.st_mode):
        digest.update(f"F:{info.st_size}:{info.st_mtime_ns}".encode())
        return digest.hexdigest()
    for base, dirs, files in os.walk(node, followlinks=False):
        base_path = Path(base)
        for name in sorted(dirs):
            child = base_path / name
            try:
                child_info = os.lstat(child)
            except OSError:
                continue
            digest.update(f"D:{_norm(child.relative_to(root).as_posix())}:{child_info.st_mode}\n".encode())
        for name in sorted(files):
            child = base_path / name
            try:
                child_info = os.lstat(child)
            except OSError:
                continue
            digest.update(
                f"F:{_norm(child.relative_to(root).as_posix())}:{child_info.st_size}:{child_info.st_mtime_ns}\n".encode()
            )
    return digest.hexdigest()


def _manifest_entries(root: Path, guard: dict, manifest: dict) -> tuple[list[dict], int, list[dict]]:
    """Manifest builds, classified. Returns (targets, kept, kept_entries)."""
    targets: list[dict] = []
    kept_entries: list[dict] = []
    by_id = {
        str(entry.get("id")): entry
        for entry in manifest["builds"]
        if isinstance(entry.get("id"), str) and entry.get("id")
    }
    for entry in manifest["builds"]:
        relative = entry["path"]
        retention, reason, deletable = _build_entry_class(root, entry, by_id, guard)
        node = root / relative
        problems = _structural_audit(root, relative, guard) if node.exists() else [f"{relative}: no bytes on disk"]
        declared = str(entry.get("inventory_sha256") or "")
        if not problems and declared and inventory_digest(root, relative) != declared:
            problems = [
                f"{relative}: contents do not match the declared inventory digest "
                "(the build was modified after the manifest claimed it)"
            ]
        if problems:
            retention = BUILD_UNVERIFIED
            reason = "; ".join(problems[:4])
            deletable = False
        record = {
            "path": relative,
            "class": retention,
            "reason": reason,
            "build_id": entry.get("id"),
            "audit": "build",
            "inventory_sha256": declared,
            "bytes_planned": _tree_bytes(node) if node.is_dir() and not _is_link(node) else _file_bytes(node),
            "fingerprint": _fingerprint(root, relative) if deletable else "",
        }
        if deletable:
            targets.append(record)
        else:
            kept_entries.append(record)
    return targets, len(kept_entries), kept_entries


# --------------------------------------------------------------------------- plan


def _empty_plan(guard: dict | None = None) -> dict:
    """Complete plan schema for every refusal path."""
    guard = guard or {}
    return {
        "schema": SCHEMA,
        "generated": _iso(_utc_now()),
        "git_guard": {
            "ok": bool(guard.get("ok")),
            "code": guard.get("code") or "GIT_GUARD_FAILED",
            "detail": guard.get("detail"),
        },
        "targets": [],
        "kept": 0,
        "kept_entries": [],
        "build_targets": 0,
        "bytes_planned": 0,
        "blockers": [],
    }


def _build_plan(root: Path, guard: dict, *, include_builds: bool = True) -> dict:
    root = Path(root)
    targets: list[dict] = []
    kept: list[dict] = []
    for relative in _candidates(root):
        node = root / relative
        linked = _linked_ancestor(root, relative)
        retention, reason = classify(relative, guard=guard, linked=linked)
        if retention in KEEP_CLASSES:
            kept.append({"path": relative, "class": retention, "reason": reason})
            continue
        problems = audit_target(root, relative, guard)
        if problems:
            kept.append(
                {
                    "path": relative,
                    "class": PROTECTED_GIT if guard.get("guarded") and _guarded_hit(relative, guard["guarded"]) else UNKNOWN_OWNERSHIP,
                    "reason": "; ".join(problems[:4]),
                }
            )
            continue
        size = _file_bytes(node) if node.is_file() else _tree_bytes(node)
        targets.append(
            {
                "path": relative,
                "class": retention,
                "reason": reason,
                "bytes_planned": size,
                "fingerprint": _fingerprint(root, relative),
            }
        )
    manifest = load_manifest(root)
    build_targets: list[dict] = []
    build_kept = 0
    if include_builds and manifest["status"] == "ok":
        build_targets, build_kept, kept_builds = _manifest_entries(root, guard, manifest)
        kept.extend(kept_builds)
        targets.extend(build_targets)
    evidence = root / ".saipen/evidence"
    blockers: list[dict] = []
    if evidence.is_dir():
        blockers.append(
            {
                "code": "EVIDENCE_KEPT",
                "detail": (
                    f"{_tree_bytes(evidence)} bytes under .saipen/evidence are canonical proof; "
                    "no compact replacement is verified by a consumer, so none is planned"
                ),
            }
        )
    blockers.extend(budget_report(root, load_state(root))["blockers"])
    if manifest["status"] == "corrupt":
        blockers.append(
            {
                "code": "BUILD_MANIFEST_CORRUPT",
                "detail": "; ".join(manifest["problems"]) or "the build manifest is unreadable",
            }
        )
    for problem in manifest["problems"]:
        blockers.append({"code": "BUILD_MANIFEST_PROBLEM", "detail": problem})
    return {
        "schema": SCHEMA,
        "generated": _iso(_utc_now()),
        "git_guard": {"ok": guard.get("ok"), "code": guard.get("code"), "detail": guard.get("detail")},
        "targets": sorted(targets, key=lambda item: item["path"]),
        "kept": len(kept),
        "kept_entries": sorted(kept, key=lambda item: item["path"]),
        "build_targets": len(build_targets),
        "bytes_planned": sum(item["bytes_planned"] for item in targets),
        "blockers": blockers,
    }


def plan(root: Path | str, *, include_builds: bool = True) -> dict:
    """Zero-write plan: what would go, what is kept, and why.

    A Git guard that could not complete yields an EMPTY target list and the
    refusal in ``blockers``. A failed guard never produces a deletion plan.
    """
    root = Path(root)
    guard = git_guard(root)
    report = _build_plan(root, guard, include_builds=include_builds)
    if not guard["ok"]:
        report["targets"] = []
        report["bytes_planned"] = 0
        report["blockers"] = [
            {
                "code": "GIT_GUARD_FAILED",
                "detail": f"{guard['code']}: {guard['detail']}",
            },
            *report["blockers"],
        ]
    health = read_state(root)
    report["state_health"] = health["status"]
    return report


def inventory(root: Path | str) -> dict:
    """Read-only typed inventory of every candidate the collector would consider."""
    root = Path(root)
    guard = git_guard(root)
    entries = []
    for relative in _candidates(root):
        linked = _linked_ancestor(root, relative)
        retention, reason = classify(relative, guard=guard, linked=linked)
        entries.append({"path": relative, "class": retention, "reason": reason})
    manifest = load_manifest(root)
    return {
        "entries": entries,
        "guarded": len(guard.get("guarded") or set()),
        "git_guard": {"ok": guard.get("ok"), "code": guard.get("code"), "detail": guard.get("detail")},
        "manifest": {"status": manifest["status"], "builds": len(manifest["builds"]), "problems": manifest["problems"]},
    }


# ---------------------------------------------------------------------- execute


def runs_dir(root: Path | str) -> Path:
    return Path(root) / RUNS_REL


def _write_record(path: Path, root: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_atomic_write_bytes(
        path,
        (json.dumps(payload, indent=1, sort_keys=True) + "\n").encode("utf-8"),
        kind="GC run record",
        ownership_root=root,
    )


def _append_progress(path: Path, entry: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _remove_tree(node: Path, root: Path, progress: Path, run_id: str) -> tuple[int, list[str]]:
    """Unlink one audited target with a per-file journal. Returns (bytes, problems)."""
    removed = 0
    problems: list[str] = []

    def _journal(event: str, relative: str, **fields) -> None:
        _append_progress(progress, {"run_id": run_id, "event": event, "path": relative, **fields})

    for base, dirs, files in os.walk(node, topdown=False, followlinks=False):
        base_path = Path(base)
        for name in files:
            child = base_path / name
            child_relative = _norm(child.relative_to(root).as_posix())
            if _is_link(child):
                problems.append(f"{child_relative}: link/reparse point; refused")
                continue
            try:
                size = os.lstat(child).st_size
            except OSError as exc:
                problems.append(f"{child_relative}: cannot be measured ({exc})")
                continue
            _journal(DELETE_STARTED, child_relative, size=size)
            try:
                os.unlink(child)
            except OSError as exc:
                _journal(PARTIAL, child_relative, size=size, error=str(exc))
                problems.append(f"{child_relative}: {exc}")
                continue
            _journal(DELETE_CONFIRMED, child_relative, size=size, removed=True)
            removed += size
        for name in dirs:
            child = base_path / name
            child_relative = _norm(child.relative_to(root).as_posix())
            if _is_link(child):
                problems.append(f"{child_relative}: linked directory; refused")
                continue
            try:
                os.rmdir(child)
            except OSError as exc:
                problems.append(f"{child_relative}: {exc}")
    try:
        os.rmdir(node)
    except OSError as exc:
        problems.append(f"{_norm(node.name)}: {exc}")
    return removed, problems


def _recover_runs(root: Path) -> list[dict]:
    """Reconcile runs a crash left half-journaled. Deletes nothing, credits proof."""
    runs = runs_dir(root)
    reconciled: list[dict] = []
    for progress in sorted(runs.glob("*" + PROGRESS_SUFFIX)):
        run_id = progress.name[: -len(PROGRESS_SUFFIX)]
        record_path = runs / f"{run_id}.json"
        if record_path.is_file():
            continue
        try:
            lines = progress.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        entries: list[dict] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except ValueError:
                continue
            if isinstance(parsed, dict):
                entries.append(parsed)
        confirmed: dict[str, int] = {}
        started: dict[str, int] = {}
        committed: dict[str, int] = {}
        started_at = entries[0].get("started") if entries else None
        for entry in entries:
            event = entry.get("event")
            path = entry.get("path")
            if not isinstance(path, str):
                continue
            size = entry.get("size")
            size = int(size) if isinstance(size, int) and size >= 0 else 0
            if event == DELETE_STARTED:
                started[path] = size
            elif event == DELETE_CONFIRMED:
                confirmed[path] = size
            elif event == COMMITTED:
                committed[path] = size
        targets: dict[str, dict] = {}
        for path in sorted(set(committed) | set(confirmed) | set(started)):
            node = root / path
            present = node.exists() or _is_link(node)
            if path in committed:
                state = COMMITTED
            elif path in confirmed:
                state = DELETE_CONFIRMED
            elif path in started:
                # The unlink ran but its outcome was never journaled. A missing
                # path is NOT proof of removal, so this is reconciliation debt,
                # never reclaimed storage.
                state = RECONCILE_REQUIRED
            else:
                state = PLANNED
            targets[path] = {
                "path": path,
                "state": state,
                "present": present,
                "bytes_confirmed": confirmed.get(path, 0),
                "bytes_requested": started.get(path, 0),
            }
        payload = {
            "schema": SCHEMA,
            "run_id": run_id,
            "started": started_at,
            "finished": _iso(_utc_now()),
            "recovered": True,
            "kept": 0,
            "protected_bytes": 0,
            # ONLY observed confirmations are credited.
            "bytes_reclaimed": sum(confirmed.values()),
            "accounting_matches": True,
            "blockers": [
                {
                    "code": "INTERRUPTED_RUN_RECOVERED",
                    "detail": (
                        f"{run_id} had no completion record; {len(confirmed)} confirmed unlink(s) "
                        f"and {sum(1 for t in targets.values() if t['state'] == RECONCILE_REQUIRED)} "
                        "unproven target(s) were reconciled, not re-deleted"
                    ),
                }
            ],
            "targets": list(targets.values()),
        }
        _write_record(record_path, root, payload)
        try:
            progress.unlink()
        except OSError:
            pass
        reconciled.append(
            {
                "run_id": run_id,
                "bytes_reclaimed": payload["bytes_reclaimed"],
                "reconcile_required": sum(
                    1 for target in targets.values() if target["state"] == RECONCILE_REQUIRED
                ),
            }
        )
    return reconciled


def recover(root: Path | str) -> dict:
    return {"reconciled": _recover_runs(Path(root))}


def execute(root: Path | str, agent: str, *, dry_run: bool = False) -> dict:
    """Run one collection under the project's single-writer lock.

    The plan is recomputed AFTER the lock is held and every target is re-audited
    and re-fingerprinted immediately before mutation: a stale plan cannot delete
    bytes that changed since it was built.
    """
    root = Path(root)
    if dry_run:
        report = plan(root)
        report["dry_run"] = True
        return report
    health = read_state(root)
    if health["status"] in ("corrupt", "unreadable"):
        return {
            "schema": SCHEMA,
            "ok": False,
            "code": "CORRUPT_GC_STATE",
            "detail": (
                f"{health['detail']}; destructive collection is refused until "
                "`saipen gc repair` reconstructs the counter from canonical closure "
                "history and preserves the bad bytes"
            ),
            "bytes_reclaimed": 0,
        }
    from .lock import project_writer_lock

    run_id = _new_run_id()
    started = _iso(_utc_now())
    runs = runs_dir(root)
    progress = runs / f"{run_id}{PROGRESS_SUFFIX}"
    record_path = runs / f"{run_id}.json"
    targets: list[dict] = []
    blockers: list[dict] = []
    reclaimed = 0
    planned_bytes = 0
    with project_writer_lock(root):
        reconciled = _recover_runs(root)
        guard = git_guard(root)
        current = _empty_plan(guard)
        if not guard["ok"]:
            blockers.append(
                {
                    "code": "GIT_GUARD_FAILED",
                    "detail": f"{guard['code']}: {guard['detail']}; nothing was deleted",
                }
            )
        else:
            current = _build_plan(root, guard)
            blockers.extend(current["blockers"])
        planned_bytes = current["bytes_planned"]
        if not guard["ok"]:
            # GIT_GUARD_FAILED is a REFUSED collection, never a run: recording a
            # clean "last_run" here would advance counted_at_run and silently
            # consume the 20-closure budget debt while nothing was collected.
            payload = {
                "schema": SCHEMA,
                "run_id": run_id,
                "started": started,
                "finished": _iso(_utc_now()),
                "agent": agent,
                "kept": current["kept"],
                "protected_bytes": 0,
                "bytes_planned": 0,
                "bytes_reclaimed": 0,
                "accounting_matches": True,
                "recovered_runs": reconciled,
                "blockers": blockers,
                "targets": [],
                "git_guard": {
                    "ok": False,
                    "code": guard["code"],
                    "detail": guard["detail"],
                },
            }
            _write_record(record_path, root, payload)
            try:
                progress.unlink()
            except OSError:
                pass
            payload["ok"] = False
            payload["code"] = "GIT_GUARD_FAILED"
            payload["detail"] = f"{guard['code']}: {guard['detail']}"
            return payload
        state = load_state(root)
        for item in current["targets"]:
            relative = item["path"]
            node = root / relative
            if not (node.exists() or _is_link(node)):
                targets.append(
                    {
                        "path": relative,
                        "class": item["class"],
                        "reason": item["reason"],
                        "bytes_planned": item.get("bytes_planned", 0),
                        "bytes_removed": 0,
                        "state": PLANNED,
                        "outcome": "skipped",
                    }
                )
                continue
            # Deletion-time proof, not plan-time proof: Git ownership is re-probed
            # per target, because a tree can be committed, staged or left dirty
            # between the plan and its deletion, and a run-single guard snapshot
            # would hand the collector bytes it no longer owns.
            fresh = git_guard(root)
            if not fresh["ok"]:
                problems = [f"GIT_GUARD_FAILED: {fresh['code']}: {fresh['detail']}"]
            elif item.get("audit") == "build":
                # A manifest-proven build tree is not a cache tree: its content
                # is arbitrary build output, so the cache rule ("every file must
                # be bytecode") would refuse every legal target. The plan proved
                # it structurally and by inventory digest; re-prove exactly that
                # pair here, never the cache-name rule.
                problems = list(_structural_audit(root, relative, fresh))
                declared = str(item.get("inventory_sha256") or "")
                if not problems and declared and inventory_digest(root, relative) != declared:
                    problems.append(
                        f"{relative}: contents do not match the declared inventory digest "
                        "(the build was modified after the manifest claimed it)"
                    )
            else:
                problems = audit_target(root, relative, fresh)
            fingerprint = _fingerprint(root, relative)
            if item.get("fingerprint") and fingerprint != item["fingerprint"]:
                problems.append("contents changed after the plan was built")
            if problems:
                targets.append(
                    {
                        "path": relative,
                        "class": item["class"],
                        "reason": item["reason"],
                        "bytes_planned": item.get("bytes_planned", 0),
                        "bytes_removed": 0,
                        "state": RECONCILE_REQUIRED,
                        "outcome": "refused",
                        "blocker": "; ".join(problems[:4]),
                    }
                )
                blockers.append(
                    {"code": "TARGET_REFUSED", "detail": f"{relative}: {'; '.join(problems[:4])}"}
                )
                continue
            _append_progress(
                progress,
                {
                    "run_id": run_id,
                    "event": PREPARED,
                    "path": relative,
                    "class": item["class"],
                    "bytes_planned": item.get("bytes_planned", 0),
                    "fingerprint": fingerprint,
                    "started": started,
                    "agent": agent,
                },
            )
            if node.is_dir() and not _is_link(node):
                removed, problems = _remove_tree(node, root, progress, run_id)
            else:
                size = _file_bytes(node)
                _append_progress(progress, {"run_id": run_id, "event": DELETE_STARTED, "path": relative, "size": size})
                try:
                    os.unlink(node)
                    removed, problems = size, []
                    _append_progress(progress, {"run_id": run_id, "event": DELETE_CONFIRMED, "path": relative, "size": size, "removed": True})
                except OSError as exc:
                    removed, problems = 0, [f"{relative}: {exc}"]
                    _append_progress(progress, {"run_id": run_id, "event": PARTIAL, "path": relative, "size": size, "error": str(exc)})
            state_label = COMMITTED if not problems else PARTIAL
            _append_progress(
                progress,
                {
                    "run_id": run_id,
                    "event": state_label,
                    "path": relative,
                    "size": removed,
                    "bytes_removed": removed,
                },
            )
            targets.append(
                {
                    "path": relative,
                    "class": item["class"],
                    "reason": item["reason"],
                    "bytes_planned": item.get("bytes_planned", 0),
                    "bytes_removed": removed,
                    "state": state_label,
                    "outcome": "removed" if not problems else "partial",
                }
            )
            if problems:
                blockers.append({"code": "TARGET_KEPT", "detail": "; ".join(problems[:4])})
            reclaimed += removed
        # Kept carriers are reported by size where they are cheap to measure.
        evidence = root / ".saipen/evidence"
        kept_bytes = _tree_bytes(evidence) if evidence.is_dir() else 0
        payload = {
            "schema": SCHEMA,
            "run_id": run_id,
            "started": started,
            "finished": _iso(_utc_now()),
            "agent": agent,
            "kept": current["kept"],
            "protected_bytes": kept_bytes,
            "bytes_planned": planned_bytes,
            "bytes_reclaimed": reclaimed,
            "accounting_matches": reclaimed
            == sum(int(item.get("bytes_removed") or 0) for item in targets),
            "recovered_runs": reconciled,
            "blockers": blockers,
            "targets": targets,
        }
        _write_record(record_path, root, payload)
        try:
            progress.unlink()
        except OSError:
            pass
        state = load_state(root)
        state["runs"] = [
            entry
            for entry in list(state.get("runs") or [])
            if isinstance(entry, dict) and entry.get("run_id") != run_id
        ]
        state["runs"].append(
            {
                "run_id": run_id,
                "bytes": reclaimed,
                "started": started,
                "finished": payload["finished"],
                "counted_at_run": len(state.get("counted_done") or []),
            }
        )
        state["last_run"] = {
            "run_id": run_id,
            "counted_at_run": len(state.get("counted_done") or []),
        }
        run_interval = int(state["config"].get("interval_done") or DEFAULTS["interval_done"])
        state["last_interval_consumed"] = _interval_consumed(
            len(state.get("counted_done") or []), run_interval
        )
        save_state(root, state)
    payload["ok"] = True
    payload["code"] = "GC_RUN_COMPLETE"
    return payload


# ------------------------------------------------------------------------- debt


def maintenance_fingerprint(root: Path | str) -> str:
    """Stable identity of every input a collection verdict depends on.

    Covers the retention policy, the Git ownership manifest, the protected
    carrier prefixes, the measured budgets and the candidate inventory. Two
    runs with the same fingerprint are the same problem: an identical
    expensive retry is suppressed, a changed one reactivates maintenance.
    Policy, not bytes, is the subject: the digest is of the DECLARED inputs
    (config, manifest, prefixes) plus the MEASURED sizes, never of candidate
    content, so a retry is only suppressed when nothing the decision reads has
    moved.
    """
    root = Path(root)
    state = load_state(root)
    guard = git_guard(root)
    budgets = budget_report(root, state)
    manifest = load_manifest(root)
    digest = hashlib.sha256()
    digest.update(json.dumps(state.get("config") or {}, sort_keys=True).encode("utf-8"))
    digest.update(json.dumps(sorted(PROTECTED_PREFIXES), sort_keys=True).encode("utf-8"))
    digest.update(json.dumps(sorted(budgets.get("blockers") or []), sort_keys=True).encode("utf-8"))
    digest.update(
        json.dumps(
            {
                "evidence_bytes": budgets["evidence_bytes"],
                "generated_build_bytes": budgets["generated_build_bytes"],
            },
            sort_keys=True,
        ).encode("utf-8")
    )
    for relative in sorted(guard.get("guarded") or ()):
        digest.update(f"G:{relative}\n".encode("utf-8"))
    digest.update(f"guard:{guard.get('code')}:{guard.get('ok')}\n".encode("utf-8"))
    digest.update(f"manifest:{manifest.get('status')}\n".encode("utf-8"))
    for problem in sorted(str(item) for item in (manifest.get("problems") or [])):
        digest.update(f"manifest-problem:{problem}\n".encode("utf-8"))
    for entry in sorted(manifest["builds"], key=lambda item: str(item.get("path"))):
        digest.update(
            json.dumps(
                {
                    "path": entry.get("path"),
                    "class_hints": [
                        entry.get("id"),
                        entry.get("owner"),
                        entry.get("recipe"),
                        entry.get("inventory_sha256"),
                        entry.get("superseded_by"),
                        entry.get("verified") or entry.get("verified_evidence"),
                        entry.get("current"),
                        entry.get("current_build"),
                        entry.get("retain_current"),
                        entry.get("deployed"),
                        entry.get("rollback"),
                        entry.get("references"),
                    ],
                },
                sort_keys=True,
            ).encode("utf-8")
        )
        relative = str(entry.get("path") or "").strip()
        if relative:
            digest.update(
                f"manifest-bytes:{relative}:{_fingerprint(root, relative)}\n".encode("utf-8")
            )
    for relative in sorted(_candidates(root)):
        digest.update(f"C:{relative}:{_fingerprint(root, relative)}\n".encode("utf-8"))
    return digest.hexdigest()


def _append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _read_jsonl(path: Path) -> list[dict]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return []
    entries: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            entries.append(parsed)
    return entries


def settlement_records(root: Path | str) -> list[dict]:
    """Every committed closure identity, read from an append-only ledger.

    `GC_STATE.json` holds the counter; this ledger is the DURABLE settlement
    receipt per closure. Neither one is a projection of the other, so a restart,
    a replay, a BOARD scrub or a LOG seal cannot lose or duplicate one.
    """
    return _read_jsonl(Path(root) / SETTLEMENT_REL)


def _settlement_key(ticket: str, settlement_id: str | None) -> str:
    """One distinct completion = one key. A replay reuses the ticket identity."""
    return f"{ticket}:{settlement_id}" if settlement_id else ticket


def record_settlement(
    root: Path | str,
    ticket: str,
    event_id: str | None = None,
    *,
    state: str = "done",
    key: str | None = None,
) -> dict:
    """Persist that this closure identity settled maintenance, exactly once."""
    root = Path(root)
    record = {
        "schema": SCHEMA,
        "ticket": ticket,
        "event_id": event_id,
        "key": key or _settlement_key(ticket, event_id),
        "at": _iso(_utc_now()),
        "state": state,
    }
    _append_jsonl(root / SETTLEMENT_REL, record)
    return record


def record_maintenance_failure(root: Path | str, agent: str, exc: BaseException) -> dict:
    """Durable, visible maintenance failure; the closure is never rewritten."""
    root = Path(root)
    record = {
        "schema": SCHEMA,
        "code": "GC_MAINTENANCE_FAILED",
        "agent": agent,
        "at": _iso(_utc_now()),
        "error_type": type(exc).__name__,
        "error": str(exc)[:1000],
    }
    _append_jsonl(root / FAILURE_REL, record)
    return record


def maintenance_failures(root: Path | str) -> list[dict]:
    return _read_jsonl(Path(root) / FAILURE_REL)


def _fully_collected(outcome: dict) -> bool:
    """True only when every attempted target reached a CONFIRMED journal state.

    A run that reclaimed bytes from one tree while another target refused or a
    deletion only PARTIALLY applied is a partial collection: the bytes are gone,
    the debt is not paid, and a PARTIAL state is the honest durable answer.
    """
    targets = [entry for entry in (outcome.get("targets") or []) if isinstance(entry, dict)]
    if not targets:
        return False
    return all(entry.get("state") in {DELETE_CONFIRMED, COMMITTED} for entry in targets)


def _write_debt(root: Path, state: dict, outcome: dict, fingerprint: str) -> None:
    """Turn one run's measured outcome into durable maintenance debt."""
    settled = (
        bool(outcome.get("ok"))
        and int(outcome.get("bytes_reclaimed") or 0) > 0
        and _fully_collected(outcome)
    )
    blockers = [
        {"code": entry.get("code"), "detail": entry.get("detail")}
        for entry in (outcome.get("blockers") or [])
        if isinstance(entry, dict)
    ]
    if settled:
        maintenance_state = DEBT_SETTLED
        reason = f"{outcome.get('bytes_reclaimed')} byte(s) reclaimed; maintenance debt settled"
    elif not outcome.get("ok"):
        maintenance_state = DEBT_FAILED
        reason = outcome.get("detail") or outcome.get("code") or "maintenance execution refused"
    elif any(entry.get("code") == "EVIDENCE_BUDGET_EXCEEDED" for entry in blockers):
        maintenance_state = DEBT_BLOCKED_PROTECTED_BUDGET
        reason = (
            "canonical evidence exceeds its budget and no consumer-verified compact "
            "replacement exists: the proof is KEPT, not deleted"
        )
    elif not (outcome.get("targets") or []):
        maintenance_state = DEBT_BLOCKED_NO_SAFE_CANDIDATES
        reason = "no reclaimable candidate exists; nothing is safe to delete"
    elif any(
        entry.get("state") in {PARTIAL, RECONCILE_REQUIRED}
        for entry in (outcome.get("targets") or [])
        if isinstance(entry, dict)
    ):
        maintenance_state = DEBT_PARTIAL
        reason = (
            "a deletion only partially applied or a target was refused at the last "
            "moment: the collection is incomplete, so the debt is not paid"
        )
    else:
        maintenance_state = DEBT_PARTIAL
        reason = "candidates existed but every one was refused; the debt is not paid"
    state["maintenance"] = {
        "state": maintenance_state,
        "reason": reason,
        "fingerprint": fingerprint,
        "last_attempt_fingerprint": fingerprint,
        "blockers": blockers,
        "protected_bytes": int(outcome.get("protected_bytes") or 0),
        "bytes_reclaimed": int(outcome.get("bytes_reclaimed") or 0),
        "run_id": outcome.get("run_id"),
        "updated": _iso(_utc_now()),
    }


def _debt_block(root: Path | str) -> dict:
    state = load_state(root)
    debt = state.get("maintenance")
    return debt if isinstance(debt, dict) else _default_state()["maintenance"]


# ---------------------------------------------------------------------- assessment


def assess(root: Path | str, now: datetime | None = None) -> dict:
    """Zero-write maintenance verdict from the durable counter and budgets."""
    root = Path(root)
    now = now or _utc_now()
    health = read_state(root)
    state = health["state"]
    config = state["config"]
    if not config.get("enabled", True):
        return {
            "due": False,
            "reason": "collector disabled by policy",
            "blocked": None,
            "total": len(state.get("counted_done") or []),
            "pending": 0,
            "interval": int(config.get("interval_done") or 0),
            "state_health": health["status"],
            "blockers": [],
        }
    total = canonical_total(root, state)
    counted = len(total["union"])
    # A corrupt carrier is reported, never "repaired" by the scheduler.
    if health["status"] in ("corrupt", "unreadable"):
        return {
            "due": False,
            "reason": None,
            "blocked": "CORRUPT_GC_STATE",
            "detail": health["detail"],
            "total": len(state.get("counted_done") or []),
            "pending": len(total["pending"]),
            "interval": int(config.get("interval_done") or 0),
            "state_health": health["status"],
            "blockers": [{"code": "CORRUPT_GC_STATE", "detail": health["detail"]}],
        }
    interval = int(config.get("interval_done") or DEFAULTS["interval_done"])
    last_total = int(state.get("last_interval_consumed") or 0)
    pending = counted - last_total
    interval_due = interval > 0 and counted >= next_threshold(last_total, config)
    budgets = budget_report(root, state)
    blockers = list(budgets["blockers"])
    debt = _debt_block(root)
    due = None
    reason = None
    blocked = None
    if interval_due:
        due = True
        reason = (
            f"{pending} distinct committed closure(s) since the {interval}-closure "
            f"interval was last consumed"
        )
    elif config.get("budget_trigger", True) and budgets["blockers"]:
        due = True
        reason = "storage budget breached: " + "; ".join(item["code"] for item in budgets["blockers"])
    elif debt.get("state") in OPEN_DEBT_STATES:
        due = True
        reason = debt.get("reason") or f"outstanding maintenance debt {debt.get('state')}"
    if due:
        fingerprint = maintenance_fingerprint(root)
        if (
            debt.get("state") in ZERO_PROGRESS_DEBT_STATES
            and debt.get("last_attempt_fingerprint") == fingerprint
        ):
            # Same problem, same inputs, already proven to reclaim nothing: an
            # identical expensive retry is suppressed, the OPEN debt stays due
            # in the state (never settled), and any real change to policy,
            # ownership, budgets or candidates reactivates it.
            return {
                "due": True,
                "retry_suppressed": True,
                "reason": (
                    f"identical retry fingerprint {fingerprint[:16]} already produced zero "
                    f"reclaimable candidates; maintenance debt {debt.get('state')} stays open"
                ),
                "blocked": debt.get("state"),
                "total": counted,
                "pending": pending,
                "interval": interval,
                "state_health": health["status"],
                "next_threshold": next_threshold(counted, config),
                "blockers": blockers,
            }
        return {
            "due": True,
            "reason": reason,
            "blocked": None,
            "total": counted,
            "pending": pending,
            "interval": interval,
            "state_health": health["status"],
            "next_threshold": next_threshold(counted, config),
            "blockers": blockers,
        }
    return {
        "due": False,
        "reason": None,
        "blocked": blocked,
        "total": counted,
        "pending": pending,
        "interval": interval,
        "state_health": health["status"],
        "next_threshold": next_threshold(counted, config),
        "blockers": blockers,
    }


def state_task(root: Path | str) -> str | None:
    """The subject ticket of the live STATE, for a settlement with no explicit id."""
    from .state import parse_state

    try:
        text = (Path(root) / ".saipen/STATE.md").read_text(encoding="utf-8-sig")
    except OSError:
        return None
    task = str(parse_state(text).get("task") or "").strip()
    return task or None


def settle_ticket_completion(
    root: Path | str,
    ticket: str | None,
    agent: str,
    *,
    settlement_id: str | None = None,
    source: str = "closure",
) -> dict:
    """Run one crash-resumable checkpoint for a committed closure.

    ``pending`` is written before the checkpoint and ``done`` only after it
    answers. A crash in that window therefore retries. If the checkpoint had
    already committed a collection before the crash, its durable counter makes
    the retry a no-op. Completed receipts deduplicate overlapping public closure
    routes by ticket identity; refused and dry-run closures never call here.
    """
    root = Path(root)
    subject = ticket or state_task(root)
    if not subject:
        return {"ok": True, "code": "GC_SETTLEMENT_SKIPPED", "detail": "no ticket identity"}
    key = _settlement_key(subject, settlement_id)
    entries = _read_jsonl(root / SETTLEMENT_REL)
    matching = [
        record
        for record in entries
        if record.get("key") == key or record.get("ticket") == subject
    ]
    completed = next(
        (record for record in reversed(matching) if record.get("state", "done") == "done"),
        None,
    )
    if completed is not None:
        return {
            "ok": True,
            "code": "ALREADY_SETTLED",
            "ticket": subject,
            "key": key,
            "settled_at": completed.get("at"),
            "prior_key": completed.get("key"),
        }
    if not matching:
        record_settlement(root, subject, settlement_id, state="pending")
    outcome = maintenance_checkpoint(root, agent)
    if not isinstance(outcome, dict):
        outcome = {
            "ok": False,
            "code": "GC_MAINTENANCE_FAILED",
            "detail": "maintenance_checkpoint returned no outcome",
        }
    record_settlement(root, subject, settlement_id, state="done", key=key)
    outcome["settlement"] = {"ticket": subject, "key": key, "source": source}
    return outcome


def maintenance_checkpoint(root: Path | str, agent: str) -> dict:
    """The safe checkpoint after a committed closure (T-2049 trigger).

    Never raises, never touches STATE/BOARD/LOG and never forces an active Work
    ticket into CLEAN: it syncs the durable counter, asks ``assess`` whether work
    is due, and runs the tested collector when it is. A refusal becomes a run
    record with a blocker, i.e. durable maintenance debt.
    """
    root = Path(root)
    try:
        health = read_state(root)
        if health["status"] in ("corrupt", "unreadable"):
            return {
                "ok": False,
                "code": "CORRUPT_GC_STATE",
                "detail": health["detail"],
                "due": False,
            }
        sync = sync_counter(root)
        verdict = assess(root)
        if verdict.get("retry_suppressed"):
            return {"ok": True, "code": "GC_RETRY_SUPPRESSED", **verdict}
        if not verdict["due"]:
            return {"ok": True, "code": "GC_NOT_DUE", **verdict}
        outcome = execute(root, agent)
        from .lock import project_writer_lock

        fingerprint = maintenance_fingerprint(root)
        with project_writer_lock(root):
            if not isinstance(outcome, dict):
                outcome = {
                    "ok": False,
                    "code": "GC_MAINTENANCE_FAILED",
                    "detail": "execute returned no outcome",
                }
            state = load_state(root)
            _write_debt(root, state, outcome, fingerprint)
            save_state(root, state)
        return {
            "ok": bool(outcome.get("ok")),
            "code": outcome.get("code") or "GC_RUN_COMPLETE",
            "bytes_reclaimed": outcome.get("bytes_reclaimed", 0),
            "blockers": outcome.get("blockers", []),
            "run_id": outcome.get("run_id"),
            "debt": (load_state(root).get("maintenance") or {}).get("state"),
            "due": True,
            "reason": verdict["reason"],
        }
    except Exception as exc:  # never let maintenance break a closure
        # Silent loss replaced by an auditable, fail-closed report: the
        # committed ticket stays closed and the debt is durable and visible.
        report = record_maintenance_failure(root, agent, exc)
        return {
            "ok": False,
            "code": "GC_MAINTENANCE_FAILED",
            "detail": f"{type(exc).__name__}: {exc}",
            "due": False,
            "receipt": FAILURE_REL,
            "record": report,
        }


# ------------------------------------------------------------------------ repair


def repair(root: Path | str, agent: str) -> dict:
    """Reconstruct a corrupt counter from canonical closure history.

    Order is fixed: preserve the bad bytes, rebuild from independently
    validated history, journal the reconstruction, activate, then reload and
    verify. A failed verification restores the preserved bytes and refuses.
    """
    root = Path(root)
    health = read_state(root)
    if health["status"] == "ok":
        return {"ok": True, "code": "GC_STATE_OK", "detail": "nothing to repair"}
    if health["status"] == "missing":
        save_state(root, _default_state())
        return {"ok": True, "code": "GC_STATE_SEEDED", "detail": "no counter existed; seeded from empty history"}
    raw = health.get("raw") or b""
    stamp = _iso(_utc_now()).replace(":", "").replace("-", "")
    preserved = root / CORRUPT_REL / f"GC_STATE.{stamp}.{_sha(raw)[:12]}.json"
    preserved.parent.mkdir(parents=True, exist_ok=True)
    preserved.write_bytes(raw)
    fresh = _default_state()
    closures = canonical_closures(root, fresh)
    fresh["counted_done"] = list(dict.fromkeys(closures["identities"]))
    fresh["closure_sources"] = {"sealed": [path.name for path in sealed_logs(root)]}
    fresh["protocol_digest"] = protocol_digest(root)
    journal = root / REPAIR_REL / f"repair.{stamp}.json"
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal_doc = {
        "schema": SCHEMA,
        "agent": agent,
        "at": _iso(_utc_now()),
        "reason": health["detail"],
        "preserved_bytes": _norm(preserved.relative_to(root).as_posix()),
        "preserved_sha256": _sha(raw),
        "reconstructed_count": len(fresh["counted_done"]),
        "sources": closures["sources"],
        "protocol_digest": fresh["protocol_digest"],
    }
    journal.write_text(json.dumps(journal_doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    save_state(root, fresh)
    check = read_state(root)
    if check["status"] != "ok" or check["state"]["counted_done"] != fresh["counted_done"]:
        preserved_bytes = preserved.read_bytes()
        safe_atomic_write_bytes(
            state_path(root),
            preserved_bytes,
            kind="GC state restore",
            ownership_root=root,
        )
        return {
            "ok": False,
            "code": "GC_STATE_REPAIR_UNVERIFIED",
            "detail": (
                f"the reconstructed counter did not reload identically; the preserved bytes "
                f"at {journal_doc['preserved_bytes']} were restored"
            ),
        }
    return {
        "ok": True,
        "code": "GC_STATE_REPAIRED",
        "reconstructed_count": len(fresh["counted_done"]),
        "preserved_bytes": journal_doc["preserved_bytes"],
        "preserved_sha256": journal_doc["preserved_sha256"],
        "journal": _norm(journal.relative_to(root).as_posix()),
        "sources": closures["sources"],
    }


# ------------------------------------------------------------------------- audit


def audit(root: Path | str) -> dict:
    """Independent cross-check of counter, records, accounting and retention."""
    root = Path(root)
    health = read_state(root)
    state = health["state"]
    findings: list[dict] = []
    if health["status"] in ("corrupt", "unreadable"):
        findings.append({"code": "CORRUPT_GC_STATE", "detail": health["detail"]})
    counted = list(state.get("counted_done") or [])
    if len(counted) != len(set(counted)):
        findings.append({"code": "DUPLICATE_IDENTITY", "detail": "a closed identity is counted twice"})
    canonical = canonical_total(root, state)
    missing = canonical["pending"]
    if missing:
        findings.append(
            {
                "code": "UNCOUNTED_DONE",
                "detail": f"{len(missing)} committed closure(s) are absent from the counter: "
                + ", ".join(missing[:8]),
            }
        )
    board = set(board_done_identities(root))
    off_board = [tid for tid in counted if tid not in board]
    removed_bytes = 0
    for entry in sorted(runs_dir(root).glob("*.json")):
        try:
            document = json.loads(entry.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            findings.append({"code": "UNREADABLE_RUN", "detail": entry.name})
            continue
        total = sum(
            int(item.get("bytes_removed") or item.get("bytes_confirmed") or 0)
            for item in document.get("targets") or []
            if isinstance(item, dict) and item.get("state") in (COMMITTED, DELETE_CONFIRMED, "removed")
        )
        credited = int(document.get("bytes_reclaimed") or 0)
        removed_bytes += credited
        if total != credited:
            findings.append(
                {
                    "code": "ACCOUNTING_MISMATCH",
                    "detail": f"{entry.name}: journal-confirmed {total} != reported {credited}",
                }
            )
        for target in document.get("targets") or []:
            if isinstance(target, dict) and target.get("state") == RECONCILE_REQUIRED:
                findings.append(
                    {
                        "code": "RECONCILE_REQUIRED",
                        "detail": f"{entry.name}: {target.get('path')} has no proven deletion outcome",
                    }
                )
    evidence = root / ".saipen/evidence"
    budgets = budget_report(root, state)
    report = {
        "schema": SCHEMA,
        "state_health": health["status"],
        "counted": len(counted),
        "canonical": len(canonical["union"]),
        "next_threshold": next_threshold(len(canonical["union"]), state["config"]),
        "runs": len(state.get("runs") or []),
        "bytes_reclaimed_recorded": removed_bytes,
        "evidence_bytes": budgets["evidence_bytes"],
        "generated_build_bytes": budgets["generated_build_bytes"],
        "counted_off_board": len(off_board),
        "counted_off_board_sample": off_board[:8],
        "blockers": budgets["blockers"],
        "findings": findings,
        "ok": not findings,
    }
    return report


# ------------------------------------------------------------------------ status


def status(root: Path | str) -> dict:
    """Zero-write operator view: counter, threshold, budgets, last run, health."""
    root = Path(root)
    health = read_state(root)
    state = health["state"]
    verdict = assess(root)
    budgets = budget_report(root, state)
    manifest = load_manifest(root)
    return {
        "schema": SCHEMA,
        "state_health": health["status"],
        "state_detail": health["detail"],
        "counted": verdict["total"],
        "pending_since_last_run": verdict.get("pending"),
        "interval": verdict.get("interval"),
        "next_threshold": verdict.get("next_threshold"),
        "due": verdict["due"],
        "due_reason": verdict["reason"],
        "blocked": verdict.get("blocked"),
        "last_run": state.get("last_run"),
        "runs_recorded": len(state.get("runs") or []),
        "evidence_bytes": budgets["evidence_bytes"],
        "evidence_budget_bytes": budgets["evidence_budget_bytes"],
        "generated_build_bytes": budgets["generated_build_bytes"],
        "generated_build_budget_bytes": budgets["generated_build_budget_bytes"],
        "build_manifest": {
            "status": manifest["status"],
            "builds": len(manifest["builds"]),
            "problems": manifest["problems"],
        },
        "config": state["config"],
        "blockers": budgets["blockers"],
    }


def policy(root: Path | str) -> dict:
    """Zero-write view of the retention policy the collector actually applies."""
    state = load_state(root)
    return {
        "schema": SCHEMA,
        "config": state["config"],
        "defaults": DEFAULTS,
        "protected_prefixes": list(PROTECTED_PREFIXES),
        "ephemeral_dir_names": sorted(EPHEMERAL_DIR_NAMES),
        "ephemeral_suffixes": list(EPHEMERAL_SUFFIXES),
        "unknown_policy": state["config"].get("unknown_policy", "KEEP"),
        "evidence_rule": "canonical evidence is only ever reported, never deleted",
        "build_rule": "only a manifest-proven superseded build with a verified successor is reclaimable",
        "manifest": MANIFEST_REL,
    }


def configure(root: Path | str, agent: str, changes: dict) -> dict:
    """Change retention policy under the writer lock. Never touches the ledger."""
    root = Path(root)
    unknown = [key for key in changes if key not in DEFAULTS]
    if unknown:
        return {"ok": False, "code": "INVALID_POLICY_KEY", "detail": ", ".join(sorted(unknown))}
    from .lock import project_writer_lock

    with project_writer_lock(root):
        health = read_state(root)
        if health["status"] in ("corrupt", "unreadable"):
            return {"ok": False, "code": "CORRUPT_GC_STATE", "detail": health["detail"]}
        state = health["state"]
        config = dict(state["config"])
        config.update(changes)
        state["config"] = config
        save_state(root, state)
    return {"ok": True, "code": "GC_POLICY_UPDATED", "agent": agent, "config": config}
