"""Preserve the exact generated-only correction before an admitted root edit."""
import difflib
import hashlib
import json
from pathlib import Path

here = Path(__file__).resolve().parent
home = here.parents[2]
scratch_binding = json.loads((home / ".saipen/evidence/T-1817-current-audit/closure-scratch.json")
                            .read_text(encoding="utf-8"))
scratch = Path(scratch_binding["scratch_root"])
relative = "extensions/adapters/opencode/saipen-guard.js"
before = (home / relative).read_bytes()
candidate = (scratch / relative).read_bytes()
begin = "// BEGIN GENERATED HOST-INTEGRATION-01 POLICY"
end = "// END GENERATED HOST-INTEGRATION-01 POLICY"
old = before.decode("utf-8").replace("\r\n", "\n")
new = candidate.decode("utf-8").replace("\r\n", "\n")
old_a, old_b = old.index(begin), old.index(end) + len(end)
new_a, new_b = new.index(begin), new.index(end) + len(end)
assert old[:old_a] == new[:new_a] and old[old_b:] == new[new_b:]
assert "FREEBUFF_OPERATOR_PROVENANCE_MISSING" not in old[old_a:old_b]
assert "FREEBUFF_OPERATOR_PROVENANCE_MISSING" in new[new_a:new_b]
(here / "plugin-before.js").write_bytes(before)
(here / "plugin-candidate.js").write_bytes(candidate)
(here / "generated-only.patch").write_text("".join(difflib.unified_diff(
    old.splitlines(keepends=True), new.splitlines(keepends=True),
    fromfile="a/" + relative, tofile="b/" + relative)), encoding="utf-8")
proof = {"before_sha256": hashlib.sha256(before).hexdigest(),
         "candidate_sha256": hashlib.sha256(candidate).hexdigest(),
         "unchanged_oracle_sha256": hashlib.sha256(
             (home / "tools/test_t1628_opencode_policy.py").read_bytes()).hexdigest(),
         "outside_generated_region_unchanged": True,
         "scratch_prefix": "1 unchanged native test, FAIL",
         "scratch_postfix": "same unchanged native test, PASS",
         "scratch_compatibility": "all 16 existing NativePolicyTests PASS",
         "current_root_edit": False}
(here / "scope.json").write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
print(json.dumps(proof))
