"""Derive SRC-253 clauses through the public CLI, one `source req` per clause."""

import json
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
launcher = sys.argv[2]
CLAUSES = [
    ("R001", "acceptance-criterion", "SAIPEN has a documented canonical Auto-Doctor contract (SELF_HEALING_CONTINUATION): typed failure classes that each produce a canonical action, reusing existing owners"),
    ("R002", "acceptance-criterion", "cc can invoke authorized recovery automatically inside the normal continuation path, without a separate operator command"),
    ("R003", "acceptance-criterion", "The reference STALE_PASS conformance condition recovers without a manual saipen validate"),
    ("R004", "acceptance-criterion", "CURRENT_PASS is verified after recovery rather than assumed; a zero exit code alone is insufficient"),
    ("R005", "acceptance-criterion", "The original Work resumes automatically after a successful recovery, without a second cc"),
    ("R006", "acceptance-criterion", "The recovery stays bound to the real original operator command: no new operator decision is synthesized"),
    ("R007", "acceptance-criterion", "No duplicate execution occurs across the original cc, the recovery, validation and the resumed Work"),
    ("R008", "acceptance-criterion", "Unsafe failures preserve STOP, NO_GO, operator and integrity boundaries and stop with an exact canonical reason"),
    ("R009", "acceptance-criterion", "Recovery attempts are bounded and idempotent: one automatic revalidation per chain, no cc-validate-cc loop"),
    ("R010", "acceptance-criterion", "Race conditions and restart behavior are tested (concurrent writer, crash between recovery and resume)"),
    ("R011", "acceptance-criterion", "Health checks add no unacceptable overhead to a healthy cc; expensive validation runs only when the contract requires it"),
    ("R012", "acceptance-criterion", "ZAICODE has a structured integration contract for Doctor stages; ZAICODE code itself is changed only under its own admission"),
    ("R013", "acceptance-criterion", "A real host acceptance test proves the user-facing behavior when separately authorized"),
    ("R014", "acceptance-criterion", "Existing protocol regression gates remain passing"),
    ("R015", "acceptance-criterion", "Relevant recovery and provenance evidence is preserved and survives interruption"),
    ("R016", "acceptance-criterion", "Remaining unsupported failure conditions are explicitly classified with an owner and next action"),
    ("R017", "invariant", "Safety invariants: no forged operator authority, no ledger rewriting or event deletion, no weakened receipt hashing, no disabled conformance checks, no ownership preemption, no destructive cleanup, no infinite retries"),
    ("R018", "non-goal", "Do not rewrite SAIPEN wholesale and do not modify ZAICODE or Wintage code under this mission; publish a consumer contract instead"),
]
for rid, klass, text in CLAUSES:
    proc = subprocess.run(
        [launcher, "source", "req", "SRC-253", rid, klass, text, "--json"],
        cwd=str(root), capture_output=True, text=True, encoding="utf-8",
    )
    try:
        code = json.loads(proc.stdout).get("code")
    except ValueError:
        code = (proc.stdout or proc.stderr).strip()[:200]
    print(rid, klass, code)
