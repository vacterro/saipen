"""Read-only R001 proof: current SRC-003 archive consistency in the real target.

No validator run, no foreign write. Every pinned file is hashed before and after
so the observation itself proves it changed nothing.
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HOME = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(HOME / "tools"))
from saipen_engine import board, intake

root = Path("V:/___VAC/__K/__CODE/_PY/_SMART_VAC_MEDIA_COMPRESSOR").resolve()
archive = root / ".saipen/archive/source"
pins = sorted(archive.glob("SRC-003.*")) + [
    root / ".saipen/STATE.md",
    root / ".saipen/BOARD.md",
    root / ".saipen/intake/index.json",
]


def hashes():
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in pins}


before = hashes()
tomb = (intake._read_index(root).get("tombstones") or {}).get("SRC-003") or {}
bundle = None
try:
    meta, contract, coverage, summary = intake._closed_archive_bundle(
        root, "SRC-003", tomb, allow_active_fallback=False
    )
    bundle = {
        "proved": True,
        "meta_status": meta.get("status"),
        "meta_storage_status": meta.get("storage_status"),
        "meta_source_sha256": meta.get("source_sha256"),
        "tombstone_source_sha256": tomb.get("source_sha256"),
        "meta_digest_matches_tombstone": meta.get("source_sha256") == tomb.get("source_sha256"),
        "contract_clauses": len((contract or {}).get("clauses") or {}),
        "coverage_dispositions": {
            k: v.get("disposition")
            for k, v in ((coverage or {}).get("requirements") or {}).items()
        },
        "summary_requirements": summary.get("requirements"),
        "summary_actionable": summary.get("actionable"),
        "summary_unresolved": len(summary.get("unresolved") or []),
    }
except Exception as exc:  # noqa: BLE001 - the refusal IS the observation
    bundle = {"proved": False, "refusal": f"{type(exc).__name__}: {exc}"}

parsed = board.parse_board((root / ".saipen/BOARD.md").read_text(encoding="utf-8-sig"))
receipts = sorted((root / ".saipen/recovery/conformance").glob("*_core_*.json"))
latest = json.loads(receipts[-1].read_text(encoding="utf-8")) if receipts else {}
observation = {
    "observed_utc": datetime.now(timezone.utc).isoformat(),
    "external_root": str(root),
    "read_only": True,
    "tombstone": tomb,
    "archive_bundle": bundle,
    "archive_sidecars_present": sorted(p.name for p in archive.glob("SRC-003.*")),
    "intake_status": intake.status(root, "SRC-003"),
    "board_tickets": {t: parsed["tickets"][t]["section"] for t in ("T-57", "T-62")
                      if t in parsed["tickets"]},
    "latest_core_conformance": {
        "file": receipts[-1].name if receipts else None,
        "status": latest.get("status"),
        "recorded_at": latest.get("recorded_at") or latest.get("created_at"),
    },
    "before_hashes": before,
    "observed_files_unchanged": before == hashes(),
    "limitation": "No validator execution, no foreign mutation, no historical writer "
                  "attribution and no claim that the missing sidecars ever existed. "
                  "Present-day consistency is proved; historical origin stays UNKNOWN.",
}
assert observation["observed_files_unchanged"], "observation mutated the target"
out = Path(__file__).with_name("external-r001-current.json")
out.write_text(json.dumps(observation, indent=2, ensure_ascii=False, default=str) + "\n",
               encoding="utf-8")
print(json.dumps({"bundle": bundle, "intake_ok": observation["intake_status"].get("ok"),
                  "intake_status": observation["intake_status"].get("status"),
                  "tickets": observation["board_tickets"],
                  "latest_core": observation["latest_core_conformance"],
                  "unchanged": observation["observed_files_unchanged"]}, default=str))
