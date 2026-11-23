"""HOST-INTEGRATION-01: one taxonomy and one decision table for host failures.

Defect class: a supported host that can physically run was locked out by its
own integration. `HOST_AUTHORITY_UNAVAILABLE` blocked every Claude Code prompt
before the model saw it, the operator was offered no recovery, and whether a
failure blocked or degraded was decided by matching a substring of a reason
sentence. A new hardening therefore became a new lockout simply by adding a
failure nobody had classified.

This module is the classification. Every failure a host integration can report
is one registered code with its family, its severity, whether the runtime can
recover it, whether ordinary work may continue UNVERIFIED while it stands, what
the runtime attempts by itself, the ONE action left to the operator and what
happens to the prompt when recovery fails. Policy is decided from the code and
never from prose: `decide` reads the table, and a problem that carries no
registered code is BLOCKING, so an unclassified failure cannot be waved through
-- and `problem` refuses to build one, so no engine path can emit it.

The product invariant the table encodes:

    If a supported host can physically run, SAIPEN does not prevent ordinary
    productive work unless continuing would be impossible or actually unsafe.

"Could not be proven" is not "unsafe". An unreachable authority, a stale hook,
an unreadable authority document or a host whose process identity the platform
will not report all leave the operator with a working model and a truthful
UNVERIFIED marker. What stays blocked in every mode is the short list of states
that are conflicts rather than gaps: a forged, replayed or transplanted
capability, and a project binding that contradicts the project it names.

Two admission policies, chosen by the operator and never changed silently:

    degraded   DEGRADED_ALLOWED, the default. Degradable failures permit the
               prompt and claim nothing.
    strict     STRICT. Every failure blocks, after the same automatic recovery,
               with the same exact operator action.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

FAMILY_INSTALLATION = "INSTALLATION"
FAMILY_FRESHNESS = "FRESHNESS"
FAMILY_AUTHORITY = "AUTHORITY"
FAMILY_ADMISSION = "ADMISSION"
FAMILY_BINDING = "BINDING"
FAMILY_HOST_LAUNCH = "HOST_LAUNCH"
FAMILY_RESPONSE = "RESPONSE_ENFORCEMENT"
FAMILY_RECOVERY = "RECOVERY"
FAMILIES = (
    FAMILY_INSTALLATION,
    FAMILY_FRESHNESS,
    FAMILY_AUTHORITY,
    FAMILY_ADMISSION,
    FAMILY_BINDING,
    FAMILY_HOST_LAUNCH,
    FAMILY_RESPONSE,
    FAMILY_RECOVERY,
)

#: What the failure means when nothing softens it.
SEVERITY_INFO = "INFO"
SEVERITY_DEGRADED = "DEGRADED"
SEVERITY_BLOCKING = "BLOCKING"
SEVERITIES = (SEVERITY_INFO, SEVERITY_DEGRADED, SEVERITY_BLOCKING)

MODE_STRICT = "strict"
MODE_DEGRADED = "degraded"
MODES = (MODE_STRICT, MODE_DEGRADED)
#: The product default: a missing policy file is DEGRADED_ALLOWED.
DEFAULT_MODE = MODE_DEGRADED
#: Operator spellings of the same two policies.
MODE_ALIASES = {
    "strict": MODE_STRICT,
    "degraded": MODE_DEGRADED,
    "degraded_allowed": MODE_DEGRADED,
    "degraded-allowed": MODE_DEGRADED,
}
MODE_LABELS = {MODE_STRICT: "STRICT", MODE_DEGRADED: "DEGRADED_ALLOWED"}

DECISION_ADMIT = "ADMIT"
DECISION_ALLOW_DEGRADED = "ALLOW_DEGRADED"
DECISION_BLOCK = "BLOCK"

#: The one operator entry point every recoverable failure names.
REPAIR = "saipen host repair"
DOCTOR = "saipen host doctor"


@dataclass(frozen=True)
class Failure:
    """One registered host-integration failure. Data, never behavior."""

    code: str
    family: str
    severity: str
    #: Can the runtime, or the one operator action, clear it?
    recoverable: bool
    #: May ordinary work continue UNVERIFIED under DEGRADED_ALLOWED?
    degradable: bool
    #: What the runtime attempts by itself before anyone is told.
    auto_recovery: str
    #: The ONE exact operator action that remains.
    operator_action: str
    #: What happens to the prompt when recovery does not succeed.
    fallback: str
    #: One plain sentence for a person who has never heard of admission.
    summary: str


_PROCEED = "the prompt proceeds; the session is marked UNVERIFIED"
_REFUSED = "the prompt is blocked until the operator action is taken"
_NOT_ON_PROMPT_PATH = "no prompt is affected; the native host launch keeps working"


def _f(code, family, severity, recoverable, degradable, auto, action, fallback, summary):
    return Failure(code, family, severity, recoverable, degradable, auto, action, fallback, summary)


_TABLE = (
    # ---------------------------------------------------------- AUTHORITY
    _f(
        "AUTHORITY_UNREACHABLE", FAMILY_AUTHORITY, SEVERITY_DEGRADED, True, True,
        "start the authority service once and retry the handshake",
        REPAIR, _PROCEED,
        "The SAIPEN authority service did not answer.",
    ),
    _f(
        "AUTHORITY_FAULT", FAMILY_AUTHORITY, SEVERITY_DEGRADED, True, True,
        "restart the authority service once and retry the handshake",
        REPAIR, _PROCEED,
        "The SAIPEN authority service answered with a fault.",
    ),
    _f(
        "AUTHORITY_GENERATION_MISMATCH", FAMILY_AUTHORITY, SEVERITY_DEGRADED, True, True,
        "retire the older authority service and start the installed generation",
        REPAIR, _PROCEED,
        "The running authority service belongs to another SAIPEN generation.",
    ),
    _f(
        "AUTHORITY_IMPOSTOR", FAMILY_AUTHORITY, SEVERITY_DEGRADED, True, True,
        "none: an endpoint served by something else is never trusted or replaced",
        DOCTOR, _PROCEED,
        "The authority endpoint is served by a process that is not the SAIPEN service.",
    ),
    _f(
        "AUTHORITY_CLIENT_UNPROVEN", FAMILY_AUTHORITY, SEVERITY_DEGRADED, True, True,
        "none: the authority answered, it could not place this process in the host's hook",
        DOCTOR, _PROCEED,
        "The authority could not prove that this request came from the host's own hook.",
    ),
    _f(
        "AUTHORITY_IDENTITY_UNSUPPORTED", FAMILY_AUTHORITY, SEVERITY_DEGRADED, False, True,
        "none: this platform does not report process identity",
        DOCTOR, _PROCEED,
        "This platform cannot report process identity, so admission cannot be mechanical here.",
    ),
    _f(
        "HOST_AUTHORITY_UNAVAILABLE", FAMILY_AUTHORITY, SEVERITY_DEGRADED, True, True,
        "start the authority service once and retry the handshake",
        REPAIR, _PROCEED,
        "Host authority could not be established for this session.",
    ),
    # ---------------------------------------------------------- ADMISSION
    _f(
        "CAPABILITY_FORGED", FAMILY_ADMISSION, SEVERITY_BLOCKING, True, False,
        "none: a capability the authority never issued is never accepted",
        "remove SAIPEN_ADMISSION_TRANSPORT from the host environment and restart the host",
        _REFUSED,
        "A forged admission capability was presented.",
    ),
    _f(
        "CAPABILITY_REPLAYED", FAMILY_ADMISSION, SEVERITY_BLOCKING, True, False,
        "none: a capability from another authority generation is never accepted",
        "remove SAIPEN_ADMISSION_TRANSPORT from the host environment and restart the host",
        _REFUSED,
        "An admission capability from another authority generation was replayed.",
    ),
    _f(
        "CAPABILITY_EXPIRED", FAMILY_ADMISSION, SEVERITY_BLOCKING, True, False,
        "none: an expired capability that is still presented is never accepted",
        "remove SAIPEN_ADMISSION_TRANSPORT from the host environment and restart the host",
        _REFUSED,
        "An expired admission capability was presented.",
    ),
    _f(
        "CAPABILITY_BINDING_MISMATCH", FAMILY_ADMISSION, SEVERITY_BLOCKING, True, False,
        "none: a capability bound to another project, session, host or model is never accepted",
        "remove SAIPEN_ADMISSION_TRANSPORT from the host environment and restart the host",
        _REFUSED,
        "An admission capability bound to another project or session was presented.",
    ),
    _f(
        "HOST_EVIDENCE_UNAVAILABLE", FAMILY_ADMISSION, SEVERITY_DEGRADED, False, True,
        "none: this host exposes no evidence channel",
        DOCTOR, _PROCEED,
        "This host cannot prove that protocol authority was delivered.",
    ),
    _f(
        "PROTOCOL_ADMISSION_REQUIRED", FAMILY_ADMISSION, SEVERITY_BLOCKING, True, False,
        "re-deliver authority on the next prompt",
        "send the prompt again", _REFUSED,
        "Protocol admission is not current for this session.",
    ),
    _f(
        "PROTOCOL_ADMISSION_TRANSPORT_REQUIRED", FAMILY_ADMISSION, SEVERITY_BLOCKING, True, False,
        "none: establish and invalidate are host-hook operations",
        "send a prompt through the host; the hook establishes admission", _REFUSED,
        "An admission write was requested outside the host's own hook.",
    ),
    # ------------------------------------------------------------ BINDING
    _f(
        "BINDING_FOREIGN_PROJECT", FAMILY_BINDING, SEVERITY_BLOCKING, True, False,
        "none: a session is never attached to a project it does not belong to",
        "start the host in the intended project, or clear SAIPEN_PROJECT_ROOT and "
        "SAIPEN_PROJECT_LINEAGE", _REFUSED,
        "This session is bound to a different SAIPEN project than the one it is running in.",
    ),
    _f(
        "BINDING_CONFLICT", FAMILY_BINDING, SEVERITY_BLOCKING, True, False,
        "none: two contradictory bindings are never guessed between",
        "start the host in the intended project, or clear SAIPEN_PROJECT_ROOT and "
        "SAIPEN_PROJECT_LINEAGE", _REFUSED,
        "Two project bindings contradict each other.",
    ),
    _f(
        "BINDING_CARRIER_INVALID", FAMILY_BINDING, SEVERITY_DEGRADED, True, True,
        "ignore the carrier and use the project the session directory belongs to",
        "clear SAIPEN_PROJECT_ROOT and SAIPEN_PROJECT_LINEAGE, or start the host in the project",
        _PROCEED,
        "A project carrier in the host environment names nothing usable.",
    ),
    _f(
        "PROJECT_IDENTITY_UNREADABLE", FAMILY_BINDING, SEVERITY_DEGRADED, True, True,
        "none on the prompt path", "saipen recover", _PROCEED,
        "The project's SAIPEN identity could not be read.",
    ),
    # ------------------------------------------------------- INSTALLATION
    _f(
        "ENGINE_UNREACHABLE", FAMILY_INSTALLATION, SEVERITY_DEGRADED, True, True,
        "none: the hook cannot repair the runtime it failed to start",
        REPAIR, _PROCEED,
        "The SAIPEN runtime behind this host hook could not be run.",
    ),
    _f(
        "AUTHORITY_DOCUMENT_UNREADABLE", FAMILY_INSTALLATION, SEVERITY_DEGRADED, True, True,
        "none on the prompt path", REPAIR, _PROCEED,
        "A SAIPEN protocol document could not be read from the installed runtime.",
    ),
    _f(
        "AUTHORITY_DOCUMENT_INVALID", FAMILY_INSTALLATION, SEVERITY_DEGRADED, True, True,
        "none on the prompt path", REPAIR, _PROCEED,
        "A SAIPEN protocol document in the installed runtime is not valid.",
    ),
    _f(
        "ACTIVATION_BLOCK_ABSENT", FAMILY_INSTALLATION, SEVERITY_DEGRADED, True, True,
        "none on the prompt path", REPAIR, _PROCEED,
        "The host's instruction file carries no SAIPEN activation block.",
    ),
    _f(
        "HOST_UNREGISTERED", FAMILY_INSTALLATION, SEVERITY_DEGRADED, True, True,
        "none on the prompt path", REPAIR, _PROCEED,
        "This host is not registered in the installed SAIPEN runtime.",
    ),
    _f(
        "HOOK_UNOBSERVABLE", FAMILY_INSTALLATION, SEVERITY_DEGRADED, True, True,
        "none on the prompt path", REPAIR, _PROCEED,
        "The installed host hook could not be inspected.",
    ),
    _f(
        "SKILL_UNRESOLVED", FAMILY_INSTALLATION, SEVERITY_DEGRADED, True, True,
        "none on the prompt path", REPAIR, _PROCEED,
        "A skill the protocol requires could not be found on this machine.",
    ),
    _f(
        "CANONICAL_RUNTIME_SOURCE_UNPROVEN", FAMILY_INSTALLATION, SEVERITY_DEGRADED, True, True,
        "none: an unproven source is never installed from",
        REPAIR, _NOT_ON_PROMPT_PATH,
        "The SAIPEN source this installation was made from could not be proven.",
    ),
    _f(
        "HOST_UNIDENTIFIED", FAMILY_INSTALLATION, SEVERITY_INFO, True, True,
        "none: a source checkout serves every host and is no host itself",
        "name the host: saipen runtime --prelaunch --adapter <id>", _NOT_ON_PROMPT_PATH,
        "This SAIPEN runtime is not the installed runtime of one particular host.",
    ),
    _f(
        "INSTALL_PREFLIGHT_FAILED", FAMILY_INSTALLATION, SEVERITY_DEGRADED, True, True,
        "keep the previous hook generation active; activate nothing",
        REPAIR, _PROCEED,
        "A new host hook failed its self-test and was not activated.",
    ),
    _f(
        "POLICY_INVALID", FAMILY_INSTALLATION, SEVERITY_INFO, True, True,
        "treat the unreadable policy as STRICT, never as a silent downgrade",
        "saipen host mode degraded", _REFUSED,
        "The admission policy file is unreadable, so STRICT is in force.",
    ),
    # ---------------------------------------------------------- FRESHNESS
    _f(
        "HOOK_STALE", FAMILY_FRESHNESS, SEVERITY_DEGRADED, True, True,
        "none on the prompt path; repair and the supported launch path resync it",
        REPAIR, _PROCEED,
        "The installed host hook is not the current SAIPEN generation.",
    ),
    _f(
        "ACTIVATION_BLOCK_STALE", FAMILY_FRESHNESS, SEVERITY_INFO, True, True,
        "none on the prompt path", REPAIR, _PROCEED,
        "The SAIPEN activation block in the host's instruction file is out of date.",
    ),
    _f(
        "HOST_RUNTIME_STALE", FAMILY_FRESHNESS, SEVERITY_DEGRADED, True, True,
        "resync the installed runtime before the next host start",
        REPAIR, _PROCEED,
        "The installed SAIPEN runtime is older than its source.",
    ),
    _f(
        "RUNTIME_STALE", FAMILY_FRESHNESS, SEVERITY_DEGRADED, True, True,
        "resync the installed runtime before the next host start",
        REPAIR, _PROCEED,
        "The installed SAIPEN runtime is older than its source.",
    ),
    _f(
        "PLUGIN_RESTART_REQUIRED", FAMILY_FRESHNESS, SEVERITY_INFO, True, True,
        "none: a loaded plugin is never hot-replaced",
        "restart the host application", _PROCEED,
        "The host is still running the previous SAIPEN generation it loaded at start.",
    ),
    # -------------------------------------------------------- HOST_LAUNCH
    _f(
        "HOST_LAUNCH_REFUSED", FAMILY_HOST_LAUNCH, SEVERITY_INFO, True, True,
        "none: the optional launcher refuses instead of guessing",
        "start the host application normally", _NOT_ON_PROMPT_PATH,
        "The optional SAIPEN launcher could not start this host.",
    ),
    # ----------------------------------------------- RESPONSE_ENFORCEMENT
    _f(
        "CLAUDE_STOP_GATE_UNAVAILABLE", FAMILY_RESPONSE, SEVERITY_INFO, True, True,
        "record the reply as unenforced and let the turn finish",
        DOCTOR, "the reply is delivered and recorded as unenforced",
        "The final-response check could not be consulted for this reply.",
    ),
    _f(
        "CLAUDE_STOP_REENTRY_NO_FAIL_CLOSED", FAMILY_RESPONSE, SEVERITY_INFO, False, True,
        "record the capability boundary; one correction round per turn",
        "none", "the reply is delivered and recorded as unenforced",
        "The host allows one correction round per turn and it is already used.",
    ),
    # ----------------------------------------------------------- RECOVERY
    _f(
        "RUNTIME_RESYNC_FAILED", FAMILY_RECOVERY, SEVERITY_DEGRADED, True, True,
        "keep the previously installed generation", REPAIR, _PROCEED,
        "The installed runtime could not be refreshed from its source.",
    ),
    _f(
        "BOOTSTRAP_INSTALL_FAILED", FAMILY_RECOVERY, SEVERITY_DEGRADED, True, True,
        "keep the previously installed generation", REPAIR, _PROCEED,
        "The canonical installer did not complete.",
    ),
    _f(
        "BOOTSTRAP_INCOMPLETE", FAMILY_RECOVERY, SEVERITY_DEGRADED, True, True,
        "keep the previously installed generation", REPAIR, _PROCEED,
        "The installed runtime still differs from its source after installing.",
    ),
    _f(
        "BOOTSTRAP_PROVENANCE_INVALID", FAMILY_RECOVERY, SEVERITY_DEGRADED, True, True,
        "keep the previously installed generation", REPAIR, _PROCEED,
        "The installer's provenance record does not describe the installed runtime.",
    ),
    _f(
        "REPAIR_INCOMPLETE", FAMILY_RECOVERY, SEVERITY_DEGRADED, True, True,
        "leave every host on its last working generation", DOCTOR, _PROCEED,
        "Repair finished with a host that still needs attention.",
    ),
)

_BY_CODE = {entry.code: entry for entry in _TABLE}

#: Wire refusals of the authority service -> the failure they mean here. A wire
#: code that is absent maps to AUTHORITY_FAULT: an answer nobody classified is a
#: fault of the service, never a pass and never a silent block.
_BROKER_CODES = {
    "BROKER_UNREACHABLE": "AUTHORITY_UNREACHABLE",
    "BROKER_CLIENT_NOT_AUTHENTICATED": "AUTHORITY_CLIENT_UNPROVEN",
    "BROKER_NOT_A_HOST_CLIENT": "AUTHORITY_CLIENT_UNPROVEN",
    "BROKER_PEER_IDENTITY_UNAVAILABLE": "AUTHORITY_IDENTITY_UNSUPPORTED",
    "BROKER_SERVER_UNPROVEN": "AUTHORITY_IMPOSTOR",
    "BROKER_GENERATION_MISMATCH": "AUTHORITY_GENERATION_MISMATCH",
    "BROKER_CAPABILITY_INVALID": "CAPABILITY_FORGED",
    "BROKER_CAPABILITY_REPLAY": "CAPABILITY_REPLAYED",
    "BROKER_CAPABILITY_EXPIRED": "CAPABILITY_EXPIRED",
    "BROKER_BINDING_MISMATCH": "CAPABILITY_BINDING_MISMATCH",
    "BROKER_GENERATION_STALE": "CAPABILITY_REPLAYED",
    "BROKER_BAD_REQUEST": "AUTHORITY_FAULT",
    "BROKER_UNKNOWN_OP": "AUTHORITY_GENERATION_MISMATCH",
    "HANDLER_ERROR": "AUTHORITY_FAULT",
    "BAD_REQUEST": "AUTHORITY_FAULT",
}


def known(code: object) -> bool:
    return isinstance(code, str) and code in _BY_CODE


def get(code: str) -> Failure:
    """The registered failure. An unregistered code is a programming error."""
    return _BY_CODE[code]


def codes() -> tuple[str, ...]:
    return tuple(_BY_CODE)


def table() -> list[dict]:
    """The whole table as plain data, for the doctor view, docs and tests."""
    return [asdict(entry) for entry in _TABLE]


def from_broker(code: object) -> str:
    """The failure a broker wire code means. Never raises, never passes."""
    return _BROKER_CODES.get(str(code or ""), "AUTHORITY_FAULT")


#: The shape of a proof step: a closed machine code such as
#: `NOT_HOST_DESCENDANT`. Anything else a reply carries in that place is text
#: from another generation and is not repeated as a step.
_STEP_RE = re.compile(r"[A-Z][A-Z0-9_]{2,47}")


def as_step(value: object) -> str | None:
    """`value` as a proof step code, or None when it is not one."""
    text = str(value or "")
    return text if _STEP_RE.fullmatch(text) else None


#: One plain sentence per identity step (T-1747). A step says WHO could not be
#: proven, and that is the cause the operator can act on. Without it the notice
#: fell back to the table sentence of the code above the step, and a session
#: whose hook belonged to another configuration profile was told that the
#: authority service "did not answer" -- a service nobody had asked.
_STEP_SUMMARIES = {
    "HOOK_ARTIFACT_MISMATCH": (
        "This session runs a SAIPEN hook that is not its own: it belongs to another "
        "configuration profile, or it is not the installed generation."
    ),
    "HOOK_CHAIN_UNRECOGNIZED": (
        "The SAIPEN hook was not started by the host application the way a host starts its hooks."
    ),
    "HOOK_NOT_FOUND": "No SAIPEN hook invocation was found above this process.",
    "HOOK_HOST_MISMATCH": "The SAIPEN hook names another host than the one that started it.",
    "NOT_HOST_DESCENDANT": "This process was not started by a registered host application.",
    "HOST_IMAGE_UNVERIFIED": (
        "The host application above this process is not signed by a registered publisher."
    ),
    "IDENTITY_UNAVAILABLE": "The process identity needed to prove the host could not be read.",
    "PARENT_REUSED": "A process above this one changed identity while it was being read.",
}


def step_summary(value: object) -> str | None:
    """The plain sentence for an identity step, or None for an unknown one."""
    return _STEP_SUMMARIES.get(str(value or ""))


def problem(component: str, code: str, reason: str, step: object = None) -> dict:
    """One typed problem. Refuses an unregistered code where it is written, so
    the failure shows up in the unit that introduced it and not in the field.

    `step` names WHICH proof refused under that code (T-1649): one failure code
    can cover several steps, and a diagnostic that repeats only the code cannot
    tell a forged client from a process walk that lost its parent.
    """
    if code not in _BY_CODE:
        raise KeyError(f"unregistered host-integration failure code: {code!r}")
    typed = {"component": str(component), "code": code, "reason": str(reason)}
    if as_step(step):
        typed["step"] = as_step(step)
    return typed


def degradable(problems: object) -> bool:
    """Is every problem a registered, degradable failure?

    An empty list is vacuously degradable. Anything that is not a typed problem
    with a registered code makes the whole set non-degradable: policy is never
    decided from a sentence, and never in favor of something unclassified.
    """
    if not isinstance(problems, (list, tuple)):
        return False
    for item in problems:
        if not isinstance(item, dict):
            return False
        entry = _BY_CODE.get(str(item.get("code") or ""))
        if entry is None or not entry.degradable:
            return False
    return True


def blocking(problems: object) -> list[dict]:
    """The problems that block in every mode (unregistered ones included)."""
    found: list[dict] = []
    for item in problems if isinstance(problems, (list, tuple)) else []:
        entry = _BY_CODE.get(str(item.get("code") or "")) if isinstance(item, dict) else None
        if entry is None or not entry.degradable:
            found.append(item if isinstance(item, dict) else {"reason": str(item)})
    return found


def normalize_mode(value: object) -> str | None:
    """The canonical mode for an operator spelling, or None when unrecognized."""
    return MODE_ALIASES.get(str(value or "").strip().lower().replace(" ", "_"))


def decide(mode: str, problems: object, *, admitted: bool = False) -> str:
    """The one decision table: ADMIT, ALLOW_DEGRADED or BLOCK.

    `admitted` is the authority's own positive answer and outranks nothing: a
    blocking problem beside it still blocks. With no problem and no admission
    the session is merely not admitted yet, which STRICT blocks and
    DEGRADED_ALLOWED lets through unverified.
    """
    listed = list(problems) if isinstance(problems, (list, tuple)) else [problems]
    if blocking(listed):
        return DECISION_BLOCK
    if admitted and not listed:
        return DECISION_ADMIT
    if mode == MODE_DEGRADED:
        return DECISION_ALLOW_DEGRADED
    return DECISION_BLOCK


def first_action(problems: object) -> str:
    """The single operator action for a set of problems: the blocking one wins,
    then the first that has an action at all."""
    listed = [item for item in (problems or []) if isinstance(item, dict)]
    ordered = blocking(listed) + [item for item in listed if item not in blocking(listed)]
    for item in ordered:
        entry = _BY_CODE.get(str(item.get("code") or ""))
        if entry is not None and entry.operator_action and entry.operator_action != "none":
            return entry.operator_action
    return DOCTOR


def describe(problems: object) -> list[dict]:
    """Each problem with its table row attached, for diagnostics."""
    described: list[dict] = []
    for item in problems if isinstance(problems, (list, tuple)) else []:
        if not isinstance(item, dict):
            continue
        entry = _BY_CODE.get(str(item.get("code") or ""))
        described.append({**item, **(asdict(entry) if entry else {"family": None})})
    return described


__all__ = [
    "DECISION_ADMIT",
    "DECISION_ALLOW_DEGRADED",
    "DECISION_BLOCK",
    "DEFAULT_MODE",
    "DOCTOR",
    "FAMILIES",
    "MODES",
    "MODE_ALIASES",
    "MODE_DEGRADED",
    "MODE_LABELS",
    "MODE_STRICT",
    "REPAIR",
    "SEVERITIES",
    "Failure",
    "as_step",
    "blocking",
    "codes",
    "decide",
    "degradable",
    "describe",
    "first_action",
    "from_broker",
    "get",
    "known",
    "normalize_mode",
    "problem",
    "step_summary",
    "table",
]
