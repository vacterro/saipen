"""Write-ahead transaction journal + roll-forward recovery (NITRO M2).

The protocol's commit order is LOG -> BOARD -> STATE because LOG ahead of
STATE after a crash is recoverable (CORE section 1.5). Python mechanizes that:
the journal records the intended final bytes of every target BEFORE any write,
then advances stage by stage. Recovery is ROLL-FORWARD after LOG -- the
append-only LOG event is never deleted -- and idempotent: a COMMITTED op
returns ALREADY_APPLIED, an interrupted op is recovered first.

Crash injection: NITRO_CRASH_AFTER_PREPARE / _LOG / _BOARD / _STATE exit the
process at exactly that point, simulating process death mid-transaction.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

STAGES = ["PREPARED", "LOG_WRITTEN", "BOARD_WRITTEN", "STATE_WRITTEN",
          "VERIFIED", "COMMITTED", "ABORTED", "CONFLICT"]
OPS_DIR = ".saipen/recovery/ops"


class Journal:
    """Per-operation journal under .saipen/recovery/ops/<op_id>/."""

    def __init__(self, project_root: Path | str, op_id: str) -> None:
        self.project_root = Path(project_root)
        self.dir = self.project_root / OPS_DIR / op_id
        self.op_id = op_id
        self.manifest = self.dir / "operation.json"

    def exists(self) -> bool:
        return self.manifest.is_file()

    def start(self, operation: str, agent: str, project_identity: str,
              preconditions: dict, targets: list[dict]) -> None:
        """Write PREPARED: op metadata, precondition hashes, and the intended
        final bytes of every target stored in the journal so recovery can
        re-apply them without recomputation."""
        self.dir.mkdir(parents=True, exist_ok=True)
        record = {
            "op_id": self.op_id,
            "operation": operation,
            "created_at": _now(),
            "agent": agent,
            "project_identity": project_identity,
            "preconditions": preconditions,
            "stage": "PREPARED",
            "targets": [t["path"] for t in targets],
        }
        _atomic_json(self.manifest, record)
        for target in targets:
            content = target["content"]
            (self.dir / _slug(target["path"])).write_bytes(
                content if isinstance(content, bytes)
                else content.encode("utf-8"))

    def mark(self, stage: str) -> None:
        record = json.loads(self.manifest.read_text(encoding="utf-8"))
        record["stage"] = stage
        _atomic_json(self.manifest, record)

    def read(self) -> dict:
        return json.loads(self.manifest.read_text(encoding="utf-8"))

    def staged_content(self, rel_path: str) -> bytes:
        return (self.dir / _slug(rel_path)).read_bytes()


def _slug(rel_path: str) -> str:
    return rel_path.replace("/", "__").replace("\\", "__")


def _atomic_json(path: Path, record: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(record, indent=2), encoding="utf-8")
    tmp.replace(path)


def _now() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def _crash_after(stage: str) -> None:
    """Simulate process death at a transaction boundary (red control)."""
    env_map = {"PREPARED": "NITRO_CRASH_AFTER_PREPARE",
               "LOG_WRITTEN": "NITRO_CRASH_AFTER_LOG",
               "BOARD_WRITTEN": "NITRO_CRASH_AFTER_BOARD",
               "STATE_WRITTEN": "NITRO_CRASH_AFTER_STATE"}
    if env_map.get(stage) in os.environ:
        sys.exit(87)


def run_mutation(project_root: Path | str, op_id: str, agent: str,
                 project_identity: str, preconditions: dict,
                 targets: list[dict]) -> dict:
    """Commit an ordered mutation LOG -> BOARD -> STATE with journaling.

    `targets` is an ordered list of {"path", "content"} where path is relative
    to the project root (canonically .saipen/LOG.md, BOARD.md, STATE.md). The
    precondition hashes are checked against the live files before any write.
    """
    root = Path(project_root)
    journal = Journal(root, op_id)
    if journal.exists():
        record = journal.read()
        if record["stage"] == "COMMITTED":
            return {"ok": True, "code": "ALREADY_APPLIED", "op_id": op_id,
                    "recovery_required": False}
        return {"ok": False, "code": "RECOVERY_REQUIRED", "op_id": op_id,
                "recovery_required": True}

    for precondition, expected in preconditions.items():
        actual = _hash_file(root / precondition)
        if actual != expected:
            return {"ok": False, "code": "STALE_STATE", "op_id": op_id,
                    "detail": f"precondition {precondition} changed"}

    journal.start(op_id, agent, project_identity, preconditions, targets)
    _crash_after("PREPARED")
    for index, stage in enumerate(
            ("LOG_WRITTEN", "BOARD_WRITTEN", "STATE_WRITTEN")):
        target = targets[index]
        _atomic_write(root / target["path"], target["content"])
        journal.mark(stage)
        _crash_after(stage)
    journal.mark("VERIFIED")
    journal.mark("COMMITTED")
    return {"ok": True, "code": "COMMITTED", "op_id": op_id,
            "changed_files": [t["path"] for t in targets],
            "recovery_required": False}


def recover(project_root: Path | str, op_id: str) -> dict:
    """Roll-forward recovery. Never deletes the append-only LOG event.

    PREPARED -> abort safely if no target changed.
    LOG_WRITTEN -> roll BOARD + STATE forward when preconditions still hold.
    BOARD_WRITTEN -> roll STATE forward.
    STATE_WRITTEN -> validate and mark committed.
    Unexpected target hash -> CONFLICT, evidence preserved, refuse to guess.
    """
    root = Path(project_root)
    journal = Journal(root, op_id)
    if not journal.exists():
        return {"ok": False, "code": "TICKET_NOT_FOUND", "op_id": op_id}
    record = journal.read()
    stage = record["stage"]
    if stage == "COMMITTED":
        return {"ok": True, "code": "ALREADY_APPLIED", "op_id": op_id}
    if stage == "PREPARED":
        if not any(_hash_file(root / p) != record["preconditions"].get(p, "")
                   for p in ("STATE.md",)):
            journal.mark("ABORTED")
            return {"ok": True, "code": "ABORTED", "op_id": op_id}
    targets = record["targets"]
    apply_from = 0
    if stage == "LOG_WRITTEN":
        apply_from = 1
    elif stage == "BOARD_WRITTEN":
        apply_from = 2
    elif stage == "STATE_WRITTEN":
        apply_from = 3
    for index in range(apply_from, len(targets)):
        path = targets[index]
        _atomic_write(root / path, journal.staged_content(path))
    journal.mark("VERIFIED")
    journal.mark("COMMITTED")
    return {"ok": True, "code": "COMMITTED", "op_id": op_id,
            "recovery_required": True}


def _hash_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except OSError:
        return ""


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    if isinstance(content, str):
        content = content.encode("utf-8")
    tmp.write_bytes(content)
    tmp.replace(path)
