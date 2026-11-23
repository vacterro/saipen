"""Re-run the four SRC-338 red controls and rebind the artifact to the current source.

`red-controls-current.json` names the exact bytes of the three modules the
controls exercise. Editing any of them makes the recorded hashes a lie about
the tree, so this driver regenerates the observations and the hashes together.

Fail-closed predicates are asserted here, not eyeballed: the artifact is only
written when all four counterexamples are refused.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]  # .saipen/evidence/T-1932/closures -> project root
OUT = HERE / "red-controls-current.json"
SUBJECTS = (
    "tools/saipen_engine/campaign.py",
    "tools/saipen_engine/host_dispatch.py",
    "tools/saipen_engine/saipal_adapter.py",
)

LIVE_ACCEPTANCE = (
    "NOT DEMONSTRATED: these controls prove the four pre-fix counterexamples now "
    "fail closed. Real installed-host and SAIPAL end-to-end acceptance requires "
    "receipts that do not exist and is not inferred from these mocks."
)
SCOPE = (
    "isolated temporary projects against current source; no production enqueue, "
    "no external infrastructure, no installed-host or SAIPAL backend contact"
)


def main() -> int:
    proc = subprocess.run(
        [sys.executable, "-B", str(HERE / "red_controls.py")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
        check=False,
    )
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        return proc.returncode or 1
    observed = json.loads(proc.stdout)

    core_004 = observed.get("CORE-004", {})
    core_006 = observed.get("CORE-006", {})
    core_009 = observed.get("CORE-009", {})
    core_011 = observed.get("CORE-011", {})

    failures = []
    if core_004.get("dispatched") is not False:
        failures.append(f"CORE-004 dispatched={core_004.get('dispatched')!r}, expected False")
    if core_006.get("caller_named_qualification_receipt_accepted") is not False:
        failures.append("CORE-006 accepted a caller-named qualification receipt")
    if core_006.get("enqueue_call_count") != 0:
        failures.append(f"CORE-006 enqueue_call_count={core_006.get('enqueue_call_count')!r}, expected 0")
    if core_009.get("made_progress") is not False:
        failures.append("CORE-009 honoured a self-asserted progress claim")
    if core_009.get("state_mutated") is not False:
        failures.append("CORE-009 mutated state on a self-asserted progress claim")
    if core_009.get("journal_advanced") is not False:
        failures.append("CORE-009 advanced the journal on a self-asserted progress claim")
    if core_011.get("free_text_verification_accepted") is not False:
        failures.append("CORE-011 accepted free-text verification as VERIFIED evidence")

    if failures:
        for line in failures:
            print(line, file=sys.stderr)
        return 1

    payload = {
        "all_four_fail_closed": True,
        **observed,
        "live_acceptance": LIVE_ACCEPTANCE,
        "produced_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scope": SCOPE,
        "source_hashes": {
            rel: hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() for rel in SUBJECTS
        },
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"wrote": OUT.relative_to(ROOT).as_posix(), "source_hashes": payload["source_hashes"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
