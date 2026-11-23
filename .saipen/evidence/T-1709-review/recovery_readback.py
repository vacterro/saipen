"""Read the completed recovery back without INIT, checkpoint, or consumer cutover."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RECOVERY_EVIDENCE = ROOT / ".saipen/evidence/AUDAPACK-recovery-20261010"
sys.path.insert(0, str(RECOVERY_EVIDENCE))
sys.path.insert(0, str(ROOT / "tools"))
from preflight import ORIGINAL, RECOVERY, git, inventory
from acceptance import inspect_protocol
from saipen_engine import codec, journal, lifecycle_authority, log, paths, state
from saipen_engine.board import parse_board


def load(name):
    return json.loads((RECOVERY_EVIDENCE / name).read_text(encoding="utf-8"))


def main():
    output = HERE / "recovery-readback.json"
    if output.exists():
        raise SystemExit("Existing readback is immutable")
    p0, p2, p3 = load("phase0.json"), load("phase2.json"), load("phase3.json")
    layout, accepted = load("passive-evidence-layout.json"), load("phase4-v3.json")
    original_before, recovery_before = inventory(ORIGINAL), inventory(RECOVERY)
    original_lineage = paths.project_lineage_identity(ORIGINAL)
    recovery_lineage = paths.project_lineage_identity(RECOVERY)
    mismatches = []
    for row in layout["placements"]:
        actual = recovery_before["files"].get(row["destination"])
        if (actual is None or actual["sha256"] != row["sha256"]
                or actual["bytes"] != row["bytes"] or actual["nlink"] != 1
                or [actual["device"], actual["inode"]] == row["source_node"]):
            mismatches.append(row["destination"])
    protocol = inspect_protocol()
    original_history = log.read_history_snapshot(ORIGINAL)
    original_authority = lifecycle_authority.assess(
        ORIGINAL, state.parse_state(codec.read_doc(ORIGINAL / ".saipen/STATE.md")),
        parse_board(codec.read_doc(ORIGINAL / ".saipen/BOARD.md")), original_history.events,
    )
    pending, conflicts = journal.scan_pending(ORIGINAL)
    refs = {key: git(root, "for-each-ref", "--format=%(refname) %(objectname)").decode()
            for key, root in (("original", ORIGINAL), ("recovery", RECOVERY))}
    histories = {key: hashlib.sha256(git(root, "rev-list", "--all", "--objects")).hexdigest()
                 for key, root in (("original", ORIGINAL), ("recovery", RECOVERY))}
    native = []
    for name, root in (("original", ORIGINAL), ("recovery", RECOVERY)):
        command = [sys.executable, "-B", str(ROOT / "tools/validate.py"),
                   "--project-root", str(root), "--gate", "core", "--no-receipt"]
        run = subprocess.run(command, cwd=root, stdin=subprocess.DEVNULL,
                             capture_output=True, check=False, timeout=300)
        raw = run.stdout + run.stderr
        path = HERE / ("recovery-readback-" + name + "-native.txt")
        path.write_bytes(raw)
        native.append({"root": str(root), "exit_code": run.returncode,
                       "output": str(path.relative_to(ROOT)),
                       "sha256": hashlib.sha256(raw).hexdigest()})
    original_after, recovery_after = inventory(ORIGINAL), inventory(RECOVERY)
    checks = {
        "prior_acceptance_pass": accepted["acceptance_pass"],
        "original_baseline_preserved": original_before["content_sha256"]
            == p0["complete_original"]["content_sha256"],
        "original_lineage_preserved": original_lineage == p3["original_lineage"],
        "new_lineage_preserved": recovery_lineage == p3["new_lineage"]
            and recovery_lineage != original_lineage,
        "copy_mapping_preserved": not mismatches,
        "original_reads_zero_mutation": original_before["content_sha256"]
            == original_after["content_sha256"],
        "recovery_reads_zero_mutation": recovery_before["content_sha256"]
            == recovery_after["content_sha256"],
        "independent_regular_storage": not original_before["risks"]
            and not recovery_before["risks"],
        "git_refs_and_history_preserved": all(v == p0["git_projection"]["refs"]
            for v in refs.values()) and all(v == p0["git_projection"]["reachable_history_sha256"]
            for v in histories.values()),
        "original_remains_unauthorized": original_authority["status"] == "UNAUTHORIZED",
        "no_original_pending_or_conflicts": not pending and not conflicts,
        "recovery_native_pass": native[1]["exit_code"] == 0,
        "original_native_refuses": native[0]["exit_code"] != 0,
    }
    record = {
        "checked_utc": datetime.now(timezone.utc).isoformat(), "checks": checks,
        "original_root": str(ORIGINAL), "recovery_root": str(RECOVERY),
        "original_lineage": original_lineage, "new_lineage": recovery_lineage,
        "original_file_count": original_before["file_count"],
        "recovery_file_count": recovery_before["file_count"],
        "verified_copy_mappings": len(layout["placements"]), "copy_mismatches": mismatches,
        "original_authority": original_authority["status"],
        "recovery_authority": protocol["lifecycle_authority"]["status"],
        "recovery_ledger_errors": protocol["ledger_errors"],
        "recovery_receipt_errors": protocol["receipt_errors"],
        "recovery_pending": protocol["pending"], "recovery_conflicts": protocol["conflicts"],
        "native": native, "acceptance_pass": all(checks.values()),
        "original_verdict": "NO_GO", "recovery_verdict": "GO_CANONICAL_OPERATIONS_ONLY",
        "mutations": [], "cutover": False, "publication": False,
        "scope": "Fresh readback of already completed SRC-211 recovery; no new recovery operation.",
    }
    output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))
    return 0 if record["acceptance_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
