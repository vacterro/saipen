"""Hash live originals and immutable captures; canonical readers run only on copies."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
OLD = ROOT / ".saipen/evidence/T-1696-queued-audapack"
TARGET = Path(r"V:\___VAC\__K\__CODE\_PY\_AUDAPACK")
PREFIX = sys.argv[1]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.log import read_history_snapshot, snapshot_contract_errors
from saipen_engine.journal import semantic_receipt_snapshot
from saipen_engine.fast_check import validate_texts


def sha(body):
    return hashlib.sha256(body).hexdigest()


def check_originals():
    checked = 0
    for label in ("live-snapshot", "durable-snapshot"):
        directory = OLD / label
        manifest = json.loads((directory / "capture.json").read_bytes())
        for name, expected in manifest["files"].items():
            path = TARGET / name
            info = path.lstat()
            assert stat.S_ISREG(info.st_mode) and not path.is_symlink()
            assert not getattr(info, "st_file_attributes", 0) & 0x400
            assert sha(path.read_bytes()) == expected["sha256"], (name, "live changed")
            assert sha((directory / name).read_bytes()) == expected["sha256"], (name, "copy changed")
            checked += 1
    return checked


before = check_originals()
producer = OLD / "producer"
provenance = json.loads((producer / "provenance.json").read_bytes())
writer = json.loads((producer / "zcode-writer.json").read_bytes())
producer_files = []
for row in provenance["messages"]:
    assert sha((producer / row["parts_path"]).read_bytes()) == row["sha256"]
    producer_files.append(row["parts_path"])
for row in writer["records"]:
    assert sha((producer / row["path"]).read_bytes()) == row["sha256"]
    producer_files.append(row["path"])
passes = []
copy = OLD / "durable-snapshot"
for _ in range(2):
    history = read_history_snapshot(copy)
    receipts = semantic_receipt_snapshot(copy)
    docs = [(copy / ".saipen" / name).read_text(encoding="utf-8")
            for name in ("STATE.md", "BOARD.md", "LOG.md")]
    passes.append({"tail": history.tail, "history_hash": history.hash,
                   "ledger_errors": snapshot_contract_errors(history),
                   "fast_errors": validate_texts(*docs, current_agent="forensic", sealed_events=history),
                   "semantic_receipts": len(receipts.records), "receipt_errors": list(receipts.errors),
                   "receipt_digest": receipts.digest})
assert passes[0] == passes[1], "canonical read-only result was not idempotent"
assert passes[0]["tail"] == 3146 and passes[0]["semantic_receipts"] == 4170
assert not passes[0]["receipt_errors"] and len(passes[0]["ledger_errors"]) == 4
registry = Path(r"C:\Users\vac34\.config\freebuff-desktop\projects\_AUDAPACK-4f7eebe8-9eeb-44db-bce0-9e7514935b65\project.json")
assert registry.read_bytes() == (OLD / "registry-original.json").read_bytes()
git = []
for label, args, original in (
    ("head", ("rev-parse", "HEAD"), "git-1.txt"),
    ("dirty", ("status", "--porcelain=v1", "-uall"), "git-2.txt"),
    ("unstaged", ("diff", "--binary"), "git-3.txt"),
    ("staged", ("diff", "--cached", "--binary"), "git-4.txt"),
):
    result = subprocess.run(["git", *args], cwd=TARGET,
                            env=dict(os.environ, GIT_OPTIONAL_LOCKS="0"), capture_output=True, timeout=60)
    raw = result.stdout + result.stderr
    assert result.returncode == 0 and raw == (OLD / "live-snapshot" / original).read_bytes(), label
    git.append({"kind": label, "sha256": sha(raw), "unchanged": True})
after = check_originals()
assert before == after == 8048
report = {"observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "target": str(TARGET), "before_originals": before, "after_originals": after,
          "copies_and_live_sha256_equal": True, "registry_unchanged": True,
          "producer_originals_verified": producer_files,
          "git": git, "canonical_reader_passes": passes, "idempotent": True,
          "target_writes": 0, "disposition": "HISTORY_LEDGER_CORRUPT / INTEGRITY_BLOCKED"}
(OUT / (PREFIX + "-preservation.json")).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"preserved_originals": after, "idempotent": True,
                  "ledger_errors": passes[0]["ledger_errors"], "semantic_receipts": 4170,
                  "target_writes": 0}))
