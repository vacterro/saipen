#!/usr/bin/env python
"""FORCE-FRESH Scenarios.md: keep committed rows 1-184, add 185-254 by ID from CONFORMANCE."""
import re
import subprocess

WIKI = ".saipen/extensions/subs/saiwiki/kitchen/wiki"

committed = subprocess.run(
    ["git", "-C", WIKI, "show", "HEAD:Scenarios.md"],
    capture_output=True, text=True, encoding="utf-8",
).stdout

# Parse CONFORMANCE rows -> {id: (scenario, enforcement)}
rows = {}
for line in open("saipen/CONFORMANCE.md", encoding="utf-8"):
    m = re.match(r"^\| (\d+) \| (.*?)(?: \| (.*))? \|\s*$", line)
    if m:
        n = int(m.group(1))
        sc = m.group(2).strip()
        en = (m.group(3) or "").strip()
        rows[n] = (sc, en)


def title_of(t: str) -> str:
    """First clause of the CONFORMANCE scenario text."""
    for sep in (". ", " -- "):
        if sep in t:
            return t.split(sep)[0].strip()
    return t[:140].strip()


def inv_of(e: str) -> str:
    """Short invariant from the enforcement column."""
    e = re.sub(r"^Enforced (directly )?by ", "", e)
    for sep in (". ", " -- ", ": "):
        if sep in e:
            e = e.split(sep)[0].strip()
    e = e.strip()
    return e[:120].strip()


# Build committed lines 1-184 as-is, drop junk, replace header, re-add closing quote
out = []
for line in committed.splitlines():
    m = re.match(r"^\| (\d+) \| .* \| .* \|$", line)
    if m and int(m.group(1)) <= 184:
        out.append(line)
    elif line.startswith("# Scenarios"):
        out.append(line)
    elif "behavioral conformance scenarios" in line:
        out.append("254 behavioral conformance scenarios (CONFORMANCE.md rows 1-254). Each tests a specific SAIPEN invariant.")
    elif line.strip().startswith("> ") and "сценария" in line:
        continue
    elif line.startswith("|") and not line.startswith("|---") and not line.startswith("| #"):
        continue

out.append("")
for n in range(185, 255):
    sc, en = rows[n]
    out.append(f"| {n} | {title_of(sc)} | {inv_of(en)} |")
out.append("")
out.append('> "254 сценария. Каждый проверяет одно правило. Никаких \'ну, это редко бывает\'. Тест упал — значит что-то сломалось. Тест прошёл — значит работает. Агент не гадает. Агент проверяет."')

path = f"{WIKI}/Scenarios.md"
with open(path, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(out) + "\n")
print("written", path)
