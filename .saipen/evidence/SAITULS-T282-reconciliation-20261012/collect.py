"""Observe SAITULS without changing its project; save evidence here only."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOME = HERE.parents[2]
TARGET = Path(r"V:\___VAC\__K\__CODE\__SAITULS")
sys.path.insert(0, str(HOME / "tools"))
from saipen_engine.board import REQUIRED_HEADINGS, duplicate_records, parse_board

OUTPUT = HERE / "read-only-inspection.json"
if OUTPUT.exists():
    raise ValueError("immutable evidence already exists")

protected = [
    ".saipen/STATE.md", ".saipen/BOARD.md", ".saipen/LOG.md",
    ".saipen/intake/active/SRC-099.md", ".saipen/intake/active/SRC-099.meta.json",
    ".saipen/intake/contracts/SRC-099.json", ".saipen/intake/coverage/SRC-099.json",
    ".saipen/evidence/T-282-w2-002-ownership-generation.md",
    "Scripts/accounts/SaiAccountsHelper.cs", "tests/test_accounts_ownership_generation.py",
]

def hashes():
    return {p: hashlib.sha256((TARGET / p).read_bytes()).hexdigest() for p in protected}

def execute(label, command, timeout=180):
    result = subprocess.run(command, cwd=TARGET, capture_output=True, timeout=timeout)
    for channel in ("stdout", "stderr"):
        (HERE / (label + "." + channel + ".bin")).write_bytes(getattr(result, channel))
    return {"command": command, "exit_code": result.returncode,
            "stdout": label + ".stdout.bin", "stderr": label + ".stderr.bin"}

def git(*args):
    return subprocess.check_output(["git", *args], cwd=TARGET).decode("utf-8").strip()

before = hashes()
status_before = git("status", "--porcelain=v1", "--untracked-files=all")
index_before = hashlib.sha256(git("ls-files", "--stage").encode()).hexdigest()
head_before = git("rev-parse", "HEAD")
board_text = (TARGET / ".saipen/BOARD.md").read_text(encoding="utf-8-sig")
parsed = parse_board(board_text)
logs = (TARGET / ".saipen/LOG.md").read_text(encoding="utf-8-sig").splitlines()
meta = json.loads((TARGET / ".saipen/intake/active/SRC-099.meta.json").read_text())
operations = []
for area in ("ops", "settled"):
    for path in sorted((TARGET / ".saipen/recovery" / area).glob("*/operation.json")):
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if area == "ops" or data.get("op_id") in (
            "userreq-4fd1ad12db894d5bb82d07379cc969fd", "run-w2-002-residual"
        ):
            operations.append({"path": str(path.relative_to(TARGET)), "record": data})

commands = [
    execute("status", [str(HOME / "bin/saipen.cmd"), "status", "--json"]),
    execute("recover-dry-run", [str(HOME / "bin/saipen.cmd"), "recover", "--dry-run", "--json"]),
    execute("core-read-only", [sys.executable, "-B", str(HOME / "tools/validate.py"),
        "--project-root", str(TARGET), "--gate", "core", "--no-receipt",
        "--findings-json", str(HERE / "core-findings.json")]),
]
after = hashes()
code = (TARGET / "Scripts/accounts/SaiAccountsHelper.cs").read_text(encoding="utf-8-sig")
markers = ("CheckRollbackOwnershipAt", "MarkTxnIntentState", "HasExactHelperRuleVerified",
           "post_write_acl_fp", "mutation_written")
result = {
    "observed_utc": datetime.now(timezone.utc).isoformat(), "project_root": str(TARGET),
    "head": head_before, "git_status_counts": dict(Counter(s[:2] for s in status_before.splitlines())),
    "index_entries_sha256": index_before, "protected_before": before, "protected_after": after,
    "protected_unchanged": before == after,
    "git_unchanged": status_before == git("status", "--porcelain=v1", "--untracked-files=all")
        and index_before == hashlib.sha256(git("ls-files", "--stage").encode()).hexdigest()
        and head_before == git("rev-parse", "HEAD"),
    "state": (TARGET / ".saipen/STATE.md").read_text(encoding="utf-8-sig"),
    "required_headings": REQUIRED_HEADINGS, "actual_headings": parsed["headings"],
    "board_errors": parsed["errors"], "t282_physical_records": duplicate_records(board_text, "T-282"),
    "t282_parser_record": parsed["tickets"].get("T-282"),
    "source_meta": meta, "source_body_digest_matches": before[protected[3]] == meta["source_sha256"],
    "source_contract": json.loads((TARGET / protected[5]).read_text()),
    "source_coverage": json.loads((TARGET / protected[6]).read_text()),
    "event_chain_tail": [s for s in logs if re.search(r"\[E-(299[5-9]|300[0-2])\]", s)],
    "operation_records": operations, "commands": commands,
    "current_code_markers": {marker: [i for i, line in enumerate(code.splitlines(), 1) if marker in line]
                             for marker in markers},
    "test_execution": "Not repeated; existing narrative and E-3002 claims retained without new PASS attribution.",
    "conclusion": "AUTHORITY_REQUIRED; no canonical mutation applied. PAUSED cannot be preserved by the proposed SCOUT recovery.",
}
OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"output": str(OUTPUT), "protected_unchanged": result["protected_unchanged"],
                  "git_unchanged": result["git_unchanged"], "board_errors": result["board_errors"],
                  "commands": [{"name": c["stdout"], "exit_code": c["exit_code"]} for c in commands]}))
