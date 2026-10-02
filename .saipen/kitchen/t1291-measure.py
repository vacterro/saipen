"""Read-only size and runtime evidence for the knowledge feature."""
import json
import subprocess
import sys
import time
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.context import context_cold
from saipen_engine.knowledge import build_index, retrieve, validate_knowledge

def old(path):
    return subprocess.check_output(["git", "show", f"HEAD:{path}"], cwd=ROOT)

result = {}
for path in ("saipen/BOOT.md", "saipen/INDEX.md", "saipen/CORE.md",
             "saipen/phases/scout.md", "saipen/phases/review.md", "saipen/phases/clean.md"):
    before = old(path).decode().replace("\r\n", "\n")
    after = (ROOT / path).read_text(encoding="utf-8")
    result[path] = {
        "bytes_before": len(before.encode()), "bytes_after": len(after.encode()),
        "line_delta": len(after.splitlines()) - len(before.splitlines()),
        "estimated_token_delta": (len(after.encode()) - len(before.encode())) / 4,
    }
baseline = types.ModuleType("saipen_engine.context_before_knowledge")
baseline.__package__ = "saipen_engine"
exec(compile(old("tools/saipen_engine/context.py"), "context_before_knowledge.py", "exec"), baseline.__dict__)
for name, function in (("cold_before", baseline.context_cold), ("cold_after", context_cold)):
    started = time.perf_counter()
    value = function(ROOT, current_agent="codex-astra")
    result[name] = {key: value.get(key) for key in ("bytes", "tokens", "knowledge")}
    result[name]["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
for name, function in (("build_index", build_index), ("retrieve", lambda r: retrieve(r, "repair CSS colour contrast")), ("validate_knowledge", validate_knowledge)):
    started = time.perf_counter()
    value = function(ROOT)
    result[name] = {"elapsed_ms": round((time.perf_counter() - started) * 1000, 2)}
    if isinstance(value, str):
        result[name]["bytes"] = len(value.encode())
    else:
        result[name]["result"] = value
print(json.dumps(result, indent=2))
