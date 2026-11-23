"""Apply the T-1749 change set: exact replacements, counts asserted, endings kept.

Run from the repository root:
    python -B .saipen/evidence/T-1749-home-root-check/apply_t1749.py [--check]
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path.cwd()
HERE = Path(__file__).resolve().parent
EDITS: list[tuple[str, str, str]] = []


def edit(path: str, old: str, new: str) -> None:
    EDITS.append((path, old, new))


edit(
    "tools/validate.py",
    "    # injector probes the first time this check ran, which is the same\n"
    "    # install-layout blind spot T-413 names.\n"
    '    _is_repo_clone = (_tools_parent / "saipen" / "RFC.md").is_file()\n',
    "    # injector probes the first time this check ran, which is the same\n"
    "    # install-layout blind spot T-413 names.\n"
    "    # T-1749: and only while that clone is the project being validated. A\n"
    "    # managed project validated through this home (`--project-root`) is\n"
    "    # judged on its own files: one zero-byte stray in the home's root refused\n"
    "    # the closure gate of every project bound to the home. The home's own\n"
    "    # validation still reports it.\n"
    "    try:\n"
    "        _validates_its_home = os.path.samefile(PROJECT_ROOT, _tools_parent)\n"
    "    except OSError:\n"
    "        _validates_its_home = False\n"
    '    _is_repo_clone = (_tools_parent / "saipen" / "RFC.md").is_file() and _validates_its_home\n',
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
    target = ROOT / "tools" / "test_t1749_home_root_files.py"
    shutil.copyfile(HERE / "draft" / "test_t1749_home_root_files.py", target)
    print(f"wrote {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
