#!/usr/bin/env python
"""Translate new SPEC.md sections to all 32 locales using Ollama."""

import hashlib
import re
import subprocess
import sys
from pathlib import Path

KITCHEN = Path(".saipen/saitranslate/kitchen")
SPEC_SOURCE = Path("SPEC.md")

# The new sections to translate (English source)
NEW_SECTIONS_EN = """
## Work, Attempts, and Completion Authority
The BOARD ticket is the durable **Work**. An **Attempt** (`A-###`) is one bounded execution episode of one agent working that Work, recorded as machine-owned `DEC` events in the existing append-only `LOG.md` plus a single optional `STATE.attempt` pointer. The Attempt is deliberately not a storage subsystem: no database, no daemon, no second writer.

- An Attempt may end `candidate | failed | interrupted | yielded | superseded` with an independent stop reason (`context_limit`, `process_crash`, `deliberate_handoff`, ...). **Attempt failure never touches Work identity** -- the successor closes the dangling episode honestly and re-claims the same ticket.
- Completion authority is not transferable to the producer: a candidate episode, its RUN lines and its own assertions are *claims*. Only verification evidence recorded after the claim (the VERIFY boundary + PASS/MANUAL-VERIFY grammar) plus the independent VERIFY -> REVIEW -> SHIP gates admit a transition to DONE. A producer cannot close its own Work, and retroactive self-admission fails validation.
- `saipen brief` synthesizes a cold-handoff projection (Work, objective, current/last attempt, why it stopped, blockers, known unknowns, exact next action). It is a derived view: it writes nothing, runs nothing, and can always be rebuilt from canonical state.
- Information honesty is structural: `unknown:` clauses record what is genuinely unknown; missing information is never promoted to fact, and uncertainty never substitutes for verification evidence.
- Canonical project files are the only authority. CLI output, projections, caches or external consumers that disagree with `.saipen/` are stale by definition and must be rebuildable from it.

## Guarantees, Bounds, and Non-Claims
Stated plainly, at the strength the implementation actually supports.

GUARANTEED (implemented + validated):
- Project-local persistent state: cold reconstruction of Work, objective, last attempt, stop reason, known evidence and next action from `.saipen/` alone.
- Validated state transitions: every canonical mutation passes the transactional fast gate; the release validator re-checks the full contract fail-closed.
- Bounded single-writer semantics on a shared filesystem (claim serialization, one open attempt, OPS transaction ordering LOG -> BOARD -> STATE).

BOUNDED (designed for, environment-dependent):
- Local/shared-filesystem assumptions: atomicity is temp-file-plus-rename ordering, not fsync-durability guarantees.
- Explicitly supported protocol/schema versions: older states read as legacy with upgrade-at-next-checkpoint; newer-than-running states refuse fail-closed.

NOT GUARANTEED:
- Distributed consensus across disconnected machines (see Concurrency below).
- Correctness of arbitrary LLM output -- only that fabricated completions cannot reach the board green unchallenged.
- External provider availability, model quality, or uninterrupted execution -- the protocol assumes every agent may vanish mid-word and makes that survivable rather than preventing it.
- Durability beyond what the host filesystem itself promises.

Maturity vocabulary used throughout the docs and release notes: DESIGNED -> IMPLEMENTED -> TESTED -> VERIFIED -> RELEASED. A claim is written at the strongest level it has actually reached, never higher.
"""

# Language names for translation prompts
LANGUAGES = {
    "ar": ("Arabic", "العربية"),
    "bg": ("Bulgarian", "български"),
    "cs": ("Czech", "čeština"),
    "da": ("Danish", "dansk"),
    "de": ("German", "Deutsch"),
    "ded": ("Ded Voice", "Дед голос"),
    "el": ("Greek", "ελληνικά"),
    "es": ("Spanish", "español"),
    "et": ("Estonian", "eesti"),
    "fi": ("Finnish", "suomi"),
    "fr": ("French", "français"),
    "he": ("Hebrew", "עברית"),
    "hi": ("Hindi", "हिन्दी"),
    "hr": ("Croatian", "hrvatski"),
    "hu": ("Hungarian", "magyar"),
    "id": ("Indonesian", "Bahasa Indonesia"),
    "it": ("Italian", "italiano"),
    "ja": ("Japanese", "日本語"),
    "ko": ("Korean", "한국어"),
    "nl": ("Dutch", "Nederlands"),
    "no": ("Norwegian", "norsk"),
    "pl": ("Polish", "polski"),
    "pt": ("Portuguese", "português"),
    "ro": ("Romanian", "română"),
    "ru": ("Russian", "русский"),
    "sk": ("Slovak", "slovenčina"),
    "sv": ("Swedish", "svenska"),
    "th": ("Thai", "ไทย"),
    "tr": ("Turkish", "Türkçe"),
    "uk": ("Ukrainian", "українська"),
    "vi": ("Vietnamese", "Tiếng Việt"),
    "zh": ("Chinese", "中文"),
}


def translate_with_ollama(text: str, target_lang: str, lang_name: str) -> str:
    """Translate text using Ollama."""
    if target_lang == "ded":
        # Ded voice: angry grandpa, compressed, mocking, but factually exact
        prompt = f"""Translate the following technical specification text to Russian in the "Ded voice" style:
- Blunt, compressed, street-smart tone
- Cut articles, filler, pleasantries
- Mock bad code/errors
- Still factually exact - no jokes in technical content
- Keep all code references (A-###, STATE.md, LOG.md, etc.) unchanged
- Keep markdown formatting intact

Text to translate:
{text}"""
    else:
        prompt = f"""Translate the following technical specification text to {lang_name}.
Rules:
- Keep all code references (A-###, STATE.md, LOG.md, etc.) unchanged
- Keep markdown formatting intact
- Keep technical terms accurate
- Natural, professional translation

Text to translate:
{text}"""

    try:
        result = subprocess.run(
            ["ollama", "run", "qwen3:14b"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"  Error translating to {lang_name}: {e}", file=sys.stderr)
        return ""


def update_spec_locale(locale_dir: Path, lang_code: str, lang_name: str, translation: str):
    """Insert translated sections into the locale's SPEC file."""
    spec_file = locale_dir / f"SPEC_{lang_code.upper()}.md"
    if not spec_file.exists():
        print(f"  {spec_file} not found, skipping")
        return False

    content = spec_file.read_text(encoding="utf-8")

    # Check if sections already exist
    if "## Work, Attempts" in content or "## Work/" in content or "Work" in content.split("## Concurrency")[0].split("##")[-1]:
        # Check more carefully - might be a different "Work"
        if "candidate | failed | interrupted" in content or "A-###" in content:
            print(f"  {lang_code}: Sections already present, skipping")
            return True

    # Find the insertion point - before "## Concurrency"
    concurrency_marker = "## Concurrency"
    if concurrency_marker in content:
        # Insert before Concurrency section
        parts = content.split(concurrency_marker)
        new_content = parts[0] + translation + "\n\n" + concurrency_marker + parts[1]
    else:
        # Append at end
        new_content = content + "\n\n" + translation

    # Update source digest
    # Remove old digest line
    new_content = re.sub(r'\n*<!-- source-digest:.*-->\s*$', '', new_content)

    spec_file.write_text(new_content, encoding="utf-8")
    print(f"  {lang_code}: Updated {spec_file.name}")
    return True


def compute_source_digest(path: Path) -> str:
    """Compute source digest for a file."""
    VERSION_RE = re.compile(r"\d+\.\d+\.\d+")
    with open(path, "rb") as f:
        content = f.read()
    text = content.decode("utf-8").replace("\r\n", "\n")
    return hashlib.sha256(VERSION_RE.sub("VERSION", text).encode("utf-8")).hexdigest()[:16]


def main():
    print("=== Translating new SPEC.md sections to all 32 locales ===")
    print(f"Source: {SPEC_SOURCE}")
    print(f"Kitchen: {KITCHEN}")
    print()

    # Check which locales need translation
    needs_translation = []
    for lang_code, (lang_name, _) in sorted(LANGUAGES.items()):
        locale_dir = KITCHEN / lang_code
        spec_file = locale_dir / f"SPEC_{lang_code.upper()}.md"
        if not spec_file.exists():
            print(f"  {lang_code}: SPEC file missing, will create")
            needs_translation.append((lang_code, lang_name))
            continue

        content = spec_file.read_text(encoding="utf-8")
        # Check if new sections exist
        if "candidate | failed | interrupted" in content or "A-###" in content:
            print(f"  {lang_code}: Already has new sections")
        else:
            print(f"  {lang_code}: Needs new sections")
            needs_translation.append((lang_code, lang_name))

    print(f"\n{len(needs_translation)} locales need translation")
    print()

    if not needs_translation:
        print("All locales already have the new sections!")
        return

    # Translate to each locale
    for i, (lang_code, lang_name) in enumerate(needs_translation):
        print(f"[{i+1}/{len(needs_translation)}] Translating to {lang_name} ({lang_code})...")

        translation = translate_with_ollama(NEW_SECTIONS_EN, lang_code, lang_name)
        if not translation:
            print(f"  FAILED: No translation returned")
            continue

        locale_dir = KITCHEN / lang_code
        update_spec_locale(locale_dir, lang_code, lang_name, translation)
        print(f"  Done")

    print("\n=== Translation complete ===")


if __name__ == "__main__":
    main()
