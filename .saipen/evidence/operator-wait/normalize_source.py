"""Normalize the captured audit through the canonical batch operation."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import intake

clauses = [
    ("R001", "requirement", "Register WAIT_OPERATOR in the canonical error registry; emitted entry refusals retain the code without unregistered_code, and registry consistency/inventory tests cover this construction."),
    ("R002", "requirement", "Prevent newly supplied invalid next_action values at the authoritative STATE construction boundary. Reuse one canonical grammar across the writer, strict reader, checkpoint validation and reconciliation; preserve field ownership and refuse malformed PHASE/RUN/RESUME or arbitrary operator prose without coercion."),
    ("R003", "requirement", "Canonical operator WAIT round-trips through strict STATE readers, status, continue and recovery without a spurious RECONCILE_REAUTH_REQUIRED; WAIT is not executable and cannot itself grant mutation or invent an operator decision. Existing valid PHASE/RUN/RESUME/saipen forms remain valid."),
    ("R004", "requirement", "Legacy malformed next_action remains boundedly recoverable through an explicit canonical WAIT replacement; preserve original STATE and decision evidence, keep executable grammar strict, and make printed recovery syntax directly executable with global flags in the documented position and spaces/punctuation preserved."),
    ("R005", "acceptance-criterion", "Prove deterministic controls A-F: original unregistered WAIT_OPERATOR and invalid STATE construction are red before repair; unchanged controls pass afterward; valid WAIT, no WAIT execution, valid action forms and an exact rendered recovery command are exercised. Keep verification independent from the production subject."),
    ("R006", "acceptance-criterion", "Relevant state/recovery/refusal tests, registry validation, canonical validator and declared full core family pass truthfully; report exact focused counts and any skip/capability limitations without baselining regressions."),
    ("R007", "invariant", "Use a proper claimed SAIPEN Work lifecycle and canonical operations throughout; preserve BOARD/STATE/LOG provenance, retain source integrity and perform source/audit cleanup only through their normal journaled closure gates."),
    ("R008", "requirement", "Persist a reviewable report of root causes, canonical grammar, legacy recovery, exact changed paths, same-oracle red/green evidence, focused/full validation, lifecycle evidence and remaining risks."),
    ("R009", "non-goal", "Do not modify SAIPAL, add release roots, resolve SAIPAL conflicts, weaken strict executable grammar, execute WAIT payloads, invent authority, redesign the whole state machine or rewrite historical evidence. Publication remains excluded by the controlling run source."),
    ("R010", "context", "The imported report describes a legitimate operator-only boundary with zero of 751 sessions runnable. A read-only current SAIPAL STATE observation is now DONE/saipen continue, so the historical operator prose is a reported shape, not a claim about its current bytes or an invitation to mutate that project."),
]
result = intake.add_requirements(ROOT, "SRC-167", [
    {"rid": rid, "class": kind, "text": text} for rid, kind, text in clauses
])
print(json.dumps(result, indent=2))
raise SystemExit(0 if result.get("ok") else 1)
