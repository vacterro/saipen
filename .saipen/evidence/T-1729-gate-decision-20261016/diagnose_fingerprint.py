"""Read-only bounded comparison of the actual freshness inputs."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
import freshness  # noqa: E402

previous = None
for sample in range(6):
    listing = freshness._git_delta_listing(ROOT)
    evidence = freshness._parse_git_delta_evidence(ROOT, *listing)
    current = {item.path: item for item in evidence}
    changes = [] if previous is None else [
        path.decode("utf-8", "replace")
        for path in sorted(set(previous) | set(current))
        if previous.get(path) != current.get(path)
    ]
    print(json.dumps({"sample": sample, "inputs": len(current), "changed": changes}))
    previous = current
