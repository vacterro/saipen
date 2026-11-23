"""Read back the current source, complete family and reclaimed proof boundaries."""
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.core_unit import baseline_digest, tree_fingerprint


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    label, native_file = sys.argv[1:3]
    native = json.loads((HERE / native_file).read_text(encoding="utf-8"))
    cleanup = json.loads((HERE / "reclaimed.json").read_text(encoding="utf-8"))
    unit_path = ROOT / ".saipen/evidence/core-unit/5e8c632d2983e78c-20261003T153839Z.json"
    unit = json.loads(unit_path.read_text(encoding="utf-8"))
    roots = {str(Path(tempfile.gettempdir()).resolve() / name) for name in
             ("saipen-evidence-t1603-full-scenarios-jo3mhdg_",
              "saipen-evidence-t1603-full-scenarios-xa77qg2_")}
    hashes = {path: digest for row in cleanup["records"]
              for path, digest in row["proof_sha256"].items()}
    checks = {
        "native_control_passes": native["failures"] == 0 and len(native["checks"]) == 4
            and all(row["ok"] for row in native["checks"]),
        "native_subject_is_live": native["subject_sha256"] == sha(ROOT / "tools/saipen_engine/evidence.py"),
        "exact_old_allocations_absent": {row["original_allocation"] for row in cleanup["records"]} == roots
            and all(not Path(path).exists() for path in roots),
        "six_original_durable_proofs_unchanged": len(hashes) == 6
            and all(sha(Path(path)) == digest for path, digest in hashes.items()),
        "failed_empty_allocation_absent": not (Path(tempfile.gettempdir())
            / "saipen-evidence-completed-scenario-cleanup-opr_zsc6").exists(),
        "complete_family_is_current": unit["fingerprint"] == tree_fingerprint(ROOT)
            and unit["baseline_sha256"] == baseline_digest(ROOT)
            and unit["status"] == "PASS" and unit["exit_code"] == 0
            and unit["ran"] == unit["discovered"] == 4864
            and not unit["red"] and not unit["new_red"] and not unit.get("partition_error"),
    }
    report = {"checks": checks, "failures": sum(not passed for passed in checks.values()),
              "verifier_sha256": sha(Path(__file__)), "unit_record_sha256": sha(unit_path),
              "fingerprint": tree_fingerprint(ROOT), "native_receipt": native_file}
    (HERE / (label + ".json")).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
    return int(report["failures"] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
