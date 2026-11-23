"""Create an isolated subject and preserve exact inherited consumer bytes."""

import json
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[3]
here = Path(__file__).parent
sys.path.insert(0, str(root / "tools"))
from saipen_engine.core_unit import copy_tree_consistent
from saipen_engine.test_runner import _ignore_copy

scratch = Path(tempfile.mkdtemp(prefix="saipen-t1684-draft-", dir=r"V:\_TEMP_"))
project = scratch / "project"
copy_tree_consistent(
    root, project,
    lambda directory, names: _ignore_copy(directory, names) | {".saipen", ".git"},
)
for name in ("tools/saipen.py", "tools/saipen_engine/commands.py",
             "tools/saipen_engine/command_effects.py"):
    saved = here / "pre" / name
    saved.parent.mkdir(parents=True, exist_ok=True)
    saved.write_bytes((root / name).read_bytes())
oracle = Path(r"V:\_TEMP_\saipen-t1631-draft-kkrri_3g\project\tools\test_t1631_option_values.py")
(project / "tools/test_t1684_operand_grammar.py").write_bytes(oracle.read_bytes())
descriptor = {"project": str(project), "scratch": str(scratch)}
(here / "scratch.json").write_text(json.dumps(descriptor, indent=2) + "\n", encoding="utf-8")
print(json.dumps(descriptor))
