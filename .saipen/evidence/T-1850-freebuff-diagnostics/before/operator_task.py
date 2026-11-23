"""Whose words a receipt actually holds, and who says so.

MEASURED, 2026-09-17, nine-condition field matrix on installed generation
f3d2104a. `long_file_task` was handed a 520-byte request over twelve lines with
four explicit constraints. It ran `saipen start` with a 46-character substitute
it wrote itself, minted `T-1` and `SRC-001`, changed `src/app.py`, and every
gate read green. T-1372's obligation never armed, because that mechanism records
what a transport refusal REFUSED and nothing refused anything: the session never
attempted the literal ingress at all.

The defect class this ends: **the operator's request reaches the protocol only
through the model's own hands, and the receipt says nothing about that.**
`source_authority: exact` is a true statement about BYTES -- the stored body is
the body we were handed, unredacted -- and it was being read as a statement
about WORDS.

So the receipt records its witness. Three values, and the difference between
them is who compared what:

* ``operator_carrier`` -- an independently verified native host event carries
  the task's bytes and scope. A matching file or environment digest alone is
  integrity evidence, not authentication of the person who supplied it.
* ``transport_obligation`` -- a transport refusal recorded these exact bytes
  and they arrived (INGRESS-AUTHORITY-01, T-1372).
* ``model_supplied`` -- operator origin is unverified. A carrier may still
  establish matching bytes; the receipt does not promote that into identity.

`model_supplied` is not a failure and is not refused: most sessions have no
carrier, and inventing one would be the fabrication this module exists to stop.
It is a fact a reader can act on, and a matrix can count.
"""

from __future__ import annotations

import os
import re
from contextlib import suppress
from pathlib import Path

#: The operator's task digest, declared by whoever launched this session.
ENV_TASK_SHA256 = "SAIPEN_TASK_SHA256"

#: The operator's task text on disk, when a launcher can write a file but not a
#: digest. Read-only, bounded; the digest is computed from its bytes.
ENV_TASK_FILE = "SAIPEN_TASK_FILE"

#: Operator task ingress carried directly by the native host adapter (OpenCode).
DECLARED_HOST_INGRESS = "host_ingress"

#: The host's stable name for the session that delivered a carrier. The
#: OpenCode adapter exports it per event (T-1384); a carrier is only authority
#: for the session that delivered it (T-1822).
ENV_HOST_SESSION = "SAIPEN_HOST_SESSION"

#: A task file past this size is not a task, and reading it unbounded would let
#: an environment variable point the engine at anything on the disk.
MAX_TASK_FILE_BYTES = 256 * 1024

WITNESS_CARRIER = "operator_carrier"
WITNESS_OBLIGATION = "transport_obligation"
WITNESS_MODEL = "model_supplied"
WITNESSES = (WITNESS_CARRIER, WITNESS_OBLIGATION, WITNESS_MODEL)

CODE_MISMATCH = "INGRESS_TASK_MISMATCH"
CODE_CARRIER_INVALID = "INGRESS_TASK_CARRIER_INVALID"
CODE_FREEBUFF_PROVENANCE_MISSING = "FREEBUFF_OPERATOR_PROVENANCE_MISSING"
#: An operator carrier exists for these bytes but this session cannot prove it
#: delivered them. The safe failure: never promote another turn's envelope.
CODE_HOST_PROVENANCE_UNAVAILABLE = "HOST_PROVENANCE_UNAVAILABLE"

_SHA256 = re.compile(r"[0-9a-f]{64}")


def host_session(env: dict | None = None) -> str | None:
    """The host's name for the running session, or None when it gave none.

    A missing name is not a match-all: it is the absence of an identity, so a
    carrier stamped for a named session cannot be attributed to it (T-1822).
    """
    env = os.environ if env is None else env
    value = str(env.get(ENV_HOST_SESSION) or "").strip()
    return value or None


def is_freebuff_host(env: dict | None = None) -> bool:
    """Detect whether this execution is running under the FreeBuff host."""
    env = os.environ if env is None else env
    for k in (
        "FREEBUFF_HOME",
        "FREEBUFF_VERSION",
        "FREEBUFF_DESKTOP",
        "FREEBUFF_SESSION",
        "FREEBUFF_WORKSPACE",
        "FREEBUFF_PORT",
        "FREEBUFF_CWD",
    ):
        if env.get(k):
            return True
    return env.get("AGENT_HOST") == "freebuff" or env.get("SAIPEN_HOST") == "freebuff"


def authority_for_provenance(
    provenance: object, *, root: Path | str | None = None, receipt: str | None = None,
    existing_only: bool = False,
) -> dict:
    """Persistence/fidelity are not operator authority (SRC-164).

    A transport obligation was created from a tool payload, not necessarily
    from human ingress. Only an external operator carrier can grant the
    operator capabilities. None of these capabilities grants publication or
    retirement: those operations still require their own scoped authority.
    """
    record = provenance if isinstance(provenance, dict) else {}
    witness_kind = record.get("witness")
    if witness_kind not in WITNESSES:
        witness_kind = WITNESS_MODEL
    carrier_matches = (
        witness_kind == WITNESS_CARRIER
        and isinstance(record.get("compared_digest"), str)
        and bool(_SHA256.fullmatch(record["compared_digest"]))
        and record.get("declared_by") in (ENV_TASK_SHA256, ENV_TASK_FILE, DECLARED_HOST_INGRESS)
    )
    # T-1844 / SRC-278 B/M: a model can set the REAL carrier variables or write
    # a matching ingress file. Integrity and a declared source are not origin.
    # Only the separated owner can verify the particular human event and scope.
    trusted = False
    reference = record.get("source_receipt") if receipt is None else receipt
    source_reference = receipt is None and "source_receipt" in record
    if source_reference and (
        not isinstance(reference, str) or not re.fullmatch(r"SRC-\d+", reference)
    ):
        carrier_matches = False
    if carrier_matches and root is not None:
        from .host_authority_client import verify_operator_origin

        trusted = verify_operator_origin(
            record.get("operator_origin"), project=root,
            request_digest=record["compared_digest"],
            session=record.get("session_id") or host_session(), receipt=reference,
            existing_only=existing_only or source_reference,
        )
    if witness_kind == WITNESS_CARRIER and not trusted:
        witness_kind = WITNESS_MODEL
    action = (record.get("operator_origin") or {}).get("action") if trusted else None
    reset_current_budget = False
    if trusted and action in {"continue", "goal", "authorize-goal"}:
        from .operator_origin import context

        with suppress(OSError, ValueError, TypeError, KeyError):
            # The broker already authenticated this proof. Its signed budget
            # must still name the independent current epoch for a reset, even
            # when a bound Source retains its original human attribution.
            reset_current_budget = context(root)["budget"] == record["operator_origin"]["budget"]
    res = {
        "witness": witness_kind,
        "capture": True,
        "local_work": True,
        "user_explicit": trusted,
        "preempt_active_work": trusted and action in {"start", "goal", "append", "handoff"},
        "goal_pivot": trusted and action in {"goal", "authorize-goal"},
        "reset_bounded_authority": reset_current_budget,
        "detailed_response": trusted,
        "gate_decision": trusted and action == "resolve-gate",
        "retirement": trusted and action == "retire",
        "claim_handoff": trusted and action == "handoff",
        "amend_work": trusted and action == "append",
        "work_supersession": trusted and action == "supersede",
        "external_action": False,
    }
    if record.get("freebuff_provenance_missing"):
        res["freebuff_provenance_missing"] = True
        res["diagnostic_code"] = CODE_FREEBUFF_PROVENANCE_MISSING
    return res


def _receipt_provenance(root, receipt):
    """An integrity-checked provenance record matching the exact request bytes."""
    from . import intake
    from .pending_ingress import ingress_digest

    found = intake.read_body(Path(root), receipt)
    if not found.get("ok"):
        return None
    meta = found.get("meta") or {}
    record = meta.get("request_provenance")
    body = str(found.get("body") or "")
    if body.startswith("# User request\n"):
        _head, separator, request = body.partition("\n## Request\n")
        if not separator:
            return None
        body = request
    if not isinstance(record, dict) or record.get("compared_digest") != ingress_digest(body):
        return None
    return record


def received_source_origin(root, receipt, *, action):
    """Historical human origin in one accepted Source; never current powers."""
    from .host_authority_client import verify_operator_source

    record = _receipt_provenance(root, receipt) or {}
    proof = record.get("operator_origin")
    return bool(record.get("witness") == WITNESS_CARRIER and isinstance(proof, dict)
                and proof.get("action") == action and verify_operator_source(
                    proof, project=root, receipt=receipt, request_digest=record["compared_digest"],
                ))


def authority_for_receipt(
    root: Path | str, receipt: str, *, existing_only: bool = True,
) -> dict:
    """Current capabilities from immutable, integrity-checked request bytes.

    Later carriers never promote old receipts. Queries accept no new Source;
    only a mutating capture/entry may pass existing_only=False after durability.
    """
    record = _receipt_provenance(root, receipt)
    if record is None:
        return authority_for_provenance(None)
    authority = authority_for_provenance(
        record, root=root, receipt=receipt, existing_only=existing_only,
    )
    if authority["user_explicit"] and record.get("ingress_id") and not existing_only:
        # Diagnostic transport retirement follows the broker's Source binding,
        # never a preview that could fail before the request is durable.
        consume_host_ingress(root, record["ingress_id"], receipt)
    return authority


def projection_priority(priority: str, authority: dict) -> str:
    """Unwitnessed candidates cannot acquire P0/P1 by arrival alone."""
    if authority.get("user_explicit"):
        return priority
    return "P" + str(max(2, int(priority[1:])))


def declared(env: dict | None = None) -> dict | None:
    """What this session was LAUNCHED with, or None when nobody said.

    Returns ``{"digest": ..., "source": ENV_TASK_SHA256|ENV_TASK_FILE}`` or an
    ``{"error": ...}`` record. A malformed carrier is an error rather than an
    absence: an environment that meant to declare the task and failed must not
    read as an environment that never declared one.
    """
    from .pending_ingress import ingress_digest

    env = os.environ if env is None else env
    raw = (env.get(ENV_TASK_SHA256) or "").strip().lower()
    if raw:
        if not _SHA256.fullmatch(raw):
            return {"error": f"{ENV_TASK_SHA256} is not a 64-character sha256 hex digest"}
        return {"digest": raw, "source": ENV_TASK_SHA256}
    path_raw = (env.get(ENV_TASK_FILE) or "").strip()
    if not path_raw:
        return None
    path = Path(path_raw)
    try:
        if path.stat().st_size > MAX_TASK_FILE_BYTES:
            return {"error": f"{ENV_TASK_FILE} is larger than {MAX_TASK_FILE_BYTES} bytes"}
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, ValueError) as exc:
        return {"error": f"{ENV_TASK_FILE} is not a readable UTF-8 file: {exc}"}
    return {"digest": ingress_digest(text), "source": ENV_TASK_FILE}


def file_route(task_file: str | None) -> str | None:
    """`saipen start --file` for a declared task file, typed so every shell carries it.

    MEASURED in four real shells (T-1380 review): the unquoted route arrived
    intact in PowerShell 5, pwsh 7 and cmd, but Git Bash handed the CLI
    `V:_TEMP_t1363-abc.saipen-launched-task.txt` -- an unquoted backslash is an
    escape there -- and a path with a space split into three arguments in all
    four. The double-quoted form arrived intact in every one. A path no quoted
    argument carries literally (a quote, `$`, a backtick, `%VAR%`, a trailing
    backslash) gets no route rather than one that breaks when typed.
    """
    from .guard_events import ingress_payload_literal

    path = (task_file or "").strip()
    if not path or not ingress_payload_literal(path, '"'):
        return None
    return f'saipen start --file "{path}"'


def _reachable_route(env: dict | None) -> str | None:
    """The command a session can actually RUN to answer a mismatch, or None.

    Measured 2026-09-17 on the final matrix: a refusal whose only instruction is
    "carry the operator's own bytes" is unanswerable when the carrier declared a
    DIGEST, because a digest is irreversible. `long_file_task` was refused, wrote
    its own paraphrase to a file, was refused again, then dumped
    SAIPEN_TASK_SHA256 and built a list of text variants to search for one that
    hashes to it. A route the session cannot run is worse than no route: it
    turns a correct refusal into a guessing loop.
    """
    env = os.environ if env is None else env
    return file_route(env.get(ENV_TASK_FILE))


def ingress_cache_dir(root: Path | str) -> Path:
    return Path(root) / ".saipen" / "cache" / "ingress"


def admit_host_ingress(
    ingress_data: dict,
    root: Path | str,
    *,
    event_session: str | None = None,
) -> dict:
    """Validate and admit an operator ingress delivered by the native host adapter."""
    from datetime import datetime, timezone
    import json
    import urllib.parse
    from .cold_recovery import is_continuation_command
    from .paths import project_lineage_identity
    from .pending_ingress import ingress_digest

    if not isinstance(ingress_data, dict):
        return {
            "ok": False,
            "code": "INGRESS_TASK_CARRIER_INVALID",
            "detail": "ingress data invalid",
        }
    request_text = ingress_data.get("request_text")
    if not isinstance(request_text, str) or not request_text.strip():
        return {"ok": False, "code": "INGRESS_TASK_CARRIER_INVALID", "detail": "ingress text empty"}

    computed = ingress_digest(request_text)
    if ingress_data.get("request_digest") and ingress_data["request_digest"] != computed:
        return {"ok": False, "code": "INGRESS_TASK_MISMATCH", "detail": "request digest mismatch"}

    session_id = ingress_data.get("session_id")
    if event_session and session_id and session_id != event_session:
        return {
            "ok": False,
            "code": "INGRESS_TASK_CARRIER_INVALID",
            "detail": "ingress session mismatch",
        }

    root_path = Path(root)
    lineage = ingress_data.get("project_lineage")
    expected_lineage = project_lineage_identity(root_path)
    if lineage and expected_lineage and lineage != expected_lineage:
        return {
            "ok": False,
            "code": "INGRESS_TASK_CARRIER_INVALID",
            "detail": "ingress lineage mismatch",
        }

    # File resolution: check if request references a file
    file_path = None
    file_digest = None
    cleaned = request_text.strip().strip("\"'")
    candidate_path = None
    if cleaned.startswith("file:///"):
        parsed = urllib.parse.urlparse(cleaned)
        candidate_path = Path(urllib.parse.unquote(parsed.path).lstrip("/"))
    elif "\n" not in cleaned and ("\\" in cleaned or "/" in cleaned) and len(cleaned) < 500:
        candidate_path = Path(cleaned)
    else:
        m = re.search(
            r'["\']?([A-Za-z]:\\[^"\'\r\n]+\.[A-Za-z0-9_-]+|\/[^"\'\r\n]+\.[A-Za-z0-9_-]+)["\']?',
            request_text,
        )
        if m:
            candidate_path = Path(m.group(1).strip().strip("\"'"))

    if candidate_path:
        try:
            resolved = (
                candidate_path
                if candidate_path.is_absolute()
                else (root_path / candidate_path).resolve()
            )
            if resolved.is_file() and resolved.stat().st_size <= MAX_TASK_FILE_BYTES:
                file_text = resolved.read_text(encoding="utf-8-sig")
                file_path = str(resolved)
                file_digest = ingress_digest(file_text)
        except (OSError, ValueError):
            pass

    destination_op = "continue" if is_continuation_command(request_text) else "start"

    ingress_dir = ingress_cache_dir(root_path)
    ingress_dir.mkdir(parents=True, exist_ok=True)
    # T-1822: the id is the operator's message, not the request text. Naming the
    # file after the text digest made two sessions that delivered the SAME text
    # share one path, so the later envelope OVERWROTE the earlier one including
    # its session_id (measured: message_id m-A replaced by m-B). A host may
    # deliver the same words twice -- a restart, a re-send, a second window --
    # and each delivery is its own delivery. Digest the message id when the host
    # supplies one, then disambiguate on collision instead of overwriting.
    identity = computed
    message_id = ingress_data.get("message_id")
    if message_id:
        identity = ingress_digest(f"{message_id}\x00{computed}")
    ingress_id = f"ing-{identity[:16]}"
    target_file = ingress_dir / f"{ingress_id}.json"

    if target_file.exists():
        try:
            existing = json.loads(target_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            existing = None
        if isinstance(existing, dict):
            same_delivery = (
                existing.get("message_id") == message_id
                and existing.get("session_id") == session_id
                and existing.get("request_digest") == computed
            )
            if same_delivery:
                # Idempotent re-delivery of the envelope already on disk.
                return {
                    "ok": True,
                    "ingress_id": ingress_id,
                    "destination_op": existing.get("destination_op"),
                    "consumed": bool(existing.get("consumed")),
                }
            # A different delivery whose identity collided: never overwrite it.
            suffix = identity[16:24] or computed[16:24]
            ingress_id = f"ing-{identity[:12]}-{suffix}"
            target_file = ingress_dir / f"{ingress_id}.json"
            counter = 2
            while target_file.exists():
                ingress_id = f"ing-{identity[:12]}-{suffix}-{counter}"
                target_file = ingress_dir / f"{ingress_id}.json"
                counter += 1

    record = {
        "ingress_id": ingress_id,
        "message_id": ingress_data.get("message_id"),
        "request_text": request_text,
        "request_digest": computed,
        "file_path": file_path,
        "file_digest": file_digest,
        "session_id": session_id,
        "project_lineage": lineage or expected_lineage,
        "destination_op": destination_op,
        "consumed": False,
        "consumed_by": None,
        "consumed_at": None,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "witness": WITNESS_MODEL,
        "declared_by": DECLARED_HOST_INGRESS,
    }
    if isinstance(ingress_data.get("operator_origin"), dict):
        # Transport only: the separated verifier, not this writable file,
        # decides whether the supplied proof authenticates a human event.
        record["operator_origin"] = ingress_data["operator_origin"]
    target_file.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return {"ok": True, "ingress_id": ingress_id, "destination_op": destination_op}


def active_host_ingress(
    root: Path | str, session_id: str | None = None, *, include_consumed: bool = False,
) -> list[dict]:
    import json

    ingress_dir = ingress_cache_dir(root)
    if not ingress_dir.is_dir():
        return []
    records = []
    for item in ingress_dir.glob("*.json"):
        try:
            data = json.loads(item.read_text(encoding="utf-8"))
            if isinstance(data, dict) and (include_consumed or not data.get("consumed")):
                if session_id and data.get("session_id") and data["session_id"] != session_id:
                    continue
                records.append(data)
        except (OSError, ValueError):
            continue
    records.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
    return records


def consume_host_ingress(root: Path | str, ingress_id: str, consumed_by: str) -> bool:
    from datetime import datetime, timezone
    import json

    target = ingress_cache_dir(root) / f"{ingress_id}.json"
    if not target.is_file():
        return False
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return False
        if data.get("consumed"):
            return data.get("consumed_by") == consumed_by
        data["consumed"] = True
        data["consumed_by"] = consumed_by
        data["consumed_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        target.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return True
    except (OSError, ValueError):
        return False


def witness(
    text: str,
    *,
    obligation_met: bool = False,
    env: dict | None = None,
    root: Path | str | None = None,
) -> dict:
    """How this request's fidelity was established, or why it is refused.

    ``{"witness": ..., "compared_digest": ...}`` when the ingress may proceed;
    ``{"code": ..., "detail": ...}`` when an operator carrier contradicts the
    text that arrived.
    """
    from .pending_ingress import ingress_digest

    supplied = ingress_digest(text)
    record = declared(env)
    raw_carrier = None
    if record and record.get("error"):
        return {
            "code": CODE_CARRIER_INVALID,
            "detail": (
                str(record["error"])
                + ". The session declares an operator task it cannot prove, so this "
                "ingress is refused rather than recorded as unwitnessed. Fix the "
                "carrier or unset it"
            ),
            "canonical_next_command": _reachable_route(env),
        }
    if record:
        if record["digest"] != supplied:
            route = _reachable_route(env)
            reach = (
                "The operator's own bytes are on disk at the declared task file; run "
                "the command in canonical_next_command, which needs no shell quoting."
                if route
                else (
                    "This session cannot reach the operator's text: the carrier declared "
                    "a DIGEST, and a digest is irreversible -- do not try to reconstruct "
                    "the text from it. Ask the operator to restate the request, or have "
                    "the launcher declare " + ENV_TASK_FILE + " so the bytes are readable."
                )
            )
            return {
                "code": CODE_MISMATCH,
                "detail": (
                    "this session was launched with a task whose sha256 is "
                    + record["digest"]
                    + " (declared by "
                    + record["source"]
                    + ") and the text supplied to the ingress has digest "
                    + supplied
                    + ". A receipt built from it would carry the session's words under "
                    "the operator's authority. " + reach
                ),
                "declared_digest": record["digest"],
                "supplied_digest": supplied,
                "canonical_next_command": route,
                "operator_text_reachable": bool(route),
            }
        raw_carrier = {
            "witness": WITNESS_MODEL,
            "compared_digest": supplied,
            "declared_by": record["source"],
            "carrier_integrity": "MATCHED",
            "note": "matching carrier bytes are not authenticated operator origin",
        }
        if is_freebuff_host(env):
            raw_carrier.update(host_identity="freebuff", freebuff_provenance_missing=True,
                               diagnostic_code=CODE_FREEBUFF_PROVENANCE_MISSING)
    effective_root = root or os.environ.get("SAIPEN_PROJECT_ROOT")
    if effective_root is not None:
        # T-1822: the write path refuses a session mismatch, and that check is
        # useless if the READ path ignores the same field. Measured: an
        # envelope stamped session_id=session-A was consumed when session-B
        # supplied the same text, and the witness reported operator_carrier
        # with user_explicit true -- a replayed carrier earning the operator's
        # authority. Bind every matching envelope to the delivering session.
        delivering_session = host_session(env)
        active_records = active_host_ingress(effective_root)
        candidates = [
            rec
            for rec in active_records
            if rec.get("request_digest") == supplied or rec.get("file_digest") == supplied
        ]
        matching = None
        for rec in candidates:
            carrier_session = str(rec.get("session_id") or "").strip() or None
            # An envelope that names no session is the legacy shape and stays
            # admissible. One that names a DIFFERENT session is another turn's
            # carrier: replaying it would hand this session words it never
            # received, so it is refused rather than assumed (T-1822).
            if carrier_session is None or carrier_session == delivering_session:
                matching = rec
                break
        if matching is None and candidates:
            # The bytes match an envelope this session cannot prove it
            # delivered. Accepting it is the replay hole; choosing silently
            # between "stale" and "wrong session" would hide which happened.
            return {
                "code": CODE_HOST_PROVENANCE_UNAVAILABLE,
                "detail": (
                    "this project holds an operator ingress for these exact bytes, but "
                    "it was delivered by "
                    + (
                        "session " + str(candidates[0].get("session_id"))
                        if candidates[0].get("session_id")
                        else "no named session"
                    )
                    + " and this session is "
                    + (
                        "session " + delivering_session
                        if delivering_session
                        else "not identified by " + ENV_HOST_SESSION
                    )
                    + ". A carrier proves operator authority only for the turn that "
                    "delivered it; replaying another session's envelope would hand this "
                    "session words it never received. Ask the operator to send the "
                    "request again from this session."
                ),
                "ingress_id": candidates[0].get("ingress_id"),
                "carrier_session": candidates[0].get("session_id"),
                "delivering_session": delivering_session,
                "supplied_digest": supplied,
            }
        if matching:
            candidate = {
                "witness": WITNESS_CARRIER,
                "compared_digest": supplied,
                "declared_by": DECLARED_HOST_INGRESS,
                "ingress_id": matching["ingress_id"],
                "message_id": matching.get("message_id"),
                "session_id": matching.get("session_id"),
            }
            if isinstance(matching.get("operator_origin"), dict):
                candidate["operator_origin"] = matching["operator_origin"]
            if not authority_for_provenance(candidate, root=effective_root)["user_explicit"]:
                if "operator_origin" in candidate:
                    # A transport/issuer fault must not spend the event before
                    # authenticated verification can succeed on a safe retry.
                    return {
                        "code": CODE_HOST_PROVENANCE_UNAVAILABLE,
                        "detail": (
                            "the native operator-event proof could not be verified; "
                            "the envelope was not consumed"
                        ),
                        "ingress_id": matching["ingress_id"],
                    }
                candidate["witness"] = WITNESS_MODEL
                candidate["carrier_integrity"] = "MATCHED"
                if is_freebuff_host(env):
                    candidate.update(host_identity="freebuff", freebuff_provenance_missing=True,
                                     diagnostic_code=CODE_FREEBUFF_PROVENANCE_MISSING)
            if "operator_origin" not in candidate:
                consume_host_ingress(effective_root, matching["ingress_id"], "witness")
            return candidate
        start_pending = next(
            (r for r in active_records if r.get("destination_op") == "start"), None
        )
        if start_pending:
            expected_digest = start_pending.get("file_digest") or start_pending["request_digest"]
            route = file_route(start_pending.get("file_path"))
            reach = (
                "The operator's own bytes are on disk at the declared task file; run "
                "the command in canonical_next_command, which needs no shell quoting."
                if route
                else (
                    "Carry the operator's own bytes without rewording. "
                    "Run saipen start with the exact text or use a file."
                )
            )
            return {
                "code": CODE_MISMATCH,
                "detail": (
                    "this session received a host ingress whose sha256 is "
                    + expected_digest
                    + " (declared by "
                    + DECLARED_HOST_INGRESS
                    + ") and the text supplied to the ingress has digest "
                    + supplied
                    + ". A receipt built from it would carry the session's words under "
                    "the operator's authority. " + reach
                ),
                "declared_digest": expected_digest,
                "supplied_digest": supplied,
                "canonical_next_command": route
                or ("saipen start --file <path>" if start_pending.get("file_path") else None),
                "operator_text_reachable": bool(route or start_pending.get("file_path")),
            }
    if effective_root is not None and delivering_session:
        # An accepted Source is a continuation reference, never another fresh
        # delivery. Cache fields only locate it: the live owner must already
        # bind this exact Source to this worker, event, content and current scope.
        for prior in active_host_ingress(effective_root, include_consumed=True):
            if (not prior.get("consumed") or prior.get("session_id") != delivering_session
                    or supplied not in (prior.get("request_digest"), prior.get("file_digest"))
                    or not isinstance(prior.get("operator_origin"), dict)
                    or not re.fullmatch(r"SRC-\d+", str(prior.get("consumed_by") or ""))):
                continue
            candidate = {
                "witness": WITNESS_CARRIER, "compared_digest": supplied,
                "declared_by": DECLARED_HOST_INGRESS, "session_id": delivering_session,
                "operator_origin": prior["operator_origin"],
                "source_receipt": prior["consumed_by"],
            }
            if authority_for_provenance(candidate, root=effective_root)["user_explicit"]:
                return candidate
    if raw_carrier is not None:
        return raw_carrier
    if obligation_met:
        return {"witness": WITNESS_OBLIGATION, "compared_digest": supplied}
    rec = {
        "witness": WITNESS_MODEL,
        "compared_digest": supplied,
        "note": (
            "no operator carrier and no transport obligation: the stored bytes are "
            "what this session supplied, and nothing compared them with what the "
            "operator wrote"
        ),
    }
    if is_freebuff_host(env):
        rec["host_identity"] = "freebuff"
        rec["freebuff_provenance_missing"] = True
        rec["diagnostic_code"] = CODE_FREEBUFF_PROVENANCE_MISSING
    return rec


def unstarted(root: Path | str, env: dict | None = None) -> dict | None:
    """The task this session was launched with that this project has not taken.

    Returns ``{"digest", "source", "command"}`` when a carrier declares a task
    and NO receipt here already holds those bytes; None otherwise (including
    when nothing was declared, which is most sessions).

    Measured 2026-09-17: four of nine field sessions opened with `saipen status`
    or `saipen continue` although BOOT's entry table says a new actionable task
    goes to `saipen start`. `status` answered `next_action: saipen continue`,
    and `continue` answered IMPROVE_AUDIT_ASSIGNMENT -- it sent a session that
    was handed a user task into an improvement audit. The table was right and
    the runtime's own answer did not agree with it, which is a protocol defect
    rather than a model one: the session asked the project what to do and the
    project did not say "start the task you were given".
    """
    import json as _json

    record = declared(env)
    root = Path(root)
    index = root / ".saipen" / "intake" / "index.json"
    active: dict = {}
    try:
        active = (_json.loads(index.read_text(encoding="utf-8")) or {}).get("active") or {}
    except (OSError, ValueError):
        active = {}

    if record and not record.get("error"):
        for receipt_id in active:
            meta_path = root / ".saipen" / "intake" / "active" / f"{receipt_id}.meta.json"
            try:
                meta = _json.loads(meta_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            provenance = meta.get("request_provenance")
            if (
                isinstance(provenance, dict)
                and provenance.get("compared_digest") == record["digest"]
            ):
                return None
        env = os.environ if env is None else env
        command = file_route(env.get(ENV_TASK_FILE)) or (
            "saipen start '<the task you were given, one line>'"
        )
        return {"digest": record["digest"], "source": record["source"], "command": command}

    # Check unconsumed host ingress
    active_starts = [r for r in active_host_ingress(root) if r.get("destination_op") == "start"]
    for host_rec in active_starts:
        rec_digest = host_rec.get("file_digest") or host_rec["request_digest"]
        taken = False
        for receipt_id in active:
            meta_path = root / ".saipen" / "intake" / "active" / f"{receipt_id}.meta.json"
            try:
                meta = _json.loads(meta_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            provenance = meta.get("request_provenance")
            if isinstance(provenance, dict) and provenance.get("compared_digest") == rec_digest:
                taken = True
                break
        if not taken:
            fpath = host_rec.get("file_path")
            command = file_route(fpath) or (
                f'saipen start --file "{fpath}"'
                if fpath
                else (
                    f'saipen start "{host_rec["request_text"]}"'
                    if len(host_rec["request_text"]) < 120 and "\n" not in host_rec["request_text"]
                    else "saipen start '<the task you were given, one line>'"
                )
            )
            return {"digest": rec_digest, "source": DECLARED_HOST_INGRESS, "command": command}

    return None


__all__ = [
    "CODE_CARRIER_INVALID",
    "CODE_MISMATCH",
    "DECLARED_HOST_INGRESS",
    "ENV_TASK_FILE",
    "ENV_TASK_SHA256",
    "MAX_TASK_FILE_BYTES",
    "WITNESSES",
    "WITNESS_CARRIER",
    "WITNESS_MODEL",
    "WITNESS_OBLIGATION",
    "active_host_ingress",
    "admit_host_ingress",
    "authority_for_provenance",
    "authority_for_receipt",
    "consume_host_ingress",
    "declared",
    "projection_priority",
    "unstarted",
    "witness",
]
