"""STATE frontmatter parsing -- the shared primitive."""

from __future__ import annotations

import re


def coerce(raw: str):
    """Coerce a frontmatter scalar: strip quotes, booleans, integers."""
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1]
    if raw in ("true", "false"):
        return raw == "true"
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    return raw


def parse_frontmatter(text: str):
    """Parse the YAML subset STATE.md actually uses: scalar `key: value`
    lines and simple `- item` lists. Returns (dict, error-or-None)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, "no opening --- frontmatter fence"
    fields = {}
    current_list_key = None
    for line in lines[1:]:
        if line.strip() == "---":
            return fields, None
        if not line.strip():
            continue
        item = re.match(r"^\s+-\s+(.*)$", line)
        if item and current_list_key:
            fields[current_list_key].append(coerce(item.group(1).strip()))
            continue
        kv = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", line)
        if not kv:
            return None, f"unparseable frontmatter line: {line!r}"
        key, raw = kv.group(1), kv.group(2).strip()
        if raw == "":
            fields[key] = []
            current_list_key = key
        else:
            fields[key] = coerce(raw)
            current_list_key = None
    return None, "no closing --- frontmatter fence"


def parse_state(text: str) -> dict:
    """Return the STATE field dict; {} on a corrupt/missing fence."""
    fields, _error = parse_frontmatter(text)
    return fields if fields is not None else {}


def _render_value(value) -> str:
    """Render one owned scalar in the frontmatter subset STATE uses."""
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
    needs_quote = (any(c in text for c in ":,[]{}&*!|>'\"%@`")
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
    lines = text.split("\n")
    close = None
    for idx, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            close = idx
            break
    if close is None:
        raise ValueError("STATE has no closing --- frontmatter fence")

    body = lines[1:close]
    pending = dict(owned)
    out: list[str] = []
    index = 0
    _list_key_re = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):\s*$")

    def emit_block(key: str, value) -> None:
        if isinstance(value, (list, tuple)):
            out.append(f"{key}:")
            for item in value:
                out.append(f"  - {item}")
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

    return "---\n" + "\n".join(out) + "\n---\n"


def remove_state_fields(text: str, keys) -> str:
    """Remove exact frontmatter fields, including their list items.

    Intent-family transitions need absence, not an empty scalar: goal counters
    left behind as `""` are still fields from the wrong schema family.
    """
    if not text or not text.startswith("---"):
        raise ValueError("STATE has no opening --- frontmatter fence")
    remove = set(keys)
    lines = text.split("\n")
    close = next((i for i, line in enumerate(lines[1:], 1)
                  if line.strip() == "---"), None)
    if close is None:
        raise ValueError("STATE has no closing --- frontmatter fence")
    out = ["---"]
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
    out.append("---")
    return "\n".join(out) + "\n"


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
