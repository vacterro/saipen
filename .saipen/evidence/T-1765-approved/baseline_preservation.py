"""Record or verify local old-baseline bytes; never edit baseline files."""
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

here = Path(__file__).resolve().parent
root = here.parents[2]
directory = root / ".saipen/recovery/conformance/debt"
manifest = here / "baselines-before.json"


def read_rows():
    rows = {}
    for path in sorted(directory.glob("DEBT-*.json")):
        raw = path.read_bytes()
        record = json.loads(raw.decode("utf-8-sig"))
        rows[path.name] = {
            "sha256": hashlib.sha256(raw).hexdigest(),
            "ruleset_version": record.get("ruleset_version"),
        }
    return rows


current = read_rows()
if sys.argv[1:] == ["capture"]:
    if manifest.exists():
        raise SystemExit("Original baseline manifest already exists; preserve it.")
    report = {
        "scope": str(directory.relative_to(root)),
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "files": current,
    }
    manifest.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"captured": len(current), "manifest": str(manifest.relative_to(root))}))
elif sys.argv[1:] == ["verify"]:
    old = json.loads(manifest.read_text(encoding="utf-8"))["files"]
    missing = sorted(set(old) - set(current))
    changed = sorted(name for name in old.keys() & current.keys() if old[name] != current[name])
    added = {name: current[name] for name in sorted(set(current) - set(old))}
    report = {
        "scope": str(directory.relative_to(root)),
        "verified_utc": datetime.now(timezone.utc).isoformat(),
        "old_count": len(old), "missing": missing, "changed": changed,
        "all_old_files_unchanged": not missing and not changed,
        "new_files": added,
        "new_ruleset_versions": dict(Counter(str(row["ruleset_version"]) for row in added.values())),
    }
    (here / "baselines-after.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "new_files"}, indent=2))
    raise SystemExit(bool(missing or changed))
else:
    raise SystemExit("Use capture immediately before the v2 product edit, then verify afterward.")
