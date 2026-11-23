"""Independent readback of the recovery, native validation, and real admission.

The only positive mutation is the operator-authorized, ticketless canonical
recovery-verification checkpoint. It creates no historical or fictitious Work.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from preflight import HERE, HOME, ORIGINAL, RECOVERY, git, inventory, sha, write_new

sys.path.insert(0, str(HOME / "tools"))
from saipen_engine import codec, guard_events, journal, lifecycle_authority, log, mailbox, paths, state
from saipen_engine.board import parse_board

COMMANDS = []
GATES = {}


def environment():
    result = os.environ.copy()
    result.update(PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8", GIT_OPTIONAL_LOCKS="0")
    return result


def cli(*args, env=None):
    command = [str(HOME / "bin/saipen.cmd"), "--project-root", str(RECOVERY),
               "--agent", "saipen-cli", *args, "--json"]
    result = subprocess.run(command, cwd=RECOVERY, env=env or environment(),
                            stdin=subprocess.DEVNULL, capture_output=True, check=False, timeout=300)
    try:
        payload = json.loads(result.stdout)
    except ValueError:
        payload = None
    record = {"argv": command, "exit_code": result.returncode, "payload": payload,
              "stdout": result.stdout.decode("utf-8", errors="replace"),
              "stderr": result.stderr.decode("utf-8", errors="replace")}
    COMMANDS.append(record)
    return record


def native(label):
    command = [sys.executable, "-B", str(HOME / "tools/validate.py"), "--project-root",
               str(RECOVERY), "--gate", "core", "--no-receipt"]
    run = subprocess.run(command, cwd=RECOVERY, env=environment(), stdin=subprocess.DEVNULL,
                         capture_output=True, check=False, timeout=600)
    raw = run.stdout + run.stderr
    (HERE / f"phase4-v3-{label}-native.txt").write_bytes(raw)
    text = raw.decode("utf-8", errors="replace")
    record = {"argv": command, "exit_code": run.returncode,
              "output": str(HERE / f"phase4-v3-{label}-native.txt"),
              "output_sha256": sha(HERE / f"phase4-v3-{label}-native.txt"),
              "summary": re.findall(r"Validation (?:FAILED|complete)[^\r\n]*", text),
              "failed_lines": [line for line in text.splitlines() if line.startswith("FAIL:")]}
    COMMANDS.append(record)
    assert run.returncode == 0 and not record["failed_lines"], record
    return record


def inspect_protocol():
    history = log.read_history_snapshot(RECOVERY)
    ledger_errors = log.snapshot_contract_errors(history)
    parsed_board = parse_board(codec.read_doc(RECOVERY / ".saipen/BOARD.md"))
    parsed_state = state.parse_state(codec.read_doc(RECOVERY / ".saipen/STATE.md"))
    assert not ledger_errors and not parsed_board["errors"], (ledger_errors, parsed_board["errors"])
    authority = lifecycle_authority.assess(RECOVERY, parsed_state, parsed_board, history.events)
    assert authority["status"] != "UNAUTHORIZED" and not authority["findings"], authority
    pending, conflicts = journal.scan_pending(RECOVERY)
    assert not pending and not conflicts, (pending, conflicts)
    receipts = journal.semantic_receipt_snapshot(RECOVERY)
    assert not receipts.errors, receipts.errors
    assert not parsed_board["tickets"], "No historical or manufactured Work may enter recovery BOARD"
    for name in ("STATE.md", "BOARD.md", "LOG.md", "IDENTITY.md"):
        paths.prove_owned_dir_chain(RECOVERY / ".saipen", kind="recovery authority", ownership_root=RECOVERY)
        paths.prove_owned_regular(RECOVERY / ".saipen" / name, kind="recovery authority")
    return {"state": parsed_state, "board_errors": parsed_board["errors"],
            "ledger_errors": ledger_errors, "ledger_segments": len(log.history_paths(RECOVERY)),
            "events": history.events, "lifecycle_authority": authority,
            "pending": pending, "conflicts": conflicts,
            "receipt_count": len(receipts.records),
            "receipt_errors": receipts.errors, "ticket_count": len(parsed_board["tickets"])}


def main():
    p0 = json.loads((HERE / "phase0.json").read_text(encoding="utf-8"))
    p2 = json.loads((HERE / "phase2.json").read_text(encoding="utf-8"))
    p3 = json.loads((HERE / "phase3.json").read_text(encoding="utf-8"))
    layout = json.loads((HERE / "passive-evidence-layout.json").read_text(encoding="utf-8"))
    assert layout["phase2_sha256"] == sha(HERE / "phase2.json")
    placements = layout["placements"]
    assert len(placements) == len(p2["original_files"]) + len(p2["supporting_files"])
    assert len({row["destination"] for row in placements}) == len(placements)
    assert p2["copy_pass"] and p3["init_pass"]
    failure = None
    inspection = None
    try:
        assert paths.project_lineage_identity(RECOVERY) == p3["new_lineage"]
        assert p3["new_lineage"] != paths.project_lineage_identity(ORIGINAL)
        resolved = paths.resolve_project_root(explicit=RECOVERY, host_lineage=p3["new_lineage"], authority="mutation")
        assert resolved.root == RECOVERY, resolved
        GATES["new_identity_and_binding"] = True
        before = inspect_protocol()
        GATES["initial_complete_ledger_and_ownership"] = True
        initial_native = native("initial")
        GATES["initial_native_core"] = True
        source = inventory(ORIGINAL)
        assert source["content_sha256"] == p0["complete_original"]["content_sha256"]
        copy = inventory(RECOVERY)
        assert not source["risks"] and not copy["risks"]
        # Current authority replaces exactly the four original core/identity paths;
        # every original is still retained at its explicit, byte-verified mapping.
        for row in placements:
            actual = copy["files"][row["destination"]]
            assert actual["sha256"] == row["sha256"] and actual["bytes"] == row["bytes"], row
            assert [actual["device"], actual["inode"]] != row["source_node"] and actual["nlink"] == 1
        GATES["source_legacy_and_supporting_bytes"] = True
        for alias in ("worktrees", "commondir", "objects/info/alternates", "objects/info/http-alternates"):
            assert not os.path.lexists(RECOVERY / ".git" / alias), alias
        assert Path(git(RECOVERY, "rev-parse", "--absolute-git-dir").decode().strip()).resolve() == RECOVERY / ".git"
        assert git(RECOVERY, "for-each-ref", "--format=%(refname) %(objectname)").decode() == p0["git_projection"]["refs"]
        assert hashlib.sha256(git(RECOVERY, "rev-list", "--all", "--objects")).hexdigest() == p0["git_projection"]["reachable_history_sha256"]
        assert sha(RECOVERY / ".recovery-legacy/original/.git/index") == p0["git_raw_index_sha256"]
        assert hashlib.sha256(git(RECOVERY, "ls-files", "--stage", "-z")).hexdigest() == p0["git_projection"]["index_projection_sha256"]
        assert git(RECOVERY, "worktree", "list", "--porcelain").decode().count("worktree ") == 1
        git(RECOVERY, "fsck", "--full", "--no-reflogs")
        GATES["independent_git_integrity"] = True
        # Two real negative controls, both with complete before/after bytes.
        before_denial = inventory(RECOVERY)
        env = environment()
        env["SAIPEN_PROJECT_LINEAGE"] = p3["original_lineage"]
        refused = cli("checkpoint", "RUN", "Foreign-lineage refusal control", env=env)
        assert refused["exit_code"] != 0 and refused["payload"]["code"] == "PROJECT_LINEAGE_MISMATCH", refused
        event = {"event": "before_tool", "host": "opencode", "cwd": str(RECOVERY), "actor": "saipen-cli",
                 "tool_name": "write", "tool_input": {"filePath": str(RECOVERY / ".saipen/LOG.md"),
                                                        "content": "fabricated historical DONE\n"}}
        guard = guard_events.evaluate_event(event)
        assert guard["admitted"] is False and guard["code"] == "PROTECTED_CANONICAL_NAMESPACE", guard
        assert inventory(RECOVERY)["content_sha256"] == before_denial["content_sha256"]
        GATES["unauthorized_and_foreign_refused_zero_bytes"] = {"foreign": refused["payload"]["code"], "guard": guard}
        checkpoint = cli("checkpoint", "RUN",
                         "RECOVERY VERIFICATION -- native core PASS; captured source, legacy namespace, Git refs/objects/index and independent storage verified; controls A-G PASS; original remains NO_GO; no historical Work imported. Operator authorization: SRC-211@lineage-b512942bac884a8691f6c98afcd6ddb9. No publication or cutover.")
        assert checkpoint["exit_code"] == 0 and checkpoint["payload"]["ok"], checkpoint
        GATES["authorized_canonical_verification_operation"] = checkpoint["payload"]
        final_native = native("final")
        GATES["final_native_core"] = True
        inspection = inspect_protocol()
        assert inspection["lifecycle_authority"]["status"] == "AUTHORIZED", inspection
        assert inspection["lifecycle_authority"]["floor"] == inspection["state"]["last_event"] == 1
        assert len(inspection["events"]) == 1
        assert inspection["events"][0]["op_id"] == checkpoint["payload"]["op_id"]
        GATES["final_operation_backed_ledger"] = True
        status = cli("status")
        assert status["exit_code"] == 0 and status["payload"]["ok"], status
        GATES["normal_status_admission"] = True
        original_after = inventory(ORIGINAL)
        assert original_after["content_sha256"] == p0["complete_original"]["content_sha256"]
        assert git(ORIGINAL, "for-each-ref", "--format=%(refname) %(objectname)").decode() == p0["git_projection"]["refs"]
        assert sha(ORIGINAL / ".git/index") == p0["git_raw_index_sha256"]
        destination_after = inventory(RECOVERY)
        assert not destination_after["risks"]
        for row in placements:
            actual = destination_after["files"][row["destination"]]
            assert actual["sha256"] == row["sha256"] and actual["bytes"] == row["bytes"]
        marker = mailbox.default_workspace() / mailbox.MARKER_NAME
        assert sha(marker) == p0["mailbox_marker_sha256"]
        GATES["original_and_refs_preserved"] = True
        GATES["external_mailbox_unmodified"] = True
    except Exception:
        failure = traceback.format_exc()
    record = {"checked_utc": datetime.now(timezone.utc).isoformat(), "original_root": str(ORIGINAL),
              "recovery_root": str(RECOVERY), "original_lineage": p3["original_lineage"],
              "new_lineage": p3["new_lineage"], "gates": GATES, "commands": COMMANDS,
              "final_protocol": inspection, "failure": failure,
              "acceptance_pass": failure is None, "original_verdict": "NO_GO",
              "recovery_verdict": "GO_CANONICAL_OPERATIONS_ONLY" if failure is None else "NO_GO",
              "cutover": False, "publication": False, "consumer_agents_enabled": False,
              "legacy_terminal_claims": "Unverified; preserved exclusively outside active authority",
              "host_hook_limit": "CLI authority and native guard refusal are proved; no live-host blocking capability or OS sandbox is inferred."}
    write_new(HERE / "phase4-v3.json", record)
    print(json.dumps({"acceptance_pass": record["acceptance_pass"], "gates": list(GATES),
                      "new_lineage": p3["new_lineage"], "failure": failure,
                      "original_verdict": record["original_verdict"], "recovery_verdict": record["recovery_verdict"]}, indent=2))
    if failure:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
