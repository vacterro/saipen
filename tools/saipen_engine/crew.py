"""Serial, evidence-derived SAICREW fixed-point planner and finalizer."""

from __future__ import annotations

import json
from contextlib import suppress
from dataclasses import asdict, dataclass
from pathlib import Path

from .board import convergence_closure_problems, parse_board
from .journal import (hash_file_dependency, hash_tree_dependency, pending_ops,
                      source_identity_dependency)
from .result import Result
from .state import parse_state
from .subs import (CREW_ROLES, CREW_STAGES, HEALTH_BLOCKED, HEALTH_CURRENT,
                   HEALTH_INVALID, HEALTH_NOT_RUN, HEALTH_READY_FOR_REVIEW,
                   HEALTH_STALE, HEALTH_WORK_PENDING, SUBS_REL,
                   current_local_role_revision, parse_manifest_file,
                   parse_outbox, shared_contract_status, sub_adopt,
                   sub_instance_health, sub_spawn, sub_sync)

SATISFIED = "SATISFIED"
UNSATISFIED = "UNSATISFIED"
WAITING = "WAITING_ON_PREDECESSOR"
_STAGE_NAMES = {stage: name for stage, name, _condition in CREW_STAGES}


@dataclass(frozen=True)
class CrewAction:
    stage: str
    role: str | None
    action: str
    source_identity: dict
    required_contract: str
    inputs: tuple[str, ...]
    expected_evidence: str
    completion_condition: str
    on_success: str = "REPLAN"
    on_failure: str = "BLOCK"


@dataclass(frozen=True)
class CrewEpoch:
    event: int
    op_id: str
    ticket: str | None
    created_at: str


@dataclass(frozen=True)
class ReleaseEvidence:
    op_id: str
    ticket: str
    tag: str
    source_head: str
    closure_commit: str
    created_at: str
    stages: tuple[str, ...]
    pre_ship_evidence: dict


@dataclass(frozen=True)
class CrewSnapshot:
    root: Path
    source_id: object | None
    source_error: str | None
    state_text: str
    state: dict
    board_text: str
    board: dict
    log_text: str
    log_tail: int | None
    saipen_home: str
    home_problem: str | None
    contract_status: dict
    manifest_entries: tuple
    manifest_errors: tuple[str, ...]
    pending: tuple[dict, ...]
    roles: dict
    packages: dict
    epoch: CrewEpoch | None
    release: ReleaseEvidence | None
    input_hashes: dict[str, str]
    stable: bool


def _refuse(code: str, detail: str = "", **extra) -> Result:
    return Result(ok=False, code=code, message=detail, data=extra)


def _source_identity(root: Path):
    try:
        from freshness import compute_source_identity
        return compute_source_identity(root), None
    except Exception as exc:
        return None, str(exc)


def _read_maybe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except OSError:
        return ""


def _root_dependency_specs(root: Path) -> dict[str, tuple[Path, bool]]:
    """Every mutable artifact family a crew decision reads.

    Directory dependencies bind both membership and bytes, so a package,
    charter, receipt, or sealed LOG cannot appear/disappear between the
    planner's first read and its decision without making the snapshot stale.
    """
    return {
        ".saipen/STATE.md": (root / ".saipen/STATE.md", False),
        ".saipen/BOARD.md": (root / ".saipen/BOARD.md", False),
        ".saipen/LOG.md": (root / ".saipen/LOG.md", False),
        ".saipen/extensions/subs": (
            root / ".saipen/extensions/subs", True),
        ".saipen/saitranslate": (root / ".saipen/saitranslate", True),
        ".saipen/logs": (root / ".saipen/logs", True),
    }


def _stability_only_specs(root: Path) -> dict[str, tuple[Path, bool]]:
    # The operation tree is sampled for intra-snapshot movement, but cannot be
    # a finalizer CAS dependency as a whole: starting the finalizer's own
    # journal legitimately adds one child there. Exact receipts used by the
    # verdict are added separately to input_hashes below.
    return {".saipen/recovery/ops": (
        root / ".saipen/recovery/ops", True)}


def _home_dependency_specs(home: str) -> dict[str, tuple[Path, bool]]:
    if not home:
        return {}
    root = Path(home)
    specs = {
        str((root / "extensions/subs").resolve()): (
            root / "extensions/subs", True),
    }
    for candidate in (root / "saipen/BOOT.md", root / "BOOT.md"):
        specs[str(candidate.resolve())] = (candidate, False)
    return specs


def _capture_dependencies(
        specs: dict[str, tuple[Path, bool]]) -> dict[str, str]:
    return {name: (hash_tree_dependency(path) if is_tree else
                   hash_file_dependency(path))
            for name, (path, is_tree) in specs.items()}


def _unsafe_dependency(digest: str) -> bool:
    return digest.startswith("object") or not digest


def _full_log(root: Path) -> str:
    def number(path: Path) -> int:
        try:
            return int(path.stem.split("-")[1])
        except (IndexError, ValueError):
            return -1

    text = ""
    for path in sorted((root / ".saipen/logs").glob("LOG-*.md"), key=number):
        text += _read_maybe(path) + "\n"
    return text + _read_maybe(root / ".saipen/LOG.md")


def _crew_epoch(root: Path, log_text: str) -> CrewEpoch | None:
    from .log import parse_log_line
    found = None
    for line in log_text.splitlines():
        parsed = parse_log_line(line)
        if parsed and parsed.get("text") == "execution intent -> converge/crew" \
                and parsed.get("op_id"):
            receipt = root / ".saipen/recovery/ops" / parsed["op_id"] \
                / "operation.json"
            created = ""
            with suppress(OSError, json.JSONDecodeError):
                created = json.loads(receipt.read_text(
                    encoding="utf-8")).get("created_at", "")
            found = CrewEpoch(parsed["event"], parsed["op_id"],
                              parsed.get("ticket"), created)
    return found


def _release_evidence(root: Path, epoch: CrewEpoch | None) \
        -> ReleaseEvidence | None:
    if epoch is None or not epoch.created_at:
        return None
    candidates = []
    for receipt in (root / ".saipen/recovery/ops").glob("release-*/operation.json"):
        try:
            record = json.loads(receipt.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        stages = tuple(record.get("stages") or ())
        if (record.get("operation") == "release"
                and record.get("status") == "COMMITTED"
                and record.get("release_stage") == "COMMITTED"
                and record.get("crew_epoch") == epoch.op_id
                and record.get("created_at", "") > epoch.created_at
                and record.get("closure_commit")
                and "REMOTE_VERIFIED" in stages):
            candidates.append(record)
    if not candidates:
        return None
    record = max(candidates, key=lambda item: item.get("created_at", ""))
    return ReleaseEvidence(
        record["op_id"], record["ticket_id"], record.get("tag", ""),
        record.get("source_head", ""), record["closure_commit"],
        record.get("created_at", ""), tuple(record.get("stages") or ()),
        dict(record.get("crew_pre_ship_evidence") or {}))


def _specialized_health(snapshot_source, root: Path, role) -> dict:
    path = root / role.outbox_path
    model = parse_outbox(_read_maybe(path), role.name) if path.is_file() else None
    current_role = current_local_role_revision(root, role.name,
                                               _saipen_home_of(root))
    statuses = {"ready": False, "reviewed": False}
    current_ids = []
    if model and not model.errors and snapshot_source and current_role:
        for package in model.packages:
            fields = package.fields
            status = fields.get("status")
            if status not in statuses:
                continue
            if (fields.get("source_head") == snapshot_source.source_head
                    and fields.get("source_tree_fingerprint")
                    == snapshot_source.source_tree_fingerprint
                    and fields.get("role_revision") == current_role):
                statuses[status] = True
                current_ids.append(package.package_id)
    errors = list(model.errors) if model else ([] if path.is_file()
                                               else ["no OUTBOX"])
    if sum(1 for package in (model.packages if model else ())
           if package.fields.get("status") == "ready"
           and package.package_id in current_ids) > 1:
        errors.append("multiple current READY packages")
    return {"health": (HEALTH_INVALID if errors else
                       HEALTH_READY_FOR_REVIEW if statuses["ready"] else
                       HEALTH_CURRENT if statuses["reviewed"] else
                       HEALTH_NOT_RUN),
            "ready_current": statuses["ready"],
            "reviewed_current": statuses["reviewed"],
            "errors": errors, "package_ids": current_ids}


def crew_snapshot(project_root: Path | str) -> CrewSnapshot:
    root = Path(project_root)
    state_path = root / ".saipen/STATE.md"
    board_path = root / ".saipen/BOARD.md"
    root_specs = _root_dependency_specs(root)
    stability_specs = _stability_only_specs(root)
    root_before = _capture_dependencies(root_specs)
    stability_before = _capture_dependencies(stability_specs)
    state_text = _read_maybe(state_path)
    state = parse_state(state_text)
    home = state.get("saipen_home") or ""
    home_specs = _home_dependency_specs(home)
    home_before = _capture_dependencies(home_specs)
    home_problem = _home_problem_for(home)
    source_id, source_error = _source_identity(root)
    source_token = (source_identity_dependency(source_id)
                    if source_id is not None else "")
    board_text = _read_maybe(board_path)
    log_text = _full_log(root)
    from .log import log_tail_event
    board = parse_board(board_text)
    status = shared_contract_status(root, home)
    entries, manifest_errors = parse_manifest_file(root)
    entry_by_name = {entry.name: entry for entry in entries}
    roles = {}
    for role in CREW_ROLES:
        if role.runtime_kind == "generic-sub":
            health = sub_instance_health(
                root, role.name, source_id, entry_by_name.get(role.name))
            health["instance_present"] = (
                root / SUBS_REL / role.name / "STATE.md").is_file()
        else:
            health = _specialized_health(source_id, root, role)
            health["instance_present"] = (root / role.outbox_path).is_file()
        roles[role.name] = health
    packages = {role.name: _current_packages_for(
        root, source_id, home, role) for role in CREW_ROLES}
    epoch = _crew_epoch(root, log_text)
    release = _release_evidence(root, epoch)
    pending = tuple(pending_ops(root))
    receipt_paths = {
        f".saipen/recovery/ops/{op_id}/operation.json"
        for op_id in {item for item in (
            epoch.op_id if epoch else None,
            release.op_id if release else None) if item}
    }
    contract_receipt_path = status.get("inventory_receipt_path")
    if isinstance(contract_receipt_path, str) and contract_receipt_path:
        receipt_paths.add(contract_receipt_path)
    receipt_hashes = {}
    for receipt_path in sorted(receipt_paths):
        receipt_hashes[receipt_path] = hash_file_dependency(
            root / receipt_path)
    repeated_source, repeated_error = _source_identity(root)
    repeated_token = (source_identity_dependency(repeated_source)
                      if repeated_source is not None else "")
    root_after = _capture_dependencies(root_specs)
    stability_after = _capture_dependencies(stability_specs)
    home_after = _capture_dependencies(home_specs)
    source_stable = ((source_id is None and repeated_source is None
                      and source_error == repeated_error)
                     or (source_id is not None and repeated_source is not None
                         and source_id == repeated_source
                         and source_token == repeated_token))
    hashes = {**root_before, **home_before, **receipt_hashes}
    if source_token:
        hashes["."] = source_token
    dependencies_stable = (root_before == root_after
                           and home_before == home_after
                           and stability_before == stability_after
                           and not any(_unsafe_dependency(value)
                                       for value in hashes.values()))
    return CrewSnapshot(
        root, source_id, source_error, state_text, state, board_text, board,
        log_text, log_tail_event(log_text), home, home_problem, status,
        tuple(entries), tuple(manifest_errors), pending, roles, packages,
        epoch, release, hashes, source_stable and dependencies_stable)


def _saipen_home_of(root: Path) -> str:
    return parse_state(_read_maybe(root / ".saipen/STATE.md")).get(
        "saipen_home") or ""


def _source_dict(snapshot: CrewSnapshot) -> dict:
    if snapshot.source_id is None:
        return {"error": snapshot.source_error or "UNKNOWN"}
    return {"source_head": snapshot.source_id.source_head,
            "source_tree_fingerprint":
            snapshot.source_id.source_tree_fingerprint}


def _action(snapshot: CrewSnapshot, stage: str, action: str,
            role: str | None, contract: str, evidence: str,
            completion: str, *inputs: str) -> CrewAction:
    return CrewAction(stage, role, action, _source_dict(snapshot), contract,
                      tuple(inputs), evidence, completion)


def _home_problem_for(saipen_home: str) -> str | None:
    if not saipen_home:
        return "HOME_REQUIRED: STATE.saipen_home is missing"
    home = Path(saipen_home)
    if not ((home / "extensions/subs/PROTOCOL.md").is_file()
            and ((home / "saipen/BOOT.md").is_file()
                 or (home / "BOOT.md").is_file())):
        return ("SYNC_SOURCE_UNAVAILABLE: saipen_home "
                f"{saipen_home!r} cannot provide installed protocol "
                "and extensions/subs/PROTOCOL.md")
    return None


def _home_problem(snapshot: CrewSnapshot) -> str | None:
    """The home verdict captured before the snapshot's closing hash barrier."""
    return snapshot.home_problem


def _core_fixed_point(snapshot: CrewSnapshot) -> tuple[bool, str]:
    errors = convergence_closure_problems(
        snapshot.board, snapshot.state.get("agent"))
    if snapshot.state.get("phase") != "DONE":
        errors.append(f"Core phase is {snapshot.state.get('phase')!r}, not DONE")
    if snapshot.state.get("task") not in (None, "", "none"):
        errors.append(f"Core task is {snapshot.state.get('task')!r}, not none")
    return not errors, "; ".join(errors[:3])


def _sensor_executed(health: dict) -> tuple[bool, str]:
    kind = health.get("health")
    if kind in (HEALTH_CURRENT, HEALTH_READY_FOR_REVIEW):
        return True, ""
    if kind == HEALTH_INVALID:
        errors = health.get("board", {}).get("errors", []) \
            + health.get("outbox", {}).get("errors", [])
        return False, "invalid role evidence: " + "; ".join(errors[:2])
    if kind == HEALTH_BLOCKED:
        return False, "role has operational BLOCKED work"
    if kind == HEALTH_WORK_PENDING:
        return False, "role board has pending work"
    if kind == HEALTH_STALE:
        return False, "role/package evidence is stale"
    return False, "role has no current certification" if kind == HEALTH_NOT_RUN \
        else f"health is {kind}"


def _release_current(snapshot: CrewSnapshot) -> tuple[bool, str]:
    release = snapshot.release
    if release is None:
        return False, "no canonical release receipt binds this crew epoch"
    if snapshot.source_id is None:
        return False, "source identity unavailable"
    if release.closure_commit != snapshot.source_id.source_head:
        return False, "crew release closure is not current HEAD"
    missing = [role.name for role in CREW_ROLES
               if role.name not in release.pre_ship_evidence]
    if missing:
        return False, "release lacks pre-ship crew evidence: " + ", ".join(missing)
    return True, ""


def _current_packages_for(root: Path, source_id, saipen_home: str,
                          role) -> list[dict]:
    path = root / role.outbox_path
    if not path.is_file() or source_id is None:
        return []
    model = parse_outbox(_read_maybe(path), role.name)
    current_role = current_local_role_revision(
        root, role.name, saipen_home)
    if model.errors or current_role is None:
        return []
    return [{"package_id": package.package_id,
             "status": package.fields.get("status"),
             "role_revision": current_role}
            for package in model.packages
            if package.fields.get("status") in ("ready", "reviewed")
            and package.fields.get("source_head")
            == source_id.source_head
            and package.fields.get("source_tree_fingerprint")
            == source_id.source_tree_fingerprint
            and package.fields.get("role_revision") == current_role]


def _current_packages(snapshot: CrewSnapshot, role) -> list[dict]:
    """Return package evidence captured inside the coherent snapshot."""
    return list(snapshot.packages.get(role.name, ()))


def crew_release_context(project_root: Path | str) -> dict:
    """Evidence canonical release stores when active crew authorizes SHIP."""
    snapshot = crew_snapshot(project_root)
    if snapshot.state.get("execution_intent") != "converge" \
            or snapshot.state.get("converge_target") != "crew" \
            or snapshot.epoch is None:
        return {"ok": False, "detail": "active crew epoch missing"}
    stages, _next = _evaluate(snapshot)
    blockers = [stage for stage in stages
                if stage["stage"] in {f"SC-{n}" for n in range(0, 11)}
                and stage["state"] != SATISFIED]
    if blockers:
        return {"ok": False,
                "detail": "crew not ready to ship: " + "; ".join(
                    f"{stage['stage']} {stage['reason']}" for stage in blockers[:3])}
    evidence = {role.name: _current_packages(snapshot, role)
                for role in CREW_ROLES}
    missing = [name for name, packages in evidence.items() if not packages]
    if missing:
        return {"ok": False,
                "detail": "current pre-ship package identity missing: "
                          + ", ".join(missing)}
    return {"ok": True, "crew_epoch": snapshot.epoch.op_id,
            "crew_pre_ship_source": _source_dict(snapshot),
            "crew_pre_ship_evidence": evidence}


def _post_ship(snapshot: CrewSnapshot) -> tuple[bool, str, CrewAction | None]:
    release_ok, reason = _release_current(snapshot)
    if not release_ok:
        return False, reason, None
    for role in CREW_ROLES:
        health = snapshot.roles[role.name]
        if role.role_class == "core-review":
            ok, role_reason = _sensor_executed(health)
            if not ok or health.get("health") != HEALTH_CURRENT:
                return False, f"{role.name}: {role_reason or 'not reviewed'}", \
                    _action(snapshot, "SC-12", "RUN_ROLE", role.name,
                            "post-ship current reviewed sensor package",
                            "complete source-bound package and Core review",
                            "worker health CURRENT against shipped HEAD",
                            role.outbox_path)
    translate = snapshot.roles["saitranslate"]
    if not translate.get("ready_current"):
        return False, "final EE is not READY/current", _action(
            snapshot, "SC-12", "PREPARE_TRANSLATE_FINAL", "saitranslate",
            "fresh terminal producer package", "READY translation package",
            "READY/current package against shipped HEAD",
            next(r.outbox_path for r in CREW_ROLES
                 if r.name == "saitranslate"))
    wiki = snapshot.roles["saiwiki"]
    if not wiki.get("outbox", {}).get("ready_current"):
        return False, "final QQ is not READY/current", _action(
            snapshot, "SC-12", "PREPARE_WIKI_FINAL", "saiwiki",
            "fresh terminal producer package", "READY wiki package",
            "READY/current package against shipped HEAD",
            next(r.outbox_path for r in CREW_ROLES if r.name == "saiwiki"))
    return True, "", None


def _evaluate(snapshot: CrewSnapshot) -> tuple[list[dict], CrewAction | None]:
    evaluations: list[tuple[str, str, str, str, CrewAction | None]] = []
    home_problem = _home_problem(snapshot)
    contract = snapshot.contract_status
    sc0_reason = ""
    sc0_action = None
    if snapshot.pending:
        sc0_reason = "unresolved recovery: " + ", ".join(
            item.get("op_id", "?") for item in snapshot.pending[:3])
        sc0_action = _action(snapshot, "SC-0", "RECOVER", None,
                             "no unresolved journal", "settled operation",
                             "pending_ops is empty", ".saipen/recovery/ops")
    elif home_problem:
        sc0_reason = home_problem
    elif not snapshot.stable:
        sc0_reason = "STALE_PLAN: crew inputs moved during snapshot"
    elif snapshot.source_error:
        sc0_reason = "source identity UNKNOWN: " + snapshot.source_error
    elif snapshot.manifest_errors:
        sc0_reason = "MANIFEST malformed: " + "; ".join(
            snapshot.manifest_errors[:2])
    elif not contract.get("current"):
        drift = (contract.get("missing_files", [])
                 + contract.get("missing_dirs", [])
                 + contract.get("stale_files", [])
                 + contract.get("obsolete_files", [])
                 + contract.get("obsolete_dirs", []))
        if contract.get("inventory_lineage") == "ambiguous":
            drift.append("sub-sync receipt lineage ambiguous")
        elif contract.get("inventory_establishment"):
            drift.append("shared-contract ownership receipt missing")
        elif contract.get("inventory_changed") and not drift:
            drift.append("shared-contract source inventory changed")
        drift = drift or ["shared-contract status is not current"]
        sc0_reason = "shared contract drift: " + "; ".join(drift[:3])
        sc0_action = _action(snapshot, "SC-0", "SYNC_SHARED", None,
                             "project-local inherited contract current",
                             "journaled exact-byte sync receipt",
                             "shared_contract_status.current", *drift[:3])
    evaluations.append(("SC-0", _STAGE_NAMES["SC-0"],
                        SATISFIED if not sc0_reason else UNSATISFIED,
                        sc0_reason, sc0_action))

    active_task = snapshot.state.get("task")
    if active_task not in (None, "", "none"):
        action = _action(snapshot, "CORE-TASK", "CONTINUE_CORE", None,
                         "crew target is outer to active Core ticket",
                         "normal phase/ticket completion evidence",
                         "Core task reaches local terminal point",
                         snapshot.state.get("next_action", ""))
        evaluations.append(("CORE-TASK", "active-core-task", UNSATISFIED,
                            "finish active Core task before crew roles", action))
        stages = _reachable(evaluations)
        return stages, _first_action(stages)

    manifest_names = {entry.name for entry in snapshot.manifest_entries}
    roster_reason = ""
    roster_action = None
    for role in CREW_ROLES:
        if not role.ensure_instance:
            continue
        health = snapshot.roles[role.name]
        state_path = snapshot.root / SUBS_REL / role.name / "STATE.md"
        if role.name not in manifest_names or not health.get(
                "instance_present"):
            roster_reason = f"missing durable role {role.name}"
            roster_action = _action(
                snapshot, "SC-1", "SPAWN_ROLE", role.name,
                "all durable generic built-ins registered and present",
                "STATE/BOARD/LOG/OUTBOX plus strict manifest registration",
                f"{role.name} health is not missing", str(state_path))
            break
        if health.get("role_revision_state") == "STALE":
            roster_reason = f"stale role revision: {role.name}"
            roster_action = _action(
                snapshot, "SC-1", "ADOPT_ROLE", role.name,
                "worker role revision equals project-local charter",
                "journaled STATE adoption preserving history",
                f"{role.name} role_revision_state CURRENT",
                f"{SUBS_REL}/{role.name}.md")
            break
        if health.get("health") == HEALTH_INVALID:
            roster_reason = f"invalid/conflicting role {role.name}; refuse overwrite"
            break
    evaluations.append(("SC-1", _STAGE_NAMES["SC-1"],
                        SATISFIED if not roster_reason else UNSATISFIED,
                        roster_reason, roster_action))

    for role in (item for item in CREW_ROLES
                 if item.role_class == "core-review"):
        ok, reason = _sensor_executed(snapshot.roles[role.name])
        action = None if ok else _action(
            snapshot, role.stage, "RUN_ROLE", role.name,
            "current source-bound independent role evidence",
            "complete strict OUTBOX package (payload [] allowed)",
            "role evidence READY_FOR_REVIEW or CURRENT", role.outbox_path)
        evaluations.append((role.stage, role.name,
                            SATISFIED if ok else UNSATISFIED, reason, action))

    ready = [role.name for role in CREW_ROLES
             if role.role_class == "core-review"
             and snapshot.roles[role.name].get("health")
             == HEALTH_READY_FOR_REVIEW]
    collect_action = None
    if ready:
        role = ready[0]
        collect_action = _action(
            snapshot, "SC-6", "COLLECT_ROLE", role,
            "core-review package durably ingested once",
            "ordinary Core review unit with immutable provenance",
            f"{role} health CURRENT and no READY package",
            next(item.outbox_path for item in CREW_ROLES
                 if item.name == role))
    evaluations.append(("SC-6", _STAGE_NAMES["SC-6"],
                        SATISFIED if not ready else UNSATISFIED,
                        "" if not ready else "ready package(s): " + ", ".join(ready),
                        collect_action))

    core_ok, core_reason = _core_fixed_point(snapshot)
    evaluations.append(("SC-7", _STAGE_NAMES["SC-7"],
                        SATISFIED if core_ok else UNSATISFIED, core_reason,
                        None if core_ok else _action(
                            snapshot, "SC-7", "CONVERGE_CORE", None,
                            "canonical Core convergence closure predicate",
                            "DONE/no active or workable present work",
                            "convergence_closure_problems is empty",
                            ".saipen/BOARD.md", ".saipen/STATE.md")))

    for role in (item for item in CREW_ROLES
                 if item.role_class == "producer"):
        health = snapshot.roles[role.name]
        release_integrated = (snapshot.release is not None
                              and role.name
                              in snapshot.release.pre_ship_evidence)
        reviewed = release_integrated or (
            health.get("reviewed_current") if
            role.runtime_kind == "specialized-translate" else
            health.get("outbox", {}).get("package_current")
            and not health.get("outbox", {}).get("ready_current"))
        ready_current = (health.get("ready_current") if
                         role.runtime_kind == "specialized-translate" else
                         health.get("outbox", {}).get("ready_current"))
        action_name = ("COLLECT_TRANSLATE" if role.name == "saitranslate" else
                       "COLLECT_WIKI") if ready_current else (
                       "PREPARE_TRANSLATE" if role.name == "saitranslate" else
                       "PREPARE_WIKI")
        action = None if reviewed else _action(
            snapshot, role.stage, action_name, role.name,
            "pre-ship producer package integrated on current source",
            "reviewed current package" if ready_current else "READY current package",
            "producer_integrated_current", role.outbox_path)
        reason = "" if reviewed else (
            "current READY package awaits integration" if ready_current
            else "no reviewed/current producer package")
        evaluations.append((role.stage, role.name,
                            SATISFIED if reviewed else UNSATISFIED, reason, action))

    sensors_current = all(snapshot.roles[role.name].get("health") == HEALTH_CURRENT
                          for role in CREW_ROLES
                          if role.role_class == "core-review")
    final_fixed = sensors_current and core_ok
    evaluations.append(("SC-10", _STAGE_NAMES["SC-10"],
                        SATISFIED if final_fixed else UNSATISFIED,
                        "" if final_fixed else
                        "Core/sensor evidence changed after producer integration",
                        None if final_fixed else _action(
                            snapshot, "SC-10", "REVERIFY_FIXED_POINT", None,
                            "all sensor/Core evidence current after integration",
                            "fresh Core and worker proof",
                            "Core fixed point and all sensors CURRENT")))

    release_ok, release_reason = _release_current(snapshot)
    evaluations.append(("SC-11", _STAGE_NAMES["SC-11"],
                        SATISFIED if release_ok else UNSATISFIED, release_reason,
                        None if release_ok else _action(
                            snapshot, "SC-11", "SHIP", None,
                            "canonical release bound to this crew epoch/ticket",
                            "COMMITTED release receipt with REMOTE_VERIFIED",
                            "release closure commit is current HEAD")))

    post_ok, post_reason, post_action = _post_ship(snapshot)
    evaluations.append(("SC-12", _STAGE_NAMES["SC-12"],
                        SATISFIED if post_ok else UNSATISFIED,
                        post_reason, post_action))
    evaluations.append(("SC-13", _STAGE_NAMES["SC-13"],
                        SATISFIED, "", _action(
                            snapshot, "SC-13", "FINALIZE", None,
                            "all substantive crew invariants proven",
                            "canonical final LOG+STATE event",
                            "normal intent, DONE, final public crew gate PASS")))
    stages = _reachable(evaluations)
    return stages, _first_action(stages)


def _reachable(evaluations, forced_action: CrewAction | None = None) -> list[dict]:
    blocked_by = None
    stages = []
    for stage, name, status, reason, action in evaluations:
        if blocked_by is not None:
            stages.append({"stage": stage, "name": name, "state": WAITING,
                           "satisfied": False,
                           "reason": f"waiting on predecessor {blocked_by}",
                           "action": None})
            continue
        stages.append({"stage": stage, "name": name, "state": status,
                       "satisfied": status == SATISFIED, "reason": reason,
                       "action": asdict(action) if action else None})
        if status == UNSATISFIED:
            blocked_by = stage
    if forced_action and blocked_by is None:
        stages.append({"stage": "CORE-TASK", "name": "active-core-task",
                       "state": UNSATISFIED, "satisfied": False,
                       "reason": "finish active Core task before crew roles",
                       "action": asdict(forced_action)})
    return stages


def _first_action(stages: list[dict]) -> CrewAction | None:
    for stage in stages:
        raw = stage.get("action")
        if raw and stage.get("state") == UNSATISFIED:
            raw = dict(raw)
            raw["inputs"] = tuple(raw.get("inputs", ()))
            return CrewAction(**raw)
    return None


def crew_plan(project_root: Path | str) -> dict:
    snapshot = crew_snapshot(project_root)
    stages, action = _evaluate(snapshot)
    substantive_ok = all(stage["state"] == SATISFIED
                         for stage in stages if stage["stage"] != "SC-13")
    state = snapshot.state
    finalized = (state.get("execution_intent") in (None, "normal")
                 and "converge_target" not in state
                 and state.get("phase") == "DONE"
                 and _final_marker_problem(snapshot) is None)
    if substantive_ok:
        action = None if finalized else _action(
            snapshot, "SC-13", "FINALIZE", None,
            "all substantive crew invariants proven",
            "canonical final LOG+STATE event",
            "normal intent, DONE, final public crew gate PASS")
    return {"stages": stages,
            "first_unsatisfied": next((stage["stage"] for stage in stages
                                       if stage["state"] == UNSATISFIED), None),
            "action": asdict(action) if action else
                      ({"action": "DONE"} if finalized else None),
            "roles": {name: data.get("health")
                      for name, data in snapshot.roles.items()},
            "source": _source_dict(snapshot),
            "snapshot": {"state": snapshot.input_hashes.get(".saipen/STATE.md"),
                         "board": snapshot.input_hashes.get(".saipen/BOARD.md"),
                         "log_tail": snapshot.log_tail,
                         "stable": snapshot.stable},
            "ok": substantive_ok,
            "finalized": finalized}


def _finalize_problems(snapshot: CrewSnapshot) -> list[str]:
    stages, _action_value = _evaluate(snapshot)
    problems = [f"{stage['stage']}: {stage['reason']}" for stage in stages
                if stage["stage"] != "SC-13" and stage["state"] != SATISFIED]
    if snapshot.state.get("execution_intent") != "converge" \
            or snapshot.state.get("converge_target") != "crew":
        problems.append("active execution intent is not converge/crew")
    return problems


def crew_ready_to_finalize(project_root: Path | str) -> tuple[bool, list[str]]:
    snapshot = crew_snapshot(project_root)
    problems = _finalize_problems(snapshot)
    return not problems, problems


def finalize_crew(project_root: Path | str, dry_run: bool = False) -> Result:
    root = Path(project_root)
    # ONE coherent snapshot owns both the verdict and the CAS tokens handed to
    # the canonical finalizer. A second independent snapshot would open a gap
    # where role evidence could change after the green verdict.
    snapshot = crew_snapshot(root)
    problems = _finalize_problems(snapshot)
    if problems:
        return _refuse("VALIDATION_FAILED",
                       "crew not ready to finalize: " + "; ".join(problems[:4]))
    release = snapshot.release
    epoch = snapshot.epoch
    if release is None or epoch is None:
        return _refuse("VALIDATION_FAILED", "crew release/epoch evidence missing")
    from .operations import finalize_converge_intent
    message = (f"crew finalized {epoch.op_id} release {release.tag} "
               f"@{release.closure_commit}")
    return finalize_converge_intent(
        root, snapshot.state.get("agent") or "saipen-cli", "crew", message,
        ticket_id=epoch.ticket, dry_run=dry_run,
        evidence_preconditions=snapshot.input_hashes)


def crew_apply(project_root: Path | str) -> Result:
    """Execute exactly one bounded mechanical crew action."""
    root = Path(project_root)
    if pending_ops(root):
        return _refuse("RECOVERY_REQUIRED", "unresolved operation; recover first")
    from .fast_check import validate_project
    base_errors = validate_project(root)
    if base_errors:
        return _refuse("VALIDATION_FAILED", "; ".join(base_errors[:5]))
    snapshot = crew_snapshot(root)
    home_problem = _home_problem(snapshot)
    if home_problem:
        return _refuse("HOME_REQUIRED", home_problem)
    if snapshot.state.get("execution_intent") != "converge" \
            or snapshot.state.get("converge_target") != "crew":
        from .operations import set_converge_intent
        intent = set_converge_intent(
            root, snapshot.state.get("agent") or "saipen-cli", "crew")
        if not intent.ok:
            return intent
        plan = crew_plan(root)
        return Result(ok=True, code="CREW_INTENT_SET", op_id=intent.op_id,
                      changed_files=intent.changed_files,
                      data={"plan": plan, "action": plan.get("action")})

    plan = crew_plan(root)
    action = plan.get("action") or {}
    kind = action.get("action")
    role = action.get("role")
    if kind == "SYNC_SHARED":
        return sub_sync(root, snapshot.saipen_home)
    if kind == "SPAWN_ROLE":
        return sub_spawn(root, role, snapshot.saipen_home)
    if kind == "ADOPT_ROLE":
        return sub_adopt(root, role, snapshot.saipen_home)
    if kind == "FINALIZE":
        return finalize_crew(root)
    if kind == "DONE":
        return Result(ok=True, code="CREW_DONE", data={"plan": plan})
    return Result(ok=bool(action), code="CREW_ACTION" if action else "CREW_BLOCKED",
                  message="" if action else "no executable action; inspect first blocker",
                  data={"plan": plan, "action": action})


def _final_marker_problem(snapshot: CrewSnapshot) -> str | None:
    release = snapshot.release
    epoch = snapshot.epoch
    if release is None or epoch is None:
        return "crew epoch/release evidence missing"
    marker = (f"crew finalized {epoch.op_id} release {release.tag} "
              f"@{release.closure_commit}")
    from .log import parse_log_line
    if not any((parsed := parse_log_line(line)) and parsed.get("text") == marker
               for line in snapshot.log_text.splitlines()):
        return "canonical crew finalization event missing"
    return None


def crew_gate_problems(project_root: Path | str) -> list[str]:
    """Public terminal gate: finalized Core state plus immutable crew proof."""
    snapshot = crew_snapshot(project_root)
    problems = []
    state = snapshot.state
    if state.get("execution_intent") not in (None, "normal"):
        problems.append("final execution_intent is not normal")
    if "converge_target" in state:
        problems.append("final state still carries converge_target")
    if state.get("phase") != "DONE" or state.get("task") not in (
            None, "", "none"):
        problems.append("final Core state is not DONE/task none")
    stages, _action_value = _evaluate(snapshot)
    problems.extend(f"{stage['stage']} {stage['name']}: {stage['reason']}"
                    for stage in stages
                    if stage["stage"] != "SC-13"
                    and stage["state"] != SATISFIED)
    marker_problem = _final_marker_problem(snapshot)
    if marker_problem:
        problems.append(marker_problem)
    return problems
