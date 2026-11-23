"""Find paragraphs of the protocol law that restate one another.

Paragraph = a run of non-blank lines (a table row counts as its own
paragraph). Similarity = Jaccard overlap of word 4-grams. Reported: pairs in
DIFFERENT files, or far apart in one file, above a threshold, largest first.
"""
import re
import sys
from pathlib import Path

base = Path(sys.argv[1])
threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 0.45
word = re.compile(r"[a-z0-9_`-]+")


def paragraphs(path: Path):
    block, start = [], 0
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        text = line.strip()
        if text.startswith("|") and not text.startswith("|--"):
            if block:
                yield start, " ".join(block)
                block = []
            yield number, text
            continue
        if not text or text.startswith(("#", "<!--", "```", "|--")):
            if block:
                yield start, " ".join(block)
                block = []
            continue
        if not block:
            start = number
        block.append(text)
    if block:
        yield start, " ".join(block)


def shingles(text: str) -> frozenset:
    words = word.findall(text.lower())
    return frozenset(tuple(words[i : i + 4]) for i in range(len(words) - 3))


items = []
for path in sorted(base.rglob("*.md")):
    rel = path.relative_to(base).as_posix()
    for number, text in paragraphs(path):
        if len(text) >= 160:
            grams = shingles(text)
            if len(grams) >= 12:
                items.append((rel, number, text, grams))
print("paragraphs measured:", len(items))
pairs = []
for i, (rel_a, n_a, text_a, grams_a) in enumerate(items):
    for rel_b, n_b, text_b, grams_b in items[i + 1 :]:
        if rel_a == rel_b and abs(n_a - n_b) < 3:
            continue
        common = len(grams_a & grams_b)
        if common < 8:
            continue
        score = common / len(grams_a | grams_b)
        if score >= threshold:
            pairs.append((min(len(text_a), len(text_b)), score, rel_a, n_a, rel_b, n_b, text_a, text_b))
pairs.sort(reverse=True)
print("restating pairs at or above", threshold, ":", len(pairs),
      "| bytes of the smaller side, summed:", sum(p[0] for p in pairs))
for size, score, rel_a, n_a, rel_b, n_b, text_a, text_b in pairs[:25]:
    print(f"{size:5d} {score:.2f} {rel_a}:{n_a} <-> {rel_b}:{n_b}")
    print("      A:", text_a[:150])
    print("      B:", text_b[:150])
