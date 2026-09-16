"""SRC-054: what citation accounting says about every registered SAIPEN project.

Read-only. For each project AUDAPACK packs, collect with the repaired consumer
and judge the discovery set as if every collected file reached the archive, so
the only way a project can read incomplete here is through its own citations
(a cited file absent on disk, a truncated or unreadable discovery) or a
pre-existing contract problem. A citation that makes a healthy project read
incomplete would be a false veto this change introduced; this census is where
it would show.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

AUDAPACK = Path(r"V:\___VAC\__K\__CODE\_PY\_AUDAPACK")
CONFIG = Path(os.environ.get("LOCALAPPDATA", "")) / "AUDAPACK" / "config" / "config.json"


def main() -> int:
    sys.path.insert(0, str(AUDAPACK))
    from audapack import saipen_evidence as se

    projects = json.loads(CONFIG.read_text(encoding="utf-8")).get("projects", [])
    rows = []
    for project in projects:
        root = Path(project.get("source_path") or "")
        if not se.detect(root):
            continue
        collection = se.collect_for_inventory(root)
        verdict = se.evaluate(collection, included=set(collection.paths))
        citations = verdict.get("evidence_citations") or {}
        rows.append(
            {
                "project": project.get("display_name"),
                "status": verdict["status"],
                "rules": citations.get("rules_source"),
                "carriers": citations.get("carriers_scanned"),
                "carrier_bytes": citations.get("carrier_bytes_scanned"),
                "cited_files": len(citations.get("cited_files") or []),
                "cited_dirs": len(citations.get("cited_dirs") or []),
                "cited_missing": citations.get("cited_missing_on_disk"),
                "truncated": citations.get("truncated"),
                "unreadable_carriers": citations.get("unreadable_carriers"),
                "omitted_required": [
                    (item["path"], item["tier"], item["reason"]) for item in verdict["omitted_required"]
                ],
            }
        )
    for row in rows:
        print(json.dumps(row, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
