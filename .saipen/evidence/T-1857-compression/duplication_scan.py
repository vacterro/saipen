"""Read-only duplicate/near-duplicate analysis across saipen/ docs.

Purpose: SRC-289 §7 asks for proven duplicate knowledge to be removed through a
single authoritative owner. This measures candidates; it changes nothing.

Three measurements:
  1. exact duplicate sentences across documents
  2. near-duplicate paragraphs (token-set Jaccard) across documents
  3. duplicate lines within CORE.md itself

Every reported duplicate still has to be judged by a human before deletion:
a repeated normative clause in two owners is a contradiction, not redundancy.
"""

from __future__ import annotations

import collections
import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parents[3] / "saipen"


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\r\n", "\n")).strip()


def sentences(text: str) -> list[str]:
    body = normalized(text)
    parts = re.split(r"(?<=[.!?])\s+", body)
    return [p for p in parts if len(p) >= 60]


def paragraphs(text: str) -> list[str]:
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n"))
    return [normalized(b) for b in blocks if len(normalized(b)) >= 160]


def tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9_\-]{4,}", text.lower())}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def main() -> int:
    docs = sorted(p for p in ROOT.glob("*.md"))
    texts = {p.name: p.read_text(encoding="utf-8", errors="replace") for p in docs}

    print(f"scanned {len(docs)} documents\n")

    # 1. exact duplicate sentences across documents
    owner: dict[str, set[str]] = collections.defaultdict(set)
    for name, text in texts.items():
        for s in set(sentences(text)):
            owner[s].add(name)
    cross = {s: names for s, names in owner.items() if len(names) > 1}
    print(f"== exact duplicate sentences across documents: {len(cross)}")
    for s, names in sorted(cross.items(), key=lambda kv: -len(kv[0]))[:10]:
        print(f"   [{','.join(sorted(names))}] {len(s)}B  {s[:110]}...")

    # 2. near-duplicate paragraphs across documents
    para: dict[str, list[tuple[str, set[str]]]] = collections.defaultdict(list)
    for name, text in texts.items():
        for p in paragraphs(text):
            para[name].append((p, tokens(p)))
    near: list[tuple[float, str, str, str, str]] = []
    names = list(para)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            for pa, ta in para[a]:
                for pb, tb in para[b]:
                    score = jaccard(ta, tb)
                    if score >= 0.62:
                        near.append((score, a, b, pa, pb))
    near.sort(reverse=True)
    print(f"\n== near-duplicate paragraph pairs (jaccard>=0.62): {len(near)}")
    for score, a, b, pa, pb in near[:12]:
        print(f"   {score:.2f} {a} <-> {b}")
        print(f"        {pa[:120]}...")
        print(f"        {pb[:120]}...")

    # 3. duplicate lines within each document
    print("\n== repeated lines within one document")
    any_repeat = False
    for name, text in texts.items():
        lines = [normalized(ln) for ln in text.replace("\r\n", "\n").split("\n")]
        repeated = [
            (ln, n) for ln, n in collections.Counter(ln for ln in lines if len(ln) >= 50).items() if n > 1
        ]
        if repeated:
            any_repeat = True
            print(f"   {name}: {len(repeated)}")
            for ln, n in repeated[:4]:
                print(f"      x{n} {ln[:110]}")
    if not any_repeat:
        print("   none")

    # 4. per-document size, largest first
    print("\n== document sizes")
    for name, text in sorted(texts.items(), key=lambda kv: -len(kv[1].encode("utf-8"))):
        print(f"   {name:26} {len(text.encode('utf-8')):7} B")

    return 0


if __name__ == "__main__":
    sys.exit(main())
