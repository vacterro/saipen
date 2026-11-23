import sys, json
sys.path.insert(0, "tools")
from pathlib import Path
from saipen_engine import goal_authority as G, codec
from saipen_engine.state import parse_state
from saipen_engine.log import read_history_snapshot

root = Path(".")
state = parse_state(codec.read_doc(root / ".saipen/STATE.md"))
hist = read_history_snapshot(root, lean=True).events
deps = {}
for scope in ("continuous_maintenance", "goal_complete"):
    try:
        b = G.current_binding(root, state, hist, deps, until=scope)
        print(scope, "OK")
        print(json.dumps(b, indent=1, ensure_ascii=False))
    except Exception as exc:
        print(scope, "FAIL", type(exc).__name__, exc)
print("describe:", json.dumps(G.describe(root, state), indent=1, default=str))
print("protocol_home:", G.protocol_home(root))
