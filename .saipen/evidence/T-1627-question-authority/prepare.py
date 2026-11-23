"""Draft the queued question gate beside, never inside, the running subject."""

import json
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[3]
here = Path(__file__).parent
sys.path.insert(0, str(root / "tools"))
from saipen_engine.core_unit import copy_tree_consistent
from saipen_engine.test_runner import _ignore_copy

scratch = Path(tempfile.mkdtemp(prefix="saipen-t1627-draft-", dir=r"V:\_TEMP_"))
project = scratch / "project"
copy_tree_consistent(
    root, project,
    lambda directory, names: _ignore_copy(directory, names) | {".saipen", ".git"},
)
gap_draft = Path(json.loads((root / ".saipen/evidence/T-1628-opencode-gap/scratch.json").read_text())["project"])
for name in ("extensions/adapters/opencode/saipen-guard.js", "extensions/adapters/registry.json",
             "tools/saipen_engine/host_integration.py", "tools/test_opencode_adapter.py",
             "tools/test_t1624_host_integration.py", "tools/test_t1628_opencode_gap.py"):
    (project / name).write_bytes((gap_draft / name).read_bytes())
names = (
    "tools/saipen.py", "tools/saipen_engine/host_iteration.py",
    "extensions/adapters/opencode/saipen-guard.js", "extensions/adapters/claude/saipen-guard.py",
    "extensions/adapters/registry.json", "tools/install_host_guard.py",
    "saipen/COMMANDS.md", "saipen/CORE.md", "saipen/EXECUTION.md", "saipen/REGISTRY.json",
)
for name in names:
    saved = here / "pre" / name
    saved.parent.mkdir(parents=True, exist_ok=True)
    saved.write_bytes((project / name).read_bytes())
descriptor = {"project": str(project), "scratch": str(scratch), "expected_predecessor": "T-1628"}
(here / "scratch.json").write_text(json.dumps(descriptor, indent=2) + "\n", encoding="utf-8")
print(json.dumps(descriptor))
