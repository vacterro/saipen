"""T-1889 A/B: the SAME tree and the SAME copier, differing only in `scope`.

Measures `copy_tree_consistent` twice against the live tree: once with
scope=None (the pre-T-1889 behaviour, FULL) and once with the resolved DECLARED
decision. Both arms copy identical bytes, so the delta is the narrowing alone.

The live tree is read, never written. File counts are reported for both arms so
a reader can see the two copies describe the same subject; a difference there
would mean the tree drifted between arms and the timings are not comparable.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine import core_unit, sandbox_scope  # noqa: E402
from saipen_engine.test_runner import _ignore_copy  # noqa: E402

PATTERNS = ["test_t1885_tag_peel.py", "test_t1886_gate_lock_window.py"]


def count(root: Path) -> tuple[int, int]:
    files = size = 0
    for directory, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames
                       if name not in _ignore_copy(directory, dirnames)]
        for name in filenames:
            path = Path(directory) / name
            try:
                size += path.stat().st_size
            except OSError:
                continue
            files += 1
    return files, size


def arm(label, scope):
    held = tempfile.mkdtemp(prefix="t1889-ab-")
    sandbox = Path(held) / "project"
    try:
        began = time.monotonic()
        metrics = core_unit.copy_tree_consistent(ROOT, sandbox, _ignore_copy, scope=scope)
        wall = time.monotonic() - began
        files, size = count(sandbox)
        canonical = sorted(
            name for name in ("STATE.md", "LOG.md", "BOARD.md", "MANIFEST.json",
                              "IDENTITY.md")
            if (sandbox / ".saipen" / name).is_file()
        )
        saipen_children = sorted(
            entry.name for entry in (sandbox / ".saipen").iterdir() if entry.is_dir()
        )
        return {
            "arm": label,
            "scope_mode": "FULL" if scope is None else scope["mode"],
            "scope_trees": [] if scope is None else list(scope["trees"]),
            "wall_s": round(wall, 3),
            "metrics": metrics,
            "copied_files": files,
            "copied_mib": round(size / 1048576, 1),
            "sandbox_git": (sandbox / ".git").is_dir(),
            "sandbox_canonical_files": canonical,
            "sandbox_saipen_children": saipen_children,
        }
    finally:
        shutil.rmtree(held, ignore_errors=True)


def main():
    scope = sandbox_scope.resolve(ROOT, PATTERNS)
    print(json.dumps({"patterns": PATTERNS, "resolved_scope_mode": scope["mode"]},
                     indent=2))
    results = [arm("FULL (pre-T-1889 behaviour)", None),
               arm("DECLARED (source tree only)", scope)]
    for result in results:
        print(json.dumps(result, indent=2))
    full, declared = results
    print(json.dumps({
        "same_subject_file_count": full["copied_files"] == declared["copied_files"]
        or "differs by " + str(full["copied_files"] - declared["copied_files"]),
        "wall_delta_s": round(full["wall_s"] - declared["wall_s"], 3),
        "mib_ratio": round(declared["copied_mib"] / full["copied_mib"], 4)
        if full["copied_mib"] else None,
    }, indent=2))


if __name__ == "__main__":
    main()
