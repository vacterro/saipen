"""The measured documentation bound accepts good bytes and detects overflow."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import protocol_budget

limit = 303 * 1024
current = protocol_budget.load_profiles(ROOT / "saipen")["human_markdown_total"]
assert current <= limit
assert (current + 1023) // 1024 == 303
with tempfile.TemporaryDirectory(prefix="saipen-T1605-budget-") as temp:
    subject = Path(temp) / "saipen"
    shutil.copytree(ROOT / "saipen", subject)
    (subject / "OverflowControl.md").write_bytes(b"x" * (limit - current + 1))
    bad = protocol_budget.load_profiles(subject)["human_markdown_total"]
    assert bad == limit + 1
    assert not bad <= limit
record = {"limit": limit, "current": current, "good": "PASS",
          "overflow": bad, "bad": "FAIL", "smallest_whole_kib": 303}
(HERE / "budget-control.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps(record))
