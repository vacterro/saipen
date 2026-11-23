"""Compare portable inventory order on the exact live experiment snapshot."""
import argparse
import hashlib
import json
import os
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--source", required=True)
parser.add_argument("--expected", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()
root = Path(args.source).resolve()
expected = json.loads(Path(args.expected).read_text(encoding="utf-8"))["input_inventory"]
started = time.perf_counter()
entries, total = [], 0
for path in sorted(root.rglob("*")):
    relative = path.relative_to(root).as_posix()
    if path.is_symlink():
        entries.append([relative, "symlink", os.readlink(path)])
    elif path.is_file():
        content = path.read_bytes()
        total += len(content)
        entries.append([relative, "file", len(content), hashlib.sha256(content).hexdigest()])


def digest(rows):
    return hashlib.sha256(json.dumps(rows, ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()


observed = {"files_or_links": len(entries), "bytes": total, "sha256": digest(entries)}
if any(observed[key] != expected[key] for key in observed):
    raise SystemExit("frozen Windows input changed; portable-order audit cannot bind it")
parts_order = digest(sorted(entries, key=lambda row: tuple(row[0].split("/"))))
report = {"purpose": "order-normalized byte inventory, not test acceptance",
          "source": str(root), "legacy_windows_inventory": observed,
          "portable_posix_parts_inventory": {**observed, "sha256": parts_order},
          "same_frozen_windows_bytes_proved": True,
          "wall_s": round(time.perf_counter() - started, 6),
          "note": "Windows Path sorts case-insensitively; Linux Path sorts case-sensitively. Same entries can have different ordered digests."}
Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report))
