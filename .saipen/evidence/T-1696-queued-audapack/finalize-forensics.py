"""Finish a read-only investigation; all output stays in the SAIPEN evidence tree."""
import dataclasses
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

OUT = Path(__file__).resolve().parent
HOME = OUT.parents[2]
TARGET = Path("V:/___VAC/__K/__CODE/_PY/_AUDAPACK")
LIVE = OUT / "live-snapshot"
COPY = OUT / "durable-snapshot"
sys.path.insert(0, str(HOME / "tools"))
from saipen_engine.log import read_history_snapshot, snapshot_contract_errors
from saipen_engine.journal import semantic_receipt_snapshot
from saipen_engine.fast_check import validate_texts


def sha(body):
    return hashlib.sha256(body).hexdigest()


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def check_capture(directory):
    capture = json.loads((directory / "capture.json").read_bytes())
    mismatches = []
    for relative, expected in capture["files"].items():
        if sha((directory / relative).read_bytes()) != expected["sha256"]:
            mismatches.append({"path": relative, "kind": "copy changed"})
        if sha((TARGET / relative).read_bytes()) != expected["sha256"]:
            mismatches.append({"path": relative, "kind": "live changed"})
    return {"files_rechecked": len(capture["files"]), "mismatches": mismatches}


before = {"live": check_capture(LIVE), "durable": check_capture(COPY)}
assert not any(value["mismatches"] for value in before.values()), before
# Readers run on copies, including the original lineage carrier. Do not touch
# the immutable captured copies while assembling this diagnostic projection.
for relative in json.loads((LIVE / "capture.json").read_bytes())["files"]:
    destination = COPY / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        shutil.copyfile(LIVE / relative, destination)
    assert destination.read_bytes() == (LIVE / relative).read_bytes()

passes = []
for _ in range(2):
    snapshot = read_history_snapshot(COPY)
    receipts = semantic_receipt_snapshot(COPY)
    state, board, log = [(COPY / ".saipen" / name).read_text(encoding="utf-8")
                         for name in ("STATE.md", "BOARD.md", "LOG.md")]
    prefix = dataclasses.replace(snapshot, events=tuple(
        event for event in snapshot.events if event["event"] <= 3131
    ))
    passes.append({"history_sha256": snapshot.hash, "tail": snapshot.tail,
                   "parsed_events": len(snapshot.events),
                   "illegal_lines": list(snapshot.illegal_lines),
                   "ledger_errors": snapshot_contract_errors(snapshot),
                   "structural_prefix_through_E3131_errors": snapshot_contract_errors(prefix),
                   "fast_errors": validate_texts(state, board, log,
                                                 current_agent="forensic", sealed_events=snapshot),
                   "semantic_receipts": len(receipts.records),
                   "semantic_receipt_errors": list(receipts.errors),
                   "semantic_receipt_digest": receipts.digest,
                   "finish_receipt": [record for record in receipts.records
                                      if record["op_id"] == "finish-29deadc9792e498ca581916d8a22c785"]})
assert passes[0] == passes[1], "reader verdict was not idempotent"
save("canonical-readers.json", {"scope": "copied evidence only", "passes": passes,
                                "idempotent": True, "target_writes": []})

env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
git_checks = []
for label, args, initial in [
    ("head", ["rev-parse", "HEAD"], "git-1.txt"),
    ("dirty", ["status", "--porcelain=v1", "-uall"], "git-2.txt"),
    ("unstaged", ["diff", "--binary"], "git-3.txt"),
    ("staged", ["diff", "--cached", "--binary"], "git-4.txt"),
]:
    result = subprocess.run(["git", *args], cwd=TARGET, env=env, capture_output=True, timeout=60)
    raw = result.stdout + result.stderr
    (OUT / f"final-git-{label}.txt").write_bytes(raw)
    git_checks.append({"kind": label, "exit_code": result.returncode,
                       "sha256": sha(raw), "unchanged": raw == (LIVE / initial).read_bytes()})
assert all(record["unchanged"] and record["exit_code"] == 0 for record in git_checks), git_checks

raw = subprocess.run(["git", "show", "--format=fuller", "--binary", "HEAD", "--",
                      ".saipen/STATE.md", ".saipen/BOARD.md", ".saipen/LOG.md"],
                     cwd=TARGET, env=env, capture_output=True, timeout=60)
assert raw.returncode == 0, raw.stderr
(OUT / "head-protocol.patch").write_bytes(raw.stdout)
blobs = []
for revision in ("HEAD", "HEAD^"):
    for relative in (".saipen/STATE.md", ".saipen/BOARD.md", ".saipen/LOG.md"):
        result = subprocess.run(["git", "show", f"{revision}:{relative}"], cwd=TARGET,
                                env=env, capture_output=True, timeout=60)
        assert result.returncode == 0, result.stderr
        destination = OUT / "git-blobs" / revision.replace("^", "-parent") / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(result.stdout)
        blobs.append({"revision": revision, "path": relative, "sha256": sha(result.stdout),
                      "size": len(result.stdout)})
save("git-blobs.json", blobs)

engineering = {}
for relative in ("audapack/saipen_evidence.py", "tests/test_saipen_evidence.py",
                 "resources/AUDAPACK_WIDGET.user.js", ".saipen/evidence/T-298-widget-trust-boundary.md",
                 ".saipen/saip.py", ".zcode/plans/plan-sess_c329cfaf-c7cd-4128-b005-faea70844c7a.md"):
    source = TARGET / relative
    raw = source.read_bytes()
    destination = OUT / "additional-originals" / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw)
    assert source.read_bytes() == raw
    engineering[relative] = {"sha256": sha(raw), "size": len(raw), "classification": "preserved original; no new engineering test claim"}
assert engineering["resources/AUDAPACK_WIDGET.user.js"]["sha256"] == "5efa3a49fee7bdef83f63ecfa3324e2746eb12b874baad4e1bba03edd03a09fa"
save("engineering-originals.json", engineering)

registry = Path("C:/Users/vac34/.config/freebuff-desktop/projects/_AUDAPACK-4f7eebe8-9eeb-44db-bce0-9e7514935b65/project.json")
(OUT / "registry-original.json").write_bytes(registry.read_bytes())
installation = {}
for label, path in [("state_bound_BOOT", HOME / "saipen/BOOT.md"),
                    ("AGENTS_legacy_BOOT", Path("C:/Users/vac34/.agents/skills/saipen/BOOT.md"))]:
    raw = path.read_bytes()
    (OUT / f"{label}.md").write_bytes(raw)
    installation[label] = {"path": str(path), "sha256": sha(raw), "size": len(raw),
                           "symlink": path.is_symlink()}
save("installation.json", installation)

controls = []
for name in ("1-duplicate", "2-unadmitted-done", "3-unnumbered", "3-unnumbered-repeat",
             "4-heading", "5-evidence-no-event-v2", "6-unrelated-overwrite"):
    path = OUT / f"guard-{name}.json"
    record = json.loads(path.read_bytes())
    controls.append({"case": name, "artifact": path.name, "sha256": sha(path.read_bytes()),
                     "exit_code": record["exit_code"], "code": record["verdict"].get("code"),
                     "canonical_docs_unchanged": record["canonical_docs_unchanged"]})
assert all(record["canonical_docs_unchanged"] for record in controls)
save("guardrails-final.json", {"six_controls": controls, "independent_repeat": "3-unnumbered-repeat",
                                "regression_work": "T-1699", "probe_sha256": sha((OUT / "guardrails.py").read_bytes())})

after = {"live": check_capture(LIVE), "durable": check_capture(COPY)}
assert before == after, (before, after)
source_hashes = {name: sha((HOME / name).read_bytes()) for name in (
    "tools/saipen_engine/log.py", "tools/saipen_engine/journal.py",
    "tools/saipen_engine/reconcile.py", "tools/saipen_engine/fast_check.py",
    "tools/saipen_engine/subs.py", "tools/validate.py")}
save("final-preservation.json", {"checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                 "before": before, "after": after, "git": git_checks,
                                 "current_reader_source_sha256": source_hashes,
                                 "target_mutations": [], "reader_idempotent": True,
                                 "canonical_reconciliation_performed": False})
print(json.dumps({"ledger_errors": passes[0]["ledger_errors"],
                  "prefix_errors": passes[0]["structural_prefix_through_E3131_errors"],
                  "semantic_receipts": passes[0]["semantic_receipts"],
                  "semantic_errors": passes[0]["semantic_receipt_errors"],
                  "fast_errors": passes[0]["fast_errors"],
                  "reader_idempotent": True, "preserved_files": sum(v["files_rechecked"] for v in after.values()),
                  "target_mutations": []}, ensure_ascii=False))
