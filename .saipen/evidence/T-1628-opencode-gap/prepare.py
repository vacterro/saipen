"""Prepare the queued adapter repair in an isolated, non-installed clone."""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).parent
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.core_unit import copy_tree_consistent
from saipen_engine.test_runner import _ignore_copy

scratch = Path(tempfile.mkdtemp(prefix="saipen-t1628-draft-", dir=r"V:\_TEMP_"))
project = scratch / "project"
copy_tree_consistent(
    ROOT, project,
    lambda directory, names: _ignore_copy(directory, names) | {".saipen", ".git"},
)
names = ["extensions/adapters/opencode/saipen-guard.js", "extensions/adapters/registry.json",
         "tools/saipen_engine/host_integration.py", "tools/test_opencode_adapter.py",
         "tools/test_t1624_host_integration.py"]
for name in names:
    before = HERE / "pre" / name
    before.parent.mkdir(parents=True, exist_ok=True)
    before.write_bytes((ROOT / name).read_bytes())
descriptor = {"project": str(project), "scratch": str(scratch)}
(HERE / "scratch.json").write_text(json.dumps(descriptor, indent=2) + "\n", encoding="utf-8")
print(json.dumps(descriptor))
