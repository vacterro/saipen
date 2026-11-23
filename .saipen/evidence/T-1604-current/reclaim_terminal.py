"""Remove exact terminal allocations with the existing reclaim helper."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from reclaim_completed import HERE, ROOT, RUNS, WRAPPER, sha
from saipen_engine.core_unit import reclaim


def main():
    temp = Path(tempfile.gettempdir()).resolve()
    pending = []
    for carrier, basename in RUNS:
        durable = ROOT / ".saipen/evidence" / carrier / "full-current"
        paths = [durable / name for name in
                 ("binding.json", "result.json", "verify-scenarios.txt")]
        hashes = {str(path): sha(path) for path in paths}
        binding = json.loads(paths[0].read_text(encoding="utf-8"))
        result = json.loads(paths[1].read_text(encoding="utf-8"))
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
                or result["checks"] != 1354 or result["fingerprint"] != binding["fingerprint"]
                or sha(paths[2]) != result["output_sha256"]):
            raise RuntimeError("exact terminal allocation proof refused")
        # The existing helper's permission retry must encounter no foreign link.
        for entry in owned.rglob("*"):
            if entry.is_symlink():
                raise RuntimeError("allocation contains a link; refuse recursive cleanup")
            entry.resolve().relative_to(expected)
        pending.append((owned, hashes))

    # The failed move allocated only this one file; remove it non-recursively.
    orphan = temp / "saipen-evidence-completed-scenario-cleanup-opr_zsc6"
    retained_owner = HERE / "cleanup-saipen-evidence-t1603-full-scenarios-jo3mhdg_/ownership.json"
    owner = json.loads(retained_owner.read_text(encoding="utf-8"))
    orphan_proof = orphan / "ownership.json"
    if (Path(owner["new_allocation"]) != orphan or orphan.resolve() != orphan
            or orphan.is_symlink() or list(orphan.iterdir()) != [orphan_proof]
            or orphan_proof.is_symlink() or orphan_proof.resolve().parent != orphan
            or sha(orphan_proof) != sha(retained_owner)):
        raise RuntimeError("failed empty allocation ownership refused")
    orphan_proof.unlink()
    orphan.rmdir()

    records = []
    for owned, hashes in pending:
        if owned.resolve() != owned or owned.parent != temp:
            raise RuntimeError("absolute deletion target changed after proof")
        removed = reclaim(owned)
        unchanged = all(sha(Path(path)) == digest for path, digest in hashes.items())
        records.append({"original_allocation": str(owned), "removed": removed,
                        "durable_proof_unchanged": unchanged, "proof_sha256": hashes,
                        "mechanism": "existing core_unit.reclaim after exact ownership/link preflight",
                        "native_gate_rerun": False})
        report = {"records": records, "failed_empty_allocation_removed": not orphan.exists(),
                  "failed_move_owner_proof": str(retained_owner),
                  "failed_move_owner_proof_sha256": sha(retained_owner)}
        (HERE / "reclaimed.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        if not removed or not unchanged:
            raise RuntimeError("owned cleanup or durable proof check failed")
    print(json.dumps({"reclaimed": len(records), "native_gate_rerun": False,
                      "failed_empty_allocation_removed": not orphan.exists(),
                      "all_proof_unchanged": all(item["durable_proof_unchanged"] for item in records)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
