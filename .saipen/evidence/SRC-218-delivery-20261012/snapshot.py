"""Read-only evidence collection for SRC-218; writes only this evidence folder."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.board import parse_board
from saipen_engine.core_unit import tree_fingerprint
from saipen_engine.intake import coverage_complete, verify_integrity


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, encoding="utf-8")


def expand_detail(ticket: dict) -> dict:
    result = dict(ticket)
    reference = ticket.get("fields", {}).get("detail_ref")
    if reference:
        meta_path = ROOT / reference
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        original = ROOT / meta["original_record_path"]
        if digest(original) != meta["original_record_sha256"]:
            raise ValueError(f"bad detail digest: {reference}")
        result["detail_original"] = original.read_text(encoding="utf-8")
        result["detail_sha256"] = digest(original)
    return result


label = sys.argv[1]
output = HERE / (label + ".json")
if output.exists():
    raise ValueError("evidence label already exists")
board = parse_board((ROOT / ".saipen/BOARD.md").read_text(encoding="utf-8"))
if board["errors"]:
    raise ValueError(board["errors"])
tickets = board["tickets"]
priority_candidates = [
    expand_detail(ticket)
    for ticket in tickets.values()
    if ticket["section"] != "## DONE"
    and ticket["description"].startswith(("[P0]", "[P1]"))
]
done_dependencies = sorted({
    need for ticket in priority_candidates for need in ticket["needs"]
    if need in tickets and tickets[need]["section"] == "## DONE"
})
evidence = {
    "observed_utc": datetime.now(timezone.utc).isoformat(),
    "scope": "current live BOARD including every open P0/P1, exact referenced details, and the named Sources; graph tools exclude tools/ and are not current symbol evidence",
    "head": git("rev-parse", "HEAD").strip(),
    "fingerprint": tree_fingerprint(ROOT),
    "state": (ROOT / ".saipen/STATE.md").read_text(encoding="utf-8"),
    "board_sha256": digest(ROOT / ".saipen/BOARD.md"),
    "log_sha256": digest(ROOT / ".saipen/LOG.md"),
    "board_counts": dict(Counter(ticket["section"] for ticket in tickets.values())),
    "git_status_counts": dict(Counter(line[:2] for line in git("status", "--porcelain=v1").splitlines())),
    "git_index_entries_sha256": hashlib.sha256(git("ls-files", "--stage").encode()).hexdigest(),
    "worktrees": git("worktree", "list", "--porcelain"),
    "open_P0_P1": priority_candidates,
    "terminal_dependencies": {need: expand_detail(tickets[need]) for need in done_dependencies},
    "named_work": {need: expand_detail(tickets[need]) for need in [
        "T-1718", "T-1717", "T-1719", "T-1720", "T-442", "T-473", "T-1644",
        "T-1317", "T-1375", "T-1446", "T-1541", "T-1551", "T-1563", "T-1602", "T-1606", "T-1702"
    ] if need in tickets},
    "sources": {},
}
for receipt in ("SRC-216", "SRC-218", "SRC-219"):
    evidence["sources"][receipt] = {
        "integrity": verify_integrity(ROOT, receipt),
        "coverage": coverage_complete(ROOT, receipt),
    }
output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({
    "evidence": str(output.relative_to(ROOT)),
    "fingerprint": evidence["fingerprint"],
    "board_counts": evidence["board_counts"],
    "open_P0_P1_count": len(priority_candidates),
    "open_P0_P1_ids": [ticket["id"] for ticket in priority_candidates],
    "terminal_dependency_count": len(done_dependencies),
    "sources": evidence["sources"],
}, ensure_ascii=True))
