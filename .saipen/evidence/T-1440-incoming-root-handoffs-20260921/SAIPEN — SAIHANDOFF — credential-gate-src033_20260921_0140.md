SAIPEN — SAIHANDOFF — credential-gate-src033
SAIHANDOFF_V1
HANDOFF_ID: SAIHANDOFF-20260921-credential-gate-src033
PROJECT_ID: lineage-b512942bac884a8691f6c98afcd6ddb9
PROJECT_NAME: SAIPEN
TOPIC: credential-gate-src033
KIND: implementation
ROLE: protocolist
TARGET_POLICY: reuse
DELIVERY: manual
CONTENT_SHA256: 3bd0e984e9784d5940cbeb47f89c1aea5a1655563a6096e28e51b958fdd46c2f
END_HEADER

# SAIPEN — SAIHANDOFF — credential-gate ship deadlock (SRC-033 class)

ROLE: SAIPEN PROTOCOLIST
MODE: IMPLEMENT PROTOCOL REPAIR IN SAIPEN HOME
PRIORITY: P1
IMPLEMENTATION AUTHORITY: repair the SAIPEN engine/host only; do NOT mutate any consumer project.

## Mission

Repair the SAIPEN source-credential release gate so its refusal is repairable
and routes to the already-implemented fix.

## Defect (measured live 2026-09-21)

`saipen ship` on AUDAPACK (T-233 / SRC-078) refused:

```
RELEASE_FAILED / stage SOURCE_COVERAGE / SOURCE_CREDENTIALS_UNSAFE
detail: credential pattern in exact archive source SRC-033; supply a
user-authorized replacement or amendment before release
```

No `canonical_next_command`. No `remediation_commands` in the conformance
receipt for this class.

Two traps compose:

1. `saipen source quarantine SRC-033 --reason CREDENTIAL_PATTERN --dry-run`
   succeeds and plans the exact fix (body -> `.saipen/quarantine/source/`,
   digest-bound QUARANTINED distribution record), and
   `tools/test_source_receipts.py:966` proves the gate then clears. The verb is
   implemented, admitted, and authority-correct -- yet nothing names it.
2. The route the refusal DOES imply -- "replacement or amendment" -- is dead for
   an ARCHIVED receipt: `saipen source retire SRC-033 --reason STALE_CREDENTIAL`
   returns `ALREADY_RETIRED` (tombstone exists), and `--amends` would mint a new
   active imported-audit receipt with unresolved coverage (trade one block for
   another).

The gate is repository-global: `intake._legacy_sensitive_source_gate` scans
`active + tombstones + archive`, so ONE archived credential-bearing receipt
freezes every release in the project, unrelated to the ticket being shipped.
Carried on AUDAPACK since 2026-09-07 (LOG E-1020 / E-1061 / E-1091).

## Required repairs (bounded)

R1. Register a remediation in `tools/saipen_engine/remediation.py` `REMEDIATIONS`
    mapping the credential-gate class to
    `saipen source quarantine <SRC-N> --reason CREDENTIAL_PATTERN`, so
    `extract_commands` carries it into the conformance receipt and the run-time
    refusal exposes it as `canonical_next_command`.

R2. Have `intake._legacy_sensitive_source_gate` (SOURCE_CREDENTIALS_UNSAFE,
    ~line 2409) name the quarantine route in its detail instead of only
    "replacement or amendment".

R3. Ensure `release.py::_preflight_plan`'s SOURCE_COVERAGE branch forwards a
    `canonical_next_command` (match `admission.py::_BRAKE_ROUTES`), so the
    refusal is never a dead end.

R4 (adjudicate, do not auto-implement): decide the truthful disposition for an
    ARCHIVED credential receipt. Either allow `source retire` an honest
    non-misroute reason class, or state explicitly that quarantine is the sole
    route and document it. Do not create a route that lets an agent assert a
    false MISROUTED_PROJECT_BINDING.

## Acceptance

- On a fixture holding one archived credential-bearing receipt with a tombstone,
  `saipen ship` (or the emittable refusal) yields
  `canonical_next_command: saipen source quarantine <SRC-N> --reason
  CREDENTIAL_PATTERN`; executing it clears the gate.
- `tools/test_remediation_self_consistency.py` passes with the new entry
  (registry + effects + parser/dispatch + docs).
- Existing controls stay green: `test_source_receipts.py` (incl. line 966),
  `test_t1400_*`, `test_audit_2026_08_28_all3.py` credential classes.
- No product/project bytes touched by the repair; no consumer project mutated.
- Red control: pre-fix the refusal carries no route; post-fix it does.

## Do NOT

- weaken the credential gate or downgrade SOURCE_CREDENTIALS_UNSAFE to a warning;
- add a `_KNOWN_LEGACY` suppression or a project-name exception;
- rewrite the archived source body;
- let an agent fabricate MISROUTED_PROJECT_BINDING;
- resolve or close AUDAPACK's T-233/T-229 or its SRC-033 from inside SAIPEN.

## Origin evidence

- Packet: `C:\Users\vac34\AppData\Local\saipen\protocol_incidents\inbox\SAI-DEFECT-20260921-credential-gate-no-quarantine-route.md`
- Body: `V:\___VAC\__K\__CODE\_PY\_AUDAPACK\.saipen\evidence\SAI-AUDAPACK-T229-SHIP-QUARANTINE-ROUTE-20260921\REPORT.md`
- AUDAPACK LOG E-1842 (ship REFUSED at PREFLIGHT/SOURCE_COVERAGE); T-233 scope
  `.saipen/kitchen/release_scope/T-233.json`; widget 0.0.63 untouched.
- Sibling classes (distinct, do not merge): SAI-DEFECT-20260917
  (quarantine-export, closed by T-1400), SAI-DEFECT-20260918
  (work-coverage deadlock, T-1399/T-1405).
