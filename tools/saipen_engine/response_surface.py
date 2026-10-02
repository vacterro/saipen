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
import shlex
from dataclasses import dataclass

from .efficiency import LINE_CHAR_BUDGET as _EFFICIENCY_LINE_CHARS
from .efficiency import line_problem as _efficiency_line_problem
from .guard_events import saipen_line_problem
from .phases import ALL_PHASES

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

#: Optional fields, rendered only AFTER the mandatory surface. EFFICIENCY
#: (T-1576) is the derived `efficiency` KPI line: final boundaries only, one
#: line, never quality evidence; DETAILS stays last.
OPTIONAL_FIELDS = ("EFFICIENCY", "DETAILS")

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

# ---------------------------------------------------------------------------
# T-1556 #1: DETAILS AUTHORIZATION IS A MACHINE FACT, NOT A STYLE CHOICE.
#
# A line budget alone made `DETAILS` free on every ordinary reply: the schema
# permitted eight lines wherever it liked. Authorization is one canonical
# machine-readable value owned HERE, derived from the HUMAN's request (never
# from the outgoing prose, which is the thing being authorized) and defaulting
# to forbidden. A host that supplies nothing gets the closed default.
DETAIL_MODE_NONE = "NONE"
DETAIL_MODE_REPORT = "EXPLICIT_REPORT"
DETAIL_MODE_AUDIT = "AUDIT"
DETAIL_MODE_HANDOFF = "HANDOFF"
DETAIL_MODE_BOUNDARY = "EXCEPTIONAL_BOUNDARY"
DETAIL_MODES = (
    DETAIL_MODE_NONE,
    DETAIL_MODE_REPORT,
    DETAIL_MODE_AUDIT,
    DETAIL_MODE_HANDOFF,
    DETAIL_MODE_BOUNDARY,
)

#: Only a direct request earns the exception. Searching anywhere in ingress
#: made "fix audit logging", negations and quoted examples authorize essays.
#: Ambiguous wording stays on the compact path; callers can transport an
#: explicitly authorized closed mode instead of guessing from a noun.
_DETAIL_REQUEST_PREFIX = (
    r"(?i)^\s*(?:please\s+)?(?:(?:can|could|would|will)\s+you\s+(?:please\s+)?)?"
)
_DETAIL_REQUEST_VERB = (
    r"(?:write|prepare|produce|generate|give|send|render)\s+"
    r"(?:me\s+|us\s+)?(?:an?\s+|the\s+)?"
)
# Recognize a whole, unambiguous request clause. A prefix alone authorized
# "write a report? No, fix the bug" and command names described as examples.
# Topics with negation, quotation or declarative wording stay conservative;
# broader requests can carry an explicitly authorized closed mode.
_DETAIL_REQUEST_SUBJECT = (
    r"(?:(?!\b(?:no|not|never|instead|rather|but|is|are|was|were|means|"
    r"example|quoted|literal)\b)[^\r\n.!?;:\"'`])+?"
)
_DETAIL_REQUEST_END = r"\s*[.!?]?\s*$"
_DETAIL_REQUEST_TOPIC = (
    r"(?:\s+(?:on|about|for|of|covering)\s+" + _DETAIL_REQUEST_SUBJECT + r")?"
)
_DETAIL_REQUEST_GRAMMARS = (
    (
        DETAIL_MODE_HANDOFF,
        re.compile(
            _DETAIL_REQUEST_PREFIX + _DETAIL_REQUEST_VERB + r"hand[\s-]?off\b"
            + _DETAIL_REQUEST_TOPIC + _DETAIL_REQUEST_END
        ),
    ),
    (
        DETAIL_MODE_AUDIT,
        re.compile(
            _DETAIL_REQUEST_PREFIX + r"audit(?:\s+(?:the|this|these|my|our|your|all)\s+"
            + _DETAIL_REQUEST_SUBJECT + r")?" + _DETAIL_REQUEST_END
        ),
    ),
    (
        DETAIL_MODE_REPORT,
        re.compile(
            _DETAIL_REQUEST_PREFIX + _DETAIL_REQUEST_VERB +
            r"(?:detailed\s+|full\s+|verbose\s+|complete\s+|final\s+|formal\s+)?"
            r"(?:report|write[\s-]?up|summary|brief)\b"
            + _DETAIL_REQUEST_TOPIC + _DETAIL_REQUEST_END
        ),
    ),
    (
        DETAIL_MODE_BOUNDARY,
        re.compile(
            _DETAIL_REQUEST_PREFIX + r"this\s+is\s+an?\s+exceptional\s+boundary\s*[.!?]?\s*$"
        ),
    ),
)

#: T-1553: the compactness budget, measured over FIELD CONTENT in NON-EMPTY
#: lines -- never over the mandatory labels themselves, which would contradict
#: the schema (six mandatory headings plus values cannot fit a five-line cap).
#: Without this the control surface degraded into a free-form report wearing six
#: headings: a RESULT of any length and a DETAILS field of any length both read
#: as VALID_BOUNDARY.
FIELD_LINE_BUDGETS = {
    "RESULT": 3,
    "BLOCKER": 1,
    "OPERATOR ACTION": 1,
    "NEXT EXACT ACTION": 1,
    "VALIDATION": 5,
    "EFFICIENCY": 1,
    # DETAILS stays permitted for the intentional detailed-report path, but it
    # is bounded: an unbounded DETAILS is the overflow bucket the surface
    # exists to remove.
    "DETAILS": 8,
}

#: T-1556 #2: LINE COUNT ALONE IS NOT A COMPACTNESS CONTRACT. One RESULT line
#: of twelve thousand characters satisfied every line budget, so the surface
#: still read as VALID_BOUNDARY while carrying a novel. These are the character
#: budgets over the same field CONTENT, machine-owned beside `FIELD_LINE_BUDGETS`
#: so no adapter has to know them and no document may drift from them.
FIELD_CHAR_BUDGETS = {
    "STATUS": 240,
    "RESULT": 720,
    "BLOCKER": 300,
    "OPERATOR ACTION": 300,
    "NEXT EXACT ACTION": 240,
    "VALIDATION": 480,
    "EFFICIENCY": _EFFICIENCY_LINE_CHARS,
    "DETAILS": 2400,
}

#: T-1558: prose plus fenced code together may not exceed this multiple of the
#: prose ceiling. Fenced code is exempt from the PROSE measures (it is fact), not
#: from every measure: without a total an essay wrapped in a fence passes. One
#: owner, here, beside the budgets it multiplies; `chat_style` reads it.
TOTAL_REPLY_CEILING_FACTOR = 3

#: Whole rendered boundary, labels included. It is deliberately BELOW the sum
#: of the per-field maxima: a response whose every field is individually legal
#: is still not a compact handback, and a ceiling that can never fire is
#: decoration rather than a contract.
ORDINARY_RESPONSE_CHAR_BUDGET = 2000
#: The detailed path earns the DETAILS budget and nothing else.
DETAILED_RESPONSE_CHAR_BUDGET = ORDINARY_RESPONSE_CHAR_BUDGET + FIELD_CHAR_BUDGETS["DETAILS"]

#: T-1556 #3: EXACTLY ONE ACTION. Chaining and sequencing are rejected by
#: shape; a value that names a canonical SAIPEN command is additionally held to
#: the canonical recognizer, so `saipen validate && saipen continue` and
#: `saipen frobnicate` are both refused for the same reason. No shell parser is
#: built here: a quoted canonical payload may legally contain a separator, and
#: the recognizer already knows that.
_ACTION_CHAIN = re.compile(r"&&|\|\||[;|&\n]")
_ACTION_SEQUENCE = re.compile(
    r"(?i)\b(?:then|after\s+that|afterwards?|followed\s+by|and\s+next)\b"
)
_ACTION_COMMAND_START = re.compile(
    r"^\s*`?(?:saipen(?:\.cmd|\.py)?|python(?:\d+(?:\.\d+)*)?|py|git|uv|ruff|"
    r"pytest|npm|node|powershell|pwsh|cmd|bash)\b",
    re.IGNORECASE,
)
#: The same vocabulary as bare tokens. A second occurrence means two commands
#: in one field, which is what `saipen validate saipen continue` is.
_ACTION_COMMAND_WORDS = frozenset(
    {
        "saipen", "saipen.cmd", "saipen.py", "python", "py", "git", "uv", "ruff",
        "pytest", "npm", "node", "powershell", "pwsh", "cmd", "bash",
    }
)


def detail_mode_for_request(request: object) -> str:
    """The authorized DETAILS mode for one human request, or DETAIL_MODE_NONE.

    The ONLY input is what the human asked for. The outgoing response is never
    read: authorizing a field from the text that carries it would let any
    response authorize itself.
    """
    if not isinstance(request, str) or not request.strip():
        return DETAIL_MODE_NONE
    for mode, grammar in _DETAIL_REQUEST_GRAMMARS:
        if grammar.fullmatch(request):
            return mode
    return DETAIL_MODE_NONE


def detail_mode_is_valid(mode: object) -> bool:
    return isinstance(mode, str) and mode in DETAIL_MODES


def _carries_a_second_command(text: str) -> bool:
    """Two canonical commands in one field, e.g. `saipen validate saipen continue`.

    Shell-quoted by the same canonical tokenizer the recognizer uses, so a
    quoted ingress payload that merely MENTIONS a command
    (`saipen start 'fix saipen guard'`) is one action, not two.
    """
    try:
        tokens = shlex.split(text)
    except ValueError:
        return False
    return any(token.lower() in _ACTION_COMMAND_WORDS for token in tokens[1:])


def _action_is_single(value: str) -> bool:
    """Is this one exact action rather than a chain, a sequence or a list?"""
    text = value.strip()
    if not text or _is_none(text):
        return True
    if _ACTION_CHAIN.search(text) or _ACTION_SEQUENCE.search(text):
        return False
    if not _ACTION_COMMAND_START.match(text):
        return True
    return saipen_line_problem(text) is None and not _carries_a_second_command(text)


def _is_none(value: object) -> bool:
    return str(value if value is not None else "").strip().upper() in NONE_VALUES


#: The phases a ticket is still WORKING in; a STATUS led by one is not final.
_IN_FLIGHT_PHASES = frozenset({"SCOUT", "BUILD", "VERIFY", "REVIEW", "SHIP"})


def _names_in_flight_phase(status: object) -> bool:
    head = re.match(r"\s*(?:T-\d+\s+)?([A-Za-z][A-Za-z_]*)", str(status or ""))
    return bool(head) and head.group(1).upper() in _IN_FLIGHT_PHASES


@dataclass(frozen=True)
class OperationalBoundary:
    status: str
    result: str
    blocker: str
    operator_action: str
    next_exact_action: str
    validation: str
    details: str = ""
    # Declared after `details` so positional callers keep their meaning; it
    # still RENDERS before DETAILS (FIELD_ORDER decides order, not this class).
    efficiency: str = ""

    def fields(self) -> dict[str, str]:
        values = {
            "STATUS": self.status,
            "RESULT": self.result,
            "BLOCKER": self.blocker,
            "OPERATOR ACTION": self.operator_action,
            "NEXT EXACT ACTION": self.next_exact_action,
            "VALIDATION": self.validation,
        }
        if self.efficiency:
            values["EFFICIENCY"] = self.efficiency
        if self.details:
            values["DETAILS"] = self.details
        return values


def render_boundary(
    boundary: OperationalBoundary,
    *,
    current_validation: str | None = None,
    detail_mode: str = DETAIL_MODE_NONE,
) -> str:
    """Assemble one operational handback from typed fields, then validate it."""
    fields = boundary.fields()
    rendered = "\n".join(f"{key}\n{value.strip()}" for key, value in fields.items())
    errors = response_errors(
        rendered, current_validation=current_validation, detail_mode=detail_mode
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
    detail_mode: str = DETAIL_MODE_NONE,
) -> list[str]:
    """Validate the actual text a host will return, including its first byte."""
    if not detail_mode_is_valid(detail_mode):
        return [f"unknown detail_mode {detail_mode!r}; authorization requires a closed mode"]
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
    if not _action_is_single(next_action):
        errors.append(
            "NEXT EXACT ACTION must be exactly one action -- a chain (`&&`, `||`, "
            "`;`), a sequence (`then`) or a second command is not one action"
        )
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
    for name, budget in FIELD_CHAR_BUDGETS.items():
        if name not in values:
            continue
        size = len(values[name])
        if size > budget:
            errors.append(
                f"{name} exceeds {budget} character(s) ({size}) -- a line count is "
                "not a compactness contract"
            )
    # T-1556 #1: DETAILS is authorization-gated before it is budgeted. A
    # forbidden field is refused whatever its size, and an authorized one is
    # still bounded.
    if "DETAILS" in values and detail_mode == DETAIL_MODE_NONE:
        errors.append(
            "DETAILS is not authorized on an ordinary response -- the detailed "
            "path is an explicit report, audit, handoff or exceptional boundary"
        )
    # T-1576: EFFICIENCY is derived telemetry for the FINAL report. Silent
    # execution has no KPI heartbeat, so a STATUS that names an in-flight
    # phase may not carry it, and its value must be the owner's rendered
    # grammar -- which has no word in which it could claim quality.
    if "EFFICIENCY" in values:
        problem = _efficiency_line_problem(values["EFFICIENCY"])
        if problem:
            errors.append(problem)
        if _names_in_flight_phase(values.get("STATUS", "")):
            errors.append(
                "EFFICIENCY belongs to the final boundary -- an in-flight STATUS "
                "carries no KPI (silent execution)"
            )
    total_budget = (
        DETAILED_RESPONSE_CHAR_BUDGET
        if detail_mode != DETAIL_MODE_NONE
        else ORDINARY_RESPONSE_CHAR_BUDGET
    )
    if len(rendered) > total_budget:
        errors.append(
            f"the whole response is {len(rendered)} characters -- the budget for "
            f"this boundary is {total_budget}"
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
    if current_phase:
        raw_status = values.get("STATUS", "")
        status_tokens = set(re.findall(r"(?<![\w-])[A-Z][A-Z_]*(?![\w-])", raw_status))
        named_phases = status_tokens & ALL_PHASES
        first_word = re.match(r"[A-Za-z][A-Za-z_]*", raw_status)
        if first_word and first_word.group().upper() in ALL_PHASES:
            named_phases.add(first_word.group().upper())
        head = re.match(r"(?:(T-\d+)\s+)?([A-Za-z][A-Za-z_]*)(?![\w-])", raw_status)
        leading_phase = head.group(2).upper() if head else ""
        leading_task = head.group(1) if head else None
        is_operator_wait = leading_task is None and leading_phase == "WAIT" and operator_due
        valid_head = (
            leading_phase == current_phase.upper()
            and (leading_task is None or leading_task == current_task)
        ) or is_operator_wait
        phase_matches = named_phases == {current_phase.upper()} or (
            is_operator_wait and not named_phases
        )
        if not valid_head or not phase_matches:
            errors.append(f"STATUS must name current phase {current_phase}")
    if current_task and current_task.lower() != "none":
        named_tasks = set(re.findall(r"(?<![\w-])T-\d+(?![\w-])", current_status))
        if named_tasks != {current_task.upper()}:
            errors.append(f"STATUS must name current task {current_task}")
    if current_blocker and current_blocker.strip() and not _is_none(current_blocker):
        # A project with no blocker reports the canonical `none` sentinel. That
        # is not a blocker CODE, so demanding the response name it refused every
        # `BLOCKER: NONE` surface on a healthy project -- the case the surface is
        # written for. `_is_none` is the one "no blocker" test.
        code = current_blocker.split(" -- ", 1)[0].split(":", 1)[0].strip()
        rendered_code = blocker.split(" -- ", 1)[0].strip()
        if code and rendered_code != code:
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
    if "EFFICIENCY" in fields:
        problem = _efficiency_line_problem(fields["EFFICIENCY"])
        if problem:
            errors.append(problem)
        if _names_in_flight_phase(status):
            errors.append("EFFICIENCY belongs to the final boundary (silent execution)")
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
#: T-1558: ordinary conversation that breaks the measurable chat contract of
#: STYLE.md (`chat_style`): an essay over the chat budget, a banned sentinel
#: phrase, the wrong pinned language. Before this class existed every reply
#: without a control-surface marker was ORDINARY_CHAT and passed unmeasured.
CLASS_CHAT_STYLE_DRIFT = "CHAT_STYLE_DRIFT"
#: PROTOCOL-ADMISSION-01: the speaker was not admitted, so no reply is permitted
#: whatever its form. Decided by `protocol_admission`, before every other layer.
CLASS_ADMISSION_BLOCKED = "ADMISSION_BLOCKED"
RESPONSE_CLASSES = (
    CLASS_VALID_BOUNDARY,
    CLASS_INVALID_OPERATIONAL_PROSE,
    CLASS_AUTONOMOUS_HANDBACK,
    CLASS_ORDINARY_CHAT,
    CLASS_CHAT_STYLE_DRIFT,
    CLASS_ADMISSION_BLOCKED,
)

LAYER_ADMISSION = "ADMISSION"
LAYER_EXEC_RESPONSE = "EXEC_RESPONSE"
LAYER_CHAT_STYLE = "CHAT_STYLE"
LAYER_NONE = "NONE"

#: Free-form report shapes that claim the response IS an operational boundary:
#: control-surface label usage (`STATUS: ...`) and canonical blocker codes
#: (`SOME_CODE -- reason`) outside a rendered block.
_CONTROL_LABEL_USE = re.compile(
    r"(?im)^\s*(?:STATUS|RESULT|BLOCKER|OPERATOR ACTION|NEXT EXACT ACTION|"
    r"VALIDATION|EFFICIENCY|DETAILS)\s*(?::|-|--)\s*\S"
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
    style_contract: object | None = None,
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
    * ``ORDINARY_CHAT`` -- ordinary non-operational conversation that meets
      the measurable chat contract of STYLE.md.
    * ``CHAT_STYLE_DRIFT`` -- ordinary conversation that does not: over the
      chat budget, a banned sentinel phrase, or not the pinned
      ``reply_language`` (T-1558, ``chat_style``).

    ``operational_turn`` is the turn-context fact only the host/canonical
    state knows (the turn executed canonical work, or canonical state routes
    it as AUTO_KICK / OPERATOR_WAIT / RECOVER). ``executable_action_remains``
    is the canonical automation fact; it is enforced ONLY on operational
    turns, mirroring the OpenCode gate's ``enforceAutonomy``.
    """
    detail_mode = check_context.get("detail_mode", DETAIL_MODE_NONE)
    if not detail_mode_is_valid(detail_mode):
        return CLASS_INVALID_OPERATIONAL_PROSE, [
            f"unknown detail_mode {detail_mode!r}; authorization requires a closed mode"
        ]
    text = rendered if isinstance(rendered, str) else ""
    claims = claims_operational_finality(text)
    if not operational_turn and not claims:
        if style_contract is not None:
            from .chat_style import chat_style_errors

            drift = chat_style_errors(
                text,
                contract=style_contract,
                detail_authorized=check_context.get("detail_mode", DETAIL_MODE_NONE)
                != DETAIL_MODE_NONE,
            )
            if drift:
                return CLASS_CHAT_STYLE_DRIFT, drift
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
        if style_contract is not None:
            # A valid surface still has to be in the pinned language: a green
            # structural layer does not compensate for a failed style layer.
            from .chat_style import boundary_style_errors

            drift = boundary_style_errors(text, contract=style_contract)
            if drift:
                return CLASS_CHAT_STYLE_DRIFT, drift
        return CLASS_VALID_BOUNDARY, []
    if any(
        marker in error
        for error in errors
        for marker in _AUTONOMY_ERROR_MARKERS
    ):
        return CLASS_AUTONOMOUS_HANDBACK, errors
    return CLASS_INVALID_OPERATIONAL_PROSE, errors


def gate_final_response(
    text: object,
    *,
    admission: dict | None,
    admission_consulted: bool,
    operational_turn: bool,
    style_contract: object | None,
    admission_skip_reason: str = "NOT_ENFORCEABLE",
    executable_action_remains: bool = False,
    **check_context: object,
) -> dict:
    """The layered verdict over one outgoing reply (PROTOCOL-ADMISSION-01).

    The chain is fixed and each layer answers a different question:

        ADMISSION      was the speaker admitted? (`protocol_admission`)
        EXEC_RESPONSE  is an operational response structurally valid?
        CHAT_STYLE     does the visible reply obey language and style?

    The first layer that fails decides, and later layers are reported
    NOT_REACHED: a green later layer never compensates for a failed earlier one,
    and a perfectly formed reply from an unadmitted speaker is still blocked. A
    host that cannot enforce admission is reported `NOT_ENFORCEABLE` (or
    `NOT_CONSULTED` when the caller supplied no session), never passed off as
    admitted.
    """
    layers = {
        "admission": (
            admission["state"] if admission_consulted and admission else admission_skip_reason
        ),
        "exec_response": "NOT_REACHED",
        "chat_style": "NOT_REACHED",
    }
    if admission_consulted and not (admission or {}).get("permitted"):
        from .protocol_admission import diagnostic

        message = diagnostic(admission or {"state": "REFUSED", "problems": []})
        return {
            "ok": False,
            "layer": LAYER_ADMISSION,
            "class": CLASS_ADMISSION_BLOCKED,
            "errors": [message],
            "diagnostic": message,
            "layers": layers,
        }
    klass, errors = classify_final_response(
        text,
        operational_turn=operational_turn,
        executable_action_remains=executable_action_remains,
        style_contract=style_contract,
        **check_context,
    )
    if klass in (CLASS_INVALID_OPERATIONAL_PROSE, CLASS_AUTONOMOUS_HANDBACK):
        layers["exec_response"] = "FAIL"
        layer = LAYER_EXEC_RESPONSE
    elif klass == CLASS_CHAT_STYLE_DRIFT:
        layers["exec_response"] = (
            "PASS"
            if operational_turn or claims_operational_finality(text)
            else "NOT_APPLICABLE"
        )
        layers["chat_style"] = "FAIL"
        layer = LAYER_CHAT_STYLE
    else:
        layers["exec_response"] = "PASS" if klass == CLASS_VALID_BOUNDARY else "NOT_APPLICABLE"
        layers["chat_style"] = "PASS" if style_contract is not None else "NOT_EVALUATED"
        layer = LAYER_NONE
    return {
        "ok": klass in (CLASS_VALID_BOUNDARY, CLASS_ORDINARY_CHAT),
        "layer": layer,
        "class": klass,
        "errors": errors,
        "diagnostic": None,
        "layers": layers,
    }
