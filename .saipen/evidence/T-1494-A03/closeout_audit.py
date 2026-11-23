"""Read back canonical closure and preservation; write only this A03 evidence."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import core_unit, inflight, intake
from saipen_engine.board import parse_board
from saipen_engine.journal import Journal, hash_bytes, scan_pending
from saipen_engine.state import parse_state


def read(name):
    return json.loads((OUT / (name + ".json")).read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout


def write(name, value):
    (OUT / (name + ".json")).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


before = read("before")
attribution = read("attribution")
core = read("core-unit-acceptance")
closure = read("closure-readback")
state = parse_state((ROOT / ".saipen/STATE.md").read_text(encoding="utf-8"))
board_bytes = (ROOT / ".saipen/BOARD.md").read_bytes()
board = parse_board(board_bytes.decode("utf-8"))
record = Journal(ROOT, closure["release_operation"]).read()
assert state["phase"] == "DONE" and state["task"] == "none"
assert state["last_event"] == 13975
assert board["tickets"]["T-1494"]["section"] == "## DONE"
assert board["tickets"]["T-1494"]["fields"]["closure_mode"] == "own_patch"
assert record["status"] == "COMMITTED" and record["mode"] == "no-publish"
assert record["closure_op_id"] == closure["closure_operation"]
assert set(record["scope_paths"]) == set(attribution["accepted_paths"])
for target in record["targets"]:
    assert target["applied"], target["path"]
    assert hash_bytes((ROOT / target["path"]).read_bytes()) == target["after_hash"], target["path"]
assert {target["path"] for target in record["targets"]} == {
    ".saipen/STATE.md", ".saipen/BOARD.md", ".saipen/LOG.md",
    ".saipen/kitchen/digest.md", ".saipen/kitchen/release_receipt.json",
}
assert all(record.get(key, "") == "" for key in (
    "content_commit", "closure_commit", "remote_tag_sha", "remote_push_url"))
assert inflight.current(ROOT) is None and scan_pending(ROOT) == ([], [])
assert all(not core_unit.pid_alive(pid) for pid in core["processes_leaked_detected"])

fingerprint = core_unit.tree_fingerprint(ROOT)
assert fingerprint == before["source_fingerprint"] == core["source_fingerprint"]
assert core_unit.baseline_digest(ROOT) == core["baseline_sha256"]
assert sha(ROOT / core["record"]) == core["record_sha256"]
assert core["accepted"] and core["new_red"] == [] and core["existing_red"] == []
assert read("final-core-validation")["accepted"]
status = read("final-status")["result"]
assert status["conformance_status"]["status"] == "CURRENT_PASS"
assert status["claimed_ticket"] is None
assert read("final-next")["result"]["action"] == state["next_action"]
for path, digest in attribution["path_sha256"].items():
    assert sha(ROOT / path) == digest, path

foreign_before = read("foreign-board-rows-before")
foreign_after = {
    match.group(1).decode(): line.decode("utf-8")
    for line in board_bytes.splitlines(keepends=True)
    if (match := re.match(rb"- \[[^]]\] (T-\d+)\b", line)) and match.group(1) != b"T-1494"
}
assert foreign_before == foreign_after
conformance_dir = ROOT / ".saipen/recovery/conformance/index"
conformance_index = json.loads((conformance_dir / "core.json").read_text(encoding="utf-8"))
conformance_generation = json.loads((conformance_dir / "active-gen.json").read_text(encoding="utf-8"))
conformance_lineage = json.loads((conformance_dir / "lineage-head.json").read_text(encoding="utf-8"))
assert conformance_index["receipt_id"] == status["conformance_status"]["receipt"]["receipt_id"]
assert sha(ROOT / conformance_index["receipt_path"]) == conformance_index["content_sha256"]
assert conformance_index["generation_root"] == conformance_generation["root"] == conformance_lineage["active_root"]
assert any(member["receipt_id"] == conformance_index["receipt_id"]
           and member["content_sha256"] == conformance_index["content_sha256"]
           for member in conformance_generation["members"])
memory = read("memory-preservation-start")
changed_memory = [path for path, digest in memory.items()
                  if (ROOT / path).is_file() and sha(ROOT / path) != digest]
missing_memory = [path for path in memory if not (ROOT / path).is_file()]
allowed_memory = {
    ".saipen/STATE.md", ".saipen/BOARD.md", ".saipen/LOG.md",
    ".saipen/intake/coverage/SRC-112.json", ".saipen/kitchen/digest.md",
    ".saipen/kitchen/release_receipt.json", ".saipen/recovery/board-terminal.json",
    ".saipen/recovery/conformance/index/core.json",
    ".saipen/recovery/conformance/index/active-gen.json",
    ".saipen/recovery/conformance/index/lineage-head.json",
}
unexpected_memory = [path for path in changed_memory
                     if path not in allowed_memory and not path.startswith(".saipen/recovery/settled-index/")]
assert not missing_memory and not unexpected_memory, (missing_memory, unexpected_memory)
source_integrity = intake.verify_integrity(ROOT, "SRC-112")
coverage = intake.coverage_summary(ROOT, "SRC-112")
assert source_integrity["ok"] and coverage["terminal"] == 5 and not coverage["unresolved"]
assert coverage["dispositions"] == {"SUPERSEDED": 1, "VERIFIED": 4}

index = git("ls-files", "--stage", "-z")
assert hashlib.sha256(index).hexdigest() == before["index_entries_sha256"]
assert git("rev-parse", "HEAD").decode().strip() == before["head"]
assert git("branch", "--show-current").decode().strip() == before["branch"]
refs = git("for-each-ref", "--format=%(refname) %(objectname)", "refs/heads", "refs/tags")
assert refs.decode().splitlines() == (OUT / "refs-before-ship.txt").read_text(encoding="utf-8").splitlines()

temporary_paths = [read(name)["temporary_root"] for name in
                   ("a01-mutations", "verify-oracle-pair", "review-oracle-pair")]
assert all(not Path(path).exists() for path in temporary_paths)
assert all(read(name)["cleanup_complete"] for name in
           ("a01-mutations", "verify-oracle-pair", "review-oracle-pair"))
digest_lines = (ROOT / ".saipen/kitchen/digest.md").read_text(encoding="utf-8").splitlines()
assert len(digest_lines) == 3
assert all(line.startswith(prefix) for line, prefix in zip(digest_lines, ("done:", "remaining:", "awaiting:")))

test_names = ["a01-unit", "a02-routing", "a02-hostile", "authority",
              "neighbor-test_t1293_valve_resume_audit_route", "neighbor-test_intent_audit_fixes",
              "neighbor-test_t1474_start_goal_entry", "neighbor-test_t1619_goal_terminality",
              "neighbor-test_t1619_iteration_boundary", "review-authority",
              "review-oracle-oracle-green", "review-oracle-a02-green",
              "review-oracle-original-checks-green"]
test_summary = []
for name in test_names:
    item = read(name)
    assert item["accepted"] and item["tests"]["ran"] > 0
    assert not item["tests"]["red"] and item["exit_code"] == 0
    test_summary.append({key: item[key] for key in (
        "name", "command", "cwd", "tests", "passed", "skipped", "exit_code",
        "source_fingerprint_before", "source_fingerprint_after", "stderr_sha256", "oracle_hashes")})
write("test-summary", test_summary)

# Create final output paths before the final porcelain count; content updates
# then cannot add a new dirty entry to the reported denominator.
for name in ("final-audit.json", "final-report.json", "FINAL_REPORT.md", "artifact-manifest.json",
             "after-status.z", "after-index.z", "after-refs.txt"):
    path = OUT / name
    if not path.exists():
        path.write_bytes(b"")
porcelain = git("status", "--porcelain=v1", "-uall", "-z")
(OUT / "after-status.z").write_bytes(porcelain)
(OUT / "after-index.z").write_bytes(index)
(OUT / "after-refs.txt").write_bytes(refs)
entries = [part for part in porcelain.split(b"\0") if part]
dirty_counts = {}
for entry in entries:
    key = entry[:2].decode()
    dirty_counts[key] = dirty_counts.get(key, 0) + 1
assert not any(entry[:1] in (b"R", b"C") or entry[1:2] in (b"R", b"C") for entry in entries)
initial_entries = [part for part in (OUT / "before-status.z").read_bytes().split(b"\0") if part]
initial_outside = {part[3:]: part[:2] for part in initial_entries if not part[3:].startswith(b".saipen/")}
current_outside = {part[3:]: part[:2] for part in entries if not part[3:].startswith(b".saipen/")}
assert initial_outside == current_outside
warnings = re.findall(r"^WARN \[([^]]+)\]", (OUT / "final-core-validation-spool/stdout").read_text(encoding="utf-8"), re.M)
assert len(warnings) == 9

audit = {
    "accepted": True, "checked_at_utc": datetime.now(timezone.utc).isoformat(),
    "phase": state["phase"], "task": state["task"], "last_event": state["last_event"],
    "head": before["head"], "branch": before["branch"], "source_fingerprint": fingerprint,
    "dirty_before": before["dirty_entries"], "dirty_after": len(entries), "dirty_counts_after": dirty_counts,
    "index_entries_sha256": before["index_entries_sha256"], "index_entries_unchanged": True,
    "heads_and_tags_unchanged": True, "non_saipen_dirty_entries_unchanged": True,
    "original_memory_files_checked": len(memory), "changed_original_memory_files": changed_memory,
    "missing_original_memory_files": missing_memory, "unexplained_memory_changes": unexpected_memory,
    "conformance_index_changes": "canonical core validation appended receipts; exact current receipt SHA256 and active generation/lineage roots verified; original receipt files preserved",
    "foreign_board_rows_preserved_exactly": len(foreign_before), "other_tickets_closed": [],
    "ticket_scope_paths": attribution["accepted_paths"], "a03_production_edits": [],
    "committed_closure_targets": [target["path"] for target in record["targets"]],
    "journal_status": record["status"], "release_operation": record["op_id"],
    "closure_operation": record["closure_op_id"], "publication": "none; no commit, staging, tag or push",
    "coverage": coverage, "source_integrity": source_integrity,
    "temporary_paths_absent": temporary_paths, "cleanup_complete": True,
    "detected_process_leaks": core["processes_leaked_detected"], "active_owned_leaks": [],
    "inflight": None, "pending_operations": [], "conflict_operations": [],
    "final_core_warnings": warnings, "current_core_conformance": "CURRENT_PASS",
    "next_action": state["next_action"], "next_ticket_started": False,
}
write("final-audit", audit)
print(json.dumps({key: audit[key] for key in (
    "accepted", "phase", "task", "last_event", "dirty_before", "dirty_after",
    "source_fingerprint", "foreign_board_rows_preserved_exactly", "changed_original_memory_files",
    "closure_operation", "release_operation", "next_action")}, indent=2))
