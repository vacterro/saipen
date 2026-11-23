# RAPORT — SAIPEN ship: the source-credential gate blocks every release and names no route

- reporter: buffy (opencode session, project `V:\___VAC\__K\__CODE\_PY\_AUDAPACK`)
- written: 2026-09-21 local
- origin: AUDAPACK T-233 / SRC-078 (`saipen ship` after the T-229 live-acceptance closure)
- protocol: SAIPEN 8.0.1
- related: `SAI-DEFECT-20260917-saimail-receipt-quarantine-export` (the same gate, the sibling escape), `SAI-DEFECT-20260918-ship-source-coverage-deadlock` (the other repo-wide ship deadlock)

## Summary

`saipen ship` on AUDAPACK is refused at preflight with **no `canonical_next_command`**, even though the fix it names (`source quarantine`) already exists and works.

Observed:

```
saipen ship --json
 -> {"ok":false,"code":"RELEASE_FAILED","stage":"SOURCE_COVERAGE",
     "detail":"active source receipt blocks ship: {'ok': False, 'code':
     'SOURCE_CREDENTIALS_UNSAFE', 'detail': 'credential pattern in exact
     archive source SRC-033; supply a user-authorized replacement or
     amendment before release'}"}
```

A second, stricter probe confirms the route gap and a second trap:

```
saipen source quarantine SRC-033 --reason CREDENTIAL_PATTERN --dry-run --json
 -> ok (DRY_RUN_PLAN): .saipen/quarantine/source/SRC-033.md + distribution record

saipen source retire SRC-033 --reason STALE_CREDENTIAL --dry-run --json
 -> {"ok":false,"code":"ALREADY_RETIRED",
     "detail":"SRC-033 already carries a tombstone; retirement never rewrites it"}
```

## Why this is a protocol defect (not an AUDAPACK one)

1. **The refusal has no route.** `release.py:_preflight_plan` returns
   `SOURCE_COVERAGE` + the raw `intake.release_gate` dict, which carries **no**
   `canonical_next_command` and no `remediation_commands`. The gate itself
   (`intake._legacy_sensitive_source_gate`) produces `SOURCE_CREDENTIALS_UNSAFE`
   with only prose ("supply a user-authorized replacement or amendment before
   release"). Neither the run-time result nor the conformance receipt maps this
   class to a command. A session following the router has nothing legal to run.

2. **The fix exists but is unreachable from the refusal.** `source quarantine
   --reason <CODE>` is implemented (`intake.quarantine_receipt`), is admitted by
   the guard, and its dry-run plans the exact fix for SRC-033 (relocate the body
   to `.saipen/quarantine/source/`, write the digest-bound `QUARANTINED`
   distribution record). After quarantine the gate returns
   `SOURCE_CREDENTIALS_SAFE` and `release_gate` proceeds (proven by the existing
   control `test_t1400_release_gate_accepts_verified_quarantined_current_work`,
   `tools/test_source_receipts.py:966`). So a reachable, authority-correct repair
   route exists and the validator simply never names it.

3. **The published precedent routes AWAY from quarantine.**
   `SAI-DEFECT-20260917-saimail-receipt-quarantine-export` (disposition:
   NEW_TICKET **T-1400**, completed 2026-09-19) and `intake.py:2327-2333` both
   document the intended route as "supply a user-authorized replacement or
   amendment". On this project that advice dead-ends: SRC-033 is an **archived
   CLOSED** receipt, `source retire` refuses it (`ALREADY_RETIRED`, a tombstone
   exists), and re-capturing the 1200+-line audit under `--amends` would mint a
   new active receipt whose own imported-audit coverage is unresolved. Quarantine
   is the *only* legal, non-fabricating, non-destructive route -- and it is not
   advertised.

4. **It is repository-global and blocks every ticket.** `_legacy_sensitive_source_gate`
   scans active + tombstoned + archived bodies on every release. One archived
   receipt therefore freezes all publication in the project, unrelated to the
   released ticket. Carried on AUDAPACK since 2026-09-07 (LOG E-1020, E-1061,
   E-1091).

## Deterministic reproduction

Work from a SAIPEN DONE project that carries one archived receipt whose body
matches a `codec.redact_credentials` pattern (e.g. `api_key = <value>`):

```
saipen ship --json
 -> RELEASE_FAILED / SOURCE_COVERAGE / SOURCE_CREDENTIALS_UNSAFE / no route

saipen source quarantine <SRC-N> --reason CREDENTIAL_PATTERN --dry-run --json
 -> ok: plans body relocation + QUARANTINED distribution record

# the one route the refusal text implies is dead:
saipen source retire <SRC-N> --reason STALE_CREDENTIAL --dry-run --json
 -> ALREADY_RETIRED (archived receipts carry a tombstone)
```

## Root cause

- `tools/saipen_engine/release.py` `_preflight_plan` SOURCE_COVERAGE branch:
  forwards the raw gate dict without a `canonical_next_command` / remediation.
- `tools/saipen_engine/intake.py` `_legacy_sensitive_source_gate`
  (`SOURCE_CREDENTIALS_UNSAFE`, ~line 2409): emits refusal prose that names only
  "replacement or amendment", not the implemented `source quarantine` verb.
- `tools/saipen_engine/remediation.py` `REMEDIATIONS`: has no entry for the
  credential-gate class, so `extract_commands` can never surface `source
  quarantine <SRC-N>`.

## Impact

- A verified, otherwise-green release is permanently unpublishable on any project
  holding one legacy credential-bearing archived receipt.
- The only route that actually works (quarantine) is unadvertised; the advertised
  route (replacement/amendment) is refused for archived receipts. A weaker model
  reaches this state and has no legal move, so it stalls or fabricates.
- Non-destructive and monotonic: quarantine never rewrites the body and cannot be
  reversed, so this is a routing/repairability defect, not a data-safety one.

## Suspected owner

`tools/saipen_engine/remediation.py` (add the credential-gate -> `source
quarantine` remediation entry); `tools/saipen_engine/release.py` +
`tools/saipen_engine/intake.py` (carry `canonical_next_command` on the
SOURCE_COVERAGE refusal, matching `admission.py::_BRAKE_ROUTES`).

## Repair candidates

1. Register a remediation: `SOURCE_CREDENTIALS_UNSAFE` -> `saipen source
   quarantine <SRC-N> --reason CREDENTIAL_PATTERN`, so the conformance receipt
   and the run-time refusal carry it as `canonical_next_command`.
2. Have `_legacy_sensitive_source_gate` name the quarantine route in its detail.
3. Consider whether a distinct reason class (`ARCHIVED_CREDENTIAL`, honest
   `--reason CREDENTIAL_PATTERN` on an archived receipt) should be allowed by
   `source retire` without fabricating a misroute.

## Scope note

This is NOT SAI-DEFECT-20260917 (that class ended with T-1400 delivering
quarantine and the alternative's docs) and NOT SAI-DEFECT-20260918 (repo-wide
*work-coverage* deadlock). This class is narrower: **the credential gate's
refusal does not route to the implemented quarantine fix, and its documented
alternative is refused for archived receipts.**

## Full context

Origin: AUDAPACK T-233 (`SRC-078`), the T-229 live-acceptance closure, LOG
E-1842 (ship REFUSED at PREFLIGHT/SOURCE_COVERAGE), scope
`.saipen/kitchen/release_scope/T-233.json`, widget 0.0.63 bytes untouched.
