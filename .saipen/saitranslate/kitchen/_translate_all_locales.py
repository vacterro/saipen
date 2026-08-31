#!/usr/bin/env python
"""Translate new SPEC.md sections to all 32 locales using Ollama API."""

import json
import re
import sys
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

KITCHEN = Path(".saipen/saitranslate/kitchen")
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

# Map locale to language name and Concurrency section header (in target language)
LANGUAGES = {
    "ar": ("Arabic", "العربية", "### الحدود والتقسيم"),
    "bg": ("Bulgarian", "български", "## Граници на конкурентността и разпределението"),
    "cs": ("Czech", "čeština", "## Konkurence a distribuční hranice"),
    "da": ("Danish", "dansk", "## Konkurrence og distributionsgrænser"),
    "de": ("German", "Deutsch", "## Wettbewerbs- und Verteilungsgrenzen"),
    "el": ("Greek", "ελληνικά", "## Όρια ανταγωνισμού και διανομής"),
    "es": ("Spanish", "español", "## Límites de concurrencia y distribución"),
    "et": ("Estonian", "eesti", "## Konkurents ja jaotuspiirid"),
    "fi": ("Finnish", "suomi", "## Kilpailu- ja jakelurajat"),
    "fr": ("French", "français", "## Limites de concurrence et de distribution"),
    "he": ("Hebrew", "עברית", "## גבולות תחרותיות והפצה"),
    "hi": ("Hindi", "हिन्दी", "## प्रतिस्पर्धा और वितरण सीमाएँ"),
    "hr": ("Croatian", "hrvatski", "## Granice konkurentnosti i distribucije"),
    "hu": ("Hungarian", "magyar", "## Verseny- és elosztási korlátok"),
    "id": ("Indonesian", "Bahasa Indonesia", "## Batasan Kompetisi dan Distribusi"),
    "it": ("Italian", "italiano", "## Limiti di concorrenza e distribuzione"),
    "ja": ("Japanese", "日本語", "## 競合と配布の境界"),
    "ko": ("Korean", "한국어", "## 경쟁 및 배포 경계"),
    "nl": ("Dutch", "Nederlands", "## Concurrentie- en distributiegrenzen"),
    "no": ("Norwegian", "norsk", "## Konkurranse- og distribusjonsgrenser"),
    "pl": ("Polish", "polski", "## Granice konkurencyjności i dystrybucji"),
    "pt": ("Portuguese", "português", "## Limites de concorrência e distribuição"),
    "ro": ("Romanian", "română", "## Limite de concurență și distribuție"),
    "ru": ("Russian", "русский", "## Границы конкурентности и распределения"),
    "sk": ("Slovak", "slovenčina", "## Hranice konkurencie a distribúcie"),
    "sv": ("Swedish", "svenska", "## Konkurrens- och distributionsgränser"),
    "th": ("Thai", "ไทย", "## ขีดจำกัดการแข่งขันและการกระจาย"),
    "tr": ("Turkish", "Türkçe", "## Rekabet ve Dağıtım Sınırları"),
    "uk": ("Ukrainian", "українська", "## Границі конкуренції та розподілу"),
    "vi": ("Vietnamese", "Tiếng Việt", "## Giới hạn cạnh tranh và phân phối"),
    "zh": ("Chinese", "中文", "## 竞争与分发边界"),
}


def translate(text: str, lang_name: str) -> str:
    prompt = f"Translate to {lang_name}. Keep markdown, code refs (A-###, STATE.md, LOG.md), and formatting intact. Professional technical translation:\n\n{text}"
    data = json.dumps({"model": "qwen3:1.7b", "prompt": prompt, "stream": False}).encode('utf-8')
    req = urllib.request.Request(OLLAMA_URL, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        result = json.loads(resp.read().decode('utf-8'))
        return result.get("response", "")


def find_insertion_point(content: str, concurrency_header: str) -> int:
    """Find where to insert new sections (before Concurrency)."""
    # Try exact match first
    idx = content.find(concurrency_header)
    if idx > 0:
        return idx
    # Try partial match (first 10 chars)
    idx = content.find(concurrency_header[:10])
    if idx > 0:
        return idx
    # Try to find any ## header that looks like concurrency
    for match in re.finditer(r'^## .*(?:oncur|oncur|ompiti|istrib| konk| grenz|limite|边界|境界|경쟁|格)', content, re.MULTILINE):
        return match.start()
    return -1


def main():
    print("=== Translating new SPEC.md sections to all 32 locales ===\n")

    translated = 0
    skipped = 0
    failed = 0

    for lang_code, (lang_name, _, concurrency_header) in sorted(LANGUAGES.items()):
        spec_file = KITCHEN / lang_code / f"SPEC_{lang_code.upper()}.md"
        if not spec_file.exists():
            print(f"{lang_code}: SPEC file missing, skipping")
            skipped += 1
            continue

        content = spec_file.read_text(encoding="utf-8")
        if "candidate | failed | interrupted" in content or "A-###" in content.split(concurrency_header[:15])[0].split("##")[-1] if concurrency_header[:15] in content else False:
            print(f"{lang_code}: already has new sections")
            skipped += 1
            continue

        insert_at = find_insertion_point(content, concurrency_header)
        if insert_at < 0:
            print(f"{lang_code}: could not find insertion point, skipping")
            skipped += 1
            continue

        print(f"{lang_code}: translating to {lang_name}...", end=" ", flush=True)
        try:
            translation = translate(NEW_SECTIONS, lang_name)
        except Exception as e:
            print(f"FAILED: {e}")
            failed += 1
            continue

        if not translation or len(translation) < 50:
            print(f"EMPTY ({len(translation)} chars)")
            failed += 1
            continue

        new_content = content[:insert_at] + translation + "\n\n" + content[insert_at:]
        spec_file.write_text(new_content, encoding="utf-8")
        print(f"OK ({len(translation)} chars)")
        translated += 1

    print(f"\n=== Done: {translated} translated, {skipped} skipped, {failed} failed ===")


if __name__ == "__main__":
    main()
