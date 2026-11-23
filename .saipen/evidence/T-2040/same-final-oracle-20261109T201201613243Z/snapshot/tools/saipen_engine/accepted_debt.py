"""Accepted legacy debt registry for immutable historical findings.

DECISION B (operator, SRC-047): a sealed historical finding -- one that cannot
be repaired without rewriting append-only history -- may be REGISTERED as
accepted legacy debt, bounded by immutable evidence, so the canonical
validator downgrades exactly that finding to a visible warning instead of a
blocking FAIL. Nothing else changes: new findings of the same rule still FAIL,
unrelated findings still FAIL, and the accepted debt stays on screen.

WHY THIS EXISTS: the `[saio]` mechanical-provenance check (T-584) legitimately
flags hand-written structural events from the pre-mechanization window; for
some projects those exact events are sealed (retroactively marking them would
forge provenance -- E-965/E-967), and the only prior honoring mechanism was a
project-local stdout shim the engine receipt path never consulted. This module
is the canonical, project-scoped, journaled replacement for that shim.

NARROW BINDING (fail-closed on every condition):
  * record is lineage-bound -- it never crosses project lineages, and it
    travels with the history it accepts when the project is copied or moved
    (T-1516; the checkout path binds only a lineage-less project);
  * record binds ONE rule and the EXACT set of missing event ids -- an extra
    new event changes the set and the acceptance no longer matches;
  * record binds each event's source FILE and the SHA-256 of that event's
    exact line bytes -- any mutation of accepted history invalidates it;
  * record binds CHECK_VERSION -- a semantic change to the consuming check
    forces conscious re-registration;
  * the record itself carries an integrity digest over its own body.

T-1851: syntax/integrity is not permission. New registrations require an
authority-only native Decision B Source and an exact reservation at the existing
separated event owner. Readers classify unproved historical origin UNKNOWN and
retain FAIL. Preview and scope live in debt_authority; native reservations bind
the operation independently of model-writable journals. No new signer is used.

Storage: `<project>/.saipen/recovery/conformance/accepted_debt/AD-NNNNNN.json`,
written through the canonical journal (run_mutation) only -- never by hand.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .paths import history_bound_here, project_lineage_identity
from .paths import project_identity as _project_identity

ACCEPTED_DEBT_DIR = ".saipen/recovery/conformance/accepted_debt"
ACCEPTED_DEBT_ID_RE = re.compile(r"\AAD-(\d{6})\Z")
#: Canonical event spelling is `E-{int}` exactly as the validator renders it:
#: a ledger `[E-003]` and an operator input `E-003` both canonicalize to
#: `E-3`, which is what the `[saio]` FAIL message, the findings subject and
#: this registry all compare.
EVENT_INPUT_RE = re.compile(r"\AE-0*(\d+)\Z")
AUTHORITY_RE = re.compile(r"\A(?:SRC-\d+|E-\d+|lineage-[0-9a-f]{32})\Z")

SCHEMA_VERSION = 1
#: The `[saio]` missing-set semantics this registry binds to. Bump when the
#: consuming check in tools/validate.py changes meaning; records then refuse
#: comparison until consciously re-registered under the new check.
CHECK_VERSION = 1
RULE_ID = "log_provenance_marker"


def canonical_event_id(event: str) -> str | None:
    """Canonical `E-{int}` spelling, or None when the input is not E-###."""
    found = EVENT_INPUT_RE.match(str(event or "").strip())
    return f"E-{int(found.group(1))}" if found else None


class AcceptedDebtRefusal(Exception):
    """Structured, fail-closed refusal carrying its protocol code."""

    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _line_sha256(raw_line: str) -> str:
    return hashlib.sha256(raw_line.encode("utf-8")).hexdigest()


def _integrity_digest(record_body: dict) -> str:
    canonical = json.dumps(record_body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _record_dir(root: Path) -> Path:
    return Path(root) / ACCEPTED_DEBT_DIR


def _record_files(root: Path) -> list[Path]:
    directory = _record_dir(root)
    if not directory.is_dir():
        return []
    return sorted(
        p for p in directory.glob("AD-*.json") if p.is_file() and ACCEPTED_DEBT_ID_RE.match(p.stem)
    )


def next_record_id(root: Path) -> str:
    numbers = [
        int(ACCEPTED_DEBT_ID_RE.match(p.stem).group(1)) for p in _record_files(Path(root))
    ]
    return f"AD-{(max(numbers) + 1) if numbers else 1:06d}"


def _read_lines(path: Path) -> list[str]:
    """Replicate tools/validate.py `read_doc` line normalization exactly.

    The registration tool and the validator MUST hash the same bytes: both
    decode BOM/UTF-16 the same way and normalize newlines before `splitlines`,
    so an accepted line hash can never depend on which side computed it.
    """
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise AcceptedDebtRefusal("VALIDATION_FAILED", f"unreadable log segment {path}: {exc}")
    for bom, enc in (
        (b"\xff\xfe\x00\x00", "utf-32-le"),
        (b"\x00\x00\xfe\xff", "utf-32-be"),
        (b"\xef\xbb\xbf", "utf-8-sig"),
        (b"\xff\xfe", "utf-16-le"),
        (b"\xfe\xff", "utf-16-be"),
    ):
        if raw.startswith(bom):
            text = raw[len(bom) :].decode(enc, errors="replace")
            break
    else:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = raw.decode("cp1251")
            except UnicodeDecodeError:
                text = raw.decode("utf-8", errors="replace")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.splitlines()


def load_record(root: Path | str, ref: str) -> dict:
    """Decode ONE accepted-debt record fail-closed (identity + integrity)."""
    root = Path(root)
    if not ACCEPTED_DEBT_ID_RE.match(ref or ""):
        raise AcceptedDebtRefusal("VALIDATION_FAILED", f"invalid accepted-debt id {ref!r}")
    path = _record_dir(root) / f"{ref}.json"
    try:
        raw = path.read_bytes()
    except FileNotFoundError as exc:
        raise AcceptedDebtRefusal("ACCEPTED_DEBT_MISSING", f"{ref} does not exist") from exc
    except OSError as exc:
        raise AcceptedDebtRefusal("ACCEPTED_DEBT_CORRUPT", f"{ref} unreadable: {exc}") from exc
    try:
        record = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise AcceptedDebtRefusal(
            "ACCEPTED_DEBT_CORRUPT", f"{ref} is not valid JSON: {exc}"
        ) from exc
    if not isinstance(record, dict) or record.get("schema_version") != SCHEMA_VERSION:
        raise AcceptedDebtRefusal("ACCEPTED_DEBT_CORRUPT", f"{ref} has an unsupported schema")
    if record.get("record_id") != ref:
        raise AcceptedDebtRefusal("ACCEPTED_DEBT_CORRUPT", f"{ref} names a different record id")
    if record.get("kind") != "accepted_legacy_debt":
        raise AcceptedDebtRefusal("ACCEPTED_DEBT_CORRUPT", f"{ref} is not an accepted-debt record")
    body = {k: v for k, v in record.items() if k != "integrity_digest"}
    if _integrity_digest(body) != record.get("integrity_digest"):
        raise AcceptedDebtRefusal(
            "ACCEPTED_DEBT_CORRUPT", f"{ref} integrity digest mismatch (hand-edited or damaged)"
        )
    if record.get("project_lineage") != project_lineage_identity(root):
        raise AcceptedDebtRefusal(
            "ACCEPTED_DEBT_FOREIGN_LINEAGE",
            f"{ref} binds a foreign lineage; an acceptance never crosses project lineages",
        )
    # T-1516: the lineage owns the acceptance; the path binds a lineage-less project only.
    if not history_bound_here(record.get("project_identity"), record.get("project_lineage"), root):
        raise AcceptedDebtRefusal(
            "ACCEPTED_DEBT_FOREIGN_PROJECT",
            f"{ref} was registered for {record.get('project_identity')!r}, not this project",
        )
    if record.get("check_id") != RULE_ID or record.get("check_version") != CHECK_VERSION:
        raise AcceptedDebtRefusal(
            "ACCEPTED_DEBT_CHECK_CHANGED",
            f"{ref} was registered for check {record.get('check_id')!r} v"
            f"{record.get('check_version')!r}; current is {RULE_ID!r} v{CHECK_VERSION} -- "
            "the check semantics changed, re-register consciously",
        )
    return record


def evaluate_provenance(
    root: Path | str, missing: list[tuple[str, str, str]]
) -> dict:
    """Decide whether the EXACT missing set is registered accepted legacy debt.

    `missing` = [(event_id, segment_relpath, raw_line), ...] exactly as the
    `[saio]` check found them. Returns ``{"accepted": bool, "record_id": ...,
    "reason": ...}``. Fail-closed: an absent registry is ordinary (accepted
    False, empty reason); any unreadable/corrupt/foreign/mismatched record or
    a set/line/file mismatch keeps the finding blocking.
    """
    root = Path(root)
    files = _record_files(root)
    if not files:
        return {"accepted": False, "record_id": None, "reason": ""}
    wanted = {event_id for event_id, _file, _line in missing}
    by_event = {event_id: (file, line) for event_id, file, line in missing}
    if len(by_event) != len(wanted):
        return {
            "accepted": False,
            "record_id": None,
            "reason": "duplicate event ids in missing set",
        }
    unknown = None
    for path in files:
        try:
            record = load_record(root, path.stem)
        except AcceptedDebtRefusal as refusal:
            # A damaged registry record must never half-accept: refuse this
            # record (the validator then keeps its ordinary FAIL).
            return {"accepted": False, "record_id": None, "reason": refusal.detail}
        accepted_events = record.get("accepted_missing_events")
        if not isinstance(accepted_events, list) or not all(
            isinstance(item, str) for item in accepted_events
        ):
            return {
                "accepted": False,
                "record_id": None,
                "reason": f"{path.stem} accepted_missing_events malformed",
            }
        if set(accepted_events) != wanted or len(accepted_events) != len(wanted):
            continue
        from . import debt_authority

        authority = debt_authority.status(root, record)
        if authority["authority_status"] != "KNOWN":
            unknown = authority["authority_reason"]
            continue
        evidence = record.get("evidence")
        if not isinstance(evidence, list):
            return {
                "accepted": False,
                "record_id": None,
                "reason": f"{path.stem} evidence malformed",
            }
        ok = True
        seen: set[str] = set()
        for item in evidence:
            if not isinstance(item, dict):
                ok = False
                break
            event_id = item.get("event")
            file = item.get("file")
            line_sha = item.get("line_sha256")
            if (
                not isinstance(event_id, str)
                or event_id not in by_event
                or event_id in seen
                or not isinstance(file, str)
                or not isinstance(line_sha, str)
            ):
                ok = False
                break
            seen.add(event_id)
            live_file, live_line = by_event[event_id]
            if file != live_file or _line_sha256(live_line) != line_sha:
                ok = False
                break
        if ok and seen == wanted:
            return {
                "accepted": True,
                "record_id": path.stem,
                "reason": "exact missing set and line evidence verified; authority KNOWN",
                "authority_status": "KNOWN",
            }
        return {
            "accepted": False,
            "record_id": None,
            "reason": f"{path.stem} does not cover the exact missing set/line evidence",
        }
    return {"accepted": False, "record_id": None,
            "reason": unknown or "no covering accepted-debt record", "authority_status": "UNKNOWN"}


def _iter_history(root: Path):
    """Yield (segment_relpath, line_no, raw_line, parsed_event) in file order.

    Walks exactly the segments the validator walks (saipen_engine.log.
    history_paths, absolute) with the shared line normalization, but records
    the ROOT-RELATIVE spelling -- that is what the validator's `[saio]`
    message and every registered evidence `file` field use.
    """
    from .log import history_paths, parse_log_line

    base = Path(root).resolve()
    for path in history_paths(Path(root)):
        if not Path(path).is_file():
            continue
        try:
            rel_str = Path(path).resolve().relative_to(base).as_posix()
        except ValueError:
            rel_str = Path(path).as_posix()
        lines = _read_lines(Path(path))
        for line_no, raw in enumerate(lines, 1):
            if not raw.strip() or raw.startswith("#"):
                continue
            parsed = parse_log_line(raw)
            if parsed is None:
                continue
            yield rel_str, line_no, raw, parsed


def _event_material(root, events):
    """Resolve eligible immutable lines once and pin their canonical carriers."""
    from .journal import hash_file_dependency, hash_tree_dependency
    from .log import history_paths

    def pins():
        return {".saipen/IDENTITY.md": hash_file_dependency(root / ".saipen/IDENTITY.md"),
                ".saipen/logs": hash_tree_dependency(root / ".saipen/logs"),
                **{p.relative_to(root.resolve()).as_posix(): hash_file_dependency(p)
                   for p in history_paths(root)}}

    before = pins()
    normalized = sorted({canonical_event_id(e) for e in events} - {None},
                        key=lambda e: int(e[2:]))
    if not normalized or any(canonical_event_id(e) is None for e in events):
        raise AcceptedDebtRefusal("VALIDATION_FAILED",
                                  "invalid or empty event set (expected E-###)")
    found, first_op = {}, None
    for file, line, raw, parsed in _iter_history(root):
        if parsed.get("op_id") and first_op is None:
            first_op = parsed["event"]
        event = f"E-{parsed['event']}"
        if event in normalized:
            if event in found:
                raise AcceptedDebtRefusal("VALIDATION_FAILED", f"ambiguous history event {event}")
            found[event] = (file, line, raw, parsed)
    absent = set(normalized) - set(found)
    if absent:
        raise AcceptedDebtRefusal(
            "VALIDATION_FAILED",
            "events not found in canonical history: " + ", ".join(sorted(absent)))
    if first_op is None:
        raise AcceptedDebtRefusal("VALIDATION_FAILED",
                                  "project history carries no provenance boundary")
    marked = [e for e in normalized if found[e][3].get("op_id")]
    if marked:
        raise AcceptedDebtRefusal("VALIDATION_FAILED", "events already carry [op:] provenance: "
                                  + ", ".join(marked))
    if any(found[e][3]["event"] < first_op for e in normalized):
        raise AcceptedDebtRefusal("VALIDATION_FAILED", "events predate the provenance boundary")
    evidence = [{"event": e, "file": found[e][0], "line_number": found[e][1],
                 "line_sha256": _line_sha256(found[e][2])} for e in normalized]
    if before != pins():
        raise AcceptedDebtRefusal("STALE_PRECONDITION",
                                  "historical carriers changed while being read")
    return normalized, evidence, before


def preview(root, events):
    """Read-only exact Decision B capsule; the host supplies a real approval."""
    from . import debt_authority

    root = Path(root).resolve()
    try:
        normalized, evidence, _pins = _event_material(root, events)
        lineage = project_lineage_identity(root)
        if not lineage:
            raise ValueError("a canonical project lineage is required")
        capsule = {"kind": debt_authority.KIND, "schema": 1, "project_lineage": lineage,
                   "check_id": RULE_ID, "check_version": CHECK_VERSION, "events": normalized,
                   "event_hashes": {e["event"]: e["line_sha256"] for e in evidence},
                   "decision": "ACCEPT_LEGACY_DEBT", "statement": "", "expires_at": ""}
        candidates = []
        for path in _record_files(root):
            record = load_record(root, path.stem)
            if (record.get("accepted_missing_events") == normalized
                    and debt_authority.status(root, record)["authority_status"] == "UNKNOWN"):
                candidates.append({"record_id": path.stem,
                                   "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        if len(candidates) > 1:
            raise ValueError("multiple unverified covering records require explicit reconciliation")
        if candidates:
            capsule["supersedes"] = candidates[0]
        return {"ok": True, "code": "PLAN", "capsule": capsule, "read_only": True,
                "authority_status": "UNKNOWN"}
    except (OSError, ValueError, TypeError, AcceptedDebtRefusal) as exc:
        return {"ok": False, "code": getattr(exc, "code", "VALIDATION_FAILED"), "detail": str(exc)}


def register(root: Path | str, *, agent: str, events: list[str],
             reason: str, authority: str) -> dict:
    """Accept only one independently witnessed, exact historical Decision B."""
    from . import debt_authority
    from .capability import may_mutate, negotiate_capability
    from .journal import hash_file_dependency, run_mutation, verify_accepted_debt

    root = Path(root).resolve()
    if not may_mutate(negotiate_capability()):
        return {"ok": False, "code": "CAPABILITY_READ_ONLY", "detail": "registration is a mutation"}
    if not str(reason or "").strip():
        return {"ok": False, "code": "VALIDATION_FAILED", "detail": "reason is required"}
    authority = str(authority or "").strip()
    if not AUTHORITY_RE.fullmatch(authority):
        return {"ok": False, "code": "VALIDATION_FAILED",
                "detail": "authority must be SRC-###, E-### or lineage-<32hex>",
                "authority_status": "UNKNOWN"}
    try:
        normalized, evidence, dependencies = _event_material(root, events)
        lineage = project_lineage_identity(root)
        if not lineage:
            raise ValueError("authority UNKNOWN: a canonical project lineage is required")
        record = {"schema_version": SCHEMA_VERSION, "kind": "accepted_legacy_debt",
                  "record_id": next_record_id(root), "created_at": _utc(), "agent": str(agent),
                  "project_identity": _project_identity(root), "project_lineage": lineage,
                  "check_id": RULE_ID, "check_version": CHECK_VERSION, "authority": authority,
                  "reason": str(reason), "accepted_missing_events": normalized,
                  "evidence": evidence}
        auth = debt_authority.source_shape(root, record, dependencies)
        wanted = set(normalized)
        for path in _record_files(root):
            existing = load_record(root, path.stem)
            prior = set(existing.get("accepted_missing_events") or [])
            overlap = wanted & prior
            if not overlap:
                continue
            if prior == wanted:
                prior_authority = debt_authority.status(root, existing)
                if (prior_authority["authority_status"] == "KNOWN"
                        and existing.get("authority") == authority
                        and existing.get("authorization") == auth):
                    problems = verify_accepted_debt(
                        root, [{"path": path.relative_to(root).as_posix()}])
                    if problems:
                        raise ValueError("existing acceptance is not current: "
                                         + "; ".join(problems))
                    return {"ok": True, "code": "ALREADY_APPLIED", "record_id": path.stem,
                            "events": normalized, "authority_status": "KNOWN"}
                replacement = auth["binding"].get("supersedes")
                expected = {"record_id": path.stem,
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                if (replacement != expected
                        or prior_authority["authority_status"] != "UNKNOWN"):
                    return {"ok": False, "code": "ACCEPTED_DEBT_EXISTS",
                            "detail": f"{path.stem} already accepts exactly this set"}
                dependencies[path.relative_to(root).as_posix()] = hash_file_dependency(path)
            elif not prior <= wanted:
                return {"ok": False, "code": "ACCEPTED_DEBT_EXISTS",
                        "detail": f"{path.stem} already accepts: " + ", ".join(sorted(overlap))}
        debt_authority.authorize(root, record, dependencies)
        content = debt_authority.record_bytes(record)
        rel = f"{ACCEPTED_DEBT_DIR}/{record['record_id']}.json"
        committed = run_mutation(
            root, op_id=record["journal_op_id"], operation="accepted_debt.register",
            agent=str(agent),
            project_identity=record["project_identity"],
            semantic_payload_hash=hashlib.sha256(content).hexdigest(),
            targets=[{"path": rel, "role": "report", "action": "write", "content": content,
                      "before_hash": "", "after_hash": hashlib.sha256(content).hexdigest()}],
            preconditions={rel: ""}, read_preconditions=dependencies,
            verification_policy="accepted_debt",
        )
        if not committed.get("ok"):
            return {"ok": False, "code": committed.get("code", "VALIDATION_FAILED"),
                    "detail": committed.get("detail", committed.get("message", "apply failed"))}
        problems = verify_accepted_debt(root, [{"path": rel}])
        if problems:
            raise ValueError("acceptance postcondition failed: " + "; ".join(problems))
        return {"ok": True, "code": "ACCEPTED_DEBT_REGISTERED", "record_id": record["record_id"],
                "events": normalized, "journal_op_id": record["journal_op_id"],
                "authority": authority, "authority_status": "KNOWN"}
    except (OSError, ValueError, TypeError, KeyError, AcceptedDebtRefusal) as exc:
        return {"ok": False, "code": getattr(exc, "code", "VALIDATION_FAILED"),
                "detail": str(exc), "authority_status": "UNKNOWN"}


# T-312: the closed rebind writer.
#
# `register` is the only sanctioned way an accepted-debt record's bytes may
# change, and it can only CREATE a record for a set no record covers yet. That
# left a real hole: when a LOG shard is rotated, a live record's evidence
# (`file`, `line_number`, `line_sha256`) stops resolving, and the generic
# `run_mutation` CAS would happily rewrite the record anyway because it takes an
# arbitrary `operation=` string. The result is exactly what AD-000002's history
# shows: bytes moved under an operation name no module implements, with
# `verification_policy: none`, and nothing in the journal able to tell a
# legitimate repair from a forgery.
#
# `rebind` is the domain writer that closes it. It is deliberately NARROWER than
# `register`, because a rebind is a repair, never a re-registration:
#
#   * the accepted EVENT SET is immutable. A rebind that changed what is
#     accepted would be a new acceptance, and must be refused outright;
#   * every new evidence line must resolve in the CURRENT history and its hash
#     is recomputed from the live line -- a caller cannot assert a hash;
#   * the live file must still hash to the caller's `expected_before`, so a
#     concurrent write is refused rather than silently overwritten;
#   * the write goes through `run_mutation` under the closed
#     `accepted_debt` verification policy, so APPLY and Recovery both rerun the
#     same semantic postcondition instead of trusting the receipt.
def rebind(
    root: Path | str,
    ref: str,
    *,
    agent: str,
    reason: str,
    expected_before: str,
) -> dict:
    """Re-point ONE record's evidence at where its events live NOW.

    Fails closed on: a missing/corrupt/foreign record, an empty reason, a stale
    `expected_before`, an event that no longer parses as a LOG line, and any
    attempt to change the accepted event set.
    """
    root = Path(root)
    from .capability import may_mutate, negotiate_capability

    if not may_mutate(negotiate_capability()):
        return {"ok": False, "code": "CAPABILITY_READ_ONLY", "detail": "rebind is a mutation"}
    if not ACCEPTED_DEBT_ID_RE.match(ref or ""):
        return {
            "ok": False,
            "code": "VALIDATION_FAILED",
            "detail": f"invalid record id {ref!r} (expected AD-######)",
        }
    if not str(reason or "").strip():
        return {"ok": False, "code": "VALIDATION_FAILED", "detail": "reason is required"}
    if not str(expected_before or "").strip():
        return {
            "ok": False,
            "code": "VALIDATION_FAILED",
            "detail": "expected_before is required: a rebind without the live hash it "
            "replaces cannot prove which bytes it is repairing",
        }

    # The engine's OWN loader: schema_version, record_id, kind, integrity digest,
    # lineage and rule binding. A refusal here means the record is damaged or
    # foreign, and repairing damaged bytes through a repair path is exactly the
    # laundering this writer exists to prevent.
    try:
        record = load_record(root, ref)
    except AcceptedDebtRefusal as refusal:
        return {
            "ok": False,
            "code": refusal.code,
            "detail": refusal.detail,
        }

    from . import debt_authority

    authority = debt_authority.status(root, record)
    if authority["authority_status"] != "KNOWN":
        return {"ok": False, "code": "VALIDATION_FAILED", "detail": authority["authority_reason"],
                "authority_status": "UNKNOWN"}

    rel = f"{ACCEPTED_DEBT_DIR}/{ref}.json"
    path = root / rel
    from .journal import run_mutation

    # The journal hashes a precondition target with its OWN 16-hex form, and
    # compares it against exactly that. Binding the rebind to the same
    # representation keeps "the bytes this repair replaces" and "the bytes the
    # journal CASes on" the same fact; a caller may pass either the truncated
    # form or a full digest, and both mean the same thing.
    live_bytes = path.read_bytes()
    live_hash = hashlib.sha256(live_bytes).hexdigest()[:16]
    if live_hash != str(expected_before).strip()[:16]:
        return {
            "ok": False,
            "code": "STALE_PRECONDITION",
            "detail": (
                f"{rel} is at {live_hash}, not the expected "
                f"{str(expected_before).strip()[:16]}"
            ),
        }

    # Resolve the SAME accepted set in the current history. The set is read from
    # the record and never from the caller: that is what makes a rebind unable
    # to silently widen or narrow an acceptance.
    events = list(record.get("accepted_missing_events") or [])
    if not events:
        return {
            "ok": False,
            "code": "ACCEPTED_DEBT_CORRUPT",
            "detail": f"{ref} accepts no events; there is nothing to rebind",
        }
    found: dict[str, tuple[str, int, str]] = {}
    for segment_rel, line_no, raw_line, parsed in _iter_history(root):
        event_id = EVENT_INPUT_RE.match(f"E-{parsed.get('event')}")
        if event_id is None:
            continue
        canonical = f"E-{int(event_id.group(1))}"
        found.setdefault(canonical, (segment_rel, line_no, raw_line))

    unresolved = [event for event in events if event not in found]
    if unresolved:
        return {
            "ok": False,
            "code": "VALIDATION_FAILED",
            "detail": "event(s) no longer parse as LOG lines and cannot be re-bound: "
            + ", ".join(unresolved[:5]),
        }

    old_evidence = record.get("evidence") or []
    new_evidence = [
        {
            "event": event,
            "file": found[event][0],
            "line_number": found[event][1],
            "line_sha256": _line_sha256(found[event][2]),
        }
        for event in sorted(events, key=lambda e: int(EVENT_INPUT_RE.match(e).group(1)))
    ]
    if new_evidence == old_evidence:
        return {
            "ok": False,
            "code": "ACCEPTED_DEBT_REBIND_NOOP",
            "detail": f"{ref} evidence already resolves at its current location; "
            "a rebind would change nothing",
        }

    rebound = dict(record)
    rebound["evidence"] = new_evidence
    rebound["rebind_reason"] = str(reason).strip()
    rebound["rebind_from_evidence"] = old_evidence
    op_id = (
        "accepted_debt.rebind-"
        + hashlib.sha256(
            f"{ref}|{live_hash}|{json.dumps(new_evidence, sort_keys=True)}".encode("utf-8")
        ).hexdigest()[:12]
    )
    rebound["journal_op_id"] = op_id
    rebound["integrity_digest"] = _integrity_digest(
        {k: v for k, v in rebound.items() if k != "integrity_digest"}
    )
    content = json.dumps(rebound, indent=2, sort_keys=True).encode("utf-8")

    committed = run_mutation(
        root,
        op_id=op_id,
        operation="accepted_debt.rebind",
        agent=str(agent or "unknown"),
        project_identity=record["project_identity"],
        semantic_payload_hash=hashlib.sha256(
            json.dumps(
                {
                    "record": ref,
                    "events": events,
                    "from": [item.get("file") for item in old_evidence],
                    "to": sorted({item["file"] for item in new_evidence}),
                    "reason": str(reason).strip(),
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest(),
        targets=[
            {
                "path": rel,
                "role": "report",
                "action": "write",
                "content": content,
                "before_hash": live_hash,
                "after_hash": hashlib.sha256(content).hexdigest(),
            }
        ],
        preconditions={rel: live_hash},
        verification_policy="accepted_debt",
    )
    if not committed.get("ok"):
        return {
            "ok": False,
            "code": committed.get("code", "VALIDATION_FAILED"),
            "detail": committed.get("detail", committed.get("message", "journal apply failed")),
        }
    return {
        "ok": True,
        "code": "ACCEPTED_DEBT_REBOUND",
        "record_id": ref,
        "events": events,
        "journal_op_id": op_id,
        "evidence_from": sorted({item.get("file") for item in old_evidence if item.get("file")}),
        "evidence_to": sorted({item["file"] for item in new_evidence}),
    }
