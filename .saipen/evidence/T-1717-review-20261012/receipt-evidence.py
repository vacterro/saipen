"""Strict canonical receipt inspection and bounded durable-carrier search."""
from __future__ import annotations
import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CONSUMER = Path("V:/___VAC/__K/__CODE/_TAMPERMONKEY/_WIN95THEME/Wintage")
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.core_unit import tree_fingerprint, FINGERPRINT_EXCLUDED
from saipen_engine.journal import semantic_receipts_for_operation, _hash_file
from saipen_engine.test_runner import _ignore_copy

op_id = "checkpoint-d898f0b0e66644ea92a33f4c18909e6d"
records = semantic_receipts_for_operation(CONSUMER, "checkpoint")
selected = [record for record in records if record.get("op_id") == op_id]
assert len(selected) == 1, [list(record) for record in records[:1]]
record = selected[0]
# Search exact bytes by digests retained by the verified canonical receipt,
# not by a fabricated message or a similar filename.
targets = record.get("targets", [])
wanted = {item.get("after_hash") for item in targets
          if "E-3286" in str(item.get("path", ""))}
wanted.discard(None)
good_id = "checkpoint-9459222118a64eebaad732e753f223e3"
good = [record for record in records if record.get("op_id") == good_id]
assert len(good) == 1
good_controls = [item for item in good[0]["targets"] if "E-3486" in item["path"]]
assert len(good_controls) == 2
for item in good_controls:
    assert _hash_file(CONSUMER / item["path"]) == item["after_hash"], item
matches = []
scanned = 0
for scope in (".saipen/recovery", ".saipen/evidence", ".saipen/archive", ".saipen/logs"):
    for directory, dirs, names in os.walk(CONSUMER / scope, followlinks=False):
        dirs[:] = [name for name in dirs if not (Path(directory) / name).is_symlink()]
        for name in names:
            path = Path(directory) / name
            if not path.is_file() or path.is_symlink():
                continue
            scanned += 1
            if wanted and _hash_file(path) in wanted:
                matches.append(path.relative_to(CONSUMER).as_posix())
files = {}
for directory, dirs, names in os.walk(ROOT):
    ignored = _ignore_copy(directory, [*dirs, *names])
    if Path(directory) == ROOT:
        ignored |= set(FINGERPRINT_EXCLUDED)
    dirs[:] = sorted(name for name in dirs if name not in ignored)
    for name in names:
        path = Path(directory) / name
        if name not in ignored and path.is_file():
            files[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).digest()
files["audit/SAIPEN_20261010_1136.md"] = hashlib.sha256(
    (ROOT / ".saipen/archive/source/SRC-215.md").read_bytes()).digest()
counterfactual = hashlib.sha256()
for relative, digest in sorted(files.items()):
    counterfactual.update(relative.encode() + b"\0")
    counterfactual.update(digest)
value = {"canonical_checkpoint_receipt": record, "bound_detail_target_hashes": sorted(wanted),
         "hash_contract": "canonical journal _hash_file uses 16-hex SHA256 prefix; not a full digest",
         "known_good_original_detail_targets": good_controls,
         "known_good_hash_matching_passed": True,
         "regular_files_scanned": scanned, "exact_digest_matches": matches,
         "search_scopes": [".saipen/recovery", ".saipen/evidence", ".saipen/archive", ".saipen/logs"],
         "limit": "only digests retained by the canonical receipt and local listed scopes; no off-machine backup claim",
         "current_fingerprint": tree_fingerprint(ROOT),
         "counterfactual_before_authorized_audit_consumption": counterfactual.hexdigest(),
         "expected_before_consumption": "2df2566be72aeb7bde515aadf1891ccb56bd24500385b60c483656fa0259fcaa"}
output = HERE / "receipt-evidence-corrected.json"
assert not output.exists()
output.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
print(json.dumps({key: value[key] for key in ("bound_detail_target_hashes", "regular_files_scanned",
                  "exact_digest_matches", "current_fingerprint", "counterfactual_before_authorized_audit_consumption")}))
