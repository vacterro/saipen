"""Preserve the revised safe oracle on the fixed and nine restored subjects."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / "tools"))
from saipen_engine.test_runner import _ignore_copy  # noqa: E402

evidence = Path(__file__).resolve().parent
subjects = evidence / "subjects-v4"
if not subjects.resolve().is_relative_to(evidence.resolve()):
    raise RuntimeError("subject destination escapes evidence")
subjects.mkdir()
control, before = subjects / "control", subjects / "pre-fix"


def ignored(directory, names):
    excluded = {".git", ".saipen"} if Path(directory).resolve() == root else set()
    return _ignore_copy(directory, names) | excluded


shutil.copytree(root, control, ignore=ignored)
shutil.copytree(control, before)
restored = []
for source in sorted((evidence / "pre" / "tools").rglob("*.py")):
    relative = source.relative_to(evidence / "pre")
    shutil.copy2(source, before / relative)
    restored.append(relative.as_posix())
print(json.dumps({"control": str(control), "pre_fix": str(before), "restored": restored}))
