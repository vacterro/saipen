"""Preserve bounded durable target evidence, including compacted journal indexes."""
import datetime
import hashlib
import json
from pathlib import Path
import stat

TARGET = Path("V:/___VAC/__K/__CODE/_PY/_AUDAPACK")
OUT = Path(__file__).resolve().parent / "durable-snapshot"
SCOPES = (".saipen/recovery", ".saipen/logs", ".saipen/intake", ".saipen/archive")
records = {}
matches = []
manifests = []
for scope in SCOPES:
    for source in sorted((TARGET / scope).rglob("*")):
        info = source.lstat()
        assert not source.is_symlink() and not getattr(info, "st_file_attributes", 0) & 0x400, str(source)
        if not stat.S_ISREG(info.st_mode):
            continue
        relative = source.relative_to(TARGET).as_posix()
        body = source.read_bytes()
        destination = OUT / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(body)
        records[relative] = {"sha256": hashlib.sha256(body).hexdigest(), "size": len(body)}
        if any(token in body for token in (b"E-3145", b"E-3146", b"T-299", b"0.1.07")):
            matches.append(relative)
        if source.name == "manifest.json":
            try:
                data = json.loads(body)
                manifests.append({"path": relative, "op_id": data.get("op_id"),
                                  "operation": data.get("operation"), "status": data.get("status"),
                                  "created_at": data.get("created_at"),
                                  "payload": data.get("semantic_payload")})
            except (ValueError, UnicodeError):
                pass
record = {"captured_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "scopes": SCOPES, "files": records, "matches": matches,
          "journal_manifests": manifests, "target_mutations": []}
(OUT / "capture.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"files": len(records), "bytes": sum(x["size"] for x in records.values()),
                  "literal_matches": matches, "journal_manifest_count": len(manifests),
                  "latest": sorted(manifests, key=lambda x: str(x["created_at"]))[-5:]}, indent=2))
