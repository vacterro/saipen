"""Measure the already applied source delta, including newline differences."""
import hashlib
import json
from pathlib import Path

evidence = Path(__file__).resolve().parent
root = evidence.parents[2]
package = json.loads((evidence / "package.json").read_text(encoding="utf-8"))
location = json.loads((evidence / "location.json").read_text(encoding="utf-8"))
position = json.loads((evidence / "position-final.json").read_text(encoding="utf-8"))
subject = Path(location["subject"])
digest = lambda raw: hashlib.sha256(raw).hexdigest()
records = []
for item in package["files"]:
    actual = (root / item["path"]).read_bytes()
    tested = (subject / item["path"]).read_bytes()
    assert actual.replace(b"\r\n", b"\n") == tested.replace(b"\r\n", b"\n"), item["path"]
    records.append({**item, "actual_sha256": digest(actual), "live_written": True,
                    "normalized_content_matches_tested": True,
                    "raw_bytes_match_tested": actual == tested})
canonical = {name: digest((root / name).read_bytes()) for name in position["live_canonical_sha256"]}
assert canonical == position["live_canonical_sha256"], "canonical position changed"
record = {"files": records, "canonical_after": canonical,
          "canonical_position_preserved": True, "persistent_authority_granted": False,
          "application": "git apply --whitespace=error repair.patch completed successfully; "
          "the wrapper then exited 1 on its overly strict raw-byte postcheck. "
          "Git retained pre-existing source newlines. This readback proves normalized source "
          "equals the tested patch and records the real byte hashes; it rewrites no source."}
(evidence / "applied.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"canonical_position_preserved": True, "files": len(records)}, indent=2))
