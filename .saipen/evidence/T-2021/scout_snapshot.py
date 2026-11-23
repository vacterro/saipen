import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / "tools"))
from saipen_engine import codec, goal_authority, persistent_goal
from saipen_engine.isolated_release import inventory_staged_entries
from saipen_engine.state import parse_state

output = Path(__file__).parent
location = subprocess.run(["git", "rev-parse", "--git-path", "index"], cwd=root,
                          capture_output=True, check=True, encoding="utf-8").stdout.strip()
index = root / location
original = index.read_bytes()
before = hashlib.sha256(original).hexdigest()
backup = output / "original-index.bin"
if not backup.exists():
    backup.write_bytes(original)
for name in (
    "tools/saipen.py", "tools/saipen_engine/board.py", "tools/saipen_engine/router.py",
    "tools/saipen_engine/continue_loop.py", "tools/saipen_engine/replenishment.py",
    "tools/saipen_engine/persistent_goal.py", "tools/saipen_engine/isolated_release.py",
    "tools/saipen_engine/discovery_providers.py", "tools/saipen_engine/automation.py",
):
    target = output / "before" / name
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / name, target)
state = parse_state(codec.read_doc(root / ".saipen/STATE.md"))
inventory = inventory_staged_entries(root)
(output / "live-index-inventory.json").write_text(json.dumps(inventory, indent=2) + "\n",
                                                   encoding="utf-8")
goals = [goal.to_dict() for goal in persistent_goal.list_goals(root)]
grant = goal_authority.describe(root, state)
after = hashlib.sha256(index.read_bytes()).hexdigest()
summary = {
    "original_index_sha256": before, "after_inventory_sha256": after,
    "index_preserved": before == after,
    "inventory_status": inventory.get("verification_status"),
    "staged_entries": len(inventory.get("entries") or []),
    "classes": inventory.get("classification_summary"),
    "persistent_goals": goals, "continuation_authority": grant,
}
(output / "scout-snapshot.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary))
assert before == after, "read-only inventory changed original index"
