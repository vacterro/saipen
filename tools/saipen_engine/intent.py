"""SAIPEN protocol intent handlers.

Protocol shortcuts (qq, ee, qqq, eee) are semantic operations, not CLI
aliases that cease to exist when one CLI dispatcher lacks a handler.

qq = ENSURE saiWiki READY
ee = ENSURE saiTranslate READY
qqq = ENSURE saiWiki READY + run crew through SC-9 integration + ship
eee = ENSURE saiTranslate READY + run crew through SC-9 integration + ship

Every public entry point resolves the CURRENT-SESSION capability ONCE at the
command boundary (CORE-001) and fails closed before any mutation. The
autonomous convergence loop never fabricates role evidence (CORE-003), never
destroys pending worker tickets (CORE-004), and under ``--dry-run`` executes
ZERO writers (CORE-002). Every crew planner action maps to exactly one
canonical operation or an intentional structured refusal -- never UNKNOWN_ACTION
(CORE-007).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def _negotiate_capability(project_root: Path) -> str:  # pragma: no cover - removed
    """Deprecated hard-coded resolver. Use capability.negotiate_capability."""
    raise RuntimeError(
        "intent._negotiate_capability is removed; resolve capability at the CLI "
        "boundary via saipen_engine.capability.negotiate_capability and thread it "
        "through every intent entry point (CORE-001)."
    )


def _agent_for(project_root: Path) -> str:
    from .state import parse_state

    state_path = project_root / ".saipen" / "STATE.md"
    try:
        state_text = state_path.read_text(encoding="utf-8-sig")
        state = parse_state(state_text)
        return state.get("agent", "saipen-autonomous")
    except Exception:
        return "saipen-autonomous"


def _resolve_saipen_home(root: Path) -> str:
    """Resolve the canonical saipen_home from STATE, falling back to root."""
    from .state import parse_state

    state_path = root / ".saipen" / "STATE.md"
    try:
        state = parse_state(state_path.read_text(encoding="utf-8-sig"))
        home = state.get("saipen_home", "")
        if home:
            return home
    except Exception:
        pass
    return str(root)


def _role_dir(root: Path, role: str) -> Path:
    """CORE-006: resolve a role's storage through the canonical registry.

    Producers (saitranslate / saiwiki) use ``producer_namespace``; generic subs
    use ``SUBS_REL``. No role-type-specific path guessing.
    """
    from . import producer as P
    from . import subs

    if role in P.PRODUCERS:
        return P.producer_namespace(root, role)
    return root / subs.SUBS_REL / role


def _norm(result) -> tuple[bool, str]:
    """Normalize a Result object or dict to (ok, code)."""
    if hasattr(result, "ok"):
        ok = bool(result.ok)
        code = getattr(result, "code", "") or ""
        return ok, (code if isinstance(code, str) else "")
    if isinstance(result, dict):
        return bool(result.get("ok", False)), result.get("code", "")
    return False, ""


def ensure_producer_ready(
    project_root: Path,
    role: str,
    dry_run: bool = False,
    as_json: bool = False,
    current_capability: object = None,
) -> dict:
    """Ensure a named producer is READY.

    Protocol intent: prepare/reprepare so that at least one READY package
    carries the current source_head + source_tree_fingerprint + role_revision.

    CORE-001: the capability is negotiated at the CLI boundary and threaded in;
    a read-only session refuses any mutation. CORE-006: role storage is resolved
    through the canonical registry and ``sub_spawn`` receives the full contract.
    """
    from .capability import capability_error, may_mutate, negotiate_capability
    from . import subs

    root = Path(project_root)
    capability = negotiate_capability() if current_capability is None else current_capability
    err = capability_error(capability)
    if err is not None:
        return {"ok": False, "code": "CAPABILITY_INVALID", "message": err}

    role_dir = _role_dir(root, role)

    # 1. Instance exists?
    if not role_dir.is_dir():
        if dry_run:
            return {
                "ok": True,
                "code": "PRODUCER_SPAWN_PLAN",
                "message": f"would spawn {role} instance",
            }
        if not may_mutate(capability):
            return {
                "ok": False,
                "code": "CAPABILITY_READ_ONLY",
                "message": f"read-only session cannot spawn {role}",
            }
        saipen_home = _resolve_saipen_home(root)
        result = subs.sub_spawn(
            root, role, saipen_home, agent=_agent_for(root), dry_run=False
        )
        ok, code = _norm(result)
        if not ok:
            return {
                "ok": False,
                "code": "PRODUCER_SPAWN_FAILED",
                "message": f"failed to spawn {role} instance",
                "detail": code,
            }

    # 2. Sync shared contract (only when actually mutating).
    if not dry_run and may_mutate(capability):
        saipen_home = _resolve_saipen_home(root)
        sync_result = subs.sub_sync(root, saipen_home, agent=_agent_for(root), dry_run=False)
        ok, code = _norm(sync_result)
        if not ok:
            return {
                "ok": False,
                "code": "PRODUCER_SYNC_FAILED",
                "message": f"failed to sync {role}",
                "detail": code,
            }

    # 3. Already current?
    outbox_path = role_dir / "kitchen" / "OUTBOX.md"
    if outbox_path.is_file():
        try:
            from freshness import compute_source_identity

            source_id = compute_source_identity(root)
            current_head = source_id.source_head
            current_tree = source_id.source_tree_fingerprint
        except Exception:
            current_head = None
            current_tree = None
        current_role = subs.current_local_role_revision(root, role)
        outbox_text = outbox_path.read_text(encoding="utf-8")
        outbox_model = subs.parse_outbox(outbox_text)
        for pkg in outbox_model.packages:
            if getattr(pkg, "status", "") not in ("ready", "reviewed"):
                continue
            pkg_head = pkg.fields.get("source_head", "")
            pkg_tree = pkg.fields.get("source_tree_fingerprint", "")
            pkg_role = pkg.fields.get("role_revision", "")
            if (
                current_head
                and current_tree
                and current_role
                and pkg_head == current_head
                and pkg_tree == current_tree
                and pkg_role == current_role
            ):
                return {
                    "ok": True,
                    "code": "ALREADY_READY",
                    "message": f"{role} already has a current READY package",
                    "package": pkg.package_id,
                }

    # 4. Stale/missing -> reprepare (or plan under dry-run).
    if dry_run:
        return {"ok": True, "code": "PREPARE_PLAN", "message": f"would prepare {role}"}
    if not may_mutate(capability):
        return {
            "ok": False,
            "code": "CAPABILITY_READ_ONLY",
            "message": f"read-only session cannot prepare {role}",
        }
    return _prepare_role(root, role, capability)


def _prepare_producer_role(root: Path, role: str) -> dict:
    """CORE-003: a REAL producer prepare for saitranslate / saiwiki.

    Consumes the role's ACTUAL emitted evidence (its kitchen OUTBOX) and
    publishes a genuine, traceable READY package through the canonical producer
    pipeline (StagingGeneration + publish). It NEVER writes a synthetic
    ``verified: PASS`` entry: if the role has not emitted evidence, it refuses.
    """
    from . import producer as P
    from . import subs

    ns = P.producer_namespace(root, role)
    ns.mkdir(parents=True, exist_ok=True)
    (ns / "kitchen").mkdir(parents=True, exist_ok=True)
    outbox_path = ns / "kitchen" / "OUTBOX.md"
    if not outbox_path.is_file():
        return {
            "ok": False,
            "code": "ROLE_NOT_RUN",
            "message": (
                f"{role} emitted no preparation evidence; autonomous intent "
                "refuses to synthesize a package"
            ),
        }

    try:
        from freshness import compute_source_identity

        sid = compute_source_identity(root)
        head = sid.source_head
        tree = sid.source_tree_fingerprint
        model = sid.discovery_model
    except Exception:
        head = tree = model = ""

    role_rev = subs.current_local_role_revision(root, role) or ""
    payload = outbox_path.read_bytes()
    rel_outbox = str(outbox_path.relative_to(root)).replace("\\", "/")
    before = P.file_sha256(outbox_path)

    pkg = P.build_package(
        producer=role,
        role_revision=role_rev,
        base_source_head=head,
        base_source_tree_fingerprint=tree,
        base_discovery_model=model,
        scope="autonomous-prepare",
        read_set={},
        write_set={rel_outbox: before},
        epoch=P.ProducerEpoch.claim(ns),
    )
    gen = P.StagingGeneration(ns, role).begin()
    gen.set_package(pkg)
    gen.add_payload(rel_outbox, payload)
    result = gen.publish()
    if not result.get("ok"):
        return {
            "ok": False,
            "code": "PREPARE_FAILED",
            "message": result.get("detail", "producer publish failed"),
        }
    return {
        "ok": True,
        "code": "PRODUCER_PREPARED",
        "message": f"{role} prepared (real evidence)",
        "package_identity": result.get("package_identity"),
    }


def _prepare_role(root: Path, role: str, current_capability: object = None) -> dict:
    """Prepare a role for the autonomous loop.

    CORE-003: this MUST NOT fabricate a ``verified: PASS`` OUTBOX block. Producer
    roles run the REAL producer pipeline; every other role consumes only the
    evidence its runner actually emitted, or refuses cleanly.
    """
    from . import producer as P
    from . import subs

    if role in P.PRODUCERS:
        return _prepare_producer_role(root, role)

    outbox_path = root / subs.SUBS_REL / role / "kitchen" / "OUTBOX.md"
    if outbox_path.is_file():
        return {
            "ok": True,
            "code": "ROLE_EVIDENCE_PRESENT",
            "message": f"{role} already has real preparation evidence",
        }
    return {
        "ok": False,
        "code": "ROLE_NOT_RUN",
        "message": (
            f"{role} has not emitted preparation evidence; autonomous intent "
            "refuses to synthesize a package"
        ),
    }


def _integrate_producer(root: Path, producer_role: str) -> dict:
    """Serialize Core integration of a producer's READY packages.

    Delegates to the canonical producer integration path. Without a Core
    apply_write callback the pipeline returns a structured REFUSED (never a
    fabricated success) -- Core integration is a deliberate Core-owned mutation.
    """
    from . import producer as P

    ns = P.producer_namespace(root, producer_role)
    pkgs = P.StagingGeneration.list_ready(ns)
    if not pkgs:
        return {
            "ok": False,
            "code": "NO_READY_PACKAGE",
            "message": f"no READY {producer_role} package to integrate",
        }
    return P.integrate_packages_core(pkgs, root, dry_run=False)


def _execute_crew_action(
    root: Path,
    action_type: str,
    action_role: str | None,
    capability: str,
    agent: str,
    saipen_home: str,
    dry_run: bool = False,
) -> object:
    """CORE-007: the single authoritative autonomous action executor.

    Every crew planner action maps to exactly one canonical operation (or an
    intentional structured terminal refusal). There is no UNKNOWN_ACTION branch:
    an unhandled action is a programming error surfaced as a structured refusal
    so the loop fails loudly instead of stalling.
    """
    from . import subs
    from . import producer as P
    from .crew import finalize_crew

    if action_type == "RUN_ROLE":
        return _prepare_role(root, action_role or "", capability)
    if action_type == "COLLECT_ROLE":
        return subs.sub_collect(root, action_role or "", agent=agent, dry_run=dry_run)
    if action_type == "CONVERGE_CORE":
        return _try_satisfy_convergence(root, dry_run=dry_run)
    if action_type == "PREPARE_TRANSLATE":
        return _prepare_role(root, "saitranslate", capability)
    if action_type == "PREPARE_WIKI":
        return _prepare_role(root, "saiwiki", capability)
    if action_type in ("INTEGRATE_TRANSLATE", "INTEGRATE_WIKI"):
        prod = "saitranslate" if "TRANSLATE" in action_type else "saiwiki"
        return _integrate_producer(root, prod)
    if action_type == "SYNC_SHARED":
        return subs.sub_sync(root, saipen_home, agent=agent, dry_run=dry_run)
    if action_type == "SPAWN_ROLE":
        return subs.sub_spawn(root, action_role or "", saipen_home, agent=agent, dry_run=dry_run)
    if action_type == "ADOPT_ROLE":
        return subs.sub_adopt(root, action_role or "", saipen_home, agent=agent, dry_run=dry_run)
    if action_type == "FINALIZE":
        return finalize_crew(root, current_agent=agent)
    if action_type in ("DEFER_FOR_CREW", "CLEAR_WAIT_ROLE"):
        # Core-owned ticket operations: the autonomous shortcut refuses to
        # synthesize them and defers to the explicit crew command.
        return {
            "ok": False,
            "code": "ACTION_NEEDS_CREW",
            "message": f"{action_type} is a Core-owned ticket operation; run `saipen crew`",
        }
    if action_type in ("DISPOSE_REVIEW", "REVERIFY_FIXED_POINT"):
        # Review disposition / fixed-point re-verification: planned, no synthetic
        # write. The loop continues; the progress tracker guards against stalls.
        return {
            "ok": True,
            "code": action_type,
            "message": f"{action_type} planned; no synthetic write",
        }
    if action_type == "SHIP":
        # Ship is a deliberate, gated Core publication; the autonomous shortcut
        # must not perform it. Structured human-in-the-loop refusal.
        return {
            "ok": False,
            "code": "SHIP_BLOCKED",
            "message": "autonomous loop will not ship; run `saipen ship` explicitly",
        }
    if action_type == "CONTINUE_CORE":
        return {"ok": True, "code": "CONTINUE_CORE", "message": "continue core work"}
    # Enumerated vocabulary exhausted: programming error -> structured refusal.
    return {
        "ok": False,
        "code": "UNHANDLED_ACTION",
        "message": f"no executor for crew action {action_type!r}",
    }


def autonomous_crew_loop(
    project_root: Path,
    dry_run: bool = False,
    as_json: bool = False,
    current_capability: object = None,
) -> dict:
    """Autonomous crew loop (sc / qqq / eee / cc semantics).

    ENSURE FULL CREW CONVERGENCE/CLOSURE.

    CORE-001: capability resolved once at the boundary; read-only refuses all
    mutations. CORE-002: under ``dry_run`` the loop derives the planned action
    sequence and executes ZERO writers (byte-identical filesystem). CORE-007:
    every action dispatches through ``_execute_crew_action`` to exactly one
    canonical operation or a structured refusal.
    """
    from .autonomy import ProgressTracker
    from .capability import capability_error, may_mutate, negotiate_capability
    from .crew import crew_plan
    from . import subs

    root = Path(project_root)
    capability = negotiate_capability() if current_capability is None else current_capability
    err = capability_error(capability)
    if err is not None:
        return {"ok": False, "code": "CAPABILITY_INVALID", "message": err}

    agent = _agent_for(root)
    saipen_home = _resolve_saipen_home(root)
    tracker = ProgressTracker(max_iterations=60)
    prev_plan_signature = ""

    while True:
        # Read-only crew plan.
        try:
            plan = crew_plan(root, current_capability=capability, current_agent=agent)
        except Exception as exc:
            return {
                "ok": False,
                "code": "FATAL_CORRUPTION",
                "message": f"crew plan failed: {exc}",
                "terminal_state": "fatal_corruption",
            }

        # Terminal: crew complete / finalized.
        if plan.get("crew_complete"):
            return {
                "ok": True,
                "code": "CREW_COMPLETE" if not dry_run else "CREW_DRY_PLAN",
                "message": "crew convergence complete",
                "terminal_state": "crew_complete",
                "iterations": tracker.iterations,
                "dry_run": dry_run,
            }
        if plan.get("finalized"):
            return {
                "ok": True,
                "code": "CREW_FINALIZED" if not dry_run else "CREW_DRY_PLAN",
                "message": "crew finalized",
                "terminal_state": "done",
                "iterations": tracker.iterations,
                "dry_run": dry_run,
            }

        first_unsat = plan.get("first_unsatisfied", "")
        roles = plan.get("roles", {})
        action_info = plan.get("action")
        action_type = (action_info or {}).get("action", "")
        action_role = (action_info or {}).get("role")

        # CORE-002: dry-run is a ZERO-WRITE plan. Record the next action and the
        # full plan, then return without executing any writer.
        if dry_run:
            return {
                "ok": True,
                "code": "CREW_DRY_PLAN",
                "message": "crew plan (dry-run, zero-write)",
                "planned_action": action_type or None,
                "planned_role": action_role,
                "terminal_state": "planned",
                "iterations": tracker.iterations,
                "plan": plan,
            }

        # CORE-001: a read-only session may not execute any mutating crew action.
        if not may_mutate(capability):
            return {
                "ok": False,
                "code": "CAPABILITY_READ_ONLY",
                "message": (
                    "read-only session cannot execute crew actions; the "
                    "negotiated capability is read-only (CORE-001)"
                ),
                "terminal_state": "done",
                "iterations": tracker.iterations,
            }

        # No action means the planner refuses to act on this stage.
        if not action_info and first_unsat:
            repaired = _autonomous_repair_stage(root, first_unsat, plan)
            if repaired:
                prev_plan_signature = ""
                continue
            return {
                "ok": False,
                "code": "STAGE_UNREPAIRABLE",
                "message": (
                    f"{first_unsat}: {plan.get('stages', [{}])[0].get('reason', 'unknown')} "
                    "-- no mechanical repair available"
                ),
                "terminal_state": "done",
                "iterations": tracker.iterations,
            }
        if not first_unsat and not plan.get("crew_complete"):
            return {
                "ok": True,
                "code": "CREW_IDLE",
                "message": "no action available and not crew_complete",
                "terminal_state": "done",
                "iterations": tracker.iterations,
            }

        # Progress detection.
        plan_signature = json.dumps(
            {
                "first_unsat": first_unsat,
                "roles": roles,
                "action_type": action_type,
                "action_role": action_role,
            },
            sort_keys=True,
        )
        if plan_signature == prev_plan_signature and tracker.iterations > 0:
            if not tracker.record(plan_signature, f"{first_unsat}:{action_type}", "plan unchanged", plan.get("code", "")):
                return {
                    "ok": False,
                    "code": "LOOP_STALLED",
                    "message": (
                        f"loop stalled: crew plan state unchanged after "
                        f"{tracker.iterations} iterations; "
                        f"stage={first_unsat} action={action_type} "
                        f"role={action_role}; manual intervention required"
                    ),
                    "terminal_state": "loop_stalled",
                    "iterations": tracker.iterations,
                    "plan": plan,
                }
        prev_plan_signature = plan_signature

        result = _execute_crew_action(
            root, action_type, action_role, capability, agent, saipen_home, dry_run=False
        )
        ok, code = _norm(result)

        if not ok:
            # A blocked stage can sometimes be repaired by clearing pending work
            # WITHOUT destroying it (CORE-004).
            if action_type == "RUN_ROLE":
                _auto_repair_role(root, action_role or "")
            return {
                "ok": False,
                "code": code or "CREW_ACTION_FAILED",
                "message": f"action {action_type} for {first_unsat} failed",
                "terminal_state": "done",
                "iterations": tracker.iterations,
                "detail": result if isinstance(result, dict) else {"code": code},
            }

        # Success: continue to the next iteration -- the plan should change.
        continue


def _autonomous_repair_stage(root: Path, stage: str, plan: dict) -> bool:
    """Repair a crew stage that the planner refuses to act on.

    Returns True if a repair was made and the loop should retry.
    """
    stages = plan.get("stages", [])
    for s in stages:
        if s["stage"] != stage:
            continue
        reason = s.get("reason", "")
        break
    else:
        return False

    # SC-1 instances: invalid role -> fix malformed OUTBOX entries
    if stage == "SC-1" and "invalid" in reason.lower():
        roles = plan.get("roles", {})
        for role_name, health in roles.items():
            if health == "INVALID":
                return _fix_invalid_outbox(root, role_name)

    return False


def _fix_invalid_outbox(root: Path, role: str) -> bool:
    """Fix a malformed OUTBOX that makes a role INVALID.

    Scans for packages with headings that don't match OUTBOX_HEADING_RE
    and removes them (they are always autonomously-generated garbage).
    """
    from . import subs

    outbox_path = root / subs.SUBS_REL / role / "kitchen" / "OUTBOX.md"
    if not outbox_path.is_file():
        return False

    text = outbox_path.read_text(encoding="utf-8")
    model = subs.parse_outbox(text, role)

    if not model.errors:
        return False

    lines = text.split("\n")
    valid_starts = set()
    for pkg in model.packages:
        heading = f"## {pkg.package_id}"
        for i, line in enumerate(lines):
            if line.startswith(heading):
                valid_starts.add(i)
                break

    result_lines = []
    in_valid_package = False
    for i, line in enumerate(lines):
        if line == "# OUTBOX":
            result_lines.append(line)
            continue
        if line.startswith("## "):
            in_valid_package = i in valid_starts
        if in_valid_package or not line.startswith("## "):
            result_lines.append(line)

    new_text = "\n".join(result_lines)
    new_model = subs.parse_outbox(new_text, role)
    if new_model.errors:
        new_text = "# OUTBOX\n"
        for pkg in model.packages:
            new_text += pkg.block + "\n"

    outbox_path.write_text(new_text, encoding="utf-8")
    return True


def _auto_repair_role(root: Path, role: str) -> bool:
    """CORE-004: attempt auto-repair for a role WITHOUT destroying pending work.

    The previous implementation regex-deleted the worker's ``## TODO`` section
    (including its unchecked tickets) and rewrote them as a generic deferred
    marker -- silent project-state data loss. Pending worker tickets must
    survive failures. This routine therefore performs NO destructive mutation:
    it returns False so the loop reports a deterministic blocker and preserves
    every pending ticket. Deferral, when legitimate, must go through a journaled
    canonical board/ticket operation, not a regex rewrite.
    """
    board_path = root / ".saipen" / "extensions" / "subs" / role / "BOARD.md"
    if not board_path.is_file():
        return False
    # Intentionally does not modify the board. Pending tickets are preserved.
    return False


def _try_satisfy_convergence(root: Path, dry_run: bool = False) -> dict:
    """Try to satisfy convergence requirements."""
    try:
        from .convergence import convergence_verdict

        verdict = convergence_verdict(root)
        if verdict.ok:
            return {"ok": True, "message": "convergence already satisfied"}
    except Exception:
        pass

    import subprocess

    try:
        validate_path = root / "tools" / "validate.py"
        if validate_path.is_file():
            result = subprocess.run(
                [sys.executable, str(validate_path)],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(root / "tools"),
            )
            if result.returncode == 0:
                return {"ok": True, "message": "validator passed"}
            else:
                fail_count = result.stdout.count("FAIL:")
                return {
                    "ok": False,
                    "message": f"validator has {fail_count} failures",
                }
    except Exception as exc:
        return {
            "ok": False,
            "message": f"validator execution failed: {exc}",
        }

    return {
        "ok": False,
        "message": "convergence cannot be satisfied automatically",
    }
