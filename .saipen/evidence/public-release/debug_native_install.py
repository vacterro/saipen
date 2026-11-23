"""Preserve one disposable installer failure for exact surface comparison."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
SUBJECT = Path("V:/_SAIPEN_RELEASE_/public-20261004")
sys.path.insert(0, str(SUBJECT / "tools"))
from saipen_engine.runtime_surface import runtime_surface_items, normalize_content

home = HERE / "debug-native-home"
assert not home.exists()
home.mkdir()
for name in (".claude", ".codex", ".gemini", ".config/opencode", ".agents/skills/user-skill"):
    (home / name).mkdir(parents=True)
env = {k:v for k,v in os.environ.items() if not k.startswith("SAIPEN_")}
env.update(HOME=str(home), USERPROFILE=str(home), LOCALAPPDATA=str(home / "AppData/Local"),
           SAIPEN_UNINSTALL_SKIP_TASK="1", SAIPEN_PYTHON=sys.executable,
           SAIPEN_USER_CONFIG_HOME=str(home / ".saipen-user"), PYTHONUTF8="1",
           PYTHONDONTWRITEBYTECODE="1")
env.pop("ZAICODE_HOME", None)
result = subprocess.run(["pwsh", "-NoProfile", "-File", str(SUBJECT / "bootstrap/inject.ps1")],
                        env=env, cwd=SUBJECT, capture_output=True, text=True, encoding="utf-8", timeout=240)
(HERE / "debug-native-output.txt").write_text(result.stdout + result.stderr, encoding="utf-8")
source = {k: hashlib.sha256(normalize_content(p)).hexdigest() for k,p in runtime_surface_items(SUBJECT)}
comparisons = {}
for name in (".claude/skills/saipen", ".codex/skills/saipen", ".config/opencode/skills/saipen", ".agents/skills/saipen"):
    dst = home / name
    installed = {k: hashlib.sha256(normalize_content(p)).hexdigest() for k,p in runtime_surface_items(dst)}
    comparisons[name] = {k:{"source":source.get(k),"installed":installed.get(k)} for k in source.keys() | installed.keys() if source.get(k) != installed.get(k)}
(HERE / "debug-native-comparison.json").write_text(json.dumps(comparisons, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"exit_code":result.returncode, "differences":comparisons}, indent=2))
