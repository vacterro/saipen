"""Native admission for declared outcomes; projections alone grant no closure.

The existing ticket_verify journal retains contract changes. Operator Sources
approve exact amendment bytes or report exact LIVE/MANUAL observations; labels
and model-supplied Sources do not authenticate an observation. Legacy untyped
clauses remain legacy evidence, not retroactive proof of product behavior.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath

from . import acceptance as ac, board_compaction as bc, intake, operator_task
from .board import parse_board
from .journal import Journal, hash_bytes, hash_file_dependency, semantic_receipts_for_operation

MAX_BYTES = 1024 * 1024
MARKER = "; declared acceptance contract"
AMENDMENT_FIELDS = {
    "schema", "work", "original_sha256", "replacement_sha256", "reason",
    "evidence", "mapping", "remaining",
}


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate acceptance JSON field: " + key)
        result[key] = value
    return result


def _decode(raw: bytes) -> dict:
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique)
    if not isinstance(value, dict):
        raise ValueError("acceptance capsule must be an object")
    return value


def _fields(value: dict, fields: set) -> None:
    if set(value) != fields or type(value.get("schema")) is not int or value["schema"] != 1:
        raise ValueError("acceptance capsule has unknown, missing or invalid fields")


def _read(root: Path, relative: str, bindings: dict, *, evidence=False) -> bytes:
    if (not isinstance(relative, str) or not relative or "\\" in relative
            or ":" in relative or any(ord(c) < 32 for c in relative)
            or PurePosixPath(relative).is_absolute()
            or any(p in ("", ".", "..") for p in relative.split("/"))):
        raise ValueError("acceptance input needs a canonical owned relative path")
    if evidence and not relative.startswith(".saipen/evidence/"):
        raise ValueError("acceptance amendment material must be retained in .saipen/evidence/")
    raw = intake._read_owned_file(root, relative, kind="acceptance input", max_bytes=MAX_BYTES)
    token = hash_bytes(raw)
    if relative in bindings and bindings[relative] != token:
        raise ValueError("acceptance input changed during admission")
    bindings[relative] = token
    return raw


def specs(text: str) -> dict:
    """Keep the projection grammar, but refuse ambiguous declarations at admission."""
    seen = set()
    for segment in (text or "").split(";"):
        part = segment.strip()
        if not part.startswith("AC-"):
            continue
        match = ac.CRITERION_RE.fullmatch(part)
        if not match or match[1] in seen:
            raise ValueError("malformed or duplicate acceptance criterion")
        seen.add(match[1])
        text_part = match[2].strip()
        if text_part.startswith("[") and not ac.CRITERION_WITNESS_RE.fullmatch(text_part):
            raise ValueError("unknown or malformed acceptance witness")
    return ac.parse_criterion_specs(text)


def protected(old: str, new: str) -> bool:
    return any(part.strip().startswith("AC-") for text in (old, new)
               for part in (text or "").split(";"))


def _expand(contract: str, aliases: dict[str, str]) -> str:
    seen = set()
    while contract in aliases:
        if contract in seen:
            raise ValueError("acceptance detail projection cycle")
        seen.add(contract)
        contract = aliases[contract]
    if ("[detail_ref: " + bc.COMPACTION_ROOT + "/" in contract
            and contract not in aliases.values()):
        raise ValueError("acceptance projection is stale or lacks bound detail authority")
    return contract


def _details(root: Path, work: str, bindings: dict) -> dict[str, str]:
    """Exact compaction projections, proved only by the current owned ancestry.

    The original record and the existing compactor prove the projection; a
    prefix, criterion id or journal description cannot substitute for either.
    Bind every inspected ancestor/checkpoint to the caller's normal APPLY CAS.
    """
    board = parse_board(_read(root, ".saipen/BOARD.md", bindings).decode("utf-8-sig"))
    ticket = board["tickets"].get(work)
    if ticket is None:
        raise ValueError("acceptance Work is not on BOARD")
    head = ticket.get("fields", {}).get("detail_ref")
    if not head:
        return {}
    identity = ".saipen/IDENTITY.md"
    bindings[identity] = hash_file_dependency(root / identity)
    bc.resolve_detail(root, head, expected_ticket_id=work)
    lineage = bc.gather_lineage(root, head, work)
    if lineage is None:
        raise ValueError("acceptance detail lineage is missing")
    # A bounded checkpoint can retain more unrelated legacy history than this
    # acquisition needs. Use only its proven entries. Any contract that needs
    # the unacquired tail still fails _expand's exact-reference check.
    aliases = {}
    for entry in lineage["entries"]:
        reference = entry["detail_ref"]
        metadata = _decode(_read(root, reference, bindings))
        original = _read(root, metadata["original_record_path"], bindings)
        checkpoint = metadata.get("supersedes_checkpoint")
        if checkpoint:
            _read(root, checkpoint, bindings)
        preserved = parse_board("## TODO\n" + original.decode("utf-8"))["tickets"][work]
        compact = bc._compact_line(preserved, reference)
        projected = parse_board("## TODO\n" + compact)["tickets"][work]
        if "verify" in projected["fields"]:
            aliases[projected["fields"]["verify"]] = preserved["fields"].get("verify", "")
    # Verify the pinned bytes, including every edge and any flattened ancestry,
    # after acquisition. A concurrent read cannot turn validation into a pin
    # of different, unvalidated bytes.
    bc.resolve_detail(root, head, expected_ticket_id=work)
    if any(hash_file_dependency(root / path) != token for path, token in bindings.items()):
        raise ValueError("acceptance detail changed while being read")
    return aliases


def resolve(root: Path, work: str, contract: str, bindings: dict | None = None) -> str:
    """Resolve full current acceptance without changing BOARD or old receipts."""
    bindings = {} if bindings is None else bindings
    return _expand(contract, _details(root, work, bindings))


def _operator_source(
    root: Path, receipt: str, bindings: dict, *, active=False, action="report", historical=True,
) -> tuple[str, str]:
    from .distribution import distribution_record_rel, quarantine_body_rel

    if not isinstance(receipt, str) or not intake._valid_receipt_id(receipt):
        raise ValueError("acceptance authority needs an exact Source id")
    paths = [f"{prefix}/{receipt}{suffix}"
             for prefix in (".saipen/intake/active", ".saipen/archive/source")
             for suffix in (".md", ".meta.json")]
    paths.extend((distribution_record_rel(receipt), quarantine_body_rel(receipt)))
    pins = {p: hash_file_dependency(root / p) for p in paths}
    found = intake.read_body(root, receipt)
    if not found.get("ok"):
        raise ValueError("acceptance authority Source is missing or corrupt: " + str(receipt))
    meta = found["meta"]
    if historical:
        authority = operator_task.received_source_origin(root, receipt, action=action)
    else:
        capability = {"append": "amend_work", "supersede": "work_supersession"}.get(action)
        authority = bool(capability and operator_task.authority_for_receipt(
            root, receipt,
        ).get(capability, False))
    if (meta.get("source_kind") != "user_instruction"
            or meta.get("status") not in ({"ACTIVE"} if active else {"ACTIVE", "CLOSED"})
            or not authority):
        raise ValueError("acceptance requires immutable operator-carrier Source authority")
    if found["location"] not in ("active", "archive"):
        raise ValueError("retired Sources cannot grant acceptance authority")
    prefix = ".saipen/intake/active" if found["location"] == "active" else ".saipen/archive/source"
    metadata_path = f"{prefix}/{receipt}.meta.json"
    if _decode(_read(root, metadata_path, bindings)) != meta:
        raise ValueError("acceptance Source metadata changed during admission")
    body_path = intake._canonical_body_rel(
        root, receipt, str(meta["source_sha256"]), found["location"]
    )
    raw = _read(root, body_path, bindings)
    if hashlib.sha256(raw).hexdigest() != meta["source_sha256"]:
        raise ValueError("acceptance Source body changed during admission")
    body = raw.decode("utf-8")
    if body.startswith("# User request\n"):
        _, separator, body = body.partition("\n## Request\n")
        if not separator:
            raise ValueError("acceptance Source request wrapper is incomplete")
    if pins != {p: hash_file_dependency(root / p) for p in paths}:
        raise ValueError("acceptance operator Source changed while being read")
    bindings.update(pins)
    return body, meta["source_sha256"]


def _source(
    root: Path, receipt: str, bindings: dict, *, active=False, action="report", historical=True,
) -> tuple[dict, str]:
    body, sha = _operator_source(
        root, receipt, bindings, active=active, action=action, historical=historical,
    )
    return _decode(body.encode("utf-8")), sha


def _observation(root, work, contract, events, record, bindings, compatible):
    receipt = record.get("source")
    if not receipt:
        raise ValueError("contract-bound acceptance requires source=SRC-N operator observation")
    capsule, _ = _source(root, receipt, bindings)
    _fields(capsule, {"schema", "kind", "work", "contract_sha256", "build_boundary", "criteria"})
    if (capsule["kind"] != "acceptance_witness" or capsule["work"] != work
            or capsule["contract_sha256"] not in compatible
            or type(capsule["build_boundary"]) is not int
            or capsule["build_boundary"] != ac.build_boundary(work, events)
            or not isinstance(capsule["criteria"], dict)):
        raise ValueError("operator observation is stale or scoped to another contract/Work")
    declared = specs(contract)
    for key, value in capsule["criteria"].items():
        if (key not in declared or not isinstance(value, dict)
                or set(value) != {"result", "witness", "surface"}
                or value["result"] not in ("PASS", "FAIL", "UNKNOWN")
                or value["witness"] not in ac.WITNESS_LEVELS
                or not isinstance(value["surface"], str) or not value["surface"]):
            raise ValueError("operator observation has invalid criterion fields")
    actual = capsule["criteria"].get(record["ac"])
    expected = {"result": record["result"], "witness": record["witness"],
                "surface": record["observed_surface"]}
    if actual != expected or expected["surface"] == "legacy-unspecified":
        raise ValueError("operator observation does not attest this criterion/witness/surface")


def _declared_at_event(fallback, history, event):
    declared = history[0]["original"] if history else fallback
    for item in history:
        if item["event"] >= event:
            break
        declared = item["replacement"]
    return specs(declared)


def _witnesses(root, work, contract, events, bindings, compatible=None, *, history=(),
               declared=None):
    specs(contract)
    compatible = compatible or {digest(contract)}
    projection = ac.reconcile(work, contract, events)
    for row in projection["criteria"]:
        if row["state"] != ac.SATISFIED:
            raise ValueError(f"acceptance {row['ac']}: {row['state']}")
        sufficient = [r for r in row["evidence"] if not r["stale"] and r["result"] == "PASS"
                      and ac.witness_satisfies(r["witness"], row["minimum_witness"])]
        # Claimed LIVE/MANUAL scope needs its origin even for a lower floor.
        # A bad Source cannot hide behind an earlier good observation.
        for record in sufficient:
            recorded = _declared_at_event(declared if declared is not None else contract,
                                          history, record["event"])
            same_outcome = recorded.get(row["ac"], {}).get("text") == row["text"]
            # An id survives a rename; its old PASS does not prove the new
            # outcome. Proposed replacements need a digest-bound observation
            # until that outcome has its own canonical declaration and check.
            if record["witness"] in ("LIVE", "MANUAL") or not same_outcome:
                _observation(root, work, contract, events, record, bindings, compatible)


def _changed(old, new):
    before, after = specs(old), specs(new)
    return any(key not in after or before[key]["text"] != after[key]["text"]
               or not ac.witness_satisfies(after[key]["minimum_witness"], spec["minimum_witness"])
               for key, spec in before.items())


def _amendment(root, work, old, new, path, authority, events, bindings, *, historical=False,
               history=()):
    raw = _read(root, path, bindings, evidence=True)
    value = _decode(raw)
    _fields(value, AMENDMENT_FIELDS)
    if (value["work"] != work or value["original_sha256"] != digest(old)
            or value["replacement_sha256"] != digest(new)
            or not isinstance(value["reason"], str) or not value["reason"].strip()):
        raise ValueError("acceptance amendment is stale, unreasoned or scoped to another Work")
    approved, source_sha = _source(
        root, authority, bindings, active=not historical, action="append", historical=historical,
    )
    _fields(approved, {"schema", "kind", "work", "sha256"})
    manifest_sha = hashlib.sha256(raw).hexdigest()
    if approved != {"schema": 1, "kind": "acceptance_amendment", "work": work,
                    "sha256": manifest_sha}:
        raise ValueError("operator Source does not approve these exact amendment bytes")
    before, after = specs(old), specs(new)
    mapping, remaining = value["mapping"], value["remaining"]
    if (not isinstance(mapping, dict) or set(mapping) != set(before)
            or not isinstance(remaining, list) or len(remaining) != len(set(remaining))
            or set(remaining) != set(after)):
        raise ValueError("acceptance amendment must map every original and remaining outcome")
    for key, destinations in mapping.items():
        if (not isinstance(destinations, list) or not destinations
                or not all(isinstance(item, str) for item in destinations)
                or len(destinations) != len(set(destinations))
                or any(item not in after or not ac.witness_satisfies(
                    after[item]["minimum_witness"], before[key]["minimum_witness"]
                ) for item in destinations)):
            raise ValueError(
                "retired acceptance outcome needs an equivalent or stronger replacement"
            )
    evidence = value["evidence"]
    if not isinstance(evidence, list) or not evidence or len(evidence) > 256:
        raise ValueError("acceptance amendment needs bounded retained retirement evidence")
    seen = set()
    for item in evidence:
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            raise ValueError("acceptance amendment evidence needs exact path and SHA256")
        data = _read(root, item["path"], bindings, evidence=True)
        if item["path"].casefold() in seen or hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError("acceptance amendment evidence is duplicated or changed")
        seen.add(item["path"].casefold())
    if not historical:
        compatible = {digest(new)}
        for candidate in (old, *(text for item in history
                                  for text in (item["original"], item["replacement"]))):
            if specs(candidate) == after:
                compatible.add(digest(candidate))
        _witnesses(root, work, new, events, bindings, compatible, history=history, declared=old)
    return {"path": path, "sha256": manifest_sha, "authority": authority,
            "authority_sha256": source_sha}


def _chain(root, work, current, events, bindings, *, aliases=None):
    aliases = _details(root, work, bindings) if aliases is None else aliases
    current = _expand(current, aliases)
    records = semantic_receipts_for_operation(root, "ticket_verify")
    contracts = []
    for record in records:
        metadata = record.get("receipt_metadata") or {}
        contract = metadata.get("acceptance_contract")
        if record.get("status") == "COMMITTED" and contract and contract.get("work") == work:
            journal = Journal(root, record["op_id"])
            before = hash_file_dependency(journal.manifest)
            if journal.read() != record or before != hash_file_dependency(journal.manifest):
                raise ValueError("acceptance journal changed while being read")
            bindings[journal.manifest.relative_to(root).as_posix()] = before
            contracts.append(contract)
    previous = None
    compatible = {digest(current)}
    contracts.sort(key=lambda item: item["event"])
    history = []
    for item in contracts:
        _fields(item, {"schema", "work", "event", "original", "replacement",
                       "original_sha256", "replacement_sha256", "amendment"})
        raw_old, raw_new = item["original"], item["replacement"]
        if (digest(raw_old) != item["original_sha256"]
                or digest(raw_new) != item["replacement_sha256"]):
            raise ValueError("acceptance contract journal chain does not preserve its preimage")
        old, new = _expand(raw_old, aliases), _expand(raw_new, aliases)
        if previous is not None and old != previous:
            raise ValueError("acceptance contract journal chain does not preserve its preimage")
        amendment = item["amendment"]
        if _changed(old, new):
            if not isinstance(amendment, dict):
                raise ValueError("acceptance contract reduction has no approved amendment")
            checked = _amendment(root, work, old, new, amendment["path"],
                                 amendment["authority"], events, bindings, historical=True)
            if checked != amendment:
                raise ValueError("acceptance amendment binding changed since approval")
        previous = new
        history.append({**item, "original": old, "replacement": new})
        # Journaled changes outside the declared criteria do not spend a
        # current observation. No prose similarity or unknown digest can do
        # this: the complete parsed criterion specifications must be equal.
        for candidate in (old, new):
            if specs(candidate) == specs(current):
                compatible.add(digest(candidate))
    if previous is not None and current != previous:
        raise ValueError("current acceptance differs from the journaled replacement contract")
    return compatible, history


def prepare(root, work, old, new, event, events, *, amendment=None, authority=None):
    """Metadata and read dependencies for the existing native verify writer."""
    bindings = {}
    aliases = _details(root, work, bindings)
    old = _expand(old, aliases)
    specs(old)
    specs(new)
    _, history = _chain(root, work, old, events, bindings, aliases=aliases)
    if bool(amendment) != bool(authority):
        raise ValueError("acceptance amendment requires both --amendment and --authority")
    approval = None
    if _changed(old, new) or amendment:
        if not amendment:
            raise ValueError(
                "declared acceptance reduction requires an operator-approved amendment"
            )
        approval = _amendment(root, work, old, new, amendment, authority, events, bindings,
                              history=history)
    return {"acceptance_contract": {
        "schema": 1, "work": work, "event": event, "original": old, "replacement": new,
        "original_sha256": digest(old), "replacement_sha256": digest(new), "amendment": approval,
    }}, bindings


def _recorded(work, events):
    # Only a trigger: this marker grants no authority. The verified journal
    # supplies the contract, including when a raw BOARD edit removed all ACs.
    return any(
        ev.get("ticket") == work and ev.get("taxonomy") == "DEC"
        and str(ev.get("text", "")).startswith("ticket verify updated via SAIOPS")
        and MARKER in str(ev.get("text", "")) for ev in events
    )


def gate(root, work, contract, events):
    """One shared REVIEW/finish admission. Caller binds returned inputs to APPLY."""
    bindings = {}
    aliases = _details(root, work, bindings)
    contract = _expand(contract, aliases)
    if not specs(contract) and not _recorded(work, events):
        return bindings
    compatible, history = _chain(root, work, contract, events, bindings, aliases=aliases)
    _witnesses(root, work, contract, events, bindings, compatible, history=history)
    return bindings


def supersession_gate(root, old_work, old, new_work, new, authority, events):
    """Preserve typed outcomes through the existing independent-successor route."""
    bindings = {}
    aliases = _details(root, old_work, bindings)
    old = _expand(old, aliases)
    new = resolve(root, new_work, new, bindings)
    if not specs(old) and not _recorded(old_work, events):
        return bindings
    _chain(root, old_work, old, events, bindings, aliases=aliases)
    before, after = specs(old), specs(new)
    if any(key not in after or after[key]["text"] != value["text"]
           or not ac.witness_satisfies(after[key]["minimum_witness"], value["minimum_witness"])
           for key, value in before.items()):
        raise ValueError("successor does not preserve every declared original outcome")
    # The old Work need not have passed; the successor independently did.
    bindings.update(gate(root, new_work, new, events))
    _operator_source(root, authority, bindings, active=True, action="supersede", historical=False)
    return bindings
