"""Read-only scope and index receipt for the carried prevention correction."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine.core_unit import tree_fingerprint  # noqa: E402
from saipen_engine.state import parse_state_or_error  # noqa: E402


def main() -> int:
    label = sys.argv[1]
    if Path(label).name != label:
        raise SystemExit("invalid receipt name")
    destination = HERE / f"{label}.json"
    if destination.exists():
        raise SystemExit("existing evidence is immutable")
    staged = subprocess.run(
        ["git", "ls-files", "--stage", "-z"], cwd=ROOT,
        capture_output=True, check=True, timeout=60,
    ).stdout
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
        text=True, encoding="utf-8", check=True, timeout=60,
    ).stdout.strip()
    state, error = parse_state_or_error((ROOT / ".saipen/STATE.md").read_text(encoding="utf-8"))
    if error:
        raise SystemExit(error)
    record = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "head": head,
        "index_projection_sha256": hashlib.sha256(staged).hexdigest(),
        "index_entry_count": staged.count(b"\0"),
        "tree_fingerprint": tree_fingerprint(ROOT),
        "execution": {key: state.get(key) for key in (
            "phase", "task", "agent", "execution_intent", "goal_waves",
            "goal_tickets", "next_action", "last_event", "continuation_authority",
        )},
        "core_sha256": {name: hashlib.sha256((ROOT / ".saipen" / name).read_bytes()).hexdigest()
                        for name in ("STATE.md", "BOARD.md", "LOG.md")},
        "audit_generations": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                              for path in sorted((ROOT / "audit").glob("*.md"))},
    }
    destination.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: record[key] for key in (
        "timestamp_utc", "head", "index_projection_sha256", "tree_fingerprint", "execution",
    )}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
