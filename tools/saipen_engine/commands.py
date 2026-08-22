"""Deterministic command parsing for SAIPEN compound inputs.

Defect class this module exists to close: a protocol command or shortcut can
reach free-form natural-language reasoning before deterministic SAIPEN
resolution ("sc" answered as a style-mode greeting; "saipen push + build ccc"
executed only one segment while the other was narrated away).

Rules enforced here:

- A compound input (``saipen push + build ccc``) is split into an ORDERED
  list of command segments BEFORE any conversational interpretation. No
  segment may disappear because a model considers it unnecessary.
- A bare whole-message token that matches a declared SAIPEN shortcut (CORE.md
  section 1.10's table) activates SAIPEN and resolves to its row. The table
  is read from CORE.md -- this module holds NO copy, so it cannot drift.
- Style commands (``stop caveman`` / ``normal mode``) are recognized as
  style tokens ONLY when the token is not a declared shortcut. ``sc`` is
  never "stop caveman".
- Chain policy is STOP_ON_FAILURE by default: a later segment after an
  earlier REFUSED/FAILED segment becomes NOT_RUN unless it is provably
  independent. Skipping with prose is forbidden; every recognized segment
  receives an explicit terminal disposition.
"""

from __future__ import annotations

import re
from pathlib import Path

# The shortcut rows are maintained ONLY in CORE.md section 1.10. We read them
# at runtime so this list cannot drift into a second source of truth. The
# regex mirrors the table's canonical row shape: `| sc | saipen crew | ... |`.
_SHORTCUT_ROW_RE = re.compile(r"^\|\s*`([a-z]{2,3})`\s*\|\s*`(saipen [^`]+)`", re.MULTILINE)

# A shortcut may be typed on a Cyrillic layout with visually identical
# letters (CORE.md section 1.10). Latin confusables are folded to Latin
# before matching, exactly as the protocol recognizes them.
_CYRILLIC_CONFUSABLES = str.maketrans("аеорсух", "aeopcyx")  # noqa: RUF001 - deliberate confusable map


def _normalize_shortcut_token(token: str) -> str:
    return token.strip().translate(_CYRILLIC_CONFUSABLES)


def load_shortcut_table(protocol_dir: Path | str | None = None) -> dict[str, str]:
    """Read the canonical shortcut table from CORE.md section 1.10.

    Returns {shortcut: canonical saipen command}. The table is derived from
    CORE.md at runtime; there is deliberately no static copy here. When no
    CORE.md is found, returns an empty table (callers must fail closed and
    never guess a shortcut).
    """
    core = None
    if protocol_dir is not None:
        candidate = Path(protocol_dir) / "CORE.md"
        if candidate.is_file():
            core = candidate
    if core is None:
        # Best-effort discovery beside this module (the repo layout): the
        # protocol home is the repo root's sibling `saipen/`, i.e. three
        # parents up from tools/saipen_engine/commands.py. W2-006 (audit
        # fdc73e06): `.parent.parent` resolved to tools/ and produced an empty
        # table, silently turning every declared shortcut into VALIDATION_FAILED.
        candidate = Path(__file__).resolve().parent.parent.parent / "saipen" / "CORE.md"
        if candidate.is_file():
            core = candidate
    if core is None:
        return {}
    try:
        text = core.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return {}
    table: dict[str, str] = {}
    for match in _SHORTCUT_ROW_RE.finditer(text):
        table[match.group(1)] = match.group(2)
    return table


def is_declared_shortcut(token: str, table: dict[str, str] | None = None) -> bool:
    """True when the whole token is a declared SAIPEN shortcut.

    An unknown two/three-letter token must NOT become a shortcut; only an
    exact table match counts. Cyrillic twins are matched first by their own
    row (CORE.md declares them explicitly), then by Latin confusable folding.
    """
    if table is not None:
        return token.strip() in table or _normalize_shortcut_token(token) in table
    full = load_shortcut_table()
    return token.strip() in full or _normalize_shortcut_token(token) in full


def parse_compound_command(message: str) -> list[str]:
    """Split a possibly-compound command message into ordered segments.

    Segments are separated by ``+`` or by newlines. Empty/whitespace-only
    segments are dropped; the surviving ORDERED list is returned. A single
    bare command yields a one-element list. This is pure lexical splitting:
    semantic resolution happens per segment afterwards.
    """
    if not message or not message.strip():
        return []
    parts = re.split(r"\s*\+\s*|\n+", message.strip())
    segments = []
    for part in parts:
        stripped = part.strip()
        if stripped:
            segments.append(stripped)
    return segments


def resolve_compound_command(
    message: str,
    *,
    protocol_dir: Path | str | None = None,
    table: dict[str, str] | None = None,
) -> list[dict]:
    """Resolve a compound message into ordered command segments with targets.

    Each segment returns::

        {"index": int, "segment": str, "command": str, "kind": "command"|"shortcut"|"unknown"}

    - a segment starting with ``saipen `` is a canonical command (kind=command);
    - a bare token that matches the shortcut table resolves to its command
      (kind=shortcut);
    - a bare token that does NOT match is kind=unknown (never a guessed
      shortcut, never a style token unless the caller decides so).

    ``stop caveman`` / ``normal mode`` are multi-word and never shortcut
    matches; they are returned as kind=unknown (style) segments.
    """
    if table is None:
        table = load_shortcut_table(protocol_dir)
    segments = parse_compound_command(message)
    resolved: list[dict] = []
    for index, segment in enumerate(segments):
        if segment.startswith("saipen "):
            resolved.append(
                {"index": index, "segment": segment, "command": segment, "kind": "command"}
            )
            continue
        if " " in segment:
            # Multi-word segment: check for a TRAILING declared shortcut. A
            # compound like ``build ccc`` means "apply the build action, where
            # ccc is the declared shortcut ccc". The trailing shortcut resolves
            # to its canonical command; the leading word stays as the action
            # context.
            words = segment.split()
            trailing = words[-1]
            # Exact table row first (Cyrillic twins are declared rows), then
            # Latin-confusable folding for layouts typed without switching.
            target = table.get(trailing) or table.get(_normalize_shortcut_token(trailing))
            if target is not None:
                resolved.append(
                    {
                        "index": index,
                        "segment": segment,
                        "command": target,
                        "kind": "shortcut",
                        "context": " ".join(words[:-1]),
                    }
                )
                continue
            # Multi-word style/tone commands and free prose are not shortcuts.
            resolved.append(
                {"index": index, "segment": segment, "command": "", "kind": "unknown"}
            )
            continue
        target = table.get(segment) or table.get(_normalize_shortcut_token(segment))
        if target is not None:
            resolved.append(
                {"index": index, "segment": segment, "command": target, "kind": "shortcut"}
            )
            continue
        resolved.append(
            {"index": index, "segment": segment, "command": "", "kind": "unknown"}
        )
    return resolved


# Chain policy: STOP_ON_FAILURE is the canonical default (CORE.md section
# 1.10 compound-command contract). A later segment runs after an earlier
# failure ONLY when the failure produced no canonical writes AND the segment
# is provably independent (CONTINUE_WHEN_INDEPENDENT, decided by the caller
# with evidence -- never by intuition).
CHAIN_STOP_ON_FAILURE = "STOP_ON_FAILURE"
CHAIN_CONTINUE_WHEN_INDEPENDENT = "CONTINUE_WHEN_INDEPENDENT"

# Closed disposition vocabulary for every recognized segment.
DISPOSITION_EXECUTED = "EXECUTED"
DISPOSITION_REFUSED = "REFUSED"
DISPOSITION_BLOCKED = "BLOCKED"
DISPOSITION_SKIPPED_BY_PROTOCOL = "SKIPPED_BY_PROTOCOL"
DISPOSITION_ALREADY_SATISFIED = "ALREADY_SATISFIED"
DISPOSITION_NOT_RUN = "NOT_RUN"
DISPOSITION_FAILED = "FAILED"

_FAILURE_DISPOSITIONS = frozenset(
    {DISPOSITION_REFUSED, DISPOSITION_BLOCKED, DISPOSITION_FAILED}
)


def chain_disposition(
    dispositions: list[str],
    *,
    policy: str = CHAIN_STOP_ON_FAILURE,
    independent: list[bool] | None = None,
) -> list[str]:
    """Apply the canonical chain policy to a sequence of segment outcomes.

    ``dispositions`` is the per-segment result in order. Under
    STOP_ON_FAILURE (default), the first failure freezes every later segment
    to NOT_RUN. Under CONTINUE_WHEN_INDEPENDENT, a later segment may keep its
    own disposition only when ``independent[i]`` is True; otherwise it is
    NOT_RUN. This is a deterministic mechanical rule -- the caller never
    "decides" per-invocation whether a segment is skipped.
    """
    result = list(dispositions)
    if policy == CHAIN_CONTINUE_WHEN_INDEPENDENT:
        independent = independent or [False] * len(dispositions)
        blocked = False
        for i, disp in enumerate(dispositions):
            if blocked and not independent[i]:
                result[i] = DISPOSITION_NOT_RUN
            elif disp in _FAILURE_DISPOSITIONS:
                blocked = True
        return result
    # STOP_ON_FAILURE
    blocked = False
    for i, disp in enumerate(dispositions):
        if blocked:
            result[i] = DISPOSITION_NOT_RUN
        elif disp in _FAILURE_DISPOSITIONS:
            blocked = True
    return result
