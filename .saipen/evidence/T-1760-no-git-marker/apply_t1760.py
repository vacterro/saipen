"""Apply the T-1760 change set: exact replacements, counts asserted, endings kept.

Run from the repository root (or from the root of a disposable copy):
    python -B <this file> [--check]
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path.cwd()
EDITS: list[tuple[str, str, str]] = []


def edit(path: str, old: str, new: str) -> None:
    EDITS.append((path, old, new))


edit(
    "tools/validate.py",
    "    _ccc_lines = [line for path in log_files for line in read_doc(path).splitlines()]\n"
    "    _ccc_markers = [\n"
    "        (index, match.group(1))\n"
    "        for index, line in enumerate(_ccc_lines)\n"
    '        if (match := re.search(rf"DEC: ccc converge target -> ship @({OID_RE})\\b", line))\n'
    "    ]\n",
    "    _ccc_lines = [line for path in log_files for line in read_doc(path).splitlines()]\n"
    "    # T-1760: a tree without Git has no commit to name. The engine's entry\n"
    "    # marker there carries the head `compute_source_identity` reports, the\n"
    "    # literal `no-git`, and this check failed the engine's own line. The same\n"
    "    # owner decides here: `@no-git` is a marker only while this tree is\n"
    "    # no-Git by that owner's rule, so a Git project still owes a commit id.\n"
    "    _ccc_no_git = False\n"
    '    if any("ccc converge target -> ship @no-git" in line for line in _ccc_lines):\n'
    "        try:\n"
    '            _ccc_no_git = compute_source_identity(Path(".")).source_head == "no-git"\n'
    "        except FreshnessError:\n"
    "            _ccc_no_git = False\n"
    '    _ccc_head = rf"{OID_RE}|no-git" if _ccc_no_git else OID_RE\n'
    "    _ccc_markers = [\n"
    "        (index, match.group(1))\n"
    "        for index, line in enumerate(_ccc_lines)\n"
    '        if (match := re.search(rf"DEC: ccc converge target -> ship @({_ccc_head})\\b", line))\n'
    "    ]\n",
)

edit(
    "tools/validate.py",
    "        _ship_at = _ship_result[0] if _ship_result else None\n",
    "        _ship_at = _ship_result[0] if _ship_result else None\n"
    "        if _ship_at is None and _ccc_no_git:\n"
    "            # No push can exist without Git: SHIP's own line there is the\n"
    "            # skipped publish (phases/ship.md), and it is the boundary J-M\n"
    "            # must follow. A Git project is still judged by its pushed head.\n"
    "            _ship_at = next(\n"
    "                (\n"
    "                    index\n"
    "                    for index in range(len(_ccc_lines) - 1, _ccc_start, -1)\n"
    "                    if re.search(\n"
    '                        r"RUN: ship .* -> skipped publish \\(no-publish: ", _ccc_lines[index]\n'
    "                    )\n"
    "                ),\n"
    "                None,\n"
    "            )\n",
)


def main() -> int:
    planned: dict[str, bytes] = {}
    for rel, old, new in EDITS:
        data = planned.get(rel) or (ROOT / rel).read_bytes()
        crlf = b"\r\n" in data
        old_b, new_b = old.encode("utf-8"), new.encode("utf-8")
        if crlf:
            old_b, new_b = old_b.replace(b"\n", b"\r\n"), new_b.replace(b"\n", b"\r\n")
        count = data.count(old_b)
        if count != 1:
            print(f"ABORT: {rel}: expected exactly one match, found {count}:\n{old[:200]}")
            return 1
        planned[rel] = data.replace(old_b, new_b, 1)
    if "--check" in sys.argv:
        print(f"CHECK OK: {len(EDITS)} edits in {len(planned)} files match exactly once")
        return 0
    for rel, data in planned.items():
        (ROOT / rel).write_bytes(data)
        print(f"patched {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
