"""Read-only production-tree snapshot for the permitted parallel lane."""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.core_unit import copy_tree_consistent
from saipen_engine.test_runner import _ignore_copy

scratch = Path(tempfile.mkdtemp(prefix="saipen-t1631-draft-", dir=r"V:\_TEMP_"))
project = scratch / "project"
copy_tree_consistent(
    ROOT, project,
    lambda directory, names: _ignore_copy(directory, names) | {".saipen", ".git"},
)
descriptor = {"scratch": str(scratch), "project": str(project)}
(Path(__file__).parent / "scratch.json").write_text(
    json.dumps(descriptor, indent=2) + "\n", encoding="utf-8",
)
print(json.dumps(descriptor))
