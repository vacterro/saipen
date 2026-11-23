"""Preserve identical repository oracles on fixed and restored subjects."""
import json
import shutil
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / "tools"))
from saipen_engine.test_runner import _ignore_copy  # noqa: E402

evidence = Path(__file__).resolve().parent
subjects = evidence / "subjects-v1"
subjects.mkdir()
control, before = subjects / "control", subjects / "pre-fix"

def ignored(directory, names):
    excluded = {".git", ".saipen"} if Path(directory).resolve() == root else set()
    return _ignore_copy(directory, names) | excluded

shutil.copytree(root, control, ignore=ignored)
shutil.copytree(control, before)
restored = []
for relative in ("tools/test_host_authority_broker.py", "tools/saipen_engine/core_unit.py"):
    shutil.copy2(evidence / "pre" / relative, before / relative)
    restored.append(relative)
print(json.dumps({"control": str(control), "pre_fix": str(before), "restored": restored}))
