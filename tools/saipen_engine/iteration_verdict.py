"""Public machine-facing iteration verdict (T-1619 finishing repair).

The ONE canonical projection a host iteration controller queries after every
model turn, so the host never has to manufacture canonical booleans itself::

    saipen iteration --json [--caps-file PATH] [--cap NAME=VALUE] [--executor ID]

``goal_complete``, ``executable_action_remains``, ``operator_due`` and
``valve_tripped`` are derived here from the canonical owners -- STATE, BOARD,
the shared router, autonomy recall and the goal authority -- never from prose
and never by duplicated protocol logic in the host. The projection delegates
the final precedence to ``iteration.decide_turn``.

Capability truth comes from the candidate harness, mapped onto semantic
capabilities (MODEL != EXECUTOR): literal host tool names are translated, and
an unknown or absent mandatory capability fails closed. Identity keys (model,
provider, route name) never decide.
"""

from __future__ import annotations

import functools
import re
from collections.abc import Mapping
from pathlib import Path

from . import iteration
from .board import parse_board
from .router import route_next
from .state import binding_brake, parse_state_or_error

#: Version of the machine contract. A host that requires a newer schema than
#: this must fail safe (never VALID_TERMINAL); see
#: ``verdict_allows_goal_complete_ui``.
ITERATION_VERDICT_SCHEMA = 1

#: Closed semantic capability vocabulary for operational continuation.
FILESYSTEM_READ = "filesystem_read"
FILESYSTEM_WRITE = "filesystem_write"
PROCESS_EXECUTION = "process_execution"
GIT = "git"
PYTHON = "python"
PATCH_APPLICATION = "patch_application"
#: SRC-189 R005: a canonical route to `saipen continue --json`. A shell is one
#: such route; a host that exposes the control plane as its own tool is
#: another, so it is a capability of its own and not a synonym for a shell.
SAIPEN_CONTROL = "saipen_control"

SEMANTIC_CAPABILITIES = frozenset(
    {
        FILESYSTEM_READ,
        FILESYSTEM_WRITE,
        PROCESS_EXECUTION,
        GIT,
        PYTHON,
        PATCH_APPLICATION,
        SAIPEN_CONTROL,
    }
)

#: SRC-189 R003/R016/R017: what a phase executes beyond reading the
#: repository and reaching the control plane. An executor is never rejected
#: for a capability the current step does not require: SCOUT reads, VERIFY and
#: REVIEW run the project's checks, and none of the three edits the tree. A
#: phase not named here keeps the whole set -- BUILD and SHIP mutate, and an
#: unknown phase fails closed.
_PHASE_EXECUTION: dict[str, frozenset] = {
    "SCOUT": frozenset(),
    "VERIFY": frozenset({PROCESS_EXECUTION}),
    "REVIEW": frozenset({PROCESS_EXECUTION}),
}
_TREE_MUTATION = frozenset({FILESYSTEM_WRITE, PATCH_APPLICATION})

#: Closed vocabulary of the admission contract carried by the verdict.
ADMISSION_ADMIT = "ADMIT"
ADMISSION_REJECT = "REJECT"
ADMISSION_UNASSESSED = "UNASSESSED"
NEXT_NONE = "NONE"
NEXT_FAILOVER = "FAILOVER"
NEXT_NO_COMPATIBLE_EXECUTOR = "NO_COMPATIBLE_EXECUTOR"

#: Host tool names onto semantic capabilities. A host without a literal
#: "patch" tool but with safe filesystem_write capability satisfies
#: ``patch_application`` through that mapping. ``read_tabular`` and
#: ``system_todo_write`` deliberately grant nothing: tabular reads plus todo
#: writes are not repository mutation execution. Anything unlisted grants
#: nothing (fail closed for unknown mandatory capabilities).
_RUNS_PROCESSES = frozenset({PROCESS_EXECUTION, SAIPEN_CONTROL})
_HOST_TOOL_ALIASES: dict[str, frozenset] = {
    # The whole filesystem is read AND write, and an executor that can write
    # files can apply an edit: the narrower `filesystem_write` always granted
    # patch application and the broader name did not, so an executor that
    # advertised exactly what STATE `requires` names was rejected (SRC-189 R015).
    "filesystem": frozenset({FILESYSTEM_READ, FILESYSTEM_WRITE, PATCH_APPLICATION}),
    "filesystem_read": frozenset({FILESYSTEM_READ}),
    "file_read": frozenset({FILESYSTEM_READ}),
    "read": frozenset({FILESYSTEM_READ}),
    "filesystem_write": frozenset({FILESYSTEM_WRITE, PATCH_APPLICATION}),
    "file_write": frozenset({FILESYSTEM_WRITE, PATCH_APPLICATION}),
    "write_file": frozenset({FILESYSTEM_WRITE, PATCH_APPLICATION}),
    # Whatever runs a process can run the CLI, so it reaches the control plane.
    "shell": _RUNS_PROCESSES,
    "bash": _RUNS_PROCESSES,
    "sh": _RUNS_PROCESSES,
    "terminal": _RUNS_PROCESSES,
    "process_execution": _RUNS_PROCESSES,
    "command_execution": _RUNS_PROCESSES,
    "exec": _RUNS_PROCESSES,
    # A trusted control-plane transport that is not a shell (SRC-189 R005).
    "saipen_control": frozenset({SAIPEN_CONTROL}),
    "saipen": frozenset({SAIPEN_CONTROL}),
    "saipen_cli": frozenset({SAIPEN_CONTROL}),
    "control_plane": frozenset({SAIPEN_CONTROL}),
    "patch": frozenset({PATCH_APPLICATION}),
    "patch_application": frozenset({PATCH_APPLICATION}),
    "apply_patch": frozenset({PATCH_APPLICATION}),
    "git": frozenset({GIT}),
    "python": frozenset({PYTHON}),
    "python3": frozenset({PYTHON}),
}

#: STATE `requires` names what the PROJECT needs of a repository, in the same
#: words. `filesystem` there asks for the tree to be read and written; whether
#: the current phase edits it is the phase's fact, not the project's.
_STATE_TOKEN_REQUIRES: dict[str, frozenset] = {
    **_HOST_TOOL_ALIASES,
    "filesystem": frozenset({FILESYSTEM_READ, FILESYSTEM_WRITE}),
}

#: Keys that name WHO the candidate is, never WHAT it can do. They are
#: ignored by normalization even when truthy: MODEL != EXECUTOR.
_IDENTITY_KEYS = frozenset(
    {
        "model",
        "provider",
        "route",
        "candidate",
        "id",
        "name",
        "executor",
        "incarnation",
        "variant",
        "effort",
        "harness",
    }
)


def _cap_truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "yes", "1", "available", "granted")
    if value is None:
        return False
    return bool(value)


def normalize_capabilities(raw: Mapping[str, object] | None) -> frozenset:
    """Map one candidate's advertised tools onto semantic capabilities.

    Only explicit advertised truth counts; an absent, unknown or falsy tool
    grants nothing (fail closed). Identity keys never grant.
    """
    granted: set[str] = set()
    if not isinstance(raw, Mapping):
        return frozenset()
    for key, value in raw.items():
        name = str(key).strip().lower()
        if name in _IDENTITY_KEYS:
            continue
        if not _cap_truthy(value):
            continue
        granted.update(_HOST_TOOL_ALIASES.get(name, frozenset()))
    return frozenset(granted & SEMANTIC_CAPABILITIES)


#: Bounds on what an executor's own tool names may put into a verdict.
_EXPLICIT_NAME_CHARS = 64
_EXPLICIT_NAME_LIMIT = 64


def explicit_grants(raw: Mapping[str, object] | None) -> frozenset:
    """Advertised tool names no alias translates, granted as themselves.

    A requirement this module has no word for (a STATE token such as `gui`
    or `dotnet`) stays required under its own name, and the comment beside it
    always said only an explicit grant satisfies it -- but nothing carried the
    grant, so such a project could admit no executor at all. An executor that
    advertises the same name, truthfully, now satisfies it; a name nothing
    requires grants nothing and is merely shown (SRC-189 R002, R004, R012).
    """
    if not isinstance(raw, Mapping):
        return frozenset()
    names: list[str] = []
    for key, value in raw.items():
        name = str(key).strip().lower()
        if (
            not name
            or len(name) > _EXPLICIT_NAME_CHARS
            or name in _IDENTITY_KEYS
            or name in _HOST_TOOL_ALIASES
            or name in SEMANTIC_CAPABILITIES
            or not _cap_truthy(value)
        ):
            continue
        names.append(name)
    return frozenset(sorted(names)[:_EXPLICIT_NAME_LIMIT])


def granted_capabilities(raw: Mapping[str, object] | None) -> frozenset:
    """Everything one candidate was granted: translated tools and own names."""
    return normalize_capabilities(raw) | explicit_grants(raw)


def required_for_state(state_requires: object, phase: object = None) -> frozenset:
    """The semantic capability set operational continuation needs here.

    STATE ``requires`` carries the repository half (filesystem/git/python);
    every operational step additionally needs a route to the control plane.
    What else is needed is the PHASE's fact (``_PHASE_EXECUTION``): a phase
    that reads or runs is not charged for editing the tree, so a read-only
    executor is admitted to SCOUT and rejected at BUILD, where the edit is.
    With no phase, or one this table does not name, the whole set is
    required. Unknown STATE tokens grant nothing on the candidate side, so
    they stay required (fail closed).
    """
    if isinstance(state_requires, (list, tuple, set, frozenset)):
        names = [str(item) for item in state_requires]
    else:
        names = []
    required: set[str] = set()
    for name in names:
        token = name.strip().lower()
        if not token or token in _IDENTITY_KEYS:
            continue
        # STATE tokens with no alias (e.g. a future requirement) must still
        # be satisfiable only by an explicit grant: keep the raw token so no
        # candidate passes it by accident.
        required.update(_STATE_TOKEN_REQUIRES.get(token, frozenset({token})))
    required.add(SAIPEN_CONTROL)
    execution = _PHASE_EXECUTION.get(str(phase or "").strip().upper())
    if execution is None:
        required.update({PROCESS_EXECUTION, PATCH_APPLICATION})
    else:
        required.difference_update(_TREE_MUTATION)
        required.update(execution)
    return frozenset(required)


#: T-1663 (SRC-189 R004, R016-R018): what ONE ticket's steps need beyond the
#: phase. The BOARD field `requires:` is a comma list of `name[@PHASE[+PHASE]]`
#: -- a name with no phase holds in every phase, a scoped one only in the
#: phases it names -- plus the single word `read_only`: the ticket reads and
#: reaches the control plane and nothing else, in every phase (R017).
READ_ONLY = "read_only"
#: SRC-189 R002: the canonical names a ticket and an executor share, one per
#: inventory class the source lists. The first seven are translated from host
#: tool names above; the rest are met only by an executor that advertises the
#: same name (`explicit_grants`). A ticket may still name something unlisted
#: (`dotnet`) -- `saipen ticket requires` reports it, so a typo is visible.
CAPABILITY_INVENTORY = (
    PROCESS_EXECUTION,
    FILESYSTEM_READ,
    FILESYSTEM_WRITE,
    PATCH_APPLICATION,
    SAIPEN_CONTROL,
    GIT,
    PYTHON,
    "repository_inspection",
    "git_read",
    "git_write",
    "build_execution",
    "test_execution",
    "windows_native",
    "gui",
    "browser",
    "file_transfer",
    "visual_inspection",
)
#: A field the grammar cannot read: required, and granted by nobody, so a
#: malformed declaration never reads as no requirement (fail closed).
TICKET_REQUIRES_INVALID = "ticket_requires_invalid"
_READ_ONLY_SET = frozenset({FILESYSTEM_READ, SAIPEN_CONTROL})
_REQUIRE_NAME = re.compile(r"[a-z][a-z0-9_]{0,63}")


@functools.lru_cache(maxsize=1)
def _known_phases() -> frozenset:
    from .registry import load_registry, require_mapping, require_string_list

    return frozenset(require_string_list(require_mapping(load_registry(), "phases"), "all"))


def parse_ticket_requires(raw: object) -> tuple[dict[str, tuple[str, ...]], bool]:
    """`({name: phases}, read_only)` for one `requires:` value; ValueError if malformed.

    Phases come from REGISTRY `phases.all`; an empty phase tuple means every
    phase. Names are lower-cased, phases upper-cased, duplicates merged.
    """
    known = _known_phases()
    spec: dict[str, tuple[str, ...]] = {}
    read_only = False
    for part in str(raw or "").split(","):
        item = part.strip()
        if not item:
            continue
        name, at, scope = item.partition("@")
        name = name.strip().lower()
        if not _REQUIRE_NAME.fullmatch(name) or name in _IDENTITY_KEYS:
            raise ValueError(f"requires: {item!r} is not a capability name")
        phases = tuple(p.strip().upper() for p in scope.split("+")) if at else ()
        if at and (not phases or any(p not in known for p in phases)):
            raise ValueError(f"requires: {item!r} names no known phase")
        if name == READ_ONLY:
            if at:
                raise ValueError("requires: read_only holds in every phase; it takes no @PHASE")
            read_only = True
            continue
        if name in spec and (not spec[name] or not phases):
            spec[name] = ()
        else:
            spec[name] = tuple(dict.fromkeys((*spec.get(name, ()), *phases)))
    return spec, read_only


def format_ticket_requires(spec: dict[str, tuple[str, ...]], read_only: bool) -> str:
    """The one stored spelling of a parsed value; empty when nothing is required."""
    items = [READ_ONLY] if read_only else []
    items += [name + ("@" + "+".join(phases) if phases else "") for name, phases in spec.items()]
    return ", ".join(items)


def required_for_ticket(base: frozenset, raw: object, phase: object = None) -> frozenset:
    """The phase's required set with one ticket's `requires:` folded in.

    `read_only` replaces the phase set with reading plus the control plane;
    every other name adds what it translates to (a host tool name maps as a
    STATE token does, an unknown name stays required under its own name).
    """
    if raw in (None, ""):
        return base
    try:
        spec, read_only = parse_ticket_requires(raw)
    except ValueError:
        return base | {TICKET_REQUIRES_INVALID}
    current = str(phase or "").strip().upper()
    required = set(_READ_ONLY_SET if read_only else base)
    for name, phases in spec.items():
        if not phases or current in phases:
            required.update(_STATE_TOKEN_REQUIRES.get(name, frozenset({name})))
    return frozenset(required)


def admit_normalized(
    candidate: Mapping[str, object] | None,
    required: object,
) -> tuple[bool, frozenset]:
    """Admit one candidate's raw tool map against the required set.

    Normalizes first, then delegates to the canonical ``iteration.admit``
    primitive. Pure: reads nothing but its arguments, writes nothing.
    """
    required_set = frozenset(required) if required is not None else frozenset()
    granted = {name: True for name in granted_capabilities(candidate)}
    return iteration.admit(granted, required_set)


def _unreadable(reason: str) -> dict:
    """Fail-safe verdict when canonical state cannot be read whole.

    A provider returning final text is only MODEL_TURN_FINISHED; an unreadable
    checkpoint is never evidence of SAIPEN_GOAL_FINISHED, so this pauses at
    the runtime level instead of completing.
    """
    return {
        "schema_version": ITERATION_VERDICT_SCHEMA,
        "decision": iteration.RUNTIME_PAUSED,
        "goal_complete": False,
        "executable_action_remains": False,
        "operator_due": False,
        "valve_tripped": False,
        "requires_human": False,
        "canonical_task": "none",
        "phase": "UNKNOWN",
        "next_action": "NONE",
        "execution_intent": "UNKNOWN",
        "executor_assessed": False,
        "executor_compatible": False,
        "executor_id": None,
        "missing_capabilities": [],
        "required_capabilities": [],
        "executor_capabilities": None,
        "admission": {"result": ADMISSION_UNASSESSED, "missing": [], "next": NEXT_NONE},
        "route_reason": "state-unreadable",
        "route_action": "NONE",
        "state_readable": False,
        "state_detail": reason,
        "recall_decision": None,
    }


def _recall_decision(root: Path) -> str | None:
    """The autonomy-recall turn-entry decision, or None when unavailable.

    Consumes the canonical owner (``cold_recovery.auto_recall``) instead of
    re-deriving turn-entry truth; any failure degrades to None, never to a
    STOP and never to a kick.
    """
    try:
        from .cold_recovery import auto_recall
    except (ImportError, ValueError):
        return None
    try:
        recall = auto_recall(root, {})
    except Exception:
        return None
    if not isinstance(recall, dict):
        return None
    turn = recall.get("turn")
    if isinstance(turn, dict):
        decision = turn.get("decision")
        return str(decision) if decision else None
    return None


def project_iteration_verdict(
    root: Path | str,
    *,
    executor_caps: Mapping[str, object] | None = None,
    runtime_info_path: Path | str | None = None,
    executor_id: str | None = None,
    all_candidates_exhausted: bool = False,
) -> dict:
    """Derive the closed iteration verdict from canonical SAIPEN state.

    Read-only: opens STATE.md/BOARD.md (and LOG.md through recall) and
    writes nothing. ``executor_caps`` is the CURRENT candidate's advertised
    tool map; when omitted the executor is unassessed (never a mismatch).
    ``runtime_info_path`` is a ``saipen runtime`` JSON document whose
    ``capabilities`` object is used when no explicit caps are given.
    """
    base = Path(root)
    try:
        state_text = (base / ".saipen" / "STATE.md").read_text(encoding="utf-8-sig")
        board_text = (base / ".saipen" / "BOARD.md").read_text(encoding="utf-8-sig")
    except OSError as exc:
        return _unreadable(f"canonical checkpoint not readable: {exc}")
    state, state_error = parse_state_or_error(state_text)
    if state_error or not state:
        return _unreadable(f"STATE not parseable whole: {state_error or 'empty'}")
    try:
        board = parse_board(board_text)
        tickets = board["tickets"]
    except (ValueError, KeyError, AttributeError, TypeError) as exc:
        return _unreadable(f"BOARD not parseable whole: {exc}")
    if board.get("errors"):
        verdict = _unreadable("BOARD carries parse errors: " + "; ".join(board["errors"][:3]))
        verdict["decision"] = iteration.OPERATOR_WAIT
        verdict["requires_human"] = True
        verdict["route_reason"] = "board-malformed"
        verdict["phase"] = str(state.get("phase") or "UNKNOWN")
        verdict["canonical_task"] = str(state.get("task") or "none")
        verdict["next_action"] = str(state.get("next_action") or "NONE")
        return verdict

    from .operations import GOAL_TICKET_CAP, GOAL_WAVE_CAP
    from . import goal_authority

    grant_errors = goal_authority.prove(base, state)
    if grant_errors:
        return _unreadable("continuation grant invalid: " + "; ".join(grant_errors))
    home_checkpoint = goal_authority.protocol_home_checkpoint(base, state)
    checkpoint = goal_authority.persistent(state) or home_checkpoint

    phase = str(state.get("phase") or "UNKNOWN")
    task = state.get("task")
    canonical_task = str(task) if task not in (None, "") else "none"
    next_action = str(state.get("next_action") or "NONE")
    intent = state.get("execution_intent")

    valve_tripped = bool(
        intent == "goal" and not checkpoint
        and (
            int(state.get("goal_waves") or 0) >= GOAL_WAVE_CAP
            or int(state.get("goal_tickets") or 0) >= GOAL_TICKET_CAP
        )
    )

    empty_todo = not any(t.get("section") == "## TODO" for t in tickets.values())
    brake = binding_brake(state, empty_todo=empty_todo)
    from .state import parse_wait

    operator_due = brake is not None and not (
        checkpoint and brake[0] == "wait" and parse_wait(next_action) == "safety valve"
    )

    recall = _recall_decision(base)
    if recall in ("OPERATOR_WAIT", "USER_INPUT"):
        operator_due = True

    try:
        routed = route_next(state_text, board_text)
    except Exception:
        routed = {}
    route_reason = str(routed.get("reason") or "unknown")
    route_action = str(routed.get("action") or "NONE")
    executable_behavior = str(routed.get("executable_behavior") or "")
    if routed.get("ok") is True:
        executable_action_remains = (
            executable_behavior != "RESTATE_AND_STOP"
            and route_reason
            not in (
                "maintain",
                "bootstrap",
                "read-only-mode",
                "wait",
                "unblock",
                "checkpoint-invalid",
                "state-malformed",
                "board-malformed",
                "capability-invalid",
            )
            and route_action != "saipen status"
        ) or (home_checkpoint and route_reason == "wait")
    else:
        # Recovery work is real executable work: the next iteration runs it.
        executable_action_remains = (
            route_reason in ("recovery-pending", "recovery-conflict")
            and route_action == "saipen recover"
        )

    doing = [t for t in tickets.values() if t.get("section") == "## DOING"]
    blocked = [t for t in tickets.values() if t.get("section") == "## BLOCKED"]
    todo = [t for t in tickets.values() if t.get("section") == "## TODO"]
    goal_complete = bool(
        phase == "DONE"
        and canonical_task == "none"
        and not doing
        and not blocked
        and not todo
    )

    caps: Mapping[str, object] | None = executor_caps
    if caps is None and runtime_info_path is not None:
        try:
            import json

            blob = Path(runtime_info_path).read_bytes()
            if len(blob) > 65536:
                raise ValueError("runtime info exceeds 64 KiB")
            document = json.loads(blob.decode("utf-8"))
            if isinstance(document, dict) and isinstance(
                document.get("capabilities"), dict
            ):
                caps = document["capabilities"]
        except (OSError, ValueError, UnicodeDecodeError):
            caps = None
    required = required_for_state(state.get("requires"), phase)
    active = tickets.get(canonical_task) if canonical_task != "none" else None
    if isinstance(active, dict):
        required = required_for_ticket(
            required, (active.get("fields") or {}).get("requires"), phase
        )
    if caps is None:
        assessed = False
        compatible = True
        missing: frozenset = frozenset()
        granted: frozenset | None = None
    else:
        assessed = True
        compatible, missing = admit_normalized(caps, required)
        granted = granted_capabilities(caps)
    if all_candidates_exhausted and (not assessed or not compatible):
        compatible = False

    decision = iteration.decide_turn(
        executor_compatible=compatible,
        goal_complete=goal_complete,
        executable_action_remains=executable_action_remains,
        operator_due=operator_due,
        valve_tripped=valve_tripped,
        all_candidates_exhausted=bool(all_candidates_exhausted and not compatible),
    )
    return {
        "schema_version": ITERATION_VERDICT_SCHEMA,
        "decision": decision,
        "goal_complete": goal_complete,
        "executable_action_remains": executable_action_remains,
        "operator_due": operator_due,
        "valve_tripped": valve_tripped,
        "requires_human": decision == iteration.OPERATOR_WAIT,
        "canonical_task": canonical_task,
        "phase": phase,
        "next_action": next_action,
        "execution_intent": str(intent) if intent else "normal",
        "executor_assessed": assessed,
        "executor_compatible": compatible,
        "executor_id": executor_id,
        "missing_capabilities": sorted(missing),
        # SRC-189 R011/R022: the admission as a contract a host reads, not a
        # sentence it interprets -- what this step requires, what the executor
        # was granted from the tools it actually advertised, and what follows.
        "required_capabilities": sorted(required),
        "executor_capabilities": None if granted is None else sorted(granted),
        "admission": {
            "result": (
                ADMISSION_UNASSESSED
                if not assessed
                else ADMISSION_ADMIT
                if compatible
                else ADMISSION_REJECT
            ),
            "missing": sorted(missing),
            "next": (
                NEXT_NONE
                if compatible
                else NEXT_NO_COMPATIBLE_EXECUTOR
                if all_candidates_exhausted
                else NEXT_FAILOVER
            ),
        },
        "route_reason": route_reason,
        "route_action": route_action,
        "state_readable": True,
        "recall_decision": recall,
    }


def verdict_allows_goal_complete_ui(verdict: object) -> bool:
    """May the host UI report goal completion on this verdict? One gate.

    True only for a known-schema verdict whose decision is VALID_TERMINAL
    with proven terminality on readable state. Unknown schemas, unknown
    decisions, missing fields and unreadable state all refuse: an unknown
    verdict is never evidence of completion.
    """
    if not isinstance(verdict, dict):
        return False
    if verdict.get("schema_version") != ITERATION_VERDICT_SCHEMA:
        return False
    if verdict.get("decision") not in iteration.TURN_DECISIONS:
        return False
    if verdict.get("state_readable") is False:
        return False
    if verdict.get("goal_complete") is not True:
        return False
    return iteration.may_report_goal_complete(str(verdict.get("decision")))
