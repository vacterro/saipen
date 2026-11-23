"""Read only this run's four stdout spools; counts are provisional."""
import json
from pathlib import Path
import re

total = selected = red = skipped = 0
rows = []
for name in ["hdc2opci", "iajvrveh", "4k6hxks8", "c674zi3a"]:
    root = Path("V:/_TEMP_/saipen-core-unit-" + name)
    if not root.exists():
        continue
    owner = json.loads((root / "owner.json").read_text(encoding="utf-8"))
    assert owner["pid"] == 27948, owner
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    text = (root / "spool/stderr").read_bytes().decode("utf-8", errors="replace")
    lines = [line for line in text.splitlines() if re.match(r"^test_.* \.\.\. (ok|FAIL|ERROR|skipped)", line)]
    failures = sum(bool(re.search(r" \.\.\. (FAIL|ERROR)", line)) for line in lines)
    skips = sum(" ... skipped" in line for line in lines)
    total += len(lines)
    selected += manifest["selected"]
    red += failures
    skipped += skips
    rows.append({"shard": name, "finished_lines": len(lines), "selected": manifest["selected"],
                 "red": failures, "last": lines[-1][:200] if lines else None})
print(json.dumps({"provisional_completed": total, "selected": selected, "red_lines": red,
                  "skipped_lines": skipped, "shards": rows}))
