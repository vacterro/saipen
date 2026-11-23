"""Before/after validator verdicts on scratch COPIES of downstream .saipen.

Usage: python downstream_diff.py <before home> <after home> <work dir> <project>...
Copies each project's .saipen (without cache/) into <work dir>/<name>/, never
touching the original, and diffs FAIL lines plus the WARN categories.
"""
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

before_home, after_home, work = (Path(p).resolve() for p in sys.argv[1:4])
projects = [Path(p) for p in sys.argv[4:]]
work.mkdir(parents=True, exist_ok=True)


def verdict(home: Path, project: Path) -> tuple[list[str], Counter]:
    proc = subprocess.run(
        [sys.executable, str(home / "tools" / "validate.py"), "--gate", "core",
         "--no-receipt", "--project-root", str(project)],
        cwd=str(project), capture_output=True, text=True, encoding="utf-8",
        errors="replace", stdin=subprocess.DEVNULL, timeout=1200,
    )
    fails = sorted(
        re.sub(r"[0-9a-f]{12,64}", "<hex>", line)
        for line in proc.stdout.splitlines() if line.startswith("FAIL")
    )
    warns = Counter(
        m.group(1) for m in re.finditer(r"(?m)^WARN \[([a-z0-9-]+)\]", proc.stdout)
    )
    return fails, warns


for original in projects:
    name = original.name.strip("_") or original.name
    copy = work / name
    if copy.exists():
        shutil.rmtree(copy)
    copy.mkdir(parents=True)
    shutil.copytree(
        original / ".saipen", copy / ".saipen",
        ignore=shutil.ignore_patterns("cache", "__pycache__"),
    )
    subprocess.run(["git", "init", "-q"], cwd=copy)
    b_fail, b_warn = verdict(before_home, copy)
    a_fail, a_warn = verdict(after_home, copy)
    gone = [f for f in b_fail if f not in a_fail]
    new = [f for f in a_fail if f not in b_fail]
    warn_delta = {k: a_warn.get(k, 0) - b_warn.get(k, 0)
                  for k in set(a_warn) | set(b_warn) if a_warn.get(k, 0) != b_warn.get(k, 0)}
    print(f"== {name}: FAIL before {len(b_fail)} after {len(a_fail)}; new {len(new)}, gone {len(gone)}; WARN delta {warn_delta}")
    for line in new[:5]:
        print("   NEW ", line[:200])
    for line in gone[:5]:
        print("   GONE", line[:200])
