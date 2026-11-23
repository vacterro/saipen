"""Reclaim two proven terminal allocations through a fresh owned EvidenceRun."""
from __future__ import annotations

import hashlib
import json
import stat
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.evidence import EvidenceRun

RUNS = [
    ("scenario-oracles", "saipen-evidence-t1603-full-scenarios-jo3mhdg_"),
    ("scenario-review", "saipen-evidence-t1603-full-scenarios-xa77qg2_"),
]
WRAPPER = "b294a582729cf0118f1356441537ab515e7c9c0a404c5ebd2032f84f393a4f9b"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    records = []
    temp = Path(tempfile.gettempdir()).resolve()
    for carrier, basename in RUNS:
        durable = ROOT / ".saipen/evidence" / carrier / "full-current"
        proof_files = [durable / name for name in
                       ("binding.json", "result.json", "verify-scenarios.txt")]
        proof_hashes = {str(path): sha(path) for path in proof_files}
        binding = json.loads(proof_files[0].read_text(encoding="utf-8"))
        result = json.loads(proof_files[1].read_text(encoding="utf-8"))
        snapshot = Path(binding["snapshot"])
        owned = snapshot.parent
        expected = temp / basename
        if (not snapshot.is_absolute() or owned != expected or owned.is_symlink()
                or owned.resolve() != expected or snapshot.name != "home"
                or Path(binding["source_root"]).resolve() != ROOT
                or binding["command"][1] != str(snapshot / "tools/run_scenarios.py")
                or binding["wrapper_sha256"] != WRAPPER
                or sha(ROOT / ".saipen/evidence" / carrier / "run_frozen_full.py") != WRAPPER
                or result["verdict"] != "PASS" or result["exit_code"] != 0
                or result["completed_groups"] != 44 or result["declared_groups"] != 44
                or result["checks"] != 1354
                or result["fingerprint"] != binding["fingerprint"]
                or sha(proof_files[2]) != result["output_sha256"]):
            raise RuntimeError("exact terminal run ownership/proof refused")
        if not owned.exists():
            raise RuntimeError("original allocation already absent; do not manufacture a cleanup run")
        run = EvidenceRun("completed-scenario-cleanup", "T-1604",
                          durable_dir=HERE / ("cleanup-" + basename))
        destination = run.register_ephemeral("old-allocation")[0]
        if (destination.exists() or destination.parent != run.temp_root
                or run.temp_root != run._owned_temp_root
                or destination.resolve().parent != run._owned_temp_root
                or owned.resolve() != expected or owned.parent != temp):
            raise RuntimeError("absolute move source/destination ownership refused")
        ownership = {"original_allocation": str(owned), "new_allocation": str(run.temp_root),
                     "registered_destination": str(destination), "proof_sha256": proof_hashes,
                     "native_gate_rerun": False,
                     "mechanism": "move proven terminal allocation into fresh owned EvidenceRun; finalize with repaired producer"}
        proof = run.temp_root / "ownership.json"
        proof.write_text(json.dumps(ownership, indent=2) + "\n", encoding="utf-8")
        run.retain(proof)
        # Both absolute operands were checked against their exact owned roots above.
        try:
            owned.rename(destination)
        except PermissionError:
            mode = owned.stat().st_mode
            if (mode & stat.S_IWRITE or owned.is_symlink()
                    or owned.resolve() != expected or destination.exists()):
                run.finalize(verdict="FAILED", extra={**ownership, "move_refused": True})
                raise
            # The terminal allocation itself can carry the Windows read-only bit.
            owned.chmod(mode | stat.S_IWRITE)
            owned.rename(destination)
        manifest = run.finalize(verdict="VERIFIED", extra=ownership)
        unchanged = all(sha(Path(path)) == digest for path, digest in proof_hashes.items())
        record = {**ownership, "original_absent": not owned.exists(),
                  "fresh_allocation_absent": not run.temp_root.exists(),
                  "durable_proof_unchanged": unchanged, "manifest_verdict": manifest["verdict"]}
        records.append(record)
        (HERE / "reclaimed.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
        if not all(record[key] for key in
                   ("original_absent", "fresh_allocation_absent", "durable_proof_unchanged")):
            raise RuntimeError("cleanup/proof verification failed")
    print(json.dumps({"reclaimed": len(records), "native_gate_rerun": False,
                      "all_proof_unchanged": all(item["durable_proof_unchanged"] for item in records)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
