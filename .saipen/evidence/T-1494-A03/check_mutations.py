"""Execute the two existing A01 CASEs, retaining exact red and green transcripts."""
import json
from pathlib import Path
import sys

from run_checks import ROOT, OUT, run, save, sha
import audit_checks as A
import fail_site_inventory as I
from saipen_engine import core_unit

labels = ("T-1494 schema rejects malformed authority_source",
          "T-1494 goal authority rejects an unbacked persistent grant")
cases = [case for case in A.CASES if case[0] in labels]
assert len(cases) == 2
owner = core_unit.new_sandbox_root()
assert not owner.is_relative_to(ROOT)
context = A.ProbeContext(owner, cases, frozenset({A.STATE}))
record = {"temporary_root": str(owner), "case_table_sha256": sha(ROOT / "tools/audit_checks.py"),
          "validator_sha256": sha(ROOT / "tools/validate.py"), "cases": []}
try:
    assert A.build_pristine(context) is None
    baseline, stdout, stderr = run("a01-valid-before", context.pristine,
                                  ("tools/validate.py", "--gate", "core"), cwd=".")
    assert baseline["accepted"], stdout + stderr
    ledger = I.ledger_index(I.load_ledger(ROOT))
    for number, case in enumerate(cases, 1):
        label, rel, mutation, expected, gate, needs = A.case_parts(case)
        site_id = next(key for key, row in ledger.items() if row.get("case") == label)
        assert ledger[site_id]["disposition"] == I.COVERED
        files = A.mutation_files(context.pristine, rel, mutation)
        before = [(path, path.read_bytes() if path.exists() else None) for path in files]
        try:
            assert A.apply_case(context.pristine, rel, mutation) is True
            red, out, err = run(f"a01-case-{number}-red", context.pristine,
                               ("tools/validate.py", "--gate", "core"), cwd=".")
            failures = [line for line in (out + err).splitlines() if line.startswith("FAIL")]
            assert red["exit_code"] == 1 and any(expected in line for line in failures), failures
        finally:
            A.restore_case_files(before)
        green, out, err = run(f"a01-case-{number}-green", context.pristine,
                             ("tools/validate.py", "--gate", "core"), cwd=".")
        assert green["accepted"], out + err
        assert all(path.read_bytes() == data for path, data in before)
        record["cases"].append({"site_id": site_id, "label": label, "expected": expected,
                                 "failures": failures, "red_exit": red["exit_code"],
                                 "green_exit": green["exit_code"], "restored_exact_bytes": True})
    source = (ROOT / I.VALIDATOR_REL).read_text(encoding="utf-8-sig")
    shifted = A.pad_above_fail_sites(source)
    assert {site.site_id for site in I.fail_sites(source)} == {site.site_id for site in I.fail_sites(shifted)}
    record["unrelated_line_shift_preserves_all_identities"] = True
    record["site_count"] = len(I.fail_sites(source))
    record["accepted"] = len(record["cases"]) == 2
finally:
    record["cleanup_complete"] = core_unit.reclaim(owner)
    save("a01-mutations", record)
print(json.dumps(record, indent=2))
sys.exit(0 if record.get("accepted") and record["cleanup_complete"] else 1)
