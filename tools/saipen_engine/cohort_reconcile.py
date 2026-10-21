"""Journal-bound adoption of pending cohort history by one reviewed final batch.

Original membership, hashes and finishes never change. A relation is not
publication: only the ordinary successor release can discharge that obligation.
The first route is deliberately flat; an existing relation cannot be rewritten.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

from . import closure, codec
from .journal import hash_bytes, hash_file_dependency, hash_tree_dependency
from .paths import project_lineage_identity
from .safeid import prove_inside

_OP = re.compile(r"cohort-reconcile-[0-9a-f]{32}")


def _reviewed(cohort: dict) -> dict:
    return {key: cohort.get(key) for key in ("cohort_id", "members", "scope")}


def _shape(cohort: object, identity: str) -> None:
    if (
        not isinstance(cohort, dict)
        or cohort.get("cohort_id") != identity
        or not isinstance(cohort.get("members"), dict)
        or not cohort["members"]
        or not isinstance(cohort.get("scope"), list)
        or any(not isinstance(rel, str) for rel in cohort["scope"])
    ):
        raise ValueError("invalid cohort reconciliation membership shape")
    for tid, member in cohort["members"].items():
        if (
            not isinstance(tid, str)
            or not re.fullmatch(r"T-\d+", tid)
            or not isinstance(member, dict)
            or member.get("ticket_id") != tid
            or not isinstance(member.get("paths"), dict)
            or not member["paths"]
            or any(
                not isinstance(rel, str) or not isinstance(value, str)
                for rel, value in member["paths"].items()
            )
        ):
            raise ValueError("invalid cohort reconciliation member paths")
    paths = {rel for member in cohort["members"].values() for rel in member["paths"]}
    if set(cohort["scope"]) != paths or len(cohort["scope"]) != len(paths):
        raise ValueError("cohort reconciliation scope disagrees with its members")


def _receipt_path(op_id: str) -> str:
    if not isinstance(op_id, str) or not _OP.fullmatch(op_id):
        raise ValueError("invalid cohort reconciliation operation identity")
    return f".saipen/recovery/cohort-reconcile/{op_id}.json"


def receipt(root: Path, registry: dict, op_id: str) -> dict:
    """Validate the immutable edge through the existing canonical journal."""
    from .journal import semantic_receipts_for_operation_safe

    rel = _receipt_path(op_id)
    path = root / rel
    prove_inside(path, root, kind="cohort reconciliation receipt")
    if path.is_symlink():
        raise ValueError("cohort reconciliation receipt is a symlink")
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    if (
        not isinstance(data, dict)
        or type(data.get("schema")) is not int
        or data.get("schema") != 1
        or data.get("op_id") != op_id
    ):
        raise ValueError("invalid cohort reconciliation receipt")
    if data.get("project_lineage") != project_lineage_identity(root):
        raise ValueError("foreign cohort reconciliation lineage")
    records, errors = semantic_receipts_for_operation_safe(root, "cohort_reconcile")
    if errors:
        raise ValueError("corrupt cohort reconciliation journal: " + "; ".join(errors[:3]))
    record = next(
        (row for row in records if row.get("op_id") == op_id and row.get("status") == "COMMITTED"),
        None,
    )
    if record is None or not any(
        item.get("path") == rel and item.get("after_hash") == hash_bytes(raw)
        for item in record.get("targets", [])
    ):
        raise ValueError("cohort reconciliation has no intact committed journal target")
    cohorts = registry.get("cohorts") or {}
    target = cohorts.get(data.get("target"))
    _shape(target, data.get("target"))
    sources = data.get("sources")
    if (
        not isinstance(target, dict)
        or target.get("reconciliation") != op_id
        or _reviewed(target) != data.get("target_reviewed")
        or not isinstance(sources, dict)
        or not sources
    ):
        raise ValueError("cohort reconciliation target changed")
    for cid, original in sources.items():
        current = cohorts.get(cid)
        _shape(current, cid)
        if not isinstance(current, dict):
            raise ValueError("cohort reconciliation source is missing")
        unchanged = {key: value for key, value in current.items() if key != "publication_successor"}
        if unchanged != original or current.get("publication_successor") != {
            "cohort": data["target"],
            "op_id": op_id,
        }:
            raise ValueError("original cohort reconciliation history changed")
    return data


def target_problem(root: Path | str, cohort: dict, registry: dict | None = None) -> str | None:
    """Additional release readiness for a reconciled final batch, read-only."""
    op_id = cohort.get("reconciliation")
    if "reconciliation" not in cohort:
        return None
    root = Path(root)
    try:
        registry = registry if registry is not None else closure.read_registry(root)
        data = receipt(root, registry, op_id)
        if data["target"] != cohort.get("cohort_id"):
            raise ValueError("reconciliation belongs to a different target")
        from .intake import work_closure_gate

        for original in data["sources"].values():
            for tid in original["members"]:
                if not work_closure_gate(root, tid).get("ok"):
                    raise ValueError(
                        f"inherited cohort member {tid} has unresolved Source coverage"
                    )
        return None
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return "invalid cohort reconciliation: " + str(exc)


def successor(root: Path | str, registry: dict, cohort_id: str) -> dict | None:
    """Return a proven flat successor; untrusted metadata is never a fallback."""
    cohort = registry["cohorts"][cohort_id]
    edge = cohort.get("publication_successor")
    if edge is None:
        return None
    if not isinstance(edge, dict):
        raise ValueError("invalid cohort publication successor")
    data = receipt(Path(root), registry, edge.get("op_id"))
    if cohort_id not in data["sources"] or edge.get("cohort") != data["target"]:
        raise ValueError("cohort publication successor does not bind this source")
    target = registry["cohorts"][data["target"]]
    if "publication_successor" in target:
        raise ValueError("nested cohort reconciliation is unsupported")
    if target.get("publication_status") == "shipped":
        published = closure._published_releases(Path(root))
        if not any(
            row.get("op_id") == target.get("release_op_id")
            and row.get("version") == target.get("version")
            and row.get("cohort_id") == data["target"]
            for row in published
        ):
            raise ValueError("successor cohort has no matching terminal publication receipt")
    return target


def plan(root: Path | str, target_id: str, agent: str, sources: list[str], review_work: str):
    """One frozen PLAN; APPLY/Recovery remain the canonical operation owners."""
    from . import core_unit, operations as ops
    from .journal import semantic_receipt_snapshot
    from .log import verification_evidence
    from .plan import TargetPlan
    from .result import Result
    from .state import patch_state

    root = Path(root)
    if (
        not isinstance(target_id, str)
        or not closure.COHORT_ID_RE.fullmatch(target_id)
        or not isinstance(review_work, str)
        or not re.fullmatch(r"T-\d+", review_work)
        or not isinstance(agent, str)
        or not agent.strip()
        or not isinstance(sources, list)
        or not sources
        or any(
            not isinstance(cid, str) or not closure.COHORT_ID_RE.fullmatch(cid) for cid in sources
        )
        or len(set(sources)) != len(sources)
        or target_id in sources
    ):
        return ops._refuse(
            "VALIDATION_FAILED", "distinct source cohorts, one target and review Work are required"
        )
    read_once = ops._read(root)
    docs, state, board, _tail = read_once
    refused = ops._active_claim_refusal(state, docs["board"].text_norm, agent)
    if refused is not None:
        return refused
    try:
        registry_doc = codec.read_document(closure.registry_path(root))
        registry = json.loads(registry_doc.text_norm)
        cohorts = registry["cohorts"]
        target = cohorts[target_id]
        _shape(target, target_id)
        if "reconciliation" in target:
            prior = receipt(root, registry, target["reconciliation"])
            if sorted(prior["sources"]) == sorted(sources) and prior["review_work"] == review_work:
                return Result(
                    True, "ALREADY_APPLIED", data={"cohort": target_id, "idempotent": True}
                )
            raise ValueError("existing cohort reconciliation cannot be rewritten")
        if "publication_successor" in target:
            raise ValueError("nested cohort reconciliation is unsupported")
        selected = {cid: cohorts[cid] for cid in sources}
        for cid, cohort in {**selected, target_id: target}.items():
            _shape(cohort, cid)
            if (
                cohort.get("publication_status") != "pending"
                or "publication_successor" in cohort
                or "reconciliation" in cohort
            ):
                raise ValueError(f"{cid} is not an unreconciled pending cohort")
            ready = closure.cohort_readiness(root, cohort)
            if not ready["ready"]:
                raise ValueError(f"{cid} is not ready: {ready['problems']}")
            if any(member.get("closed_by") != agent for member in cohort["members"].values()):
                raise ValueError("cohort reconciliation requires the original canonical owner")
        member = target["members"].get(review_work)
        ticket = board["tickets"].get(review_work)
        if member is None or ticket is None or ticket["fields"].get("owner") != agent:
            raise ValueError("review Work must be an owned DONE member of the target cohort")
        from .board import closure_paths

        if set(closure_paths(ticket)) != set(member["paths"]):
            raise ValueError("review Work path attribution disagrees with cohort membership")
        authority = semantic_receipt_snapshot(root)
        if authority.errors:
            raise ValueError(
                "corrupt canonical finish authority: " + "; ".join(authority.errors[:3])
            )
        finished = {
            row["op_id"]
            for row in authority.records
            if row.get("operation") == "finish" and row.get("status") == "COMMITTED"
        }
        events = docs["_history"].events
        if not any(
            event.get("ticket") == review_work and event.get("op_id") in finished
            for event in events
        ):
            raise ValueError("review Work has no committed canonical finish")
        proven, reason = verification_evidence(review_work, events)
        if not proven:
            raise ValueError("review Work lacks verification: " + reason)
        gate = core_unit.ship_gate(root, review_work, events)
        if gate:
            raise ValueError("review Work evidence is not current: " + gate)
        scope = closure.cohort_scope(target)
        inherited = {
            rel
            for cohort in selected.values()
            for item in cohort["members"].values()
            for rel in item["paths"]
        }
        if not inherited.issubset(scope) or not set(scope).issubset(member["paths"]):
            raise ValueError("review Work must cover the entire inherited and target path union")
        if closure.cohort_member_mismatches(root, target):
            raise ValueError("target cohort contains source changed since its owning review")
        hashes = {}
        for rel, expected in scope.items():
            path = root / rel
            if (
                not rel
                or ":" in rel
                or "\\" in rel
                or rel.startswith("/")
                or any(part in ("", ".", "..") for part in rel.split("/"))
                or rel.split("/")[0].lower() in (".git", ".saipen")
            ):
                raise ValueError("cohort reconciliation requires confined regular source paths")
            resolved = prove_inside(path, root, kind="cohort reconciliation source")
            if path.is_symlink() or resolved.relative_to(root.resolve()).parts[0].lower() in (
                ".git",
                ".saipen",
            ):
                raise ValueError("cohort reconciliation source is not a regular private path")
            raw = path.read_bytes()
            if not closure.member_hash_matches(raw, expected):
                raise ValueError("cohort source changed while planning reconciliation")
            hashes[rel] = hash_bytes(raw)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return ops._refuse("VALIDATION_FAILED", str(exc))

    op_id = "cohort-reconcile-" + ops.uuid4_hex()
    rel = _receipt_path(op_id)
    data = {
        "schema": 1,
        "op_id": op_id,
        "project_lineage": project_lineage_identity(root),
        "target": target_id,
        "review_work": review_work,
        "sources": selected,
        "target_reviewed": _reviewed(target),
    }
    raw = (json.dumps(data, sort_keys=True, indent=2) + "\n").encode("utf-8")
    updated = copy.deepcopy(registry)
    updated["cohorts"][target_id]["reconciliation"] = op_id
    for cid in sources:
        updated["cohorts"][cid]["publication_successor"] = {"cohort": target_id, "op_id": op_id}
    registry_bytes = registry_doc.encode(closure.render_registry(updated))
    dependencies = {
        **hashes,
        ".saipen/recovery": authority.digest,
        ".saipen/intake": hash_tree_dependency(root / ".saipen/intake"),
        closure.COHORT_REGISTRY_REL: hash_file_dependency(closure.registry_path(root)),
    }
    # Bind the actual cited records too: tampering between PLAN and APPLY must
    # not launder the earlier current-evidence decision into a later snapshot.
    from . import focused_unit

    for dependency in (core_unit.BASELINE_REL, focused_unit.POLICY_REL):
        dependencies[dependency] = hash_file_dependency(root / dependency)
    for event in core_unit._current_cycle(review_work, events) or []:
        if event.get("ticket") == review_work:
            if event.get("op_id") in finished:
                break
            text = event.get("text", "").strip()
            full = core_unit.parse_evidence(text)
            focused = focused_unit._CITATION.match(text)
            cited = full["record"] if full else focused.group(1) if focused else None
            if cited:
                evidence_root = root / (
                    core_unit.RECORD_DIR_REL if full else focused_unit.RECORD_DIR_REL
                )
                try:
                    prove_inside(root / cited, evidence_root, kind="review evidence")
                    dependencies[cited] = hash_file_dependency(root / cited)
                except (OSError, ValueError) as exc:
                    return ops._refuse("VALIDATION_FAILED", str(exc))

    def mutate(text, event):
        return patch_state(text, {"last_event": event, "updated": ops._utc_iso()})

    return ops._state_only_plan(
        root,
        "cohort_reconcile",
        agent,
        mutate,
        f"pending cohorts {','.join(sorted(sources))} reconciled into reviewed {target_id} "
        f"by {review_work}; original hashes preserved; publication still owed",
        {
            "ok": True,
            "code": "COHORT_RECONCILED",
            "cohort": target_id,
            "sources": sorted(sources),
            "review_work": review_work,
            "evidence_path": rel,
        },
        ops._now(),
        ops._utc_iso(),
        {"last_event", "updated"},
        ticket_id=review_work,
        evidence_preconditions=dependencies,
        op_id=op_id,
        read_once=read_once,
        extra_targets=[
            TargetPlan(rel, "generic", raw, "", hash_bytes(raw)),
            TargetPlan(
                closure.COHORT_REGISTRY_REL,
                "report",
                registry_bytes,
                ops._live_before(root, closure.COHORT_REGISTRY_REL, registry_doc),
                hash_bytes(registry_bytes),
            ),
        ],
    )
