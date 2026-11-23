"""SAIPEN Release Authority & Human Approval Surface (SRC-375 / T-2001).

Owns the canonical operator release authorization contract:
- Defines the authenticated `saipen-release-authorization` capsule schema.
- Converts structured `decision_request` proposals into valid operator-signed capsules.
- Verifies grant bounds: project lineage, target remote, branch, base commit,
  reviewed scope, protected staging hash, verification gates, and finite budget.
- Supports one-shot and bounded standing release authority (reusable for repeated
  verified releases to the approved repository/branch without repeating consent).
- Enforces strict anti-fabrication and anti-replay controls: no model synthesis,
  no unverified shell impersonation, no force-push, and explicit durable revocation.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .paths import project_identity, project_lineage_identity

KIND = "saipen-release-authorization"
SCHEMA_VERSION = 1

REQUIRED_FIELDS = frozenset(
    {
        "kind",
        "schema",
        "grant_id",
        "project_lineage",
        "project_identity",
        "operation",
        "target_remote",
        "target_url",
        "target_branch",
        "base_commit",
        "reviewed_scope",
        "protected_staging_hash",
        "verification_gate",
        "standing",
        "max_releases",
        "releases_completed",
        "no_force",
        "created_at",
        "expires_at",
        "operator_intent",
    }
)

CANONICAL_OPERATION = "publish_isolated_release"
MAX_CAPSULE_BYTES = 256 * 1024
DEFAULT_STANDING_MAX_RELEASES = 10
DEFAULT_EXPIRY_HOURS = 72

#: The fields an operator must be shown and that the grant must then carry
#: unaltered. T-2027 P0-01: the preview and the grant are two readings of ONE
#: transaction, so this tuple is what `transaction_consistency_problem` compares.
TRANSACTION_FIELDS = (
    "target_remote",
    "target_branch",
    "target_url",
    "base_commit",
    "reviewed_scope",
    "protected_staging_hash",
)


def _utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def resolve_commit(root: Path | str, ref: str | None) -> str | None:
    """The immutable commit object id behind a ref, or None.

    T-2027 P1-04: grant matching compared the literal string "HEAD" against
    immutable SHAs, so the normal isolated path could never find the grant it
    had just been given. Symbolic refs are resolved HERE, at the one boundary
    where a ref enters an authorization decision.
    """
    if not ref or not isinstance(ref, str):
        return None
    from .release import _git

    res = _git(Path(root), "rev-parse", "--verify", f"{ref}^{{commit}}")
    value = (res.stdout or "").strip()
    return value or None


def staged_entry_count(root: Path | str) -> int:
    """The live number of staged entries in the shared index."""
    from .release import _git

    res = _git(Path(root), "diff", "--cached", "--name-only")
    if not res.ok:
        return 0
    return len([line for line in (res.stdout or "").splitlines() if line.strip()])


def _packet_ancestry(packet: dict[str, Any]) -> dict[str, Any]:
    ancestry = packet.get("ancestry")
    return ancestry if isinstance(ancestry, dict) else {}


def _packet_scope(packet: dict[str, Any]) -> list[str]:
    raw = packet.get("reviewed_scope") or []
    if isinstance(raw, str):
        return [p.strip() for p in raw.split(",") if p.strip()]
    return [str(p).strip() for p in raw if str(p).strip()]


def build_release_transaction(
    root: Path | str,
    *,
    packet_path: Path | str | None = None,
    packet_data: dict[str, Any] | None = None,
    remote: str | None = None,
    branch: str | None = None,
    reviewed_scope: list[str] | None = None,
    base_commit: str | None = None,
) -> dict[str, Any]:
    """ONE immutable transaction object for the preview and the grant (T-2027 P0-01).

    Pre-fix, `approve_release_command` computed the shown destination from the
    caller's explicit `remote`/`branch` and then handed the STORED PACKET to
    `convert_decision_request_to_capsule`, which re-read the packet's own
    `ancestry.remote`. The operator could be shown `origin/main` and granted
    `github-backup/main`.

    Every value here is derived once, from live state, and is consumed
    unaltered by both the presentation and `create_release_grant`. Nothing is a
    frozen fallback: T-2027 P0-03 removed the historical packet path, the
    hardcoded base commit, the hardcoded staging hash and the hardcoded staged
    count, all of which reached NEW grants for an unrelated cohort. When the
    source cannot be authenticated this answers `RELEASE_PROPOSAL_UNAVAILABLE`
    rather than an apparently valid approval.

    Returns the transaction, or `{"ok": False, "code": ...}`.
    """
    root = Path(root).resolve()

    packet: dict[str, Any] = {}
    packet_source = "generated"
    if packet_data is not None:
        packet = dict(packet_data)
        packet_source = str(packet_path) if packet_path else "supplied"
    elif packet_path:
        p = Path(packet_path)
        resolved = p if p.is_absolute() else (root / p).resolve()
        if not resolved.is_file():
            return {
                "ok": False,
                "code": "RELEASE_PROPOSAL_UNAVAILABLE",
                "detail": f"approval packet not found: {resolved}",
            }
        try:
            packet = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return {
                "ok": False,
                "code": "RELEASE_PROPOSAL_UNAVAILABLE",
                "detail": f"approval packet is unreadable: {type(exc).__name__}: {exc}",
            }
        if not isinstance(packet, dict):
            return {
                "ok": False,
                "code": "RELEASE_PROPOSAL_UNAVAILABLE",
                "detail": "approval packet root is not a JSON object",
            }
        packet_source = str(resolved)

    ancestry = _packet_ancestry(packet)
    packet_remote = ancestry.get("remote")
    packet_branch = ancestry.get("branch")

    # A stored destination differing from the one the operator named is STALE,
    # never silently overridden in either direction.
    if remote is not None and packet_remote and remote != packet_remote:
        return {
            "ok": False,
            "code": "STALE_RELEASE_PACKET",
            "detail": (
                f"the approval packet names destination {packet_remote!r} but this "
                f"approval names {remote!r}; refuse a stale packet rather than "
                "authorizing a destination the operator was not shown"
            ),
            "packet_destination": f"{packet_remote}/{packet_branch or ''}".rstrip("/"),
            "requested_destination": f"{remote}/{branch or ''}".rstrip("/"),
        }
    if branch is not None and packet_branch and branch != packet_branch:
        return {
            "ok": False,
            "code": "STALE_RELEASE_PACKET",
            "detail": (
                f"the approval packet names branch {packet_branch!r} but this "
                f"approval names {branch!r}"
            ),
            "packet_destination": f"{packet_remote or ''}/{packet_branch}".lstrip("/"),
            "requested_destination": f"{remote or ''}/{branch}".lstrip("/"),
        }

    eff_remote = remote or packet_remote
    eff_branch = branch or packet_branch
    if not eff_remote or not eff_branch:
        return {
            "ok": False,
            "code": "RELEASE_PROPOSAL_UNAVAILABLE",
            "detail": (
                "no verified release destination: name --remote/--branch or supply an "
                "approval packet carrying a destination; this path never falls back to a "
                "historical packet or a hardcoded repository"
            ),
        }

    from .isolated_release import reconcile_remote_ancestry, snapshot_shared_index

    try:
        live = reconcile_remote_ancestry(root, remote=eff_remote, branch=eff_branch)
    except Exception as exc:  # noqa: BLE001 -- a broken remote is a refusal, not a traceback
        return {
            "ok": False,
            "code": "RELEASE_PROPOSAL_UNAVAILABLE",
            "detail": f"destination {eff_remote}/{eff_branch} is unreadable: {type(exc).__name__}: {exc}",
        }
    if not live.get("push_url"):
        return {
            "ok": False,
            "code": "RELEASE_PROPOSAL_UNAVAILABLE",
            "detail": f"remote {eff_remote!r} has no configured push URL",
        }

    raw_base = base_commit or ancestry.get("remote_head") or live.get("remote_head")
    resolved_base = resolve_commit(root, raw_base)
    if not resolved_base:
        return {
            "ok": False,
            "code": "RELEASE_PROPOSAL_UNAVAILABLE",
            "detail": (
                f"the release base {raw_base!r} does not resolve to a commit in this "
                "repository; an approval is never minted over an unverifiable base"
            ),
        }

    # T-2027 P0-05: an approved base that is not the verified destination tip
    # cannot produce a fast-forward. Say so here, before an operator is asked
    # to approve anything, and name the one route that can.
    remote_tip = live.get("remote_head") or ""
    if remote_tip and not live.get("is_fast_forward") and resolved_base != remote_tip:
        return {
            "ok": False,
            "code": "RELEASE_DESTINATION_DIVERGED",
            "detail": (
                f"{eff_remote}/{eff_branch} tip {remote_tip[:12]} is not an ancestor of "
                f"the requested base {resolved_base[:12]}; an ordinary fast-forward is "
                "impossible from here"
            ),
            "integration_route": (
                f"saipen ship --isolated --remote {eff_remote} --branch {eff_branch} "
                f"--reconcile-remote-head {remote_tip}"
            ),
            "remote_tip": remote_tip,
        }

    scope = list(reviewed_scope) if reviewed_scope is not None else _packet_scope(packet)
    scope = sorted({str(p).strip() for p in scope if str(p).strip()})

    staging_sha, _ = snapshot_shared_index(root)

    return {
        "ok": True,
        "target_remote": eff_remote,
        "target_branch": eff_branch,
        "target_url": live.get("push_url") or ancestry.get("push_url") or "",
        "base_commit": resolved_base,
        "reviewed_scope": scope,
        "protected_staging_hash": staging_sha,
        "staged_entry_count": staged_entry_count(root),
        "remote_tip": remote_tip,
        "packet_source": packet_source,
        "operator_intent": (
            f"Operator authorized isolated release to {eff_remote}/{eff_branch} on top of {resolved_base[:12]}"
        ),
    }


def transaction_consistency_problem(shown: dict[str, Any], grant: dict[str, Any]) -> str | None:
    """The first field where the displayed and granted transaction disagree (T-2027 P0-01).

    Byte-consistency in every authorization-relevant field is the contract; a
    single difference means the operator approved something other than what
    will be pushed.
    """
    for field in TRANSACTION_FIELDS:
        left, right = shown.get(field), grant.get(field)
        if isinstance(left, list) or isinstance(right, list):
            if sorted(left or []) != sorted(right or []):
                return field
            continue
        if left != right:
            return field
    return None


def _parse_iso(value: str) -> dt.datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("timestamp must be UTC ISO ending in 'Z'")
    return dt.datetime.fromisoformat(value[:-1] + "+00:00")


def compute_grant_id(payload: dict[str, Any]) -> str:
    """Compute the immutable content digest over bounded grant fields."""
    normalized = {
        "project_lineage": str(payload.get("project_lineage") or ""),
        "project_identity": str(payload.get("project_identity") or ""),
        "operation": str(payload.get("operation") or ""),
        "target_remote": str(payload.get("target_remote") or ""),
        "target_url": str(payload.get("target_url") or ""),
        "target_branch": str(payload.get("target_branch") or ""),
        "base_commit": str(payload.get("base_commit") or ""),
        "reviewed_scope": sorted(
            [str(p).strip() for p in (payload.get("reviewed_scope") or []) if str(p).strip()]
            if isinstance(payload.get("reviewed_scope"), list)
            else [p.strip() for p in str(payload.get("reviewed_scope") or "").split(",") if p.strip()]
        ),
        "protected_staging_hash": str(payload.get("protected_staging_hash") or ""),
        "verification_gate": str(payload.get("verification_gate") or ""),
        "standing": bool(payload.get("standing")),
        "max_releases": int(payload.get("max_releases") or 1),
        "no_force": bool(payload.get("no_force", True)),
        "created_at": str(payload.get("created_at") or ""),
        "expires_at": str(payload.get("expires_at") or ""),
    }
    raw = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )
    return hashlib.sha256(raw).hexdigest()


def parse_capsule(text: str) -> dict[str, Any]:
    """Parse and validate release authorization capsule text. Raises ValueError on defect."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("empty capsule text")
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].startswith("```"):
            stripped = "\n".join(lines[1:-1]).strip()
    if len(stripped.encode("utf-8")) > MAX_CAPSULE_BYTES:
        raise ValueError(f"capsule text exceeds {MAX_CAPSULE_BYTES} bytes")
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(f"capsule is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("capsule root must be a JSON object")
    if data.get("kind") != KIND:
        raise ValueError(f"unsupported capsule kind {data.get('kind')!r}; expected {KIND!r}")
    if data.get("schema") != SCHEMA_VERSION:
        raise ValueError(f"unsupported capsule schema {data.get('schema')!r}")
    missing = REQUIRED_FIELDS - set(data)
    if missing:
        raise ValueError(f"capsule missing required fields: {sorted(missing)}")
    if data.get("operation") != CANONICAL_OPERATION:
        raise ValueError(f"unsupported operation {data.get('operation')!r}")
    if data.get("no_force") is not True:
        raise ValueError("release authorization requires no_force=True; force-push is forbidden")
    if not re.fullmatch(r"[0-9a-f]{64}", str(data.get("grant_id") or "")):
        raise ValueError("invalid grant_id format")
    expected_id = compute_grant_id(data)
    if data.get("grant_id") != expected_id:
        raise ValueError(f"grant_id mismatch: recorded {data.get('grant_id')}, expected {expected_id}")
    created = _parse_iso(data["created_at"])
    expires = _parse_iso(data["expires_at"])
    if expires <= created:
        raise ValueError("expires_at must be strictly after created_at")
    return data


def capsule_problem(text: str) -> str | None:
    """Return error string if text is not a valid release capsule, else None."""
    try:
        parse_capsule(text)
        return None
    except (ValueError, TypeError, KeyError) as exc:
        return str(exc)


def create_release_grant(
    root: Path | str,
    *,
    target_remote: str,
    target_url: str,
    target_branch: str,
    base_commit: str,
    reviewed_scope: list[str] | str,
    protected_staging_hash: str,
    verification_gate: str = "python tools/core_unit.py run",
    standing: bool = False,
    max_releases: int | None = None,
    expiry_hours: int = DEFAULT_EXPIRY_HOURS,
    operator_intent: str = "Operator authorized GitHub release",
) -> dict[str, Any]:
    """Generate an executable, scope-bound release authorization capsule."""
    root = Path(root).resolve()
    lineage = project_lineage_identity(root) or ""
    proj_id = project_identity(root) or str(root)

    if isinstance(reviewed_scope, str):
        scope_list = [p.strip() for p in reviewed_scope.split(",") if p.strip()]
    else:
        scope_list = [str(p).strip() for p in reviewed_scope if str(p).strip()]

    now_dt = dt.datetime.now(dt.timezone.utc)
    created_at = now_dt.isoformat(timespec="seconds").replace("+00:00", "Z")
    expires_at = (
        (now_dt + dt.timedelta(hours=max(1, expiry_hours)))
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )

    effective_max = (
        (DEFAULT_STANDING_MAX_RELEASES if max_releases is None else max(1, max_releases))
        if standing
        else 1
    )

    payload: dict[str, Any] = {
        "kind": KIND,
        "schema": SCHEMA_VERSION,
        "project_lineage": lineage,
        "project_identity": proj_id,
        "operation": CANONICAL_OPERATION,
        "target_remote": target_remote,
        "target_url": target_url,
        "target_branch": target_branch,
        "base_commit": base_commit,
        "reviewed_scope": sorted(scope_list),
        "protected_staging_hash": protected_staging_hash,
        "verification_gate": verification_gate,
        "standing": standing,
        "max_releases": effective_max,
        "releases_completed": 0,
        "no_force": True,
        "created_at": created_at,
        "expires_at": expires_at,
        "operator_intent": operator_intent,
    }
    payload["grant_id"] = compute_grant_id(payload)
    return payload


def convert_decision_request_to_capsule(
    packet_path_or_dict: Path | str | dict[str, Any],
    root: Path | str,
    *,
    standing: bool = False,
    max_releases: int | None = None,
    expiry_hours: int = DEFAULT_EXPIRY_HOURS,
    operator_intent: str | None = None,
    transaction: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert an existing decision_request proposal into an executable authorization capsule.

    T-2027 P0-03: this function carried a hardcoded base commit
    (`3c96a989...`), a hardcoded URL and a hardcoded staging hash
    (`91a5a63c...`) as DEFAULTS, so a packet missing any of them minted a grant
    for an unrelated cohort. Those constants are gone. Every value now comes
    from the packet itself or from `transaction`, the live immutable
    transaction object `build_release_transaction` derived; a packet that names
    no destination is a `ValueError`, never a historical default.

    When `transaction` is supplied it is authoritative: `approve_release_command`
    passes it so the granted values are the values the operator was shown.
    """
    if transaction is not None:
        remote = transaction["target_remote"]
        push_url = transaction["target_url"]
        branch = transaction["target_branch"]
        base_commit = transaction["base_commit"]
        reviewed_scope = list(transaction["reviewed_scope"])
        staging_hash = transaction["protected_staging_hash"]
    else:
        if isinstance(packet_path_or_dict, (str, Path)):
            packet_path = Path(packet_path_or_dict)
            if not packet_path.is_file():
                raise FileNotFoundError(f"approval packet file not found: {packet_path}")
            packet = json.loads(packet_path.read_text(encoding="utf-8"))
        else:
            packet = dict(packet_path_or_dict)

        root = Path(root).resolve()
        ancestry = _packet_ancestry(packet)
        remote = ancestry.get("remote")
        push_url = ancestry.get("push_url")
        branch = ancestry.get("branch")
        base_commit = ancestry.get("remote_head")
        missing = [
            name
            for name, value in (
                ("remote", remote),
                ("push_url", push_url),
                ("branch", branch),
                ("remote_head", base_commit),
            )
            if not value
        ]
        if missing:
            raise ValueError(
                "decision request names no release destination (missing "
                + ", ".join(missing)
                + "); this conversion never substitutes a historical default"
            )
        reviewed_scope = _packet_scope(packet)

        staging_hash = packet.get("staging_manifest_sha256") or ""
        if not staging_hash:
            try:
                from .isolated_release import snapshot_shared_index

                index_sha, _ = snapshot_shared_index(root)
                staging_hash = index_sha or ""
            except Exception:  # noqa: BLE001 -- an unreadable index yields no identity, not a constant
                staging_hash = ""

    root = Path(root).resolve()
    intent = (
        operator_intent
        or f"Operator authorized isolated release to {remote}/{branch} on top of {str(base_commit)[:12]}"
    )

    return create_release_grant(
        root,
        target_remote=remote,
        target_url=push_url,
        target_branch=branch,
        base_commit=base_commit,
        reviewed_scope=reviewed_scope,
        protected_staging_hash=staging_hash,
        verification_gate="python tools/core_unit.py run",
        standing=standing,
        max_releases=max_releases,
        expiry_hours=expiry_hours,
        operator_intent=intent,
    )


def grants_dir(root: Path | str) -> Path:
    p = Path(root).resolve() / ".saipen" / "authority" / "release_grants"
    p.mkdir(parents=True, exist_ok=True)
    return p


def persist_grant(root: Path | str, grant: dict[str, Any]) -> Path:
    """Store the authenticated release grant in the project's authority ledger."""
    validate_capsule_data(grant, root)
    out_dir = grants_dir(root)
    file_path = out_dir / f"{grant['grant_id']}.json"
    file_path.write_text(json.dumps(grant, indent=2, ensure_ascii=False), encoding="utf-8")
    return file_path


def validate_capsule_data(grant: dict[str, Any], root: Path | str) -> None:
    """Validate capsule data against project invariants. Raises ValueError on mismatch."""
    root = Path(root).resolve()
    capsule_text = json.dumps(grant)
    parsed = parse_capsule(capsule_text)

    # Check project lineage
    lineage = project_lineage_identity(root) or ""
    if parsed["project_lineage"] and lineage and parsed["project_lineage"] != lineage:
        raise ValueError(
            f"project_lineage mismatch: grant bound to {parsed['project_lineage']}, root is {lineage}"
        )

    # Check expiration
    expires = _parse_iso(parsed["expires_at"])
    if dt.datetime.now(dt.timezone.utc) > expires:
        raise ValueError(f"release grant {parsed['grant_id']} has expired (expired at {parsed['expires_at']})")

    # Check quota
    if parsed["releases_completed"] >= parsed["max_releases"]:
        raise ValueError(
            f"release grant {parsed['grant_id']} quota exhausted ({parsed['releases_completed']}/{parsed['max_releases']} releases completed)"
        )


def find_active_grant(
    root: Path | str,
    *,
    remote: str = "github-backup",
    branch: str = "main",
    base_commit: str | None = None,
) -> dict[str, Any] | None:
    """Find a valid, unexpired, unexhausted release grant matching target destination."""
    root = Path(root).resolve()
    # T-2027 P1-04: an approved packet carries an immutable commit SHA while the
    # normal isolated path names the symbolic ref "HEAD". Comparing the two
    # strings could never match, so the requested base is resolved to its commit
    # object id FIRST. A ref that does not resolve to a commit matches nothing:
    # the match is narrower, never wider.
    requested = base_commit
    if base_commit:
        requested = resolve_commit(root, base_commit)
        if not requested:
            return None
    out_dir = grants_dir(root)
    for grant_file in sorted(out_dir.glob("*.json"), reverse=True):
        try:
            data = json.loads(grant_file.read_text(encoding="utf-8"))
            if data.get("revoked"):
                continue
            validate_capsule_data(data, root)
            if data.get("target_remote") != remote:
                continue
            if data.get("target_branch") != branch:
                continue
            if requested and data.get("base_commit") and data.get("base_commit") != requested:
                continue
            return data
        except (ValueError, OSError, KeyError):
            continue
    return None


def record_grant_release_executed(root: Path | str, grant_id: str, commit_sha: str) -> dict[str, Any]:
    """Increment the completed release counter on an authorized grant."""
    root = Path(root).resolve()
    grant_file = grants_dir(root) / f"{grant_id}.json"
    if not grant_file.is_file():
        raise FileNotFoundError(f"grant file not found: {grant_file}")
    data = json.loads(grant_file.read_text(encoding="utf-8"))
    data["releases_completed"] = int(data.get("releases_completed", 0)) + 1
    history = data.setdefault("execution_history", [])
    history.append(
        {
            "commit_sha": commit_sha,
            "timestamp": _utc_now_iso(),
            "release_number": data["releases_completed"],
        }
    )
    grant_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return data


def revoke_grant(root: Path | str, grant_id: str, reason: str = "Operator revoked") -> dict[str, Any]:
    """Revoke an existing release grant."""
    root = Path(root).resolve()
    grant_file = grants_dir(root) / f"{grant_id}.json"
    if not grant_file.is_file():
        raise FileNotFoundError(f"grant file not found: {grant_file}")
    data = json.loads(grant_file.read_text(encoding="utf-8"))
    data["revoked"] = True
    data["revocation_reason"] = reason
    data["revoked_at"] = _utc_now_iso()
    grant_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "code": "GRANT_REVOKED", "grant_id": grant_id, "reason": reason}


def list_grants(root: Path | str) -> list[dict[str, Any]]:
    """Return all recorded release grants with status metadata."""
    root = Path(root).resolve()
    out_dir = grants_dir(root)
    grants = []
    now = dt.datetime.now(dt.timezone.utc)
    for grant_file in sorted(out_dir.glob("*.json"), reverse=True):
        try:
            data = json.loads(grant_file.read_text(encoding="utf-8"))
            grant_id = data.get("grant_id") or grant_file.stem
            is_revoked = bool(data.get("revoked"))
            expires_at = _parse_iso(data["expires_at"]) if "expires_at" in data else now
            is_expired = now > expires_at
            quota = int(data.get("max_releases", 1))
            completed = int(data.get("releases_completed", 0))
            is_exhausted = completed >= quota
            status = (
                "REVOKED"
                if is_revoked
                else "EXPIRED"
                if is_expired
                else "EXHAUSTED"
                if is_exhausted
                else "ACTIVE"
            )
            grants.append(
                {
                    "grant_id": grant_id,
                    "status": status,
                    "target_remote": data.get("target_remote"),
                    "target_branch": data.get("target_branch"),
                    "standing": data.get("standing", False),
                    "releases_completed": completed,
                    "max_releases": quota,
                    "created_at": data.get("created_at"),
                    "expires_at": data.get("expires_at"),
                    "file_path": str(grant_file),
                }
            )
        except Exception:
            continue
    return grants


def _operator_provenance(
    root: Path,
    *,
    provenance: dict[str, Any] | None,
    operator_origin: dict[str, Any] | None,
    operator_operation: str,
    explicit_verification: bool,
    transaction: dict[str, Any],
) -> tuple[bool, str | None]:
    """Is this approval genuinely operator-originated? (T-2027 P0-02)

    Pre-fix this was `stdin_isatty and confirm`. Both flags are supplied by the
    caller, so a model that allocates a pseudoterminal -- or simply calls the
    function in-process with `stdin_isatty=True` -- minted a persisted release
    grant with no human anywhere. A PTY proves a terminal exists, not who typed.

    Accepted provenance, in order:
    1. `explicit_verification` -- an in-process caller that already verified
       through the broker (the CLI never sets it from argv).
    2. A carrier claim WITH an operator-origin proof the live broker
       reproduces for this project, operation and grant scope. The claim alone
       is not proof: SRC-278/T-1844 measured a model setting the real carrier
       variables into a matching ingress file.

    Conservation over convenience: when the broker cannot answer, this refuses.
    """
    if explicit_verification:
        return True, None

    if not provenance or provenance.get("witness") != "operator_carrier":
        return False, "no operator-carried ingress was presented"
    if not isinstance(operator_origin, dict):
        return False, "a carrier claim was presented without an operator-origin proof"

    grant_scope = {
        field: transaction.get(field)
        for field in (
            "target_remote",
            "target_branch",
            "target_url",
            "base_commit",
            "protected_staging_hash",
        )
    }
    grant_scope["reviewed_scope"] = list(transaction.get("reviewed_scope") or [])
    try:
        from .host_authority_client import verify_operator_goal

        verified = verify_operator_goal(
            operator_origin,
            project=root,
            operation=operator_operation,
            grant=grant_scope,
        )
    except Exception as exc:  # noqa: BLE001 -- an unreachable broker verifies nothing
        return False, f"operator provenance is unverifiable: {type(exc).__name__}"
    if not verified:
        return False, "the broker did not reproduce this operator origin for this release scope"
    return True, None


def approve_release_command(
    root: Path | str,
    *,
    packet_path: Path | str | None = None,
    remote: str | None = None,
    branch: str | None = None,
    base_commit: str | None = None,
    reviewed_scope: list[str] | None = None,
    standing: bool = False,
    max_releases: int | None = None,
    expiry_hours: int = DEFAULT_EXPIRY_HOURS,
    operator_intent: str | None = None,
    confirm: bool = False,
    stdin_isatty: bool | None = None,
    provenance: dict[str, Any] | None = None,
    operator_origin: dict[str, Any] | None = None,
    operator_operation: str = "release-authorize",
    _operator_verified: bool = False,
) -> dict[str, Any]:
    """Canonical human approval surface for release publication.

    - Presents complete transaction scope: destination, branch, reviewed files,
      base commit, live protected staging index hash, verification gate, limits.
    - Presents and grants ONE immutable transaction: the presentation and the
      capsule are two readings of the same derivation (T-2027 P0-01).
    - Requires genuine operator provenance (T-2027 P0-02): a broker-verified
      operator origin, or an authenticated carrier whose proof the broker
      reproduces. `confirm` and a caller-supplied TTY are NOT provenance -- a
      model-controlled pseudoterminal satisfied them and persisted a grant.
    - Never substitutes a historical packet path, base commit, URL, staging
      hash or staged-entry count (T-2027 P0-03): an unauthenticated source is
      RELEASE_PROPOSAL_UNAVAILABLE, never an apparently valid approval.
    """
    import sys

    root = Path(root).resolve()

    resolved_packet_path: Path | None = None
    if packet_path:
        p = Path(packet_path)
        resolved_packet_path = p if p.is_absolute() else (root / p).resolve()

    if resolved_packet_path is None:
        # T-2027 P0-03: the historical packet is no longer a DEFAULT source for
        # a new protected transaction. It is used only when the operator names
        # it, because a frozen cohort's identities must never authorise a
        # different cohort's release.
        transaction = build_release_transaction(
            root,
            remote=remote,
            branch=branch,
            base_commit=base_commit,
            reviewed_scope=reviewed_scope,
        )
    else:
        transaction = build_release_transaction(
            root,
            packet_path=resolved_packet_path,
            remote=remote,
            branch=branch,
            base_commit=base_commit,
            reviewed_scope=reviewed_scope,
        )

    if not transaction.get("ok"):
        refusal = {key: value for key, value in transaction.items() if key != "ok"}
        refusal["ok"] = False
        refusal["mutated"] = False
        return refusal

    presentation = {
        "operation": CANONICAL_OPERATION,
        "target_destination": (
            f"{transaction['target_remote']}/{transaction['target_branch']} "
            f"({transaction['target_url']})"
        ),
        "target_remote": transaction["target_remote"],
        "target_branch": transaction["target_branch"],
        "target_url": transaction["target_url"],
        "base_commit": transaction["base_commit"],
        "reviewed_files_count": len(transaction["reviewed_scope"]),
        "reviewed_files": transaction["reviewed_scope"],
        "protected_staging_hash": transaction["protected_staging_hash"],
        "protected_paths": (
            f"{transaction['staged_entry_count']} staged paths in primary shared index"
        ),
        "verification_gate": "python tools/core_unit.py run",
        "standing": standing,
        "max_releases": (
            (DEFAULT_STANDING_MAX_RELEASES if max_releases is None else max_releases)
            if standing
            else 1
        ),
        "no_force": True,
        "packet_source": transaction["packet_source"],
        "remote_tip": transaction["remote_tip"],
    }

    if stdin_isatty is None:
        stdin_isatty = sys.stdin.isatty() if hasattr(sys.stdin, "isatty") else False

    is_operator, rejection = _operator_provenance(
        root,
        provenance=provenance,
        operator_origin=operator_origin,
        operator_operation=operator_operation,
        explicit_verification=_operator_verified,
        transaction=transaction,
    )
    # `confirm` is still required: it is the "yes, I mean it" keystroke, but it
    # is not evidence of who pressed it.
    if is_operator and not confirm:
        is_operator = False
        rejection = "this approval was not confirmed"

    if not is_operator:
        return {
            "ok": False,
            "code": "REFUSED_SYNTHETIC_APPROVAL",
            "detail": (
                "Operator approval requires genuine human confirmation. "
                "Automated model shell invocations cannot synthesize operator authority. "
                + (f"({rejection})" if rejection else "")
            ),
            "remediation": (
                "Approve through the authenticated host surface, or run "
                "`saipen release approve --confirm` in your own terminal."
            ),
            "presentation": presentation,
            "mutated": False,
        }

    grant = convert_decision_request_to_capsule(
        {"ancestry": {}},
        root,
        standing=standing,
        max_releases=max_releases,
        expiry_hours=expiry_hours,
        operator_intent=operator_intent or transaction["operator_intent"],
        transaction=transaction,
    )

    mismatch = transaction_consistency_problem(transaction, grant)
    if mismatch is not None:
        # The last line of defence: never persist a grant that differs from
        # what the operator was shown.
        return {
            "ok": False,
            "code": "RELEASE_TRANSACTION_MISMATCH",
            "detail": (
                f"the granted transaction differs from the displayed one in {mismatch!r}; "
                "nothing was authorized"
            ),
            "mismatch_field": mismatch,
            "presentation": presentation,
            "mutated": False,
        }

    grant_path = persist_grant(root, grant)

    return {
        "ok": True,
        "code": "RELEASE_AUTHORIZED",
        "grant_id": grant["grant_id"],
        "target_remote": grant["target_remote"],
        "target_branch": grant["target_branch"],
        "base_commit": grant["base_commit"],
        "standing": grant["standing"],
        "max_releases": grant["max_releases"],
        "expires_at": grant["expires_at"],
        "grant_path": str(grant_path),
        "detail": f"Release successfully authorized with grant {grant['grant_id'][:16]}",
        "presentation": presentation,
    }
