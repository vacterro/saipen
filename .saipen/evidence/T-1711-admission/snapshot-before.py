"""Preserve only this Work's exact pre-images before implementation."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = HERE / "owned-before.json"
if OUT.exists():
    raise SystemExit("Existing pre-images are immutable")
paths = ["tools/saipen_engine/regression_execution.py", "tools/saipen_engine/oracle.py",
         "tools/saipen_engine/log.py", "tools/saipen_engine/operations.py",
         "tools/saipen_engine/board.py", "tools/saipen_engine/journal.py", "tools/saipen.py",
         "saipen/REGISTRY.json", "saipen/COMMANDS.md", "saipen/phases/verify.md",
         "saipen/CORE.md", "tools/test_t1711_regression_execution.py"]
manifest = {}
for relative in paths:
    source = ROOT / relative
    if not source.exists():
        manifest[relative] = None
        continue
    raw = source.read_bytes()
    manifest[relative] = hashlib.sha256(raw).hexdigest()
    target = HERE / "owned-before" / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
OUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"preserved": sum(value is not None for value in manifest.values()),
                  "expected_absent": [key for key, value in manifest.items() if value is None]}))
