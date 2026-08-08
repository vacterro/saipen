#!/usr/bin/env python
"""Optional USERPERSON preference profile mechanics (T-574).

USERPERSON is a meta-control, OFF by default. With no `.saipen/USERPERSON.md`
the protocol is silent: no warning, no boot failure, no placeholder, no
onboarding, no cold-start cost. The file is created only after explicit user
activation.

This module is the mechanical core (parse / render / merge / remove /
validate / project / onboarding). The command semantics live in CORE.md
section 1.10; this module never defines protocol law, only the file mechanics.

Canonical file format (`.saipen/USERPERSON.md`):

    # USERPERSON

    - <preference line>

A preference is one markdown bullet. Semantic identity for merging is the
normalized leading phrase, so `add` merges instead of appending duplicate
preference history.
"""

from __future__ import annotations

import re
from pathlib import Path

PROFILE_PATH = ".saipen/USERPERSON.md"
_HEADER = "# USERPERSON"
_MAGIC = "saipen-userperson-v1"

# SubSaipen projections: the relevant subset per role. A projection NEVER
# dumps the whole profile (T-574, SAIPEN v9 section 11).
_PROJECTIONS = {
    "saiui": "UI/design and workflow preferences only; exclude localization "
             "and engineering-rigor preferences that do not affect UI work.",
    "saitranslate": "localization and language preferences only; exclude "
                    "UI/design and workflow preferences.",
    "saiwiki": "documentation and communication preferences only; exclude UI "
               "and localization preferences.",
    "saihunt": "engineering rigor preferences only, and only where they "
               "materially affect investigation; normally no UI or "
               "personality baggage.",
}

_ONBOARDING_QUESTIONS = [
    "How do you prefer decisions between equivalent options to be made, "
    "for example safer and slower versus bolder and faster?",
    "What should the default presentation and tone be for the work this "
    "project produces?",
]


def _semantic_key(line: str) -> str:
    """The merge identity of a preference line.

    The normalized leading phrase up to the first clause separator. Two
    preferences that express the same leading phrase are the same preference
    regardless of how the rest of the sentence is worded, which is what makes
    `add` a merge rather than an append.
    """
    text = line.strip().lstrip("-").strip()
    text = re.split(r"[:;,\.\u2014\u2013]", text, maxsplit=1)[0]
    return re.sub(r"\s+", " ", text).strip().lower()


def parse_profile(text: str) -> dict:
    """Parse the canonical file into a preference list.

    Tolerant on purpose: a preference that does not start with `- ` is
    skipped by parsing and reported by `validate_profile`. Round-trips with
    `render_profile`.
    """
    lines = text.splitlines()
    preferences = []
    if lines and lines[0] == _HEADER:
        for line in lines[1:]:
            stripped = line.strip()
            if stripped.startswith("- "):
                preferences.append(stripped[2:].strip())
    return {"preferences": preferences}


def render_profile(preferences: list[str]) -> str:
    body = "\n".join(f"- {preference}" for preference in preferences)
    return f"{_HEADER}\n\n{body}\n" if body else f"{_HEADER}\n\n"


def merge_profile(current: list[str], additions: list[str]) -> list[str]:
    """Merge additions into the current preference list, keyed semantically.

    An addition whose leading phrase is already covered is a no-op -- never an
    appended duplicate of history.
    """
    result = list(current)
    keys = {_semantic_key(preference) for preference in result}
    for addition in additions:
        cleaned = addition.strip().lstrip("-").strip()
        if not cleaned:
            continue
        key = _semantic_key(cleaned)
        if key in keys:
            continue
        result.append(cleaned)
        keys.add(key)
    return result


def remove_preference(current: list[str], text: str) -> list[str]:
    """Remove every preference whose semantic key matches the given text."""
    target = _semantic_key(text)
    return [preference for preference in current
            if _semantic_key(preference) != target]


def validate_profile(text: str) -> list[str]:
    """Return every structural violation, empty when the profile is valid."""
    errors = []
    lines = text.splitlines()
    if not lines or lines[0] != _HEADER:
        errors.append("USERPERSON file must open with the exact heading "
                      "'# USERPERSON'")
        return errors
    for index, line in enumerate(lines[1:], 2):
        if not line.strip():
            continue
        if not line.startswith("- "):
            errors.append(f"line {index}: every preference must be a markdown "
                          f"bullet starting '- '")
    keys = [_semantic_key(preference)
            for preference in parse_profile(text)["preferences"]]
    seen = set()
    for key in keys:
        if key in seen:
            errors.append("duplicate preference -- `saipen userperson add` "
                          "merges by meaning, never by appending history")
            break
        seen.add(key)
    return errors


def projection(sub_role: str) -> str | None:
    """The relevant preference subset for a SubSaipen role, or None.

    A projection is a statement of scope, never the whole profile.
    """
    return _PROJECTIONS.get(sub_role)


def onboarding_questions() -> list[str]:
    """At most three broad onboarding questions; prefer two."""
    return list(_ONBOARDING_QUESTIONS)


def profile_path(project_root: Path | str) -> Path:
    return Path(project_root) / PROFILE_PATH
