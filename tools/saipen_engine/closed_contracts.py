"""Bounded post-closure observations; historical closure and routing stay intact."""

from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

from . import regression_execution as execution
from .board import parse_board
from .journal import hash_bytes, semantic_receipts_for_operation_safe
from .paths import history_bound_here, prove_owned_dir_chain, prove_owned_regular

MAX_RECORDS = 4096
MAX_PATHS = 100000
MAX_TOTAL_BYTES = 256 * 1024 * 1024


def projection(observation):
    """Keep immutable manifests in their receipt, not in operational output."""
    keys = ("schema", "status", "contract_path", "verifier", "executed", "summary", "reason")
    return {
        **{key: observation[key] for key in keys if key in observation},
        "dependency_count": len(observation.get("dependencies") or {}),
    }


def _files(root, relative):
    directory = root / relative
    prove_owned_dir_chain(directory, ownership_root=root, kind="closed-contract records")
    if not directory.exists():
        return []
    result = []
    for path in directory.iterdir():
        if path.suffix == ".json":
            prove_owned_regular(path, kind="closed-contract record")
            result.append(path)
            if len(result) > MAX_RECORDS:
                raise ValueError("closed-contract record limit exceeded")
    return sorted(result)


def _journal(root, operation):
    records, errors = semantic_receipts_for_operation_safe(root, operation)
    if errors:
        raise ValueError("unavailable committed provenance: " + "; ".join(errors[:2]))
    return {item["op_id"]: item for item in records if item.get("status") == "COMMITTED"}


def _bound(root, raw, relative, value, journal, op_field):
    if not history_bound_here(value.get("project_identity"), value.get("project_lineage"), root):
        raise ValueError("foreign or unbound closed-contract evidence")
    receipt = journal.get(value.get(op_field))
    if receipt is None or not any(
        item.get("path") == relative and item.get("after_hash") == hash_bytes(raw)
        for item in receipt.get("targets", [])
    ):
        raise ValueError("closed-contract bytes do not match committed provenance")


def _records(root, work=None):
    from . import debt

    paths = _files(root, debt.REVERIFY_DIR)
    if not paths:
        return []
    journal = _journal(root, "reverify.work")
    marked_paths = {
        target.get("path")
        for receipt in journal.values()
        if (receipt.get("receipt_metadata") or {}).get("closed_contract")
        for target in receipt.get("targets", [])
    }
    result = []
    for path in reversed(paths):
        relative = path.relative_to(root).as_posix()
        raw = execution._read(root, relative)
        if relative not in marked_paths and b'"closed_contract"' not in raw:
            continue
        record = json.loads(raw.decode("utf-8"), object_pairs_hook=execution._unique)
        minted = debt._reverify_minted_work(record)
        if work is not None and minted is not None and minted != work:
            continue
        if not debt._reverify_intact(record):
            raise ValueError("invalid re-verification receipt integrity: " + path.name)
        _bound(root, raw, relative, record, journal, "journal_op_id")
        if relative in marked_paths and not record.get("closed_contract"):
            raise ValueError("committed focused observation was removed")
        if record.get("closed_contract"):
            result.append(record)
    return result


def measure(root, work, contract_path, *, dry_run=False):
    """Execute a caller-selected focused check; never replay a stored shell command."""
    root = Path(root)
    try:
        material = execution._load(root, contract_path, closed=True)
        contract = material["contract"]
        observation = {
            "schema": 1,
            "contract_path": material["contract_path"],
            "contract_sha256": execution._sha(material["contract_raw"]),
            "verifier": material["verifier"],
            "runtime": material["runtime"],
            "environment_digest": execution._sha(execution._json(material["environment"])),
            "dependencies": execution._manifest(material["context"]),
            "oracle_files": contract["oracle_files"],
            "subject_files": contract["subject_files"],
            "command": contract["command"],
            "format": contract["format"],
            "status": "NOT_RUN",
            "executed": False,
        }
        if dry_run:
            return observation
        previous = [
            item["closed_contract"] for item in _records(root, work)
            if item.get("work") == work
            and item["closed_contract"].get("contract_path") == material["contract_path"]
        ]
        baseline = next((item for item in previous if item.get("status") == "CURRENT_PASS"), None)
        if baseline and baseline.get("contract_sha256") != observation["contract_sha256"]:
            return {**observation, "status": "UNVERIFIED", "reason": "CONTRACT_CHANGED"}
        if baseline and any(
            baseline["dependencies"].get(path) != observation["dependencies"].get(path)
            for path in contract["oracle_files"]
        ):
            return {**observation, "status": "UNVERIFIED", "reason": "ORACLE_CHANGED"}
        result = execution._measure(material, "closed-current", material["current"])
        refreshed = execution._load(root, contract_path, closed=True)
        if (
            execution._manifest(refreshed["context"]) != observation["dependencies"]
            or refreshed["verifier"] != material["verifier"]
            or refreshed["contract_raw"] != material["contract_raw"]
        ):
            raise ValueError("closed-contract inputs moved during execution")
        passed = result["exit_code"] == 0 and result["failed"] == 0
        failed = result["exit_code"] == 1 and result["failed"] > 0
        # Fresh execution can establish current behavior after an environment
        # refresh; historical regression attribution needs the same full verifier.
        prior_pass = baseline is not None and baseline.get("verifier") == observation["verifier"]
        changed_subject = prior_pass and baseline.get("dependencies") != observation["dependencies"]
        status = (
            "CURRENT_PASS" if passed else
            "CURRENT_REGRESSION" if failed and changed_subject else
            "CURRENT_CHECK_FAILED" if failed else "UNVERIFIED"
        )
        return {
            **observation, "status": status, "executed": True,
            "summary": {key: result[key] for key in ("ran", "failed", "skipped", "exit_code")},
            "output_digest": execution._sha((result["stdout"] + result["stderr"]).encode()),
        }
    except (
        OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError
    ) as exc:
        return {"schema": 1, "status": "UNVERIFIED", "executed": False, "reason": str(exc),
                "contract_path": str(contract_path)}


def inspect(root, work=None, *, limit=50, offset=0, include_scopes=True):
    """Read exact dependencies once per call, paginate rows, and never gate Work."""
    started = time.perf_counter()
    root = Path(root)
    rows = []
    errors = []
    cache = {}
    metadata = {}
    contexts = {}
    attempted = set()
    runtimes = {}
    total_bytes = 0

    def mark_path(relative):
        if relative not in attempted and len(attempted) >= MAX_PATHS:
            raise ValueError("closed-contract path limit exceeded")
        attempted.add(relative)

    def current(relative, *, retain=False):
        nonlocal total_bytes
        if relative not in cache or (retain and relative not in metadata):
            mark_path(relative)
            remaining = MAX_TOTAL_BYTES - total_bytes
            if remaining <= 0:
                raise ValueError("closed-contract byte limit exceeded")
            try:
                try:
                    raw = execution._read(root, relative,
                                          max_bytes=min(execution.MAX_BYTES, remaining))
                except ValueError as exc:
                    raise ValueError(
                        "closed-contract byte limit or unsafe input: " + str(exc)
                    ) from exc
                total_bytes += len(raw)
                if total_bytes > MAX_TOTAL_BYTES:
                    raise ValueError("closed-contract byte limit exceeded")
                cache[relative] = execution._sha(raw)
                if retain:
                    metadata[relative] = raw
            except FileNotFoundError:
                cache[relative] = None
                if retain:
                    metadata[relative] = None
        return cache[relative]

    try:
        if work is not None and not re.fullmatch(r"T-\d+", work):
            raise ValueError("invalid Work id")
        if type(limit) is not int or type(offset) is not int or not 0 <= limit <= 100 or offset < 0:
            raise ValueError("limit must be 0..100 and offset nonnegative")
        board = parse_board(execution._read(root, ".saipen/BOARD.md").decode("utf-8-sig"))
        if board.get("errors"):
            raise ValueError("BOARD is not safely readable")
        tickets = board["tickets"]
        seen = set()
        bound_work = set()
        for record in _records(root, work):
            ticket_id = record.get("work")
            if (work and work != ticket_id) or (
                tickets.get(ticket_id, {}).get("section") != "## DONE"
            ):
                continue
            contract = record["closed_contract"]
            key = (ticket_id, contract.get("contract_path"))
            if key in seen:
                continue
            seen.add(key)
            bound_work.add(ticket_id)
            dependencies = contract.get("dependencies")
            if not isinstance(dependencies, dict) or not dependencies:
                rows.append({"work": ticket_id, "status": "UNVERIFIED",
                             "reason": contract.get("reason", "DEPENDENCY_BINDING_MISSING")})
                continue
            contract_current = (
                current(contract["contract_path"], retain=True) == contract.get("contract_sha256")
            )
            if contract_current:
                declared = json.loads(metadata[contract["contract_path"]].decode("utf-8"),
                                      object_pairs_hook=execution._unique)
                paths = execution._paths(declared["context"])
                required = (*contract["oracle_files"], *contract["subject_files"])
                context_key = (tuple(paths), tuple(required))
                if context_key not in contexts:
                    contexts[context_key] = execution._context(
                        root, paths, allow_missing=True, required=required,
                        reader=current, on_path=mark_path,
                    )
                actual = contexts[context_key]
                changed = [path for path in sorted(dependencies.keys() | actual.keys())
                           if path not in dependencies or path not in actual
                           or dependencies[path] != actual[path]]
            else:
                changed = [path for path, expected in dependencies.items()
                           if current(path) != expected]
            status = "REGRESSION_SUSPECT" if changed else contract["status"]
            reason = ("DEPENDENCIES_CHANGED" if changed else
                      contract.get("reason", "BOUND_DEPENDENCIES"))
            if any(path in changed for path in contract["oracle_files"]):
                status, reason = "UNVERIFIED", "ORACLE_CHANGED"
            runtime_key = (contract.get("runtime") or {}).get("path")
            if not isinstance(runtime_key, str) or not runtime_key:
                raise ValueError("recorded verifier runtime is unavailable")
            if runtime_key not in runtimes:
                runtime, _, environment = execution._runtime(
                    [runtime_key, *contract["command"][1:]]
                )
                runtimes[runtime_key] = (
                    runtime, execution._sha(execution._json(environment))
                )
            runtime, environment_digest = runtimes[runtime_key]
            if runtime != contract.get("runtime"):
                status, reason = "UNVERIFIED", "RUNTIME_CHANGED"
            if environment_digest != contract.get("environment_digest"):
                status, reason = "UNVERIFIED", "ENVIRONMENT_CHANGED"
            if not contract_current:
                status, reason = "UNVERIFIED", "CONTRACT_CHANGED"
            rows.append({
                "work": ticket_id, "status": status, "changed_paths": changed,
                "receipt_id": record["receipt_id"], "contract_path": contract["contract_path"],
                "reason": reason,
                "source_receipts": tickets[ticket_id].get("fields", {}).get("source_receipts", ""),
                "active_repairs": [
                    other_id for other_id, other in tickets.items()
                    if other.get("section") != "## DONE" and ticket_id in other.get("needs", [])
                ],
            })
        if include_scopes:
            from .operations import RELEASE_SCOPE_DIR

            scopes = _files(root, RELEASE_SCOPE_DIR)
            journal = _journal(root, "scope") if scopes else {}
            for path in scopes:
                ticket_id = path.stem
                if ticket_id in bound_work or (work and work != ticket_id):
                    continue
                if tickets.get(ticket_id, {}).get("section") != "## DONE":
                    continue
                try:
                    relative = path.relative_to(root).as_posix()
                    raw = execution._read(root, relative)
                    scope = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=execution._unique)
                    _bound(root, raw, relative, scope, journal, "op_id")
                    if scope.get("ticket") != ticket_id or not isinstance(scope.get("paths"), dict):
                        raise ValueError("invalid scope identity or path map")
                    changed = []
                    for relative, expected in scope["paths"].items():
                        actual = current(relative)
                        if expected is not None and not re.fullmatch(
                            r"[0-9a-f]{16}|[0-9a-f]{64}", expected
                        ):
                            raise ValueError("unrecognized scope content identity")
                        if (actual is None) != (expected is None) or (
                            actual is not None and expected is not None
                            and not actual.startswith(expected)
                        ):
                            changed.append(relative)
                    rows.append({"work": ticket_id,
                                 "status": "REGRESSION_SUSPECT" if changed else "UNCHANGED_SCOPE",
                                 "changed_paths": changed,
                                 "reason": "SCOPE_ONLY_NO_BEHAVIORAL_PROOF"})
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    rows.append({"work": ticket_id, "status": "UNVERIFIED", "reason": str(exc)})
        if include_scopes:
            observed = {row["work"] for row in rows}
            for ticket_id, ticket in tickets.items():
                if ticket.get("section") == "## DONE" and ticket_id not in observed and (
                    work is None or ticket_id == work
                ):
                    rows.append({"work": ticket_id, "status": "UNVERIFIED",
                                 "reason": "DEPENDENCY_BINDING_MISSING"})
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        errors.append(str(exc))
    rows.sort(key=lambda row: (int(row["work"].split("-")[1]), row.get("contract_path", "")))
    counts = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return {
        "ok": not errors, "status": "UNVERIFIED" if errors else "OBSERVED",
        "advisory": True, "blocks_unrelated_work": False,
        "total": len(rows), "counts": counts, "rows": rows[offset:offset + limit],
        "has_more": len(rows) > offset + limit, "offset": offset, "limit": limit,
        "errors": errors, "paths_read": len(cache), "bytes_read": total_bytes,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
    }
