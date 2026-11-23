"""Prepare the next change outside the frozen source tree, without claiming Work."""
import json
import shutil
import tempfile
from pathlib import Path

home = Path(__file__).resolve().parents[3]
here = Path(__file__).resolve().parent
binding = here / "closure-scratch.json"
if binding.exists():
    raise SystemExit("Existing scratch binding must be inspected, not replaced")
scratch = Path(tempfile.mkdtemp(prefix="saipen-src276-closure-")).resolve()
assert not scratch.is_relative_to(home.resolve())
ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", ".ruff_cache", ".git")
for relative in ("tools", "saipen", "bootstrap", "extensions", "tests"):
    shutil.copytree(home / relative, scratch / relative, ignore=ignore)
for name in ("VERSION", "README.md", "AGENTS.md"):
    if (home / name).is_file():
        shutil.copy2(home / name, scratch / name)
shutil.copy2(home / "tools/saipen_engine/intake.py", here / "closure-intake-before.py")
shutil.copy2(here / "test_src276_closure_outcomes.py", scratch / "tools/test_src276_closure_outcomes.py")
binding.write_text(json.dumps({"scratch_root": str(scratch), "source_root": str(home),
                               "scope": "unclaimed next-Work draft, outside frozen root"},
                              indent=2) + "\n", encoding="utf-8")
print(json.dumps({"scratch_root": str(scratch)}))
