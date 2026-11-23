"""Separate Git index refresh metadata from the inherited staged blob set."""
import hashlib
import json
from pathlib import Path
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
historical = ROOT / ".saipen/evidence/T-1695-invalid-stops/pre-index.patch"
before = historical.read_bytes()
current = subprocess.check_output(["git", "diff", "--cached", "--binary"], cwd=ROOT)
entries = subprocess.check_output(["git", "ls-files", "--stage", "-z"], cwd=ROOT)

# The old snapshot is text transported with Windows CRLF. This comparison
# normalizes that transport only; Git's blob ids and binary patch data stay
# exact. It does not change any source, receipt, or protected document digest.
normalized_before = before.replace(b"\r\n", b"\n")
normalized_current = current.replace(b"\r\n", b"\n")
record = {
    "historical_snapshot": str(historical.relative_to(ROOT)),
    "historical_raw_sha256": hashlib.sha256(before).hexdigest(),
    "current_raw_sha256": hashlib.sha256(current).hexdigest(),
    "historical_staged_diff_sha256": hashlib.sha256(normalized_before).hexdigest(),
    "current_staged_diff_sha256": hashlib.sha256(normalized_current).hexdigest(),
    "current_index_entries_sha256": hashlib.sha256(entries).hexdigest(),
    "staged_blobs_and_modes_unchanged": normalized_before == normalized_current,
    "raw_index_metadata_equal": False,
    "scope": "No index was restored or staged. Raw index drift was not claimed as unchanged.",
}
(OUT / "index-adjudication.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
assert record["staged_blobs_and_modes_unchanged"], record
print(json.dumps(record))
