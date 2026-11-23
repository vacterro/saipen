"""Normalize only the admitted exact SRC-225 mission through the native source owner."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import intake, operations

docs, state, board, _ = operations._read(ROOT)
assert state["task"] == "T-1726" and state["phase"] == "SCOUT", state
assert board["tickets"]["T-1726"]["fields"]["owner"] == "saipen-cli"
body = ROOT / ".saipen/intake/active/SRC-225.md"
digest = "534002a32de0a831c3e25b3b0c487488ef317397f583be14037ed56765d359b9"
assert hashlib.sha256(body.read_bytes()).hexdigest() == digest
output = HERE / "source-derivation.json"
assert not output.exists(), "preserve immutable derivation result"
rows = [
    ("requirement", "Fulfill the complete exact SRC-225 closed-contract regression mission: a historical VERIFIED requirement can become suspect when its current implementation demonstrably regresses, preserving historical closure and independently safe engineering."),
    ("requirement", "PHASE1: inspect live SAIPEN closure, Source/evidence dependencies, code change and fingerprint invalidation, ownership and reconciliation paths; locate actual paths first. Select classification A-E only on original/current evidence; the reported FastPrompter snapshot does not prove historical T-1442 fraud."),
    ("requirement", "PHASE2 items1-3: reuse or repair meaningful requirement-to-implementation/test dependencies, reproducible verification evidence, assumption-change detection and focused behavioral rechecks. A changed byte alone is not proof of failure."),
    ("requirement", "PHASE2 items4-5: represent proven current contradictions using existing supported vocabulary where possible; check current schemas/consumers before adding enums. Keep original historical Source and evidence bytes immutable."),
    ("requirement", "PHASE2 items6-7: attribute new defects to legal current ownership, reuse an existing active recovery finding/Work, and prevent duplicate recovery tickets. FastPrompter product repairs remain its owner's scope."),
    ("requirement", "PHASE2 items8-10: bound detection cost on large repositories; do not rerun all historical tests for unrelated edits; report exact inability-to-verify reasons; reuse existing authority instead of a parallel incompatible state system."),
    ("acceptance-criterion", "PHASE3 negative control: a previously verified function replaced by an incorrect implementation is detected as a current contradiction or actionable suspect requiring the appropriate check."),
    ("acceptance-criterion", "PHASE3 negative control: removal of a required dependency is detected without fabricating successful verification."),
    ("acceptance-criterion", "PHASE3 negative control: deletion or weakening of the required test is detected; old green evidence cannot validate the weakened current verifier."),
    ("acceptance-criterion", "PHASE3 false-positive control: a harmless formatting-only change to the same file is not asserted to be a proven behavioral regression."),
    ("acceptance-criterion", "PHASE3 false-positive control: a refactor retaining the behavioral contract remains acceptable when appropriate current evidence proves it."),
    ("acceptance-criterion", "PHASE3 ownership control: a closed Source with an already active successor repair uses that legal owner and does not create another equivalent ticket."),
    ("acceptance-criterion", "PHASE3 concurrency control: two agents attempting reconciliation preserve serialized canonical authority and do not duplicate or corrupt accepted findings."),
    ("acceptance-criterion", "PHASE3 freshness control: immutable historical receipt bytes remain unchanged while stale current validation is distinguished from historical closure."),
    ("invariant", "PHASE4: permit fail-open degraded independently safe engineering and diagnostics; a suspected historical regression must not freeze unrelated Work. Hard-block only an operation whose actual safety or required integrity guarantee is violated."),
    ("invariant", "PHASE4: never silently close a confirmed current regression as historically VERIFIED, and never rewrite Source history to make the current snapshot clean."),
    ("requirement", "PHASE5: run focused protocol/lifecycle tests, controlled regressions and supported full relevant gates; measure actual detection overhead and report false-positive/false-negative controls and migration impact honestly."),
    ("requirement", "Deliver the complete SRC-225 report: actual root cause, files, protocol rule or workflow correction, red/green controls, false-positive rate, performance cost, remaining risks/limitations, migration impact and exact next action."),
    ("invariant", "Preserve all SRC-225 NON_GOALS: no FastPrompter production changes, mass historical reopening, global byte-change hard stop, automatic evidence deletion, fabricated Work IDs, commit, tag, push, release or deployment."),
]
assert len(rows) == 19
results = []
for number, (kind, text) in enumerate(rows, 1):
    clause = f"R{number:03d}"
    done = subprocess.run([str(ROOT / "bin/saipen.cmd"), "--json", "source", "req", "SRC-225",
                           clause, kind, text], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", timeout=60)
    value = json.loads(done.stdout)
    results.append({"clause": clause, "exit_code": done.returncode, "result": value})
    assert done.returncode == 0 and value["ok"], results[-1]
assert hashlib.sha256(body.read_bytes()).hexdigest() == digest
coverage = intake.coverage_summary(ROOT, "SRC-225")
assert coverage["requirements"] == coverage["actionable"] == 19 and coverage["terminal"] == 0
output.write_text(json.dumps({"source": "SRC-225", "work": "T-1726", "digest": digest,
                              "coverage": coverage, "results": results}, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"source": "SRC-225", "work": "T-1726", "clauses": 19,
                  "unknown": 19, "negative_and_false_positive_controls": 8,
                  "source_unchanged": True, "implementation_started": False}))
