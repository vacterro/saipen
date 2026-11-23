"""Observe the actual consumer with the native validator's no-receipt mode."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CONSUMER = Path("V:/___VAC/__K/__CODE/_TAMPERMONKEY/_WIN95THEME/Wintage")
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.log import read_history_snapshot
from saipen_engine.process_tree import run
from saipen_engine.state import parse_state


def canonical():
    return {name: hashlib.sha256((CONSUMER / ".saipen" / name).read_bytes()).hexdigest()
            for name in ("STATE.md", "BOARD.md", "LOG.md", "IDENTITY.md")}


before = canonical()
history = read_history_snapshot(CONSUMER, lean=True)
command = [sys.executable, "-B", str(ROOT / "tools/validate.py"), "--gate", "core",
           "--project-root", str(CONSUMER), "--no-receipt", "--findings-json",
           str(HERE / "consumer-core-findings.json")]
env = {k: v for k, v in os.environ.items() if not k.startswith("SAIPEN_")}
env.update(SAIPEN_CAPABILITY="no-publish", PYTHONDONTWRITEBYTECODE="1")
result = run(command, cwd=ROOT, env=env, capture_output=True, timeout=300)
after = canonical()
current = read_history_snapshot(CONSUMER, lean=True)
value = {"command": command, "exit_code": result.returncode,
         "stdout": result.stdout.decode("utf-8", errors="replace"),
         "stderr": result.stderr.decode("utf-8", errors="replace"),
         "before": before, "after": after, "canonical_unchanged": before == after,
         "history_unchanged": history.hash == current.hash, "history_hash": current.hash,
         "state": parse_state((CONSUMER / ".saipen/STATE.md").read_text(encoding="utf-8")),
         "E3286": [ev for ev in current.events if ev.get("event") == 3286],
         "absence": {suffix: not (CONSUMER / (".saipen/recovery/log-detail/"
                     "E-3286-f56793e5c6d3f9370cd1be66" + suffix)).exists()
                     for suffix in (".json", ".LOG.md")},
         "limits": "bounded current native core observation; not LIVE product acceptance"}
output = HERE / "consumer-protocol.json"
assert not output.exists()
output.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
assert value["canonical_unchanged"] and value["history_unchanged"], "consumer moved during probe"
assert len(value["E3286"]) == 1
print(json.dumps({k: value[k] for k in ("exit_code", "canonical_unchanged", "history_unchanged",
                                       "state", "absence")}))
for line in value["stdout"].splitlines():
    if line.startswith("FAIL") or line.startswith("Validation"):
        print(line)
# A red consumer is an observed subject verdict, not an unavailable instrument.
sys.exit(0)
