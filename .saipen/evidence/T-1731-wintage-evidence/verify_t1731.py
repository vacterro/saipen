#!/usr/bin/env python3
"""Mechanical verification of T-1731 evidence recovery and integrity."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WINTAGE = Path("V:/___VAC/__K/__CODE/_TAMPERMONKEY/_WIN95THEME/Wintage")
SRC_UNPACK = Path("V:/___VAC/__K/__CODE/_HTML/_SAI_WEBSITE/_src_unpack/wintage")

def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def test_checkpoint_journal_match():
    journal_path = WINTAGE / ".saipen/recovery/settled/checkpoint-d898f0b0e66644ea92a33f4c18909e6d/operation.json"
    assert journal_path.is_file(), f"Missing journal: {journal_path}"
    data = json.loads(journal_path.read_text(encoding="utf-8"))
    assert data["op_id"] == "checkpoint-d898f0b0e66644ea92a33f4c18909e6d"
    
    targets = {t["path"]: t for t in data["targets"]}
    log_target = targets[".saipen/recovery/log-detail/E-3286-f56793e5c6d3f9370cd1be66.LOG.md"]
    json_target = targets[".saipen/recovery/log-detail/E-3286-f56793e5c6d3f9370cd1be66.json"]
    
    # Check unpacked source
    unp_log = SRC_UNPACK / ".saipen/recovery/log-detail/E-3286-f56793e5c6d3f9370cd1be66.LOG.md"
    unp_json = SRC_UNPACK / ".saipen/recovery/log-detail/E-3286-f56793e5c6d3f9370cd1be66.json"
    assert unp_log.is_file(), "Unpack log file missing"
    assert unp_json.is_file(), "Unpack json file missing"
    
    h_log = sha256_file(unp_log)
    h_json = sha256_file(unp_json)
    
    assert h_log.startswith(log_target["after_hash"]), f"Log hash mismatch: {h_log} vs {log_target['after_hash']}"
    assert h_json.startswith(json_target["after_hash"]), f"Json hash mismatch: {h_json} vs {json_target['after_hash']}"
    
    # Check restored files in Wintage
    w_log = WINTAGE / ".saipen/recovery/log-detail/E-3286-f56793e5c6d3f9370cd1be66.LOG.md"
    w_json = WINTAGE / ".saipen/recovery/log-detail/E-3286-f56793e5c6d3f9370cd1be66.json"
    assert w_log.is_file(), "Restored log file missing"
    assert w_json.is_file(), "Restored json file missing"
    
    assert sha256_file(w_log) == h_log
    assert sha256_file(w_json) == h_json
    
    # Check json metadata
    meta = json.loads(w_json.read_text(encoding="utf-8"))
    assert meta["event_id"] == "E-3286"
    assert meta["ticket_id"] == "T-415"
    assert meta["original_event_sha256"] == h_log
    assert meta["original_event_bytes"] == len(w_log.read_bytes())
    assert meta["externalization_event"]["operation_id"] == "checkpoint-d898f0b0e66644ea92a33f4c18909e6d"

    print("ALL CHECKS PASSED: T-1731 recovered evidence verified.")

if __name__ == "__main__":
    test_checkpoint_journal_match()
