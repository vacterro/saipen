"""Classify the T-1370 core-unit A/B by failing-test IDENTITY, not by count.

A count comparison passes while one red is swapped for another, so this reads
every `FAIL:`/`ERROR:` header out of both verbose runs and does set arithmetic:

    PATCH_OWNED = red in CURRENT, green or absent in BASE
    PRE_EXISTING = red in both
    FIXED        = red in BASE, green in CURRENT
    UNKNOWN      = red in CURRENT whose module is not present in BASE at all
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HEADER = re.compile(r"^(FAIL|ERROR): (\S+) \(([^)]+)\)(.*)$")
RESULT = re.compile(r"^Ran (\d+) tests in ([\d.]+)s")


def parse(path: Path) -> dict:
    reds: dict[str, str] = {}
    modules: set[str] = set()
    ran = 0
    summary = ""
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = HEADER.match(line)
        if match:
            kind, _name, dotted, suffix = match.groups()
            reds[dotted.strip() + suffix.strip()] = kind
            continue
        ran_match = RESULT.match(line)
        if ran_match:
            ran = int(ran_match.group(1))
        if line.startswith(("OK", "FAILED (")):
            summary = line.strip()
        # "test_x (module.Class.test_x)" progress lines carry the module name.
        if " (" in line and line.rstrip().endswith("..."):
            dotted = line.split(" (", 1)[1].split(")", 1)[0]
            if "." in dotted:
                modules.add(dotted.split(".", 1)[0])
    return {"reds": reds, "modules": modules, "ran": ran, "summary": summary}


def main() -> int:
    cur = parse(Path(sys.argv[1]))
    base = parse(Path(sys.argv[2]))

    cur_ids = set(cur["reds"])
    base_ids = set(base["reds"])

    patch_owned = []
    unknown = []
    for red in sorted(cur_ids - base_ids):
        module = red.split(".", 1)[0]
        (unknown if module not in base["modules"] else patch_owned).append(red)

    report = {
        "current": {"ran": cur["ran"], "summary": cur["summary"], "reds": len(cur_ids)},
        "baseline": {"ran": base["ran"], "summary": base["summary"], "reds": len(base_ids)},
        "PATCH_OWNED": patch_owned,
        "UNKNOWN": unknown,
        "PRE_EXISTING": sorted(cur_ids & base_ids),
        "FIXED_BY_PATCH": sorted(base_ids - cur_ids),
        "new_modules_in_current": sorted(cur["modules"] - base["modules"]),
    }
    print(json.dumps(report, indent=2))
    return 0 if not patch_owned and not unknown else 1


if __name__ == "__main__":
    raise SystemExit(main())
