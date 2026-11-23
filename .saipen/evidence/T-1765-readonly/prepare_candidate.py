"""Prepare a reviewable compatibility proposal outside the product tree."""

import difflib
import hashlib
import importlib.util
import json
from pathlib import Path

here = Path(__file__).resolve().parent
root = here.parents[2]
source = root / "tools/saipen_engine/findings.py"
original = source.read_text(encoding="utf-8")
anchor = "    # Multi-id subjects (e.g. a ticket ref naming several tickets) keep the\n"
assert original.count(anchor) == 1
assert original.count("RULESET_VERSION = 1") == 1
addition = (
    "    # A global rule's captured subtype is semantic evidence; incidental\n"
    "    # ticket-shaped filenames must not replace the whole condition.\n"
    "    matched = rule.re.search(text)\n"
    "    if rule.subject_kind == \"global\" and matched and any(matched.groups()):\n"
    "        return re.sub(r\"\\s+\", \" \", text).strip()\n"
)
candidate = original.replace("RULESET_VERSION = 1", "RULESET_VERSION = 2")
candidate = candidate.replace(anchor, addition + anchor)
candidate_path = here / "candidate-findings.py"
candidate_path.write_text(candidate, encoding="utf-8")
(here / "proposed.patch").write_text("".join(difflib.unified_diff(
    original.splitlines(keepends=True), candidate.splitlines(keepends=True),
    fromfile="a/tools/saipen_engine/findings.py",
    tofile="b/tools/saipen_engine/findings.py",
)), encoding="utf-8")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


before = load("t1765_before", source)
after = load("t1765_candidate", candidate_path)
messages = [
    "cross-doc drift [root-file-set] -- unexpected root files: ['T-1446', 'tuple[bool']",
    "cross-doc drift [release-version] -- mismatch in T-1446",
]
old_rows = [before.classify("problem", text) for text in messages]
new_rows = [after.classify("problem", text) for text in messages]
assert old_rows[0]["detail_hash"] == old_rows[1]["detail_hash"]
assert new_rows[0]["detail_hash"] != new_rows[1]["detail_hash"]
assert "root-file-set" in new_rows[0]["detail"]
assert "tuple[bool" in new_rows[0]["detail"]
assert [row["finding_key"] for row in old_rows] == [row["finding_key"] for row in new_rows]
assert before.ruleset_fingerprint() != after.ruleset_fingerprint()
assert source.read_text(encoding="utf-8") == original
print(json.dumps({
    "proposal_only": True,
    "product_file_unchanged": True,
    "version_before": before.RULESET_VERSION,
    "version_proposed": after.RULESET_VERSION,
    "fingerprint_before": before.ruleset_fingerprint(),
    "fingerprint_proposed": after.ruleset_fingerprint(),
    "old_details": [row["detail"] for row in old_rows],
    "proposed_details": [row["detail"] for row in new_rows],
    "finding_keys_preserved": True,
    "stored_snapshots_rewritten": 0,
    "candidate_sha256": hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
    "pending": "T-1765's acceptance requires the operator's compatibility choice. This proposal changes no canonical product, baseline, Work or source coverage.",
}, indent=2))
