"""STATE frontmatter parsing -- the shared primitive."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from . import phases


def _decode_quoted(raw: str) -> str | None:
    """Decode a double-quoted scalar exactly, or None when not quoted."""
    if not (len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"'):
        return None
    body = raw[1:-1]
    out: list[str] = []
    i = 0
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body):
            nxt = body[i + 1]
            if nxt in ("\\", '"'):
                out.append(nxt)
                i += 2
                continue
            # an escaped character that is NOT a quote or backslash is kept
            # verbatim (backslash + char) -- the writer only ever emits
            # \\ and \", so anything else is foreign text to preserve.
            out.append(ch)
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def coerce(raw: str):
    """Coerce a frontmatter scalar: strip quotes, booleans, integers.

    Symmetric with `_render_value`: anything the writer quotes decodes back
    to the exact original string, and unquoted scalars decode to their
    natural type. A quoted `"007"` stays the string "007" (never the int
    7), and a quoted string containing `"` or `\\` round-trips exactly.
    """
    decoded = _decode_quoted(raw)
    if decoded is not None:
        return decoded
    if raw in ("true", "false"):
        return raw == "true"
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    return raw


def parse_frontmatter(text: str):
    """Parse the YAML subset STATE.md actually uses: scalar `key: value`
    lines and simple `- item` lists. Returns (dict, error-or-None).

    Strict by construction: a duplicate scalar or list key is an error, never
    a silent last-wins (a STATE with `phase: BUILD` and `phase: VERIFY` must
    not let either value hide the other). Malformed fences and unparseable
    lines are errors too -- nothing collapses to an empty dict silently.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, "no opening --- frontmatter fence"
    fields = {}
    seen: set[str] = set()
    current_list_key = None
    for lineno, line in enumerate(lines[1:], 2):
        if line.strip() == "---":
            return fields, None
        if not line.strip():
            continue
        item = re.match(r"^\s+-\s+(.*)$", line)
        if item and current_list_key:
            fields[current_list_key].append(coerce(item.group(1).strip()))
            continue
        if item:
            return None, (f"line {lineno}: list item {line.strip()!r} appears "
                          "outside any keyed list block")
        kv = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", line)
        if not kv:
            return None, f"unparseable frontmatter line: {line!r}"
        key, raw = kv.group(1), kv.group(2).strip()
        if key in seen:
            return None, (f"line {lineno}: duplicate STATE field "
                          f"{key!r} (each field may appear once)")
        seen.add(key)
        if raw == "":
            fields[key] = []
            current_list_key = key
        else:
            fields[key] = coerce(raw)
            current_list_key = None
    return None, "no closing --- frontmatter fence"


# ---------------------------------------------------------------------------
# The SHARED STATE contract (hostile-regression, P1): one hand-maintained
# mirror of extensions/schemas/state.schema.json lives HERE, and
# tools/validate.py cross-checks the schema against these constants so the
# engine and the gate can never drift. Required-set, enums, type map,
# minimums and the execution-intent conditionals are enforced in
# `state_contract_errors` for EVERY engine consumer (router, fast_check,
# journal reads) -- a state the release gate would FAIL must never route or
# commit as if it were green.
# ---------------------------------------------------------------------------

STATE_REQUIRED_FIELDS = (
    "phase", "task", "next_action", "blocker", "agent",
    "saipen_version", "mode", "updated",
)

# Every property state.schema.json defines. `additionalProperties: false`
# in the schema, so an engine-read key outside this set is unknown and
# refuses -- the same FAIL the release gate raises.
STATE_KNOWN_FIELDS = frozenset({
    "phase", "task", "next_action", "blocker", "agent", "saipen_version",
    "schema_version", "saipen_home", "requires", "mode", "execution_intent",
    "converge_target", "goal_mode", "goal_waves", "goal_tickets",
    "last_event", "style_contract", "updated", "human_note",
    "first_publish_confirmation", "role_revision", "paused_from_phase",
    "paused_from_na", "transition_from",
})

STATE_PHASE_ENUM = (
    "INIT", "PLAN", "SCOUT", "BUILD", "VERIFY", "REVIEW", "SHIP", "DONE",
    "BLOCKED", "VALIDATE", "HUNT", "MARKHUNT", "ADD", "CLEAN",
    "TRANSLATE", "PREPARE",
)

STATE_MODE_ENUM = ("full", "read-only", "no-publish", "manual-verify")

STATE_INTENT_ENUM = ("normal", "goal", "converge")

STATE_CONVERGE_TARGETS = ("done", "ship", "crew")

STATE_STRING_FIELDS = frozenset({
    "task", "next_action", "blocker", "agent", "saipen_home",
    "style_contract", "updated", "human_note", "first_publish_confirmation",
    "role_revision", "paused_from_phase", "paused_from_na",
})

STATE_INTEGER_FIELDS = {
    "saipen_version": None,
    "schema_version": 1,
    "goal_waves": 0,
    "goal_tickets": 0,
    "last_event": 1,
}

# RFC § 1.2's closed WAIT category set -- the seven tokens a `WAIT:` next_action
# must carry so a stop instruction is mechanically distinguishable from a real
# gate (hostile-regression, P0#1). Mirrored from tools/validate.py's WAIT_CATEGORIES.
WAIT_CATEGORIES = ("manual-verify", "destructive-op", "first-publish",
                   "user brake", "blocked", "safety valve", "init")

_STYLE_TOKEN_RE = re.compile(r"`style_contract:\s*(ded-[0-9a-f]{8})`")


def style_contract_token(text: str) -> str:
    """The installed STYLE.md voice marker, computed from the file minus its own
    declaration line (RFC § 1.2)."""
    body = "\n".join(
        ln for ln in text.replace("\r\n", "\n").split("\n")
        if "style_contract:" not in ln).strip()
    return "ded-" + hashlib.sha256(body.encode("utf-8")).hexdigest()[:8]


def installed_style_token(saipen_home: object) -> str | None:
    """The STYLE.md marker of the SAIPEN home the state was written against, or
    None when unreachable (legacy/explicitly absent home: skip the check)."""
    if not saipen_home or not str(saipen_home).strip():
        return None
    base = Path(str(saipen_home))
    for candidate in (base / "saipen" / "STYLE.md", base / "STYLE.md"):
        if candidate.is_file():
            try:
                return style_contract_token(
                    candidate.read_text(encoding="utf-8-sig"))
            except OSError:
                return None
    return None


def state_contract_errors(fields: dict, *, style_token: str | None = None,
                          current_schema_version: int | None = None) -> list[str]:
    """Verify exact presence/type/shape of core STATE schema against the
    protocol -- the SHARED implementation the release gate mirrors.

    ONE canonical STATE semantic validator (hostile-regression, P0#1): engine
    consumers (router, fast_check, journal reads), the fast gate and the
    release gate ALL refuse a state the others would accept. It mirrors
    state.schema.json's interpreted subset (required, enum, type, minimum,
    additionalProperties, if/then) plus the delegated execution-intent
    conditionals AND the in-memory RFC checks that must not drift between the
    engine and the validator:

      * non-INIT `transition_from` presence,
      * `phases.transition_legal`-equivalent transition pairs (the block-parked
        DONE shape is accepted here; the LOG-evidence proof is the validator's
        cross-file concern and stays there),
      * ISO-8601 UTC `updated`,
      * closed WAIT category grammar,
      * exact `style_contract` against the installed STYLE.md marker.

    A future schema_version is NOT an error here -- the validator WARNS on it to
    keep the schema-bump workflow alive, and so do we. `style_token` /
    `current_schema_version`, when supplied, enable the style_contract checks;
    callers without an installed home (legacy `saipen_home: ""`) omit them and
    the check is skipped rather than guessed.
    """
    errors = []
    for key in STATE_REQUIRED_FIELDS:
        if key not in fields:
            errors.append(f"missing required field {key}")
    for key in fields:
        if key not in STATE_KNOWN_FIELDS:
            errors.append(f"unknown STATE field {key!r} -- state.schema.json "
                          "does not define it (retired or misspelled?)")
            continue
        if key in STATE_STRING_FIELDS and not isinstance(fields[key], str):
            errors.append(f"{key} must be a string")
    phase = fields.get("phase")
    if phase is not None and (not isinstance(phase, str)
                              or phase not in STATE_PHASE_ENUM):
        errors.append(f"phase {phase!r} not one of "
                      f"{'|'.join(STATE_PHASE_ENUM)}")
    tf = fields.get("transition_from")
    if tf is not None and (not isinstance(tf, str)
                           or tf not in STATE_PHASE_ENUM):
        errors.append(f"transition_from {tf!r} not one of "
                      f"{'|'.join(STATE_PHASE_ENUM)}")
    mode = fields.get("mode")
    if mode is not None and (not isinstance(mode, str)
                             or mode not in STATE_MODE_ENUM):
        errors.append(f"mode {mode!r} not one of {'|'.join(STATE_MODE_ENUM)}")
    intent = fields.get("execution_intent")
    if intent is not None and (not isinstance(intent, str)
                               or intent not in STATE_INTENT_ENUM):
        errors.append(f"execution_intent {intent!r} not one of "
                      f"{'|'.join(STATE_INTENT_ENUM)}")
    target = fields.get("converge_target")
    if target is not None and (not isinstance(target, str)
                               or target not in STATE_CONVERGE_TARGETS):
        errors.append(f"converge_target {target!r} not one of "
                      f"{'|'.join(STATE_CONVERGE_TARGETS)}")
    for key, minimum in STATE_INTEGER_FIELDS.items():
        value = fields.get(key)
        if value is None:
            continue
        if not isinstance(value, int) or isinstance(value, bool):
            errors.append(f"{key} must be an integer")
        elif minimum is not None and value < minimum:
            errors.append(f"{key} {value!r} is below the schema minimum "
                          f"{minimum}")
    requires = fields.get("requires")
    if requires is not None:
        if not isinstance(requires, list):
            errors.append("requires must be an array")
        elif any(not isinstance(item, str) for item in requires):
            errors.append("requires items must be strings")
    gm = fields.get("goal_mode")
    if gm is not None and not isinstance(gm, bool):
        errors.append("goal_mode must be a boolean")
    # Execution-intent family conditionals (schema if/then + § 2.4 delegated
    # checks): goal requires its counters; converge requires its target and
    # forbids goal counters; every other intent forbids both families.
    if intent == "goal":
        for key in ("goal_waves", "goal_tickets"):
            if key not in fields:
                errors.append(f"execution_intent goal requires {key}")
        if "converge_target" in fields:
            errors.append("execution_intent goal with converge_target")
    elif intent == "converge":
        if "converge_target" not in fields:
            errors.append("execution_intent converge requires converge_target")
        for key in ("goal_waves", "goal_tickets"):
            if key in fields:
                errors.append(f"execution_intent converge with {key}")
    elif intent in (None, "normal"):
        for key in ("goal_waves", "goal_tickets"):
            if key in fields:
                errors.append(f"non-goal execution_intent with {key}")
        if "converge_target" in fields:
            errors.append("non-converge execution_intent with converge_target")
    # --- Canonical STATE truth shared by engine, fast gate and release validator
    # (hostile-regression, P0#1). In-memory only; the cross-file checks (block-
    # parked LOG proof, vague next_action) stay in the validator.
    tf = fields.get("transition_from")
    ph = fields.get("phase")
    if ph is not None and ph != "INIT":
        if tf is None:
            errors.append("missing transition_from -- required on all non-INIT "
                           "states to validate phase transitions (RFC § 1.6)")
        elif isinstance(tf, str):
            if tf not in phases.VALID_TRANSITIONS and tf not in phases.ANY_FROM:
                errors.append(
                    f"transition_from {tf!r} not one of the 16 phase enum values "
                    f"(RFC § 1.6)")
            elif ph != tf and ph not in phases.ANY_FROM:
                allowed = list(phases.VALID_TRANSITIONS.get(tf, []))
                # Block-parked transitional shape: an active-ticket `ticket
                # block` parks execution at DONE with transition_from set to the
                # mid-flight phase (RFC § 1.6 narrow exception). The engine
                # accepts the shape; the validator adds the LOG-evidence proof.
                if not (ph == "DONE" and tf in ("SCOUT", "BUILD", "VERIFY",
                                                 "REVIEW", "SHIP")):
                    if ph not in allowed:
                        errors.append(
                            f"invalid phase transition: {tf} -> {ph} (RFC § 1.6). "
                            f"Allowed from {tf}: {', '.join(allowed)}")
    updated = fields.get("updated")
    if isinstance(updated, str):
        if not re.fullmatch(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|\+00:00)",
                updated):
            errors.append(
                f"updated must be ISO-8601 UTC (Z or +00:00), got {updated!r} -- "
                f"Recovery miscompares staleness across timezones otherwise "
                f"(RFC § 1.2)")
    na = fields.get("next_action")
    if isinstance(na, str) and na.startswith("WAIT:"):
        body = na[len("WAIT:"):].strip().lower()
        if not any(body.startswith(c) for c in WAIT_CATEGORIES):
            errors.append(
                f"next_action is a WAIT with no category token -- RFC § 1.2 "
                f"requires 'WAIT: <category> -- <question>' where category is "
                f"one of {'/'.join(WAIT_CATEGORIES)}; got {na!r}")
    if style_token is not None:
        sc = fields.get("style_contract")
        if sc is not None and sc != style_token:
            errors.append(
                f"style_contract {sc!r} does not match the installed STYLE.md "
                f"marker {style_token!r} -- the agent that wrote this checkpoint "
                f"did not read the current voice contract (RFC § 1.2)")
        elif (current_schema_version is not None
              and fields.get("schema_version") == current_schema_version
              and sc is None):
            errors.append(
                f"schema_version {current_schema_version} requires "
                f"style_contract: {style_token} (RFC § 1.2)")
    return errors


def _current_schema_version(home: object) -> int | None:
    """The installed protocol's major version from `<home>/VERSION`, or None."""
    if not home or not str(home).strip():
        return None
    path = Path(str(home)) / "VERSION"
    if not path.is_file():
        return None
    try:
        return int(path.read_text(encoding="utf-8-sig").strip().split(".")[0])
    except (OSError, ValueError):
        return None


def parse_state_or_error(text: str):
    """Strict STATE read for authorization/routing consumers.

    Returns (fields, None) for a valid or absent (empty) STATE, and
    (None, error) for a PRESENT but malformed STATE. Read models must never
    treat a corrupt non-empty STATE as the empty dict `{}`: that is exactly
    how a duplicate-key or broken-fence STATE launders itself into a green
    routing decision (T-1003 hostile findings). The shared canonical STATE
    validator runs here too, so a state the release gate would FAIL cannot
    route or COMMIT as if it were green (hostile-regression, P0#1).
    """
    if not text or not text.strip():
        return {}, None
    fields, error = parse_frontmatter(text)
    if fields is None:
        return None, error
    home = fields.get("saipen_home")
    contract_errors = state_contract_errors(
        fields,
        style_token=installed_style_token(home),
        current_schema_version=_current_schema_version(home))
    if contract_errors:
        return None, "; ".join(contract_errors)
    return fields, None


def parse_state(text: str) -> dict:
    """Return the STATE field dict; surrogate CORRUPT on invalid STATE."""
    if not text or not text.strip():
        return {}
    fields, _error = parse_frontmatter(text)
    if fields is None:
        return {"phase": "CORRUPT", "corrupt_detail": _error}
    contract_errors = state_contract_errors(fields)
    if contract_errors:
        return {"phase": "CORRUPT", "corrupt_detail": "; ".join(contract_errors)}
    return fields


def _render_value(value) -> str:
    """Render one owned scalar in the frontmatter subset STATE uses.

    Bijective with `coerce`: a string is quoted exactly when leaving it
    bare would change its type (numeric-looking, boolean-looking, empty) or
    when it contains characters the parser would misread (spaces, colons,
    quotes, backslashes, specials). The same renderer is applied to list
    items, so a list item can never silently become an int/bool either.
    """
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, tuple)):
        return None  # caller renders lists as blocks
    text = str(value)
    if text == "":
        return '""'
    would_retype = (re.fullmatch(r"-?\d+", text) is not None
                    or text in ("true", "false"))
    needs_quote = (would_retype
                   or any(c in text for c in ":,[]{}&*!|>'\"%@`")
                   or text != text.strip()
                   or any(c.isspace() for c in text))
    if needs_quote:
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text


def patch_state(text: str, owned: dict) -> str:
    """Return the STATE frontmatter with ONLY the owned keys changed.

    Every unowned field keeps its value, line and order. Keys already present
    are rewritten in place; new owned keys are inserted before the closing
    `---`. List values are rendered as a `key:` block with `- item` lines and
    replace the original block (including any prior list items). Unknown but
    schema-valid future fields are preserved byte-for-byte.
    """
    if not text or not text.startswith("---"):
        raise ValueError("STATE has no opening --- frontmatter fence")
    fields, parse_error = parse_frontmatter(text)
    if fields is None:
        raise ValueError(f"state-malformed: {parse_error}")
    lines = text.split("\n")
    close = None
    for idx, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            close = idx
            break
    if close is None:
        raise ValueError("STATE has no closing --- frontmatter fence")

    # Everything after the closing fence (the BOUNDARY instruction comment and
    # any other trailing prose) is preserved byte-for-byte: a STATE rewriter
    # owns only the frontmatter, never the post-fence body (T-1003 / hostile
    # ticket P0#2). The shipped TEMPLATE and live sub STATE carry a mandatory
    # BOUNDARY marker there; discarding it on spawn/update is a silent
    # contract violation.
    suffix = "\n".join(lines[close:])

    body = lines[1:close]
    pending = dict(owned)
    out: list[str] = []
    index = 0
    _list_key_re = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):\s*$")

    def emit_block(key: str, value) -> None:
        if isinstance(value, (list, tuple)):
            out.append(f"{key}:")
            for item in value:
                # THE SAME scalar codec as scalar fields: a list item that
                # looks numeric/boolean must be quoted so it parses back as
                # the string it was written as (T-1003 bijectivity).
                out.append(f"  - {_render_value(item)}")
        else:
            out.append(f"{key}: {_render_value(value)}")

    while index < len(body):
        line = body[index]
        _stripped = line.strip()
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", line)
        is_list_item = bool(re.match(r"^\s+-\s+", line))
        if match and match.group(1) in pending:
            key = match.group(1)
            value = pending.pop(key)
            if isinstance(value, (list, tuple)):
                emit_block(key, value)
                index += 1
                while index < len(body) and re.match(
                        r"^\s+-\s+", body[index]):
                    index += 1
                continue
            out.append(f"{key}: {_render_value(value)}")
            index += 1
            continue
        if is_list_item:
            # A preserved list item: keep it and its block intact.
            out.append(line)
            index += 1
            continue
        out.append(line)
        index += 1

    for key, value in pending.items():
        emit_block(key, value)

    # `suffix` already begins with the closing `---` fence, so the post-fence
    # body (BOUNDARY marker, etc.) is restored exactly as it was read.
    return "---\n" + "\n".join(out) + "\n" + suffix


def remove_state_fields(text: str, keys) -> str:
    """Remove exact frontmatter fields, including their list items.

    Intent-family transitions need absence, not an empty scalar: goal counters
    left behind as `""` are still fields from the wrong schema family.
    """
    if not text or not text.startswith("---"):
        raise ValueError("STATE has no opening --- frontmatter fence")
    fields, parse_error = parse_frontmatter(text)
    if fields is None:
        raise ValueError(f"state-malformed: {parse_error}")
    remove = set(keys)
    lines = text.split("\n")
    close = next((i for i, line in enumerate(lines[1:], 1)
                  if line.strip() == "---"), None)
    if close is None:
        raise ValueError("STATE has no closing --- frontmatter fence")
    # Preserve the post-fence body (BOUNDARY marker) exactly (T-1003 / P0#2).
    suffix = "\n".join(lines[close:])
    out = []
    index = 1
    while index < close:
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$",
                         lines[index])
        if match and match.group(1) in remove:
            list_field = match.group(2).strip() == ""
            index += 1
            if list_field:
                while index < close and re.match(r"^\s+-\s+", lines[index]):
                    index += 1
            continue
        out.append(lines[index])
        index += 1
    return "---\n" + "\n".join(out) + "\n" + suffix


def transition_execution_intent(text: str, intent: str,
                                converge_target: str | None = None,
                                goal_waves: int = 0,
                                goal_tickets: int = 0) -> str:
    """Apply one complete execution-intent family transition.

    Every transition first removes fields owned by all intent families, then
    introduces only target-family fields. Callers cannot accidentally retain
    goal counters in converge state or a converge target in normal state.
    """
    if intent not in ("normal", "goal", "converge"):
        raise ValueError(f"execution_intent {intent!r} outside closed enum")
    if intent == "converge" and converge_target not in ("done", "ship", "crew"):
        raise ValueError("converge intent requires target done|ship|crew")
    if intent != "converge" and converge_target is not None:
        raise ValueError("converge_target is legal only for converge intent")
    if goal_waves < 0 or goal_tickets < 0:
        raise ValueError("goal counters must be non-negative")

    clean = remove_state_fields(
        text, ("execution_intent", "goal_mode", "goal_waves",
               "goal_tickets", "converge_target"))
    owned = {"execution_intent": intent}
    if intent == "goal":
        owned.update({"goal_waves": goal_waves,
                      "goal_tickets": goal_tickets})
    elif intent == "converge":
        owned["converge_target"] = converge_target
    result = patch_state(clean, owned)
    parsed = parse_state(result)
    family = {key for key in ("goal_waves", "goal_tickets",
                              "converge_target") if key in parsed}
    expected = ({"goal_waves", "goal_tickets"} if intent == "goal"
                else {"converge_target"} if intent == "converge" else set())
    if family != expected:
        raise ValueError(f"intent transition produced fields {family}, "
                         f"expected {expected}")
    return result


def patch_owned_text(original: str, state: dict, owned: dict) -> str:
    """Patch `original` STATE text using `owned`; convenience wrapper that
    guarantees the result re-parses with every non-owned key preserved."""
    return patch_state(original, owned)
