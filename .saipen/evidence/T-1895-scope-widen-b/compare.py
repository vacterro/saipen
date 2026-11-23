"""T-1895: per-module `ran` equality between a FULL and a narrowed sandbox.

A widened declaration is only safe when the module ran the SAME tests in the
narrowed sandbox it ran in the full one. `verdict: PASS` alone does not prove
that -- a module that silently collected fewer tests would still pass.

This reads two focused-unit records produced by the SAME pattern set, one before
the declaration and one after, and compares each module's own `ran` and red set.

    python .saipen/evidence/T-1895-scope-widen-b/compare.py <full.json> <narrow.json>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def by_pattern(record_path: str) -> dict[str, dict]:
    record = json.loads(Path(record_path).read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for run in record.get("runs") or []:
        out[str(run.get("pattern"))] = {
            "ran": run.get("ran"),
            "status": run.get("status"),
            "red": sorted(run.get("red") or []),
            "exit_code": run.get("exit_code"),
        }
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: compare.py <full.json> <narrow.json>")
        return 2
    full = by_pattern(argv[1])
    narrow = by_pattern(argv[2])
    full_record = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    narrow_record = json.loads(Path(argv[2]).read_text(encoding="utf-8"))

    scope = narrow_record.get("sandbox_scope") or {}
    print(f"full  : {argv[1]}")
    print(f"        duration {full_record.get('duration_s')}s "
          f"copy {((full_record.get('timings_s') or {}).get('copy_wall_s'))}s "
          f"mode {(full_record.get('sandbox_scope') or {}).get('mode')} "
          f"ran {full_record.get('ran')}")
    print(f"narrow: {argv[2]}")
    print(f"        duration {narrow_record.get('duration_s')}s "
          f"copy {((narrow_record.get('timings_s') or {}).get('copy_wall_s'))}s "
          f"mode {scope.get('mode')} trees {scope.get('trees')} "
          f"ran {narrow_record.get('ran')}")
    print()

    only_full = sorted(set(full) - set(narrow))
    only_narrow = sorted(set(narrow) - set(full))
    mismatched: list[tuple[str, dict, dict]] = []
    red_moved: list[tuple[str, dict, dict]] = []
    for name in sorted(set(full) & set(narrow)):
        a, b = full[name], narrow[name]
        if a["ran"] != b["ran"]:
            mismatched.append((name, a, b))
        elif a["red"] != b["red"]:
            red_moved.append((name, a, b))

    print(f"patterns compared: {len(set(full) & set(narrow))}")
    print(f"only in full     : {only_full}")
    print(f"only in narrow   : {only_narrow}")
    print(f"ran mismatches   : {len(mismatched)}")
    for name, a, b in mismatched:
        print(f"  {name}: full ran {a['ran']} ({a['status']}) -> "
              f"narrow ran {b['ran']} ({b['status']})")
    print(f"red-set changes  : {len(red_moved)}")
    for name, a, b in red_moved:
        print(f"  {name}: full {a['red']} -> narrow {b['red']}")

    clean = not only_full and not only_narrow and not mismatched and not red_moved
    print()
    print(f"VERDICT {'EQUAL' if clean else 'DIVERGENT'}")
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
