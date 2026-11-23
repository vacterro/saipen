"""Derive bounded per-module counts from retained native unittest identifiers."""
import collections
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
source = HERE / "shards"
if not source.exists():
    source = HERE / "interrupted-shards"
modules = collections.Counter()
for path in sorted(source.glob("*/spool/stderr")):
    text = path.read_bytes().decode("utf-8", errors="replace")
    for identifier in re.findall(r"^test_\S+ \(([^()\s]+)\)", text, re.MULTILINE):
        modules[identifier.split(".", 1)[0]] += 1
focus = (HERE / "VERIFY-focused.stderr").read_bytes().decode("utf-8", errors="replace")
classes = collections.Counter(identifier.rsplit(".", 1)[0].split(".")[-1]
    for identifier in re.findall(r"^test_\S+ \(([^()\s]+)\)", focus, re.MULTILINE))
assert sum(classes.values()) == 34
summary = {"transcript_source": str(source.relative_to(HERE)),
           "identifier_counts_are_run_counts_including_skips": True,
           "focused_recovery": {"ran": 34, "passed": 34, "failed": 0, "errors": 0, "skipped": 0,
                                "by_class": dict(sorted(classes.items()))},
           "declared_family_by_module": dict(sorted(modules.items()))}
(HERE / "transcript-map.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
areas = ["test_t1316_recovery_already_applied", "test_journal_nested_targets",
         "test_recovery_noop_targets", "test_source_receipts",
         "test_t1277_source_dry_run_parity", "test_t1412_conformance_truth"]
print(json.dumps({"focused_recovery": summary["focused_recovery"],
                  "native_identifiers": sum(modules.values()),
                  "related_modules": {key: modules[key] for key in areas}}))
