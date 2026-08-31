#!/usr/bin/env python
"""Translate new SPEC.md sections to all 32 locales using Ollama API."""

import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

KITCHEN = Path(".saipen/saitranslate/kitchen")
OLLAMA_URL = "http://localhost:11434/api/generate"

# Compact new sections to translate
NEW_SECTIONS = """## Work, Attempts, and Completion Authority
The BOARD ticket is the durable **Work**. An **Attempt** (`A-###`) is one bounded execution episode of one agent working that Work, recorded as machine-owned `DEC` events in the existing append-only `LOG.md` plus a single optional `STATE.attempt` pointer.

- An Attempt may end `candidate | failed | interrupted | yielded | superseded` with an independent stop reason. **Attempt failure never touches Work identity** -- the successor closes the dangling episode honestly and re-claims the same ticket.
- Completion authority is not transferable to the producer: a candidate episode, its RUN lines and its own assertions are *claims*. Only verification evidence recorded after the claim plus the independent VERIFY -> REVIEW -> SHIP gates admit a transition to DONE. A producer cannot close its own Work, and retroactive self-admission fails validation.
- `saipen brief` synthesizes a cold-handoff projection from canonical state.
- Information honesty is structural: `unknown:` clauses record genuinely unknown facts.
- Canonical project files are the only authority.

## Guarantees, Bounds, and Non-Claims

GUARANTEED: Project-local persistent state, validated state transitions, bounded single-writer semantics.
BOUNDED: Local/shared-filesystem assumptions, explicit protocol versions.
NOT GUARANTEED: Distributed consensus, LLM correctness, external provider availability, durability beyond host FS.

Maturity: DESIGNED -> IMPLEMENTED -> TESTED -> VERIFIED -> RELEASED. A claim is written at the strongest level reached, never higher.
"""

LANGUAGES = {
    "ar": "Arabic", "bg": "Bulgarian", "cs": "Czech", "da": "Danish",
    "de": "German", "el": "Greek", "es": "Spanish", "et": "Estonian",
    "fi": "Finnish", "fr": "French", "he": "Hebrew", "hi": "Hindi",
    "hr": "Croatian", "hu": "Hungarian", "id": "Indonesian", "it": "Italian",
    "ja": "Japanese", "ko": "Korean", "nl": "Dutch", "no": "Norwegian",
    "pl": "Polish", "pt": "Portuguese", "ro": "Romanian", "ru": "Russian",
    "sk": "Slovak", "sv": "Swedish", "th": "Thai", "tr": "Turkish",
    "uk": "Ukrainian", "vi": "Vietnamese", "zh": "Chinese",
}


def translate(text: str, lang_name: str) -> str:
    """Translate using Ollama API."""
    prompt = f"Translate to {lang_name}. Keep markdown, code refs (A-###, STATE.md, LOG.md), and formatting intact. Professional technical translation:\n\n{text}"
    data = json.dumps({"model": "qwen3:1.7b", "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(OLLAMA_URL, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            result = json.loads(resp.read())
            return result.get("response", "")
    except Exception as e:
        print(f"  Error: {e}", file=sys.stderr)
        return ""


def main():
    for lang_code, lang_name in sorted(LANGUAGES.items()):
        spec_file = KITCHEN / lang_code / f"SPEC_{lang_code.upper()}.md"
        if not spec_file.exists():
            continue
        content = spec_file.read_text(encoding="utf-8")
        if "candidate | failed | interrupted" in content:
            print(f"{lang_code}: already done")
            continue

        print(f"{lang_code}: translating to {lang_name}...", end=" ", flush=True)
        translation = translate(NEW_SECTIONS, lang_name)
        if not translation:
            print("FAILED")
            continue

        # Insert before ## Concurrency
        parts = content.split("## Concurrency")
        if len(parts) == 2:
            new_content = parts[0] + translation + "\n\n## Concurrency" + parts[1]
        else:
            new_content = content + "\n\n" + translation

        spec_file.write_text(new_content, encoding="utf-8")
        print(f"OK ({len(translation)} chars)")


if __name__ == "__main__":
    main()
