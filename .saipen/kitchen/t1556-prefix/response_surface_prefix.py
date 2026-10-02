"""The default SAIPEN response surface -- EXEC-RESPONSE-01 (T-1419).

One schema for every ordinary user-facing operational boundary: a control
block that renders vertically in a fixed semantic order, with no prose before
it. The rule is prose in ``saipen/EXECUTION.md``; this module is its
behavioural projection so the contract can be decided without re-reading the
document, exactly as the guard shares one classifier with the router.

Two questions the surface answers mechanically:

* Is a rendered control block well-formed -- mandatory fields present, in
  canonical order, ``DETAILS`` optional and last, and a ``WAIT`` that actually
  tells the human what to do?
* Should the agent return to the user at all, or continue executing? A control
  block with no required human action and a canonically executable next step is
  NOT a response boundary (preserves T-1416).
"""

from __future__ import annotations

import re
from dataclasses import dataclass


RULE_ID = "EXEC-RESPONSE-01"

#: The mandatory control surface, in canonical order. Every field is present on
#: every ordinary response.
MANDATORY_FIELDS = (
    "STATUS",
    "RESULT",
    "BLOCKER",
    "OPERATOR ACTION",
    "NEXT EXACT ACTION",
    "VALIDATION",
)

#: Optional fields, rendered only AFTER the mandatory surface.
OPTIONAL_FIELDS = ("DETAILS",)

FIELD_ORDER = MANDATORY_FIELDS + OPTIONAL_FIELDS

_BLOCKER_CODE = re.compile(r"^[A-Z][A-Z0-9_]* -- \S")
_VAGUE_ACTIONS = frozenset(
    {"continue as appropriate", "investigate further", "proceed with next steps", "retry if needed"}
)
_AGENT_COMMAND = re.compile(
    r"^\s*(?:please\s+)?(?:run|execute|invoke|use\s+)?\s*`?"
    r"(?:saipen(?:\.cmd|\.py)?|python(?:\d+(?:\.\d+)*)?|py|git|uv|ruff|"
    r"pytest|npm|node|powershell|pwsh|cmd|bash)(?:`)?(?:\s|$)",
    re.IGNORECASE,
)
_AGENT_INSTRUCTION = re.compile(
    r"^\s*(?:please\s+)?(?:run|execute|invoke|continue|proceed|retry|investigate)\s+"
    r"(?:(?:the|an?)\s+)?(?:(?:next|remaining|internal|canonical)\s+)*"
    r"(?:command|phase|step|processing|tests?|validator|verification)\b",
    re.IGNORECASE,
)

#: The values that mean "no action" for the two always-present action fields.
NONE_VALUES = frozenset({"", "NONE"})

FIELD_LINE_BUDGETS = {
    "RESULT": 3,
    "BLOCKER": 1,
    "OPERATOR ACTION": 1,
    "NEXT EXACT ACTION": 1,
    "VALIDATION": 5,
    # DETAILS stays permitted for the intentional detailed-report path, but it
    # is bounded: an unbounded DETAILS is the overflow bucket the surface
    # exists to remove.
    "DETAILS": 8,
}
def _is_none(value: object) -> bool:
    return str(value if value is not None else "").strip().upper() in NONE_VALUES


@dataclass(frozen=True)
class OperationalBoundary:
    status: str
    result: str
    blocker: str
    operator_action: str
    next_exact_action: str
    validation: str
    details: str = ""

    def fields(self) -> dict[str, str]:
        values = {
            "STATUS": self.status,
            "RESULT": self.result,
            "BLOCKER": self.blocker,
            "OPERATOR ACTION": self.operator_action,
            "NEXT EXACT ACTION": self.next_exact_action,
            "VALIDATION": self.validation,
        }
        if self.details:
            values["DETAILS"] = self.details
        return values


def render_boundary(
    boundary: OperationalBoundary,
    *,
    current_validation: str | None = None,
) -> str:
    """Assemble one operational handback from typed fields, then validate it."""
    fields = boundary.fields()
    rendered = "\n".join(f"{key}\n{value.strip()}" for key, value in fields.items())
    errors = response_errors(
        rendered, current_validation=current_validation
    )
    if errors:
        raise ValueError("; ".join(errors))
    return rendered


def response_errors(
    rendered: str,
    *,
    executable_action_remains: bool = False,
    response_boundary: bool = True,
    current_validation: str | None = None,
    current_phase: str | None = None,
    current_task: str | None = None,
    current_blocker: str | None = None,
    operator_due: bool = False,
) -> list[str]:
    """Validate the actual text a host will return, including its first byte."""
    if not isinstance(rendered, str) or not rendered:
        return ["empty operational response"]
    lines = rendered.splitlines()
    errors: list[str] = []
    if not lines or lines[0] != "STATUS":
        errors.append("prose before STATUS or missing STATUS header")
    headings = [(index, line) for index, line in enumerate(lines) if line in FIELD_ORDER]
    names = [name for _, name in headings]
    for name in MANDATORY_FIELDS:
        if names.count(name) != 1:
            errors.append(f"{name} must occur exactly once")
    if names.count("DETAILS") > 1:
        errors.append("DETAILS must occur at most once")
    positions = [FIELD_ORDER.index(name) for name in names]
    if positions != sorted(positions):
        errors.append("fields render outside the canonical order")
    if "DETAILS" in names and names[-1] != "DETAILS":
        errors.append("DETAILS must render last")
    values: dict[str, str] = {}
    for offset, (line_index, name) in enumerate(headings):
        end = headings[offset + 1][0] if offset + 1 < len(headings) else len(lines)
        values[name] = "\n".join(lines[line_index + 1 : end]).strip()
        if not values[name]:
            errors.append(f"{name} has no value")
    blocker = values.get("BLOCKER", "")
    if blocker and not _is_none(blocker) and not _BLOCKER_CODE.match(blocker):
        errors.append("BLOCKER needs a canonical code and bounded reason")
    operator_action = values.get("OPERATOR ACTION", "")
    if _AGENT_COMMAND.match(operator_action) or _AGENT_INSTRUCTION.match(operator_action):
        errors.append("OPERATOR ACTION cannot assign an agent command to the human")
    next_action = values.get("NEXT EXACT ACTION", "")
    if next_action.strip().lower() in _VAGUE_ACTIONS:
        errors.append("NEXT EXACT ACTION is vague")
    if values.get("STATUS", "").upper().startswith("WAIT") and _is_none(operator_action):
        errors.append("WAIT without OPERATOR ACTION is invalid")
    if should_continue(
        operator_action=operator_action,
        executable_action_remains=executable_action_remains,
        response_boundary=response_boundary,
    ):
        errors.append("eligible autonomous action remains; returning control is invalid")
    for name, budget in FIELD_LINE_BUDGETS.items():
        if name not in values:
            continue
        content = [line for line in values[name].splitlines() if line.strip()]
        if len(content) > budget:
            errors.append(
                f"{name} exceeds {budget} content line(s) -- the schema is bounded "
                "over field content, not over the mandatory labels"
            )
    for name in ("BLOCKER", "OPERATOR ACTION", "NEXT EXACT ACTION"):
        value = values.get(name, "")
        if "\n" not in value and value.strip().startswith("-"):
            errors.append(f"{name} must be one action, not a list")
    if current_validation:
        first_validation = values.get("VALIDATION", "").splitlines()
        first_token = (
            first_validation[0].strip().split()[0]
            if first_validation and first_validation[0].strip()
            else ""
        )
        if first_token != current_validation:
            errors.append(f"VALIDATION must start with current {current_validation}")
    current_status = values.get("STATUS", "").upper()
    if current_phase and current_phase.upper() not in {"DONE", "BLOCKED"}:
        if current_phase.upper() not in current_status:
            errors.append(f"STATUS must name current phase {current_phase}")
    if current_task and current_task.lower() != "none" and current_task not in current_status:
        errors.append(f"STATUS must name current task {current_task}")
    if current_blocker and current_blocker.strip() and not _is_none(current_blocker):
        # A project with no blocker reports the canonical `none` sentinel. That
        # is not a blocker CODE, so demanding the response name it refused every
        # `BLOCKER: NONE` surface on a healthy project -- the case the surface is
        # written for. `_is_none` is the one "no blocker" test.
        code = current_blocker.split(" -- ", 1)[0].split(":", 1)[0].strip()
        if code and not blocker.startswith(code):
            errors.append(f"BLOCKER must name current {code}")
    if operator_due and _is_none(operator_action):
        errors.append("OPERATOR ACTION is required by the current route")
    if executable_action_remains and not operator_due and not _is_none(operator_action):
        errors.append("OPERATOR ACTION is not due on the current route")
    return errors


def surface_errors(fields: dict, *, status: str = "") -> list[str]:
    """Why a control block does not satisfy EXEC-RESPONSE-01, or []."""
    if not isinstance(fields, dict):
        return ["control surface must be a field mapping"]
    keys = [key for key in fields if key in FIELD_ORDER]
    errors: list[str] = []
    missing = [key for key in MANDATORY_FIELDS if key not in fields]
    if missing:
        errors.append("missing mandatory field(s): " + ", ".join(missing))
    positions = [FIELD_ORDER.index(key) for key in keys]
    if positions != sorted(positions):
        errors.append("fields render outside the canonical order")
    if "DETAILS" in fields and keys and keys[-1] != "DETAILS":
        errors.append("DETAILS must render last")
    # A WAIT that names no human action is the exact ambiguity the surface
    # exists to remove: the human cannot discover whether they must act.
    if str(status).strip().upper().startswith("WAIT") and _is_none(
        fields.get("OPERATOR ACTION")
    ):
        errors.append("WAIT without OPERATOR ACTION is invalid")
    return errors


def should_continue(
    *,
    operator_action: object,
    executable_action_remains: bool,
    response_boundary: bool,
) -> bool:
    """May the agent continue internally instead of returning to the user?

    True only when NO human action is required, a canonically executable action
    remains, and the moment is not a true response boundary. A required human
    action, an exhausted route, or a genuine boundary all return the control
    surface instead.
    """
    if response_boundary:
        return False
    if not _is_none(operator_action):
        return False
    return bool(executable_action_remains)


# ---------------------------------------------------------------------------
# Host final-response gates (T-1551): ONE classifier over the outgoing text.
#
# A host Stop/text hook sees only the final message. It must decide whether
# EXEC-RESPONSE-01 governs that message at all -- and it must decide it HERE,
# in the canonical authority, never in an adapter-local copy of the rules.
# `classify_final_response` answers the only new question (does this text
# claim operational finality?) and then delegates every structural rule to
# `response_errors`, so no host adapter can drift from the contract by
# reimplementing it. There is no second response validator.

CLASS_VALID_BOUNDARY = "VALID_BOUNDARY"
CLASS_INVALID_OPERATIONAL_PROSE = "INVALID_OPERATIONAL_PROSE"
CLASS_AUTONOMOUS_HANDBACK = "AUTONOMOUS_HANDBACK"
CLASS_ORDINARY_CHAT = "ORDINARY_CHAT"
RESPONSE_CLASSES = (
    CLASS_VALID_BOUNDARY,
    CLASS_INVALID_OPERATIONAL_PROSE,
    CLASS_AUTONOMOUS_HANDBACK,
    CLASS_ORDINARY_CHAT,
)

#: Free-form report shapes that claim the response IS an operational boundary:
#: control-surface label usage (`STATUS: ...`) and canonical blocker codes
#: (`SOME_CODE -- reason`) outside a rendered block.
_CONTROL_LABEL_USE = re.compile(
    r"(?im)^\s*(?:STATUS|RESULT|BLOCKER|OPERATOR ACTION|NEXT EXACT ACTION|"
    r"VALIDATION|DETAILS)\s*(?::|-|--)\s*\S"
)
_BLOCKER_CODE_LINE = re.compile(r"(?m)^\s*[A-Z][A-Z0-9_]{2,} -- \S")

#: The autonomy failures of `response_errors`, restated as class markers so a
#: host maps its verdict without parsing rule prose.
_AUTONOMY_ERROR_MARKERS = (
    "eligible autonomous action remains",
    "OPERATOR ACTION is not due on the current route",
    "OPERATOR ACTION is required by the current route",
)


def claims_operational_finality(text: object) -> bool:
    """Does this text claim to BE a canonical operational boundary/report?

    True for a rendered control block (a FIELD_ORDER heading on its own line)
    and for free-form operational report shapes (label usage, blocker codes).
    Ordinary conversation carries none of these.
    """
    if not isinstance(text, str) or not text.strip():
        return False
    if any(line.strip() in FIELD_ORDER for line in text.splitlines()):
        return True
    return bool(_CONTROL_LABEL_USE.search(text) or _BLOCKER_CODE_LINE.search(text))


def classify_final_response(
    rendered: object,
    *,
    operational_turn: bool,
    executable_action_remains: bool = False,
    **check_context: object,
) -> tuple[str, list[str]]:
    """The ONE host-gate verdict over an outgoing final response.

    Returns ``(class, errors)`` with exactly one of ``RESPONSE_CLASSES``:

    * ``VALID_BOUNDARY`` -- a well-formed operational boundary; the host lets
      it through.
    * ``INVALID_OPERATIONAL_PROSE`` -- the response is governed by
      EXEC-RESPONSE-01 (an operational turn, or text claiming operational
      finality) but is not an accepted boundary.
    * ``AUTONOMOUS_HANDBACK`` -- an operational turn returns control while
      eligible canonical work remains (T-1416 autonomy).
    * ``ORDINARY_CHAT`` -- ordinary non-operational conversation; outside the
      response contract entirely.

    ``operational_turn`` is the turn-context fact only the host/canonical
    state knows (the turn executed canonical work, or canonical state routes
    it as AUTO_KICK / OPERATOR_WAIT / RECOVER). ``executable_action_remains``
    is the canonical automation fact; it is enforced ONLY on operational
    turns, mirroring the OpenCode gate's ``enforceAutonomy``.
    """
    text = rendered if isinstance(rendered, str) else ""
    claims = claims_operational_finality(text)
    if not operational_turn and not claims:
        return CLASS_ORDINARY_CHAT, []
    # T-1553: an OPERATOR ACTION that is DUE settles the autonomy question --
    # handing control back to a human who owes an answer is the required
    # behaviour, not a premature yield. Without this the classifier and the
    # plain checker disagreed on the SAME text for the same project: a fresh
    # INIT project (routing says `cc` stays legal, but the human owes the first
    # goal) passed `response check --auto-eligibility` and failed
    # `response check --classify --auto-eligibility`, so one host accepted the
    # handback and another livelocked on it. `operator_due` arrives in the check
    # context, so it is read here rather than re-derived.
    if check_context.get("operator_due"):
        executable_action_remains = False
    if operational_turn and executable_action_remains:
        return CLASS_AUTONOMOUS_HANDBACK, [
            "eligible autonomous action remains; returning control is invalid"
        ]
    if not claims:
        return CLASS_INVALID_OPERATIONAL_PROSE, [
            "operational turn returned free-form prose; an operational response "
            "must render the canonical control surface"
        ]
    errors = response_errors(
        text,
        executable_action_remains=False,
        response_boundary=True,
        **check_context,
    )
    if not errors:
        return CLASS_VALID_BOUNDARY, []
    if any(
        marker in error
        for error in errors
        for marker in _AUTONOMY_ERROR_MARKERS
    ):
        return CLASS_AUTONOMOUS_HANDBACK, errors
    return CLASS_INVALID_OPERATIONAL_PROSE, errors
