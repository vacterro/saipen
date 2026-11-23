"""HUNT-019 census helpers: stale markers, zero-reference defs, empty excepts.

Read-only measurements over tracked files. Output is one line per metric so a
truncated capture still leaves the numbers legible.
"""

import collections
import re
import subprocess
import sys

MARKER = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b")


def tracked():
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True).stdout
    return [f for f in out.splitlines() if f.endswith((".py", ".md", ".json", ".txt"))]


def signal3():
    hits = collections.Counter()
    cwd = subprocess.run(["pwd"], capture_output=True, text=True).stdout.strip()
    for f in tracked():
        fp = f
        if not fp.startswith("."):
            fp = f  # git ls-files already relative
        n = 0
        try:
            for line in open(fp, encoding="utf-8", errors="ignore"):
                if MARKER.search(line):
                    n += 1
        except FileNotFoundError:
            continue
        if n:
            hits[f] = n
    return hits


def toplevel(f):
    if f.startswith(".saipen/extensions/subs/"):
        return ".saipen/extensions/subs/" + f.split("/")[3]
    return f.split("/")[0] if "/" in f else f


def signal6():
    out = subprocess.run(
        ["git", "grep", "-n", "-E", r"^\s*(async )?def\s+", "tools/"],
        capture_output=True, text=True,
    ).stdout
    defs = set()
    where = {}
    for line in out.splitlines():
        parts = line.rsplit(":", 2)
        if len(parts) < 3:
            continue
        name = parts[2].split("(")[0].strip()
        if name.startswith("_"):
            continue
        defs.add(name)
        where[name] = parts[0] + ":" + parts[1]
    zero = []
    for name in sorted(defs):
        r = subprocess.run(
            ["git", "grep", "-c", "-E", name + r"\b"],
            capture_output=True, text=True,
        )
        n = 0
        for row in r.stdout.splitlines():
            try:
                n += int(row.rsplit(":", 1)[1])
            except ValueError:
                pass
        if n <= 1:
            zero.append((name, n, where[name]))
    return defs, zero


def main():
    h3 = signal3()
    print("=== SIGNAL 3 (stale markers) ===")
    print("files:", len(h3), "hits:", sum(h3.values()))
    for f, n in h3.most_common(8):
        print("  ", n, f)
    defs, zero = signal6()
    print("=== SIGNAL 6 (zero-reference defs) ===")
    print("defs:", len(defs), "zero-ref:", len(zero))
    for name, n, w in zero[:12]:
        print("  ", n, w, name)


if __name__ == "__main__":
    sys.exit(main())
