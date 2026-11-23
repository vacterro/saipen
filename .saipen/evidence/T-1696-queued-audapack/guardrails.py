"""Six independent sacrificial probes; public CLI and full validator output retained."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from test_audit_inbox import AuditInboxFixture
from saipen_engine.log import read_history_snapshot, snapshot_contract_errors
from saipen_engine.fast_check import validate_texts
from saipen_engine.board import board_record_digest, duplicate_records

ENV = dict(os.environ, PYTHONIOENCODING="utf-8", GIT_OPTIONAL_LOCKS="0")
results = []

def cli(root, *args):
    result = subprocess.run([str(ROOT / "bin/saipen.cmd"), "--project-root", str(root),
                             *args, "--json"], cwd=ROOT, env=ENV,
                            capture_output=True, timeout=60)
    try:
        value = json.loads(result.stdout)
    except ValueError:
        value = {"instrument_error": (result.stdout + result.stderr).decode("utf-8", "replace")}
    return result.returncode, value

def docs(root):
    return [(root / ".saipen" / name).read_text(encoding="utf-8")
            for name in ("STATE.md", "BOARD.md", "LOG.md")]

def hashes(root):
    return {name: hashlib.sha256((root / ".saipen" / name).read_bytes()).hexdigest()
            for name in ("STATE.md", "BOARD.md", "LOG.md")}

def run(case, change):
    fixture = AuditInboxFixture()
    fixture.setUp()
    try:
        root = fixture.root
        code, added = cli(root, "ticket", "add", "P1", "legitimate control", "--verify", "proof")
        assert code == 0 and added.get("ok"), added
        code, baseline = cli(root, "validate")
        (OUT / f"guard-{case}-good.json").write_text(json.dumps(baseline, indent=2), encoding="utf-8")
        assert code == 0 and baseline.get("ok"), ("known-good instrument unavailable", baseline)
        change(root)
        before = hashes(root)
        code, verdict = cli(root, "validate")
        history = read_history_snapshot(root)
        fast = validate_texts(*docs(root), current_agent="probe", sealed_events=history)
        output = {"case": case, "exit_code": code, "verdict": verdict,
                  "fast_errors": fast, "ledger_errors": snapshot_contract_errors(history),
                  "canonical_docs_unchanged": hashes(root) == before}
        assert output["canonical_docs_unchanged"]
        (OUT / f"guard-{case}.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
        results.append(output)
        print(json.dumps({"case": case, "exit_code": code, "code": verdict.get("code"),
                          "fast_errors": fast[:3], "ledger_errors": output["ledger_errors"][:3]}), flush=True)
    finally:
        fixture.tearDown()

def edit(root, name, transform):
    path = root / ".saipen" / name
    path.write_text(transform(path.read_text(encoding="utf-8")), encoding="utf-8")

def duplicate(root):
    edit(root, "BOARD.md", lambda s: s.replace("## DONE\n", "## DONE\n- [x] T-1 [P1] unrelated Widget | verify: proof\n"))

def closed_without_events(root):
    edit(root, "BOARD.md", lambda s: s.replace("## DONE\n", "## DONE\n- [x] T-2 [P1] unadmitted closure | verify: proof | owner: probe | closure_mode: own_patch\n"))

def unnumbered(root):
    edit(root, "LOG.md", lambda s: s.replace("# Log\n", "# Log\n- 10.10.26 [T-1] RUN: ticket finished via SAIOPS -- completion (from SHIP)\n"))

def malformed(root):
    edit(root, "BOARD.md", lambda s: s.replace("## TODO\n", "## TODO## DOING\n"))

def evidence_without_identity(root):
    edit(root, "BOARD.md", lambda s: s.replace("- [ ] T-1", "- [x] T-1").replace("## TODO\n", "## TODO\n## DONE\n"))
    # Keep exactly one DONE section; the live identity owns a real admission,
    # but its supplied report grants no completion event.
    edit(root, "BOARD.md", lambda s: s.replace("## DONE\n## BLOCKED", "## BLOCKED"))
    path = root / ".saipen/evidence/closure.md"
    path.parent.mkdir(exist_ok=True)
    path.write_text("Engineering checks passed; no event identity.\n", encoding="utf-8")
    edit(root, "BOARD.md", lambda s: s.replace("verify: proof", "verify: .saipen/evidence/closure.md reports PASS but has no event identity"))

def unrelated_reconciliation():
    fixture = AuditInboxFixture()
    fixture.setUp()
    try:
        root = fixture.root
        for title in ("legitimate original", "unrelated protected task"):
            code, result = cli(root, "ticket", "add", "P1", title, "--verify", "proof")
            assert code == 0 and result.get("ok"), result
        code, good = cli(root, "validate")
        assert code == 0 and good.get("ok"), good
        duplicate(root)
        board = docs(root)[1]
        choices = duplicate_records(board, "T-1")
        unrelated = next(line for line in board.splitlines() if "- [ ] T-2 " in line)
        before = hashes(root)
        code, verdict = cli(root, "recover", "--resolve-duplicate-id", "T-1",
                            "--keep", choices[0]["digest"],
                            "--reassign", board_record_digest(unrelated))
        output = {"case": "6-unrelated-overwrite", "exit_code": code, "verdict": verdict,
                  "canonical_docs_unchanged": hashes(root) == before,
                  "protected_unrelated_record": unrelated, "known_good": good.get("code")}
        assert code != 0 and verdict.get("code") == "STALE_DUPLICATE_ID_DECISION", verdict
        assert output["canonical_docs_unchanged"]
        (OUT / "guard-6-unrelated-overwrite.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
        results.append(output)
        print(json.dumps(output), flush=True)
    finally:
        fixture.tearDown()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "additional":
        run("3-unnumbered-repeat", unnumbered)
        run("5-evidence-no-event-v2", evidence_without_identity)
        unrelated_reconciliation()
        (OUT / "guardrails-additional.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        raise SystemExit(0)
    for name, change in (("1-duplicate", duplicate), ("2-unadmitted-done", closed_without_events),
                         ("3-unnumbered", unnumbered), ("4-heading", malformed),
                         ("5-evidence-no-event", evidence_without_identity)):
        run(name, change)
    (OUT / "guardrails-summary.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
