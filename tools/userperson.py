#!/usr/bin/env python
"""Optional USERPERSON preference profile mechanics (T-574, T-577).

USERPERSON is a meta-control, OFF by default. With no `.saipen/USERPERSON.md`
the protocol is silent: no warning, no boot failure, no placeholder, no
onboarding, no cold-start cost. The file is created only after explicit user
activation.

This module is the mechanical core: parse / render / merge / remove /
validate / projection. It NEVER claims to understand natural-language
semantics. Preference identity is STRUCTURED (a category key plus the exact
preference text); the merge is deterministic lexical dedup on that identity,
and semantic distillation (recognizing that two differently-worded preferences
mean the same thing) is the AGENT's job BEFORE calling this writer, per
saipen/IMPROVE.md section 8 and the T-577 regression. A helper that split
natural language on a separator and called the result "semantic" silently
discarded distinct preferences such as "Prefer UI: Vintage Golden" and
"Prefer UI: Material Design" (both reduced to "prefer ui") -- that false
equivalence is the defect this format fixes.

Canonical file format (`.saipen/USERPERSON.md`):

    # USERPERSON

    - [Category] preference text

Every preference is a markdown bullet with a bracketed category key and the
preference text. Legacy bullets without a category parse as category
`General`. A preference's identity is `(category, normalized full text)`; two
preferences that differ in either are distinct and BOTH are kept.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

PROFILE_PATH = ".saipen/USERPERSON.md"
_HEADER = "# USERPERSON"
_LEGACY_CATEGORY = "general"

# Category policies per SubSaipen role. A projection selects only preferences
# whose category is in the role's policy -- never the whole profile. saihunt
# deliberately excludes UI/presentation categories unless the investigation
# makes a specific category relevant, and that relevance is recorded by the
# agent in the projection handoff, never invented by the helper.
_PROJECTION_POLICIES = {
    "saiui": {"ui", "workflow"},
    "saitranslate": {"localization", "language"},
    "saiwiki": {"documentation", "communication"},
    "saihunt": {"automation"},
}

_ONBOARDING_QUESTIONS = [
    "How do you prefer decisions between equivalent options to be made, "
    "for example safer and slower versus bolder and faster?",
    "What should the default presentation and tone be for the work this "
    "project produces?",
]

_CATEGORY_RE = re.compile(r"^\[([^\]]+)\]\s*(.*)$", re.DOTALL)


def _canonical(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).lower()


def _entry(category: str, text: str) -> dict:
    entry = {"category": category.strip(), "text": text.strip()}
    identity = _canonical(f"{entry['category']}: {entry['text']}")
    entry["id"] = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]
    return entry


def _split_line(line: str) -> dict | None:
    stripped = line.strip()
    if not stripped.startswith("- "):
        return None
    body = stripped[2:].strip()
    match = _CATEGORY_RE.match(body)
    if match:
        return _entry(match.group(1), match.group(2).strip())
    return _entry(_LEGACY_CATEGORY, body)


def parse_profile(text: str) -> dict:
    """Parse the canonical file into a preference list.

    Each entry: `id` (content hash), `category`, `text`. Round-trips with
    `render_profile`.
    """
    lines = text.splitlines()
    preferences = []
    if lines and lines[0] == _HEADER:
        for line in lines[1:]:
            entry = _split_line(line)
            if entry is not None:
                preferences.append(entry)
    return {"preferences": preferences}


def render_profile(preferences: list[dict] | list[str]) -> str:
    body_lines = []
    for preference in preferences:
        if isinstance(preference, dict):
            body_lines.append(
                f"- [{preference['category']}] {preference['text']}")
        elif preference.strip().startswith("- "):
            body_lines.append(preference.strip())
        else:
            body_lines.append(f"- [{_LEGACY_CATEGORY}] {preference}")
    body = "\n".join(body_lines)
    return f"{_HEADER}\n\n{body}\n" if body else f"{_HEADER}\n\n"


def merge_profile(current: list[dict] | list[str],
                  additions: list[dict] | list[str]) -> list[dict]:
    """Deterministic lexical merge on structured preference identity.

    Two preferences are the same when category AND normalized full text are
    identical. Anything else is distinct and kept. The helper never decides
    that differently-worded preferences mean the same thing -- the agent
    distills semantics BEFORE calling this writer (T-577).
    """

    def _to_entry(value: dict | str) -> dict | None:
        if isinstance(value, dict):
            return _entry(value["category"], value["text"])
        stripped = value.strip()
        if stripped.startswith("- "):
            return _split_line(stripped)
        return _entry(_LEGACY_CATEGORY, stripped)

    result = [_to_entry(p) for p in current]
    result = [e for e in result if e is not None and e["text"]]
    keys = {_canonical(f"{e['category']}: {e['text']}") for e in result}
    for addition in additions:
        entry = _to_entry(addition)
        if entry is None or not entry["text"]:
            continue
        key = _canonical(f"{entry['category']}: {entry['text']}")
        if key in keys:
            continue
        result.append(entry)
        keys.add(key)
    return result


def remove_preference(current: list[dict], text: str) -> list[dict]:
    """Remove preferences whose text matches the given text, ignoring category."""
    target = _canonical(text)
    return [preference for preference in current
            if _canonical(preference["text"]) != target]


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
        if not line.lstrip().startswith("- "):
            errors.append(f"line {index}: every preference must be a markdown "
                          f"bullet starting '- '")
    preferences = parse_profile(text)["preferences"]
    seen = set()
    for entry in preferences:
        key = _canonical(f"{entry['category']}: {entry['text']}")
        if key in seen:
            errors.append("duplicate preference -- `saipen userperson add` "
                          "merges deterministically on category and exact "
                          "text, never by guessing meaning")
            break
        seen.add(key)
    return errors


def projection_policy(role: str) -> frozenset[str]:
    """The allowed preference categories for a SubSaipen role, or empty."""
    return frozenset(_PROJECTION_POLICIES.get(role, set()))


def project_profile(preferences: list[dict], role: str,
                    source_fingerprint: str = "") -> dict:
    """Produce the actual bounded projection for a role.

    Returns a structured handoff: the role, the allowed categories, the source
    profile fingerprint, and ONLY the preferences whose category is in the
    policy. Never the whole profile. The handoff is auditable by Core
    (saipen/IMPROVE.md section 8).
    """
    policy = projection_policy(role)
    selected = [entry for entry in preferences
                if entry["category"].strip().lower() in policy]
    return {
        "role": role,
        "projection_policy": sorted(policy),
        "source_fingerprint": source_fingerprint,
        "preferences": selected,
    }


def profile_fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def onboarding_questions() -> list[str]:
    """At most three broad onboarding questions; prefer two."""
    return list(_ONBOARDING_QUESTIONS)


def profile_path(project_root: Path | str) -> Path:
    return Path(project_root) / PROFILE_PATH
