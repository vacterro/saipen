#!/usr/bin/env python
"""Translate new SPEC sections to remaining locales using Ollama API."""

import json
import sys
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

KITCHEN = Path(".")
OLLAMA_URL = "http://localhost:11434/api/generate"

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

# Remaining locales to translate
REMAINING = {
    "bg": ("Bulgarian", "Concurrency"),
    "cs": ("Czech", "Concurrency"),
    "da": ("Danish", "Samtidighed"),
    "de": ("German", "Nebenl"),
    "el": ("Greek", "Concurrency"),
    "fi": ("Finnish", "Samanaikaisuus"),
    "fr": ("French", "Concurrence"),
    "he": ("Hebrew", "מקביל"),
    "hi": ("Hindi", "समवर्ती"),
    "hr": ("Croatian", "Concurrency"),
    "hu": ("Hungarian", "Concurrency"),
    "id": ("Indonesian", "Concurrency"),
    "nl": ("Dutch", "Gelijktijdigheid"),
    "no": ("Norwegian", "Samtidighet"),
    "ro": ("Romanian", "Concurrency"),
    "sk": ("Slovak", "Concurrency"),
    "sv": ("Swedish", "Samtidighet"),
    "th": ("Thai", "ขอบเขต"),
    "tr": ("Turkish", "Concurrency"),
    "uk": ("Ukrainian", "Межі"),
    "vi": ("Vietnamese", "Ranh giới"),
    "zh": ("Chinese", "竞争"),
}


def translate(text, lang_name):
    prompt = f"Translate to {lang_name}. Keep markdown, code refs (A-###, STATE.md, LOG.md), and formatting intact. Professional technical translation:\n\n{text}"
    data = json.dumps({"model": "qwen3:1.7b", "prompt": prompt, "stream": False}).encode('utf-8')
    req = urllib.request.Request(OLLAMA_URL, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        result = json.loads(resp.read().decode('utf-8'))
        return result.get("response", "")


def main():
    translated = 0
    for lang_code, (lang_name, frag) in sorted(REMAINING.items()):
        spec_file = KITCHEN / lang_code / f"SPEC_{lang_code.upper()}.md"
        if not spec_file.exists():
            print(f"{lang_code}: missing")
            continue
        content = spec_file.read_text(encoding="utf-8")
        if "candidate | failed | interrupted" in content:
            print(f"{lang_code}: done")
            continue
        insert_at = content.find(frag)
        if insert_at < 0:
            print(f"{lang_code}: '{frag}' not found")
            continue
        print(f"{lang_code}: translating...", end=" ", flush=True)
        try:
            t = translate(NEW_SECTIONS, lang_name)
        except Exception as e:
            print(f"FAIL: {e}")
            continue
        if len(t) < 50:
            print(f"EMPTY")
            continue
        new = content[:insert_at] + t + "\n\n" + content[insert_at:]
        spec_file.write_text(new, encoding="utf-8")
        print(f"OK ({len(t)} chars)")
        translated += 1
    print(f"\nTranslated: {translated}")


if __name__ == "__main__":
    main()
