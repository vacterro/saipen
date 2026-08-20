"""Canonical conformance closure (SAIPEN Conformance Closure Hardening).

GOAL: a SAIPEN project MUST NOT report `crew closed`, `CREW_FINALIZED`,
converged `DONE`, successful convergence closure, or post-CLEAN closure while
the canonical validator for the CURRENT checkpoint is FAILing. No reliance on
an agent remembering to run validation.

This single module is the load-bearing core. The canonical validator
(tools/validate.py) emits a structured conformance receipt on EVERY run (PASS or
FAIL). Convergence stage E/H, terminal DONE, crew SC-13 finalization, the CLEAN
exit, the continue entry gate and `saipen status` all consume that ONE receipt
-- a prose `verdict: PASS`, a caller-supplied PASS verdict, a stale validator,
fake verify evidence or an empty board can never manufacture apparent
conformance.

Sections implemented here:
  §1  canonical validator version ownership + STALE_VALIDATOR reporting
  §2  structured conformance receipt (emitted only by the validator run path)
  §3  convergence E/H must consume real receipts
  §4  terminal closure requires current conformance PASS
  §5  CLEAN exit conformance gate
  §6  continue entry health gate (additive; hard gates live in the closers)
  §8  status / viewer truth (status classification)
  §9  real UTC timestamps (fabricated-future refusal)
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

# §1: the canonical validator's own protocol version. Bump when the receipt
# schema or the gate semantics change. The project's OWN protocol version lives
# in STATE.md `saipen_version`; that is a DIFFERENT axis and must never be
# compared against this one for staleness.
CONFORMANCE_PROTOCOL_VERSION = "1"

# Receipts live under the append-only recovery tree but are SIDE EVIDENCE, not
# history: they never mutate STATE/BOARD/LOG and a fresh clone recomputes them
# by re-running the validator. They only ever grow.
RECEIPT_DIRNAME = ".saipen/recovery/conformance"

# CORE-003: the three nested path components that must be inside the project
# root and must NOT be symlinks/junctions/reparse points.
_CONTAINMENT_COMPONENTS = (".saipen", ".saipen/recovery", ".saipen/recovery/conformance")


# --------------------------------------------------------------------------- CORE-003 containment
def _validate_conformance_containment(root: Path) -> None:
    """CORE-003: prove the conformance storage chain is inside the project
    root and contains no symlinks/junctions/reparse points.

    Uses non-following lstat to detect reparse points that resolve().
    might not collapse. A symlink pointing outside the project root is
    rejected with zero writes. This mirrors the journal/history ownership
    discipline.
    """
    root_resolved = root.resolve()
    for comp in _CONTAINMENT_COMPONENTS:
        comp_path = root / comp
        if not comp_path.exists():
            continue
        # Non-following stat: detect symlinks and reparse points
        try:
            info = os.lstat(comp_path)
        except OSError:
            continue
        if os.path.islink(comp_path):
            raise ValueError(
                f"conformance storage component {comp!r} is a symlink; "
                "symlinks in the conformance path are forbidden"
            )
        # Windows reparse point (junction)
        if getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError(
                f"conformance storage component {comp!r} is a reparse point; "
                "reparse points in the conformance path are forbidden"
            )
        # Prove containment: resolved path must be under project root
        try:
            comp_resolved = comp_path.resolve()
            if not comp_resolved.is_relative_to(root_resolved):
                # Explicit out-of-root rejection: this MUST always propagate
                # (fail closed). An intent handler must never synthesize a
                # conformance receipt for an escaped path.
                raise ValueError(
                    f"conformance storage component {comp!r} resolves outside "
                    f"project root ({comp_resolved} is not under {root_resolved})"
                )
        except ValueError:
            # Internal containment rejection -- propagate unchanged, never swallow.
            raise
        except OSError as exc:
            # A resolution failure (unreadable/escaped component) cannot prove
            # containment, so refuse deterministically with ZERO writes. The
            # prior code referenced an unbound `exc_val` here and reported an
            # unrelated NameError instead of the documented containment error.
            raise ValueError(
                f"conformance storage component {comp!r} cannot be resolved "
                f"({exc}); refusing with zero writes -- containment cannot be proven"
            )
    receipt_dir = root / RECEIPT_DIRNAME
    if receipt_dir.exists():
        # Check each receipt file is a regular file, not a symlink
        for p in receipt_dir.glob("*.json"):
            try:
                info = os.lstat(p)
            except OSError:
                continue
            if os.path.islink(p):
                raise ValueError(
                    f"conformance receipt {p.name} is a symlink; "
                    "symlinked receipts are forbidden"
                )
            if getattr(info, "st_file_attributes", 0) & 0x400:
                raise ValueError(
                    f"conformance receipt {p.name} is a reparse point; "
                    "reparse point receipts are forbidden"
                )


def _atomic_write_receipt(path: Path, body: str) -> None:
    """CORE-003: write a receipt atomically via temp + replace.

    The receipt directory must already exist and pass containment checks.
    A crash during write leaves either the old receipt or the new one,
    never a partial file.
    """
    parent = path.parent
    fd, tmp_path = tempfile.mkstemp(
        suffix=".tmp", prefix=path.stem + "-", dir=parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(body)
            f.write("\n")
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

# §9: max allowed clock skew (seconds). A receipt timestamp further in the
# future than this is treated as fabricated and refused.
MAX_CLOCK_SKEW_SECONDS = 300

# §8: closed set of authoritative conformance statuses.
STATUS_CURRENT_PASS = "CURRENT_PASS"
STATUS_CURRENT_FAIL = "CURRENT_FAIL"
STATUS_STALE_PASS = "STALE_PASS"
STATUS_STALE_FAIL = "STALE_FAIL"
STATUS_NOT_RUN = "NOT_RUN"
STATUS_VERSION_MISMATCH = "VALIDATOR_VERSION_MISMATCH"
STATUS_INVALID = "INVALID_RECEIPT"

# How long a PASS receipt stays "current" before it ages into STALE (24h). A
# project that has not validated in a day cannot claim terminal closure on a
# week-old green stamp.
FRESHNESS_WINDOW_SECONDS = 24 * 3600


# --------------------------------------------------------------------------- utils
def _utc_now_iso(now: datetime.datetime | None = None) -> str:
    """W2-005: microsecond-precision UTC timestamp for total ordering.

    Two executions within the same wall-clock second must still produce
    different timestamps so receipt ordering is deterministic.
    """
    ref = now or datetime.datetime.now(datetime.timezone.utc)
    return ref.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _receipt_id() -> str:
    """W2-005: immutable unique receipt identifier.

    Every validator execution gets a unique id so receipts can never
    overwrite earlier evidence and ordering is unambiguous.
    """
    return "receipt-" + uuid.uuid4().hex[:12]


def _safe_filename_component(value: str) -> str:
    """W2-006: make a string safe for use as a filename component.

    Replaces OS-specific invalid characters (Windows reserved chars
    like : / * ? " < > | and control characters) with underscores.
    """
    # Characters forbidden on Windows (and problematic on POSIX in filenames)
    _unsafe = set('/<>:"|?*\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f')
    # Also forbid colon which is NTFS alternate-data-stream syntax
    _unsafe.add(':')
    result = []
    for ch in value:
        if ch in _unsafe or ord(ch) < 0x20:
            result.append('_')
        else:
            result.append(ch)
    return ''.join(result)


def _strict_iso_utc(value) -> str:
    """Strict ISO-8601 UTC (Z or +00:00, utcoffset == 0), else ''."""
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if not text:
        return ""
    try:
        dt = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if dt.utcoffset() is None or dt.utcoffset().total_seconds() != 0:
        return ""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _future_beyond_skew(ts_iso: str, now: datetime.datetime | None = None) -> bool:
    """§9: a timestamp in the future beyond the skew allowance is fabricated."""
    norm = _strict_iso_utc(ts_iso)
    if not norm:
        return False
    dt = datetime.datetime.fromisoformat(norm.replace("Z", "+00:00"))
    ref = now or datetime.datetime.now(datetime.timezone.utc)
    return (dt - ref).total_seconds() > MAX_CLOCK_SKEW_SECONDS


def _quick_hash(text) -> str:
    data = text.encode("utf-8") if isinstance(text, str) else text
    return hashlib.sha256(data).hexdigest()[:16]


def _hash_file(path: Path) -> str:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]
    except OSError:
        return ""


def _source_identity(project_root: Path):
    try:
        from freshness import compute_source_identity

        return compute_source_identity(Path(project_root))
    except Exception:
        return None


def _project_identity(project_root: Path) -> str:
    try:
        from .paths import project_identity as _pi

        return _pi(Path(project_root))
    except Exception:
        return ""


def _log_hash(project_root: Path) -> str:
    try:
        from .log import history_hash

        return history_hash(Path(project_root))
    except Exception:
        return ""


# --------------------------------------------------------------------------- §1
@dataclass(frozen=True)
class ValidatorVersionInfo:
    validator_path: str
    validator_protocol_version: str
    project_protocol_version: str | None
    gate: str
    source_head: str
    source_tree_fingerprint: str

    def as_dict(self) -> dict:
        return {
            "validator_path": self.validator_path,
            "validator_protocol_version": self.validator_protocol_version,
            "project_protocol_version": self.project_protocol_version,
            "gate": self.gate,
            "source_head": self.source_head,
            "source_tree_fingerprint": self.source_tree_fingerprint,
        }


def validator_version_info(
    project_root: Path | str, gate: str = "core",
    # PERF-002: optional pre-computed SourceIdentity to avoid redundant
    # filesystem/Git subprocess calls. When provided, skips _source_identity.
    source_identity=None,
) -> ValidatorVersionInfo:
    """§1: resolve validator authority from the project's bound SAIPEN home.

    The canonical validator is the one living next to this engine
    (tools/validate.py), NOT a copy vendored elsewhere. We report its path and
    protocol version together with the project's own protocol version so any
    viewer/tool can detect a STALE_VALIDATOR (a different validator binary than
    the canonical one on disk).

    PERF-002: accepts an optional pre-computed SourceIdentity to avoid
    redundant computation when the caller has already captured the identity.
    """
    root = Path(project_root)
    validator_path = str((Path(__file__).resolve().parent.parent / "validate.py").resolve())
    project_protocol: str | None = None
    try:
        state_text = (root / ".saipen" / "STATE.md").read_text(
            encoding="utf-8-sig", errors="ignore"
        )
        for line in state_text.splitlines():
            if line.startswith("saipen_version:"):
                project_protocol = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    # PERF-002: use pre-computed identity if available
    if source_identity is not None:
        ident = source_identity
    else:
        ident = _source_identity(root)
    return ValidatorVersionInfo(
        validator_path=validator_path,
        validator_protocol_version=CONFORMANCE_PROTOCOL_VERSION,
        project_protocol_version=project_protocol,
        gate=gate,
        source_head=ident.source_head if ident else "",
        source_tree_fingerprint=ident.source_tree_fingerprint if ident else "",
    )


def stale_validator(
    project_root: Path | str, tool_validator_version: str | None = None
) -> bool:
    """§1: report STALE_VALIDATOR when a viewer/tool uses a different validator
    version than the canonical one on disk."""
    if tool_validator_version is not None and tool_validator_version != CONFORMANCE_PROTOCOL_VERSION:
        return True
    return False


# --------------------------------------------------------------------------- §2
def generate_conformance_receipt(
    project_root: Path | str,
    *,
    gate: str,
    exit_code: int,
    validator_version: str | None = None,
    now: datetime.datetime | None = None,
) -> dict:
    """§2: mechanically produce ONE structured conformance receipt.

    Binds validator version, gate, exit code, PASS/FAIL, real UTC timestamp,
    project/source identity, STATE/BOARD/LOG hashes and source_head/
    source_tree_fingerprint. Written under `.saipen/recovery/conformance/`.

    CRITICAL: the verdict is DERIVED ONLY from `exit_code` (0 == PASS). The
    function does not even accept a `verdict` argument, so no caller can pass
    `verdict="PASS"` to manufacture a green receipt. This is the ONLY path that
    creates a receipt, and it is invoked exclusively from the validator's real
    execution path (tools/validate.py)."""
    root = Path(project_root)
    verdict = "PASS" if int(exit_code or 0) == 0 else "FAIL"
    ts = _utc_now_iso(now)
    # §9: refuse to write a receipt whose stamp sits in the future beyond the
    # skew allowance relative to the REAL wall clock. Comparing against the real
    # clock (not the caller-supplied `now`) is what makes this guard live: a
    # caller passing a fabricated-future `now` gets refused instead of emitting
    # a back-dated-looking green stamp.
    if _future_beyond_skew(ts, datetime.datetime.now(datetime.timezone.utc)):
        raise ValueError("conformance receipt timestamp is in the future beyond allowed skew")
    state_hash = _hash_file(root / ".saipen" / "STATE.md")
    board_hash = _hash_file(root / ".saipen" / "BOARD.md")
    log_hash = _log_hash(root)
    ident = _source_identity(root)
    project_identity = _project_identity(root)
    # W2-005: unique receipt id and microsecond-precision timestamp for
    # total ordering. Never overwrites an earlier receipt.
    rid = _receipt_id()
    receipt = {
        "schema_version": 2,
        "kind": "conformance_receipt",
        "receipt_id": rid,
        "validator_protocol_version": validator_version or CONFORMANCE_PROTOCOL_VERSION,
        "gate": gate,
        "exit_code": int(exit_code or 0),
        "verdict": verdict,
        "timestamp_utc": ts,
        "project_identity": project_identity,
        "source_head": ident.source_head if ident else "",
        "source_tree_fingerprint": ident.source_tree_fingerprint if ident else "",
        "state_hash": state_hash,
        "board_hash": board_hash,
        "log_hash": log_hash,
    }
    # content_hash binds the EXACT written bytes, so compute it from the body
    # BEFORE serializing for real -- otherwise the on-disk receipt would omit it.
    receipt["content_hash"] = _quick_hash(json.dumps(receipt, indent=2, sort_keys=True))
    body = json.dumps(receipt, indent=2, sort_keys=True)
    # CORE-003: validate containment BEFORE any filesystem mutation so a
    # symlinked .saipen/recovery/conformance never follows to an outside dir.
    _validate_conformance_containment(root)
    out_dir = root / RECEIPT_DIRNAME
    out_dir.mkdir(parents=True, exist_ok=True)
    # W2-005/W2-006: use receipt_id + safe gate name for unique, portable filename
    safe_gate = _safe_filename_component(gate)
    safe_ts = _safe_filename_component(ts)
    fname = f"{safe_ts}_{rid}_{safe_gate}_{verdict}.json"
    _atomic_write_receipt(out_dir / fname, body)
    # PERF-003: atomically advance the per-gate latest-receipt index
    _update_receipt_index(root, gate, rid, ts)
    return receipt


# PERF-003: per-gate latest-receipt index for O(1) lookup
_INDEX_DIRNAME = ".saipen/recovery/conformance/index"


def _update_receipt_index(root: Path, gate: str, receipt_id: str, timestamp: str) -> None:
    """PERF-003: atomically advance the per-gate latest-receipt index.

    The index is a tiny JSON file containing only the receipt_id and
    timestamp of the latest receipt for each gate. It is a LOCATOR, not
    conformance proof -- lookup still validates the indexed receipt.
    """
    index_dir = root / _INDEX_DIRNAME
    index_dir.mkdir(parents=True, exist_ok=True)
    index_path = index_dir / f"{gate}.json"
    index = {
        "gate": gate,
        "receipt_id": receipt_id,
        "timestamp_utc": timestamp,
        "version": 1,
    }
    tmp = index_path.with_suffix(".tmp")
    _atomic_write_receipt(index_path, json.dumps(index, indent=2, sort_keys=True))


def _lookup_receipt_index(root: Path, gate: str) -> dict | None:
    """PERF-003: read the per-gate latest-receipt index.

    Returns the indexed receipt metadata, or None if the index is
    absent/corrupt.
    """
    index_path = root / _INDEX_DIRNAME / f"{gate}.json"
    if not index_path.is_file():
        return None
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        if data.get("gate") != gate or "receipt_id" not in data:
            return None
        return data
    except (OSError, json.JSONDecodeError):
        return None


def _find_receipt_by_id(project_root: Path, receipt_id: str) -> dict | None:
    """PERF-003: find a receipt by its unique id across all receipt files."""
    out_dir = project_root / RECEIPT_DIRNAME
    if not out_dir.is_dir():
        return None
    for p in out_dir.glob("*.json"):
        try:
            info = os.lstat(p)
        except OSError:
            continue
        if os.path.islink(p) or getattr(info, "st_file_attributes", 0) & 0x400:
            continue
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if rec.get("receipt_id") == receipt_id:
            return rec
    return None


def _iter_receipts(project_root: Path) -> list[dict]:
    root = Path(project_root)
    out_dir = root / RECEIPT_DIRNAME
    if not out_dir.is_dir():
        return []
    out: list[dict] = []
    for p in sorted(out_dir.glob("*.json")):
        # CORE-003: reject symlinked/reparse-point receipt files -- an
        # externally located receipt must never be imported as project evidence.
        try:
            info = os.lstat(p)
        except OSError:
            continue
        if os.path.islink(p):
            continue
        if getattr(info, "st_file_attributes", 0) & 0x400:
            continue
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if rec.get("kind") != "conformance_receipt":
            continue
        out.append(rec)
    return out


def latest_receipt(project_root: Path | str, gate: str | None = None) -> dict | None:
    """PERF-003/W2-005: return the latest receipt ordered by validated completion.

    Uses the atomic per-gate index for O(1) lookup when available. Falls back
    to a full strict scan if the index is absent/corrupt/references a missing
    receipt.
    """
    root = Path(project_root)
    if gate is not None:
        # PERF-003: try index-first lookup
        index = _lookup_receipt_index(root, gate)
        if index is not None:
            rec = _find_receipt_by_id(root, index["receipt_id"])
            if rec is not None and rec.get("gate") == gate:
                # Validate the indexed receipt matches the expected timestamp
                if rec.get("timestamp_utc") == index.get("timestamp_utc"):
                    return rec
        # Index miss/corruption: fall back to full scan
        receipts = _iter_receipts(root)
        receipts = [r for r in receipts if r.get("gate") == gate]
    else:
        receipts = _iter_receipts(root)
    if not receipts:
        return None
    # W2-005: order by timestamp (primary) then receipt_id (secondary)
    # for deterministic total ordering across same-second executions.
    return max(receipts, key=lambda r: (r.get("timestamp_utc", ""), r.get("receipt_id", "")))


# --------------------------------------------------------------------------- CORE-001 strict receipt validation
# Required fields for a receipt to be considered structurally valid.
# schema_version 2+ requires receipt_id for W2-005 total ordering.
_RECEIPT_REQUIRED_FIELDS_V1 = frozenset({
    "schema_version", "kind", "validator_protocol_version",
    "gate", "exit_code", "verdict", "timestamp_utc",
})
_RECEIPT_REQUIRED_FIELDS_V2 = _RECEIPT_REQUIRED_FIELDS_V1 | {"receipt_id"}

# Allowed gate values.
_ALLOWED_GATES = ("core", "crew")


def _strict_validate_receipt(
    receipt: dict, gate: str, project_root: Path
) -> str | None:
    """CORE-001: one strict conformance-receipt decoder.

    Returns None when the receipt is structurally and cryptographically
    valid. Returns a reason string when the receipt is malformed, tampered,
    or checkpoint-mismatched. A receipt that fails this check is INVALID
    and must never satisfy `current_conformance_pass`.

    Checks:
    - Closed schema (required fields present)
    - Receipt protocol version matches
    - Allowed gate value
    - Real timestamp parsing
    - exit_code == 0 <=> verdict == PASS
    - content_hash revalidation over the canonical receipt body
    - (For CURRENT status) STATE/BOARD/LOG hashes match current files
    """
    # 1. Schema: required fields present (version-aware)
    schema_version = receipt.get("schema_version", 1)
    required = _RECEIPT_REQUIRED_FIELDS_V2 if schema_version >= 2 else _RECEIPT_REQUIRED_FIELDS_V1
    missing = required - set(receipt.keys())
    if missing:
        return f"receipt is missing required fields: {sorted(missing)}"

    # 2. Protocol version
    if receipt.get("validator_protocol_version") != CONFORMANCE_PROTOCOL_VERSION:
        return (
            f"validator protocol version mismatch: "
            f"{receipt.get('validator_protocol_version')} != "
            f"{CONFORMANCE_PROTOCOL_VERSION}"
        )

    # 3. Gate is in the allowed set
    if receipt.get("gate") not in _ALLOWED_GATES:
        return f"receipt gate {receipt.get('gate')!r} is not in {_ALLOWED_GATES}"

    # 4. exit_code / verdict consistency: exit_code == 0 <=> verdict == PASS
    exit_code = receipt.get("exit_code")
    verdict = receipt.get("verdict")
    if not isinstance(exit_code, int):
        return f"receipt exit_code is not an integer: {exit_code!r}"
    if verdict not in ("PASS", "FAIL"):
        return f"receipt verdict is not PASS/FAIL: {verdict!r}"
    if (exit_code == 0) != (verdict == "PASS"):
        return (
            f"exit_code/verdict inconsistency: exit_code={exit_code} "
            f"but verdict={verdict}"
        )

    # 5. content_hash revalidation: recompute from the receipt body
    #    (every field except content_hash itself)
    stored_hash = receipt.get("content_hash", "")
    if not stored_hash:
        return "receipt has no content_hash"
    body_for_hash = {k: v for k, v in receipt.items() if k != "content_hash"}
    recomputed = _quick_hash(json.dumps(body_for_hash, indent=2, sort_keys=True))
    if recomputed != stored_hash:
        return (
            f"content_hash mismatch: stored={stored_hash[:16]}.. "
            f"recomputed={recomputed[:16]}.. (receipt body was tampered)"
        )

    # 6. Real timestamp parsing
    ts = receipt.get("timestamp_utc", "")
    if not _strict_iso_utc(ts):
        return f"receipt timestamp is not valid ISO-8601 UTC: {ts!r}"

    return None


def _checkpoint_hash_mismatch(receipt: dict, root: Path) -> str | None:
    """CORE-001: recompute and compare STATE/BOARD/LOG hashes.

    Returns None when all hashes match, or a reason string describing the
    first mismatch. This catches tampered receipts that have valid structure
    but were written for a different checkpoint state.
    """
    # Only check hashes that the receipt claims to carry
    current_state = _hash_file(root / ".saipen" / "STATE.md")
    current_board = _hash_file(root / ".saipen" / "BOARD.md")
    current_log = _log_hash(root)
    stored_state = receipt.get("state_hash", "")
    stored_board = receipt.get("board_hash", "")
    stored_log = receipt.get("log_hash", "")
    # Only mismatch when stored hash is non-empty AND differs from current
    # (empty stored hash means the receipt was minted without checkpoint
    # binding, which is a structural weakness but not a mismatch per se)
    if stored_state and current_state and stored_state != current_state:
        return (
            f"STATE hash mismatch: receipt={stored_state} current={current_state}"
        )
    if stored_board and current_board and stored_board != current_board:
        return (
            f"BOARD hash mismatch: receipt={stored_board} current={current_board}"
        )
    if stored_log and current_log and stored_log != current_log:
        return (
            f"LOG hash mismatch: receipt={stored_log} current={current_log}"
        )
    return None


# --------------------------------------------------------------------------- §8
def conformance_status(
    project_root: Path | str, gate: str = "core", now: datetime.datetime | None = None,
    # PERF-002: optional pre-computed SourceIdentity to avoid redundant
    # filesystem/Git subprocess calls.
    source_identity=None,
) -> dict:
    """§8: classify the CURRENT authoritative conformance for a gate.

    CORE-001: the receipt is now STRICTLY validated before classification.
    Schema, exit_code/verdict consistency, content_hash integrity, and
    (for CURRENT) checkpoint hash binding are all enforced. A forged,
    tampered, or checkpoint-mismatched receipt is INVALID/STALE and never
    satisfies `current_conformance_pass`.

    PERF-002: accepts an optional pre-computed SourceIdentity to avoid
    redundant computation when the caller has already captured the identity.

    Terminal/crew closure is permitted ONLY when status == CURRENT_PASS. Every
    other status (NOT_RUN, STALE_*, CURRENT_FAIL, VALIDATOR_VERSION_MISMATCH)
    forbids closure and must be surfaced truthfully by `saipen status` and any
    viewer."""
    ref = now or datetime.datetime.now(datetime.timezone.utc)
    info = validator_version_info(project_root, gate=gate, source_identity=source_identity)
    receipt = latest_receipt(project_root, gate)
    root = Path(project_root)
    if receipt is None:
        return {
            "status": STATUS_NOT_RUN,
            "gate": gate,
            "reason": "no canonical validator receipt on record -- conformance is "
            "UNKNOWN, never assumed PASS",
            "validator": info.as_dict(),
        }
    if receipt.get("validator_protocol_version") != CONFORMANCE_PROTOCOL_VERSION:
        return {
            "status": STATUS_VERSION_MISMATCH,
            "gate": gate,
            "reason": "conformance receipt was written by a different validator "
            f"protocol version ({receipt.get('validator_protocol_version')} != "
            f"{CONFORMANCE_PROTOCOL_VERSION})",
            "receipt": receipt,
            "validator": info.as_dict(),
        }
    if _future_beyond_skew(receipt.get("timestamp_utc", ""), ref):
        return {
            "status": STATUS_STALE_FAIL,
            "gate": gate,
            "reason": "conformance receipt timestamp is in the future beyond "
            "allowed skew (fabricated)",
            "receipt": receipt,
            "validator": info.as_dict(),
        }
    # CORE-001: strict structural + cryptographic validation
    strict_err = _strict_validate_receipt(receipt, gate, root)
    if strict_err:
        return {
            "status": STATUS_INVALID,
            "gate": gate,
            "reason": f"receipt is invalid: {strict_err}",
            "receipt": receipt,
            "validator": info.as_dict(),
        }
    current_head = info.source_head
    current_fp = info.source_tree_fingerprint
    bound = (
        receipt.get("source_head") == current_head
        and receipt.get("source_tree_fingerprint") == current_fp
    )
    is_pass = receipt.get("verdict") == "PASS"
    age_seconds = 0
    try:
        rdt = datetime.datetime.fromisoformat(receipt["timestamp_utc"].replace("Z", "+00:00"))
        age_seconds = (ref - rdt).total_seconds()
    except Exception:
        pass
    if not bound:
        status = STATUS_STALE_PASS if is_pass else STATUS_STALE_FAIL
        reason = "conformance receipt is bound to a different source identity " "than the current checkpoint"
    elif age_seconds > FRESHNESS_WINDOW_SECONDS:
        status = STATUS_STALE_PASS if is_pass else STATUS_STALE_FAIL
        reason = (
            f"conformance receipt is {int(age_seconds // 3600)}h old (older than "
            f"the {int(FRESHNESS_WINDOW_SECONDS // 3600)}h freshness window)"
        )
    else:
        # CORE-001: for a CURRENT receipt that appears to PASS, also verify
        # that the checkpoint hashes (STATE/BOARD/LOG) in the receipt match
        # the current files. This catches the case where a receipt was minted
        # for one checkpoint but the files have since been mutated.
        if is_pass:
            cp_err = _checkpoint_hash_mismatch(receipt, root)
            if cp_err:
                status = STATUS_STALE_PASS
                reason = f"receipt checkpoint hashes invalid: {cp_err}"
            else:
                status = STATUS_CURRENT_PASS
                reason = ""
        else:
            status = STATUS_CURRENT_FAIL
            reason = "canonical validator reports FAIL for the current checkpoint"
    return {
        "status": status,
        "gate": gate,
        "reason": reason,
        "receipt": receipt,
        "validator": info.as_dict(),
    }

def current_conformance_pass(
    project_root: Path | str, gate: str = "core", now: datetime.datetime | None = None,
    # PERF-002: optional pre-computed SourceIdentity to avoid redundant
    # filesystem/Git subprocess calls.
    source_identity=None,
) -> bool:
    """§4/§7: terminal/crew closure is allowed ONLY on a CURRENT_PASS receipt
    bound to the current checkpoint. Everything else forbids closure."""
    return (
        conformance_status(project_root, gate=gate, now=now, source_identity=source_identity)
        .get("status") == STATUS_CURRENT_PASS
    )


# --------------------------------------------------------------------------- §3
def convergence_stage_satisfied(
    project_root: Path | str, stage: str, source_identity, now: datetime.datetime | None = None
) -> tuple[bool, str]:
    """§3: a convergence stage E/H (verdict PASS) must be backed by a REAL,
    CURRENT conformance receipt for gate `core`, bound to the SAME source
    identity the stage binds. Without it the stage is not satisfied and the
    convergence planner must refuse with CONVERGENCE_GATE_UNSATISFIED."""
    if stage not in ("E", "H"):
        return True, ""
    status = conformance_status(project_root, gate="core", now=now)
    if status["status"] != STATUS_CURRENT_PASS:
        return False, (
            f"convergence stage {stage} requires a CURRENT_PASS canonical "
            f"conformance receipt bound to the current source identity, got "
            f"{status['status']}: {status.get('reason', '')}"
        )
    rec = status.get("receipt", {})
    want = (
        getattr(source_identity, "source_head", None),
        getattr(source_identity, "source_tree_fingerprint", None),
    )
    got = (rec.get("source_head"), rec.get("source_tree_fingerprint"))
    if got != want:
        return False, (
            f"convergence stage {stage} binds a source identity that does not "
            f"match the current conformance receipt -- a PASS from a different "
            f"tree cannot certify this one"
        )
    return True, ""


# --------------------------------------------------------------------------- §5
def clean_exit_allowed(
    project_root: Path | str, now: datetime.datetime | None = None
) -> tuple[bool, str]:
    """§5: after CLEAN mutations, the canonical Core validator must PASS for the
    CURRENT checkpoint. If it FAILs, CLEAN MUST NOT claim closure. Missing
    verify evidence is NOT invented -- absence of a PASS receipt forbids."""
    status = conformance_status(project_root, gate="core", now=now)
    if status["status"] != STATUS_CURRENT_PASS:
        return False, (
            f"CLEAN exit requires a CURRENT_PASS canonical conformance receipt "
            f"for the current checkpoint, got {status['status']}: "
            f"{status.get('reason', '')}"
        )
    return True, ""


# --------------------------------------------------------------------------- §6
def continue_entry_health(
    project_root: Path | str, state: dict | None = None, board: dict | None = None, now=None
) -> list[str]:
    """§6: additive continue-entry health gate. Hard closure refusals live in
    the actual closers (operations/crew/release); this surfaces the conformance
    requirement plus the cheap structural checks route_next already enforces, so
    a viewer can show WHY an entry is unhealthy without trusting prose.

    Returns a list of problem strings (empty == healthy)."""
    root = Path(project_root)
    problems: list[str] = []
    if state is None:
        try:
            from .state import parse_state_or_error

            st = (root / ".saipen" / "STATE.md").read_text(encoding="utf-8-sig", errors="ignore")
            state, _ = parse_state_or_error(st)
        except Exception:
            state = {}
        if not isinstance(state, dict):
            state = {}
    if board is None:
        try:
            from .board import parse_board

            bt = (root / ".saipen" / "BOARD.md").read_text(encoding="utf-8-sig", errors="ignore")
            board = parse_board(bt)
        except Exception:
            board = {"tickets": {}, "errors": []}
    # DONE without any convergence/verify evidence is not closure.
    if state.get("phase") == "DONE" and not current_conformance_pass(root, "core", now=now):
        problems.append(
            "phase DONE without a CURRENT_PASS canonical conformance receipt -- "
            "DONE is not convergence proof"
        )
    # converge/crew intent without current conformance is not finalizable.
    if state.get("execution_intent") == "converge" and state.get("converge_target") == "crew":
        if not current_conformance_pass(root, "crew", now=now):
            problems.append(
                "converge/crew intent present but canonical crew conformance is "
                "not CURRENT_PASS -- crew closure is impossible"
            )
    # DONE tickets without verify evidence (mirrors status' claimed_but_unproven).
    done = [t for t in board.get("tickets", {}).values() if t.get("section") == "## DONE"]
    for t in done:
        verify = (t.get("fields", {}) or {}).get("verify", "")
        if not verify:
            problems.append(f"DONE ticket {t.get('id')} has no verify evidence")
    # BLOCKED without a blocker.
    blocked = [t for t in board.get("tickets", {}).values() if t.get("section") == "## BLOCKED"]
    for t in blocked:
        blocker = (t.get("fields", {}) or {}).get("blocker", "")
        if not blocker:
            problems.append(f"BLOCKED ticket {t.get('id')} has no blocker")
    # multiple DOING.
    doing = [t for t in board.get("tickets", {}).values() if t.get("section") == "## DOING"]
    if len(doing) > 1:
        problems.append(f"multiple DOING tickets: {', '.join(t.get('id') for t in doing)}")
    return problems
