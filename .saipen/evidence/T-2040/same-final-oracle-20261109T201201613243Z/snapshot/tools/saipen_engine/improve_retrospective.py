"""Append-only Core reconciliation of sealed Improve history (T-1803).

Original manifests, reports and SWEEP files remain immutable. The successor
is not a new audit, an operator capsule, or a claim that a draft completed.
The existing admission snapshot and atomic-file journal own every mutation.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import improve

from .paths import project_lineage_identity
from .safeid import prove_inside

DIRECTORY = Path(".saipen/improve-reconciliation")
SCHEMA_VERSION = 1
MAX_RECORD_BYTES = 8 * 1024 * 1024
MAX_HISTORY_FILES = 512
MAX_HISTORY_BYTES = 64 * 1024 * 1024
_ZERO = "0" * 64


def _fail(message: str, code: str = "VALIDATION_FAILED") -> None:
    error = improve.ImproveError(message)
    error.code = code
    raise error


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _native_hash(raw: bytes) -> str:
    from .journal import hash_bytes

    return hash_bytes(raw)


def record_path(cycle: Path) -> Path:
    root = improve._project_root_of(cycle)
    name = improve._validate_safe_id(cycle.name, "cycle_id")
    path = root / DIRECTORY / (name + ".jsonl")
    _prove_owned(root, path)
    return path


def _prove_owned(root: Path, path: Path) -> None:
    # Improve's older wrapper intentionally confines ordinary writers to
    # .saipen/improve. The successor uses the same containment primitive,
    # with its own explicit project-owned namespace, never a relaxed wrapper.
    try:
        prove_inside(path, root, kind="retrospective evidence")
    except ValueError as exc:
        _fail("retrospective evidence must remain owned by the project: " + str(exc))


def _owned_bytes(root: Path, path: Path, *, optional: bool = False) -> bytes | None:
    _prove_owned(root, path)
    if path.is_symlink():
        _fail("historical evidence must be an owned regular file")
    try:
        if not path.is_file():
            if optional and not path.exists():
                return None
            _fail("historical evidence file is missing or not regular")
        if path.stat().st_size > MAX_RECORD_BYTES:
            _fail("historical evidence exceeds the bounded file limit")
        return path.read_bytes()
    except OSError as exc:
        _fail(f"historical evidence is unavailable: {type(exc).__name__}")


def _snapshot(cycle: Path) -> dict:
    cycle = Path(cycle).resolve()
    root = improve._project_root_of(cycle)
    manifest = improve.load_valid_manifest(
        cycle, "retrospective reconciliation", improve.TERMINAL_CYCLE_STATUSES
    )
    if not manifest.strict:
        _fail("retrospective reconciliation refuses legacy sealed history")
    files = {}
    total = 0
    for path in sorted(cycle.rglob("*")):
        if path.is_symlink():
            _fail("historical cycle contains an unowned link")
        if not path.is_file():
            continue
        raw = _owned_bytes(root, path)
        total += len(raw)
        files[path.relative_to(root).as_posix()] = _sha(raw)
        if len(files) > MAX_HISTORY_FILES or total > MAX_HISTORY_BYTES:
            _fail("historical cycle exceeds the bounded evidence limit")
    sweep_path = cycle / "SWEEP.md"
    sweep_raw = _owned_bytes(root, sweep_path, optional=True)
    files[sweep_path.relative_to(root).as_posix()] = (
        _sha(sweep_raw) if sweep_raw is not None else ""
    )
    sweep = sweep_raw.decode("utf-8-sig") if sweep_raw is not None else ""
    errors = improve.validate_sweep(sweep)
    if errors:
        _fail("historical SWEEP binding is invalid: " + "; ".join(errors[:3]))
    seats = []
    findings = {}
    for block in improve._seat_blocks(manifest.text):
        seat = improve._validate_safe_id(improve._field(block, "seat_id"), "seat_id")
        report_name = improve._field(block, "report_path")
        report = cycle / seat / report_name
        raw = _owned_bytes(root, report, optional=True)
        availability = improve._field(block, "availability") or "expected"
        if raw is None and availability == "expected":
            _fail(f"historical expected seat {seat} has no report evidence")
        text = raw.decode("utf-8-sig") if raw is not None else ""
        parsed = improve.parse_report(text)
        errors = list(parsed.errors) + improve.validate_report_target(text)
        if errors:
            _fail(f"historical report {seat} is invalid: " + "; ".join(errors[:3]))
        keys = []
        for finding in parsed.findings:
            if finding.run is None or not all((finding.expected, finding.actual, finding.evidence)):
                _fail(f"historical finding in {seat} lacks its exact RUN or evidence triple")
            key = f"{seat}/{report_name}#{finding.ref()}"
            if key in findings:
                _fail("historical report repeats an ambiguous composite finding identity")
            findings[key] = {
                "seat_id": seat,
                "report": f"{seat}/{report_name}",
                "finding_ref": finding.ref(),
                "severity": finding.severity,
                "class": finding.cls,
                "expected": finding.expected,
                "actual": finding.actual,
                "evidence": finding.evidence,
            }
            keys.append(key)
        seats.append(
            {
                "seat_id": seat,
                "role": improve._field(block, "role"),
                "report_path": report_name,
                "report_status": parsed.header.get("report_status", ""),
                "availability": availability,
                "has_content": bool(text and not improve._un_audited_report(text)),
                "retire_reason": improve._field(block, "retire_reason"),
                "findings": keys,
            }
        )
    original = {}
    for record in improve._sweep_records(sweep):
        matching = [
            key
            for key, item in findings.items()
            if item["finding_ref"] == record.finding_ref
            and record.report
            in improve._report_ledger_keys(
                manifest.text, item["seat_id"], item["report"].split("/", 1)[1]
            )
        ]
        if len(matching) != 1 or matching[0] in original:
            _fail("historical SWEEP has a missing, duplicate or ambiguous finding binding")
        original[matching[0]] = asdict(record)
    return {
        "root": root,
        "cycle": cycle,
        "manifest": manifest,
        "lineage": project_lineage_identity(root),
        "history": files,
        "seats": seats,
        "findings": findings,
        "original": original,
    }


def _header(snapshot: dict) -> dict:
    return {
        "kind": "improve_retrospective",
        "schema_version": SCHEMA_VERSION,
        "cycle_id": snapshot["cycle"].name,
        "project_lineage": snapshot["lineage"],
        "original_history": snapshot["history"],
    }


def _proof(root: Path, reference: str) -> tuple[str, dict[str, str]]:
    if not isinstance(reference, str) or reference in ("", "-") or "://" in reference:
        _fail("retrospective verification evidence must name an owned file")
    name, separator, fragment = reference.partition("#")
    path = Path(name)
    if ".." in path.parts:
        _fail("retrospective verification evidence must stay owned by the project")
    path = path if path.is_absolute() else root / path
    raw = _owned_bytes(root, path)
    relative = path.resolve().relative_to(root.resolve()).as_posix()
    if any(char.isspace() for char in relative):
        _fail("verification evidence must have a portable token identity")
    return relative + (separator + fragment if separator else ""), {relative: _sha(raw)}


def _native_receipt(snapshot: dict, operation: str, prefix: bytes, actor: str) -> None:
    from .journal import RETROSPECTIVE_POLICY, Journal, decode_operation_record

    journal = Journal(snapshot["root"], operation)
    decoded = decode_operation_record(snapshot["root"], journal.dir)
    if not decoded.get("ok"):
        _fail("retrospective native writer receipt is absent or invalid")
    record = decoded["record"]
    relative = record_path(snapshot["cycle"]).relative_to(snapshot["root"]).as_posix()
    targets = [target for target in record.get("targets", []) if target.get("path") == relative]
    if (
        record.get("status") != "COMMITTED"
        or record.get("verification_policy") != RETROSPECTIVE_POLICY
        or record.get("operation") != "retrospective"
        or record.get("agent") != actor
        or len(targets) != 1
        or targets[0].get("role") != "coverage"
        or targets[0].get("after_hash") != _native_hash(prefix)
    ):
        _fail("retrospective native writer receipt does not bind this committed prefix")


def _read(
    snapshot: dict, *, supplied: bytes | None = None, allowed_operation: str | None = None
) -> dict:
    path = record_path(snapshot["cycle"])
    raw = supplied if supplied is not None else _owned_bytes(snapshot["root"], path, optional=True)
    if raw is None:
        return {"raw": b"", "events": [], "effective": dict(snapshot["original"]), "retired": {}}
    if not raw.endswith(b"\n") or len(raw) > MAX_RECORD_BYTES:
        _fail("retrospective record is truncated or beyond its bounded limit")
    try:
        lines = raw.splitlines(keepends=True)
        header = json.loads(lines[0])
        if header != _header(snapshot):
            _fail("retrospective lineage/original history binding changed or is stale")
        effective = dict(snapshot["original"])
        retired = {}
        events = []
        previous = _sha(_json(header).encode("utf-8"))
        groups = {}
        prefix = lines[0]
        for number, line in enumerate(lines[1:], 1):
            event = json.loads(line)
            if not isinstance(event, dict):
                _fail("retrospective event must be a JSON object")
            body = {key: value for key, value in event.items() if key != "sha256"}
            if (
                event.get("sequence") != number
                or event.get("previous") != previous
                or event.get("sha256") != _sha(_json(body).encode("utf-8"))
            ):
                _fail("retrospective append-only hash chain is invalid")
            operation = event.get("operation_id")
            if not isinstance(operation, str) or not operation.startswith("retrospective-"):
                _fail("retrospective event has no native writer identity")
            if operation in groups and events[-1]["operation_id"] != operation:
                _fail("retrospective operation prefix is not contiguous")
            if event.get("kind") == "disposition":
                record = event["record"]
                key = record["report"] + "#" + record["finding_ref"]
                if key not in snapshot["findings"]:
                    _fail("retrospective disposition names a fictional finding")
                if improve.validate_sweep(
                    "# SWEEP\n" + improve.SweepRecord(**record).render() + "\n"
                ):
                    _fail("retrospective disposition violates the canonical SWEEP grammar")
                if record["disposition"] == "CONFIRMED" or record["reproduced"] not in ("y", "n"):
                    _fail(
                        "retrospective evidence cannot mint current authority "
                        "or unknown reproduction"
                    )
                old = effective.get(key)
                if old is not None and not event.get("amends"):
                    _fail("retrospective record repeats a committed disposition")
                if event.get("amends") and event["amends"] != _sha(_json(old).encode("utf-8")):
                    _fail("retrospective correction has a stale prior-disposition binding")
                evidence = event.get("evidence", {})
                if not isinstance(evidence, dict):
                    _fail("retrospective evidence must be a JSON object")
                if old is not None:
                    same_authority = all(
                        old[name] == record[name] for name in ("disposition", "ticket", "report")
                    )
                    resolves_pending = (
                        old["disposition"] == "NEEDS_EXTERNAL_EVIDENCE"
                        and old["ticket"] == record["ticket"]
                        and bool(evidence)
                    )
                    if not (same_authority or resolves_pending):
                        _fail("retrospective correction changes committed final authority")
                if record["disposition"] != "NEEDS_EXTERNAL_EVIDENCE" and not evidence:
                    _fail("resolved retrospective disposition has no verification evidence")
                if evidence:
                    canonical_ref, bound_proof = _proof(snapshot["root"], record["verification"])
                    if canonical_ref != record["verification"] or bound_proof != evidence:
                        _fail(
                            "retrospective verification evidence does not bind "
                            "its declared reference"
                        )
                for name, digest in evidence.items():
                    actual = _owned_bytes(snapshot["root"], snapshot["root"] / name)
                    if _sha(actual) != digest:
                        _fail("retrospective verification evidence binding changed")
                effective[key] = record
            elif event.get("kind") == "retirement":
                seat = event["seat_id"]
                if seat in retired or not any(
                    item["seat_id"] == seat for item in snapshot["seats"]
                ):
                    _fail("retrospective seat retirement is duplicated or fictional")
                reason = event["reason"]
                original_seat = next(item for item in snapshot["seats"] if item["seat_id"] == seat)
                if reason not in ("EMPTY_DRAFT", "BLOCKED_EXTERNAL", "HISTORICAL_ADJUDICATED"):
                    _fail("retrospective retirement has an unknown reason")
                if reason == "EMPTY_DRAFT" and original_seat["has_content"]:
                    _fail("retrospective retirement cannot hide committed audit evidence as empty")
                unresolved = [
                    key
                    for key in original_seat["findings"]
                    if key not in effective
                    or effective[key]["disposition"] == "NEEDS_EXTERNAL_EVIDENCE"
                ]
                if unresolved and reason != "BLOCKED_EXTERNAL":
                    _fail("retrospective retirement cannot hide unresolved findings")
                retired[seat] = reason
            elif event.get("kind") == "reconcile":
                if event.get("outcome") not in ("COMPLETE", "SUPERSEDED", "BLOCKED_EXTERNAL"):
                    _fail("retrospective reconciliation uses an unknown lifecycle class")
                if any(
                    key not in effective
                    or effective[key]["disposition"] == "NEEDS_EXTERNAL_EVIDENCE"
                    for key in snapshot["findings"]
                ):
                    _fail("retrospective reconciliation cannot seal unresolved findings")
                expected = (
                    "BLOCKED_EXTERNAL"
                    if "BLOCKED_EXTERNAL" in retired.values()
                    else "SUPERSEDED"
                    if retired
                    else "COMPLETE"
                )
                if event["outcome"] != expected:
                    _fail(
                        "retrospective reconciliation outcome contradicts "
                        "the preserved seat evidence"
                    )
            else:
                _fail("retrospective record has an unknown event kind")
            previous = event["sha256"]
            events.append(event)
            prefix += line
            groups[operation] = (prefix, event.get("actor", ""))
        if not events:
            _fail("retrospective record contains no committed correction evidence")
        for operation, (committed_prefix, actor) in groups.items():
            if operation != allowed_operation:
                _native_receipt(snapshot, operation, committed_prefix, actor)
        return {"raw": raw, "events": events, "effective": effective, "retired": retired}
    except (KeyError, TypeError, ValueError, UnicodeError) as exc:
        if isinstance(exc, improve.ImproveError):
            raise
        _fail("retrospective record schema is invalid")


def _view(snapshot: dict, ledger: dict) -> dict:
    pending = []
    for key, finding in snapshot["findings"].items():
        record = ledger["effective"].get(key)
        if record is None or record["disposition"] == "NEEDS_EXTERNAL_EVIDENCE":
            pending.append({**finding, "disposition": record["disposition"] if record else None})
    blocked = any(item["disposition"] == "NEEDS_EXTERNAL_EVIDENCE" for item in pending)
    pending_seats = {item["seat_id"] for item in pending}
    blocked = blocked or any(
        reason == "BLOCKED_EXTERNAL" and seat in pending_seats
        for seat, reason in ledger["retired"].items()
    )
    sealed = bool(ledger["events"] and ledger["events"][-1]["kind"] == "reconcile" and not pending)
    needs_reconcile = bool(ledger["events"] and not sealed and not pending and not blocked)
    next_action = (
        None
        if blocked
        else (
            f"saipen improve sweep-queue {snapshot['cycle'].name}"
            if pending
            else f"saipen improve reconcile {snapshot['cycle'].name}"
            if needs_reconcile
            else None
        )
    )
    return {
        "retrospective": True,
        "cycle_id": snapshot["cycle"].name,
        "status": snapshot["manifest"].status,
        "seats": snapshot["seats"],
        "pending_findings": pending,
        "pending_findings_known": True,
        "blocked": blocked,
        "stale": bool((pending or needs_reconcile) and not blocked),
        "settled": not pending and not needs_reconcile and not blocked,
        "canonical_next_command": next_action,
        "reconciliation": {
            "record": record_path(snapshot["cycle"]).relative_to(snapshot["root"]).as_posix(),
            "events": len(ledger["events"]),
            "sealed": sealed,
            "outcome": ledger["events"][-1].get("outcome") if sealed else None,
        },
    }


def inspect_archive(cycle: Path) -> dict:
    """Read-only all-seat history projection; unavailable integrity is blocked."""
    try:
        snapshot = _snapshot(cycle)
        return _view(snapshot, _read(snapshot))
    except (improve.ImproveError, OSError, UnicodeError) as exc:
        return {
            "retrospective": True,
            "cycle_id": Path(cycle).name,
            "blocked": True,
            "stale": False,
            "settled": False,
            "pending_findings": [],
            "pending_findings_known": False,
            "detail": str(exc),
            "canonical_next_command": None,
        }


def _admit(snapshot: dict, actor: str | None = None) -> tuple[str, dict[str, str]]:
    from .admission import protocol_snapshot
    from .capability import may_mutate, negotiate_capability

    if not may_mutate(negotiate_capability()):
        _fail("retrospective mutation has no live write admission", "CAPABILITY_DENIED")
    root = snapshot["root"]
    relative = record_path(snapshot["cycle"]).relative_to(root).as_posix()
    observed = {
        (".saipen/" + name): _owned_bytes(root, root / ".saipen" / name)
        for name in ("STATE.md", "BOARD.md", "LOG.md", "IDENTITY.md")
    }
    admission = protocol_snapshot(root, actor=actor, proposed_targets=[relative])
    if admission.get("block"):
        _fail(str(admission["block"]) + ": " + admission.get("detail", ""), admission["block"])
    if not snapshot["lineage"]:
        _fail("retrospective mutation requires a canonical project lineage")
    acting = actor or admission["state"].get("agent")
    dependencies = {}
    for name, expected in snapshot["history"].items():
        raw = _owned_bytes(root, root / name, optional=True)
        if (_sha(raw) if raw is not None else "") != expected:
            _fail("historical read dependency changed before planning", "STALE_STATE")
        dependencies[name] = _native_hash(raw) if raw is not None else ""
    for name, raw in observed.items():
        if _owned_bytes(root, root / name) != raw:
            _fail("admission checkpoint changed before planning", "STALE_STATE")
        dependencies[name] = _native_hash(raw)
    return acting, dependencies


def _append(snapshot: dict, ledger: dict, additions: list[dict], actor: str | None = None) -> dict:
    acting, dependencies = _admit(snapshot, actor)
    operation = "retrospective-" + uuid.uuid4().hex
    raw = ledger["raw"] or (_json(_header(snapshot)) + "\n").encode("utf-8")
    previous = (
        ledger["events"][-1]["sha256"]
        if ledger["events"]
        else _sha(_json(_header(snapshot)).encode("utf-8"))
    )
    for number, addition in enumerate(additions, len(ledger["events"]) + 1):
        event = {
            **addition,
            "sequence": number,
            "previous": previous,
            "operation_id": operation,
            "actor": acting,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        event["sha256"] = _sha(_json(event).encode("utf-8"))
        previous = event["sha256"]
        raw += (_json(event) + "\n").encode("utf-8")
    # Pre-write and recovery use the same validator. Only this operation's
    # pending journal receipt is exempt during its own semantic postcondition.
    validated = _read(snapshot, supplied=raw, allowed_operation=operation)
    for event in validated["events"]:
        for name, expected in event.get("evidence", {}).items():
            proof_bytes = _owned_bytes(snapshot["root"], snapshot["root"] / name)
            if _sha(proof_bytes) != expected:
                _fail("verification evidence changed before planning", "STALE_STATE")
            dependencies[name] = _native_hash(proof_bytes)
    result = improve._journaled_write(
        record_path(snapshot["cycle"]),
        raw.decode("utf-8"),
        "retrospective",
        base_hash=_native_hash(ledger["raw"]) if ledger["raw"] else "",
        read_preconditions=dependencies,
        op_id=operation,
        actor=acting,
        receipt_metadata={"retrospective_operation": operation},
    )
    if not result.get("ok"):
        _fail(
            "retrospective append was not committed: "
            + str(result.get("code"))
            + " -- "
            + str(result.get("message") or result.get("detail") or ""),
            result.get("code", "VALIDATION_FAILED"),
        )
    return result


def write_disposition(cycle: Path, entry: dict) -> dict:
    snapshot = _snapshot(cycle)
    ledger = _read(snapshot)
    _admit(snapshot, entry.get("actor"))
    report = str(entry.get("report", ""))
    run = str(entry.get("run", "")).removeprefix("RUN-")
    imp = str(entry.get("imp_id", ""))
    imp = imp if imp.startswith("IMP-") else "IMP-" + imp
    key = report + "#RUN-" + run + "/" + imp
    if key not in snapshot["findings"]:
        _fail("retrospective disposition names a fictional or ambiguous original finding")
    disposition = entry.get("disposition")
    if disposition not in improve.DISPOSITION or disposition == "CONFIRMED":
        _fail(
            "retrospective evidence cannot mint current CONFIRMED authority; "
            "use a fresh active audit"
        )
    verification = str(entry.get("verification", "-") or "-")
    evidence = {}
    if disposition != "NEEDS_EXTERNAL_EVIDENCE" or verification != "-":
        verification, evidence = _proof(snapshot["root"], verification)
    ticket = str(entry.get("ticket", "-") or "-")
    if disposition in ("INVALID", "ALREADY_FIXED", "NOT_REPRODUCED") and ticket != "-":
        _fail("retrospective disposition may not carry a fictional canonical ticket")
    if ticket != "-" and not improve._ticket_exists(snapshot["root"], ticket):
        _fail("retrospective disposition names a ticket that does not exist")
    fixed_by = str(entry.get("fixed_by", "-") or "-")
    if disposition == "ALREADY_FIXED" and fixed_by == "-":
        _fail("ALREADY_FIXED requires fixed-by evidence and verification")
    record = asdict(
        improve.SweepRecord(
            "RUN-" + run + "/" + imp,
            disposition,
            ticket,
            report,
            str(entry.get("reproduced", "-")),
            fixed_by,
            verification,
        )
    )
    if record["reproduced"] not in ("y", "n"):
        _fail("retrospective reproduced must use the canonical y|n vocabulary")
    old = ledger["effective"].get(key)
    if old == record:
        return {"ok": True, "code": "ALREADY_APPLIED", "retrospective": True}
    correction = bool(entry.get("amend"))
    if old is not None and not correction:
        _fail("retrospective duplicate conflicts with an already committed disposition")
    if correction and old is None:
        _fail("retrospective amendment requires an existing disposition")
    if old is not None:
        authority_unchanged = all(
            old[name] == record[name] for name in ("disposition", "ticket", "report")
        )
        resolves_pending = (
            old["disposition"] == "NEEDS_EXTERNAL_EVIDENCE"
            and old["ticket"] == ticket
            and bool(evidence)
        )
        if not (authority_unchanged or resolves_pending):
            _fail("retrospective correction cannot replace committed final authority")
    event = {"kind": "disposition", "record": record, "evidence": evidence}
    if old is not None:
        event["amends"] = _sha(_json(old).encode("utf-8"))
    if entry.get("dry_run"):
        return {
            "ok": True,
            "code": "IMPROVE_SWEEP_PLAN",
            "retrospective": True,
            "planned_events": [event],
        }
    return _append(snapshot, ledger, [event], entry.get("actor"))


def reconcile_archive(cycle: Path, *, dry_run: bool = False, actor: str | None = None) -> dict:
    try:
        snapshot = _snapshot(cycle)
        ledger = _read(snapshot)
        view = _view(snapshot, ledger)
        if view["blocked"] or view["pending_findings"]:
            return {
                **view,
                "ok": False,
                "code": "VALIDATION_FAILED",
                "detail": (
                    "historical findings still require Core dispositions or external evidence"
                ),
            }
        if view["settled"]:
            return {
                **view,
                "ok": True,
                "code": "ALREADY_TERMINAL",
                "outcome": view["reconciliation"]["outcome"]
                or improve._outcome_for_status(snapshot["manifest"].status),
                "retired": [],
                "superseded": [],
            }
        additions = []
        for seat in snapshot["seats"]:
            if seat["report_status"] != "complete" and seat["seat_id"] not in ledger["retired"]:
                additions.append(
                    {
                        "kind": "retirement",
                        "seat_id": seat["seat_id"],
                        "reason": "HISTORICAL_ADJUDICATED"
                        if seat["has_content"]
                        else "EMPTY_DRAFT",
                    }
                )
        outcome = (
            "BLOCKED_EXTERNAL"
            if "BLOCKED_EXTERNAL" in ledger["retired"].values()
            else "SUPERSEDED"
            if additions or ledger["retired"]
            else "COMPLETE"
        )
        additions.append({"kind": "reconcile", "outcome": outcome})
        _admit(snapshot, actor)
        if dry_run:
            return {
                **view,
                "ok": True,
                "code": "RECONCILE_PLAN",
                "planned_outcome": outcome,
                "planned_events": additions,
            }
        written = _append(snapshot, ledger, additions, actor)
        return {
            **inspect_archive(cycle),
            "ok": True,
            "code": "RECONCILED",
            "outcome": outcome,
            "operation_id": written.get("op_id"),
            "retired": additions[:-1],
            "superseded": [],
        }
    except (improve.ImproveError, OSError, UnicodeError) as exc:
        return {
            "ok": False,
            "code": getattr(exc, "code", "VALIDATION_FAILED"),
            "retrospective": True,
            "blocked": True,
            "stale": False,
            "settled": False,
            "detail": str(exc),
            "pending_findings_known": False,
            "pending_findings": [],
            "canonical_next_command": None,
        }


def retire_archived(
    cycle: Path, seat_id: str, reason: str, *, dry_run: bool = False, actor: str | None = None
) -> dict:
    snapshot = _snapshot(cycle)
    ledger = _read(snapshot)
    _admit(snapshot, actor)
    seat = next((item for item in snapshot["seats"] if item["seat_id"] == seat_id), None)
    if seat is None:
        _fail("retrospective retirement names a fictional seat")
    if reason not in ("EMPTY_DRAFT", "BLOCKED_EXTERNAL", "HISTORICAL_ADJUDICATED"):
        _fail("retrospective retirement requires a canonical historical reason")
    if reason == "EMPTY_DRAFT" and seat["has_content"]:
        _fail("retrospective retirement cannot hide committed findings as empty")
    pending = [
        item for item in _view(snapshot, ledger)["pending_findings"] if item["seat_id"] == seat_id
    ]
    if pending and reason != "BLOCKED_EXTERNAL":
        _fail("retrospective retirement cannot hide unresolved historical findings")
    if seat_id in ledger["retired"]:
        if ledger["retired"][seat_id] != reason:
            _fail("retrospective retirement conflicts with its committed reason")
        return {"ok": True, "code": "ALREADY_APPLIED", "retrospective": True}
    event = {"kind": "retirement", "seat_id": seat_id, "reason": reason}
    if dry_run:
        return {"ok": True, "code": "RECONCILE_PLAN", "planned_events": [event]}
    return _append(snapshot, ledger, [event], actor)


def validate_record(root: Path, path: Path, *, allowed_operation: str | None = None) -> list[str]:
    """Target-aware semantic verifier shared by normal apply and recovery."""
    try:
        relative = path.relative_to(root / DIRECTORY)
        if len(relative.parts) != 1 or path.suffix != ".jsonl":
            _fail("retrospective record target is outside its canonical namespace")
        cycle = root / ".saipen/improve" / path.stem
        snapshot = _snapshot(cycle)
        _read(snapshot, allowed_operation=allowed_operation)
        return []
    except (improve.ImproveError, OSError, ValueError, UnicodeError) as exc:
        return [str(exc)]
