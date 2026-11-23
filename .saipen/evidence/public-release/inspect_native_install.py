"""Read the preserved native install; compare every declared runtime byte."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
SUBJECT = Path("V:/_SAIPEN_RELEASE_/public-20261004")
sys.path.insert(0, str(SUBJECT / "tools"))
from saipen_engine.runtime_surface import runtime_surface_items, content_bytes

source = {k:hashlib.sha256(content_bytes(p)).hexdigest() for k,p in runtime_surface_items(SUBJECT)}
comparisons = {}
for name in (".claude/skills/saipen", ".codex/skills/saipen", ".config/opencode/skills/saipen", ".agents/skills/saipen"):
    installed = {k:hashlib.sha256(content_bytes(p)).hexdigest() for k,p in runtime_surface_items(HERE / "debug-native-home" / name)}
    comparisons[name] = {k:{"source":source.get(k), "installed":installed.get(k)} for k in source.keys() | installed.keys() if source.get(k) != installed.get(k)}
(HERE / "debug-native-comparison.json").write_text(json.dumps(comparisons, indent=2) + "\n", encoding="utf-8")
print(json.dumps(comparisons, indent=2))
