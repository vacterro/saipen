# SAIHANDOFF trust-repair triage — reproduced against current bytes

Source: SAIHANDOFF_SAIPEN_SAIPEN_20261026_225710_6155bd71.md (user-supplied).
Baseline at triage: phase DONE, last_event E-18953, goal_tickets 6.

Only claims reproduced by execution are admitted as Work. A claim that no
longer reproduces is recorded as already-repaired and produces no ticket.

## AUT-001 — host acceptance trusts an unverified receipt: REPRODUCED (partial)

tools/saipen_engine/host_dispatch.py::validate_host_acceptance_receipt

Reproduced on current bytes (TRIAGE.txt):
- H01 `accepting_host="invented-host"` -> `(True, 'HOST_ACCEPTED', '')`
- H02 same receipt, any plausible host name -> `(True, 'HOST_ACCEPTED', '')`
  (identity is a substring blacklist, not authentication)
- H03 `status="DISPATCH_REQUEST_PERSISTED"` -> `(True, 'DISPATCH_REQUEST_PERSISTED', '')`
- H04 `iteration_id="not-an-int"` -> raises ValueError
- H05 `worker_generation="x"` -> raises ValueError

NOT reproduced / already handled: none of the six counterexamples.

## AUT-002 — SAIPAL qualification self-asserted: NOT REPRODUCED

Repaired by T-1944 CORE-001. `deliver_finding_to_audit_inbox` now requires
`_broker_verified()` for any `authenticated is True` proof and refuses a
self-declared `authenticated`/`signature` pair naming no live broker.

## AUT-003 — report cursor acknowledges before delivery: NOT REPRODUCED

Repaired by T-1944 W2-002. `iter_new_qualified_findings` acknowledges a finding
only when the canonical allocator holds a COMMITTED operation for it; the cursor
is an observability watermark and is deliberately never read as a resume gate.

## AUT-004 — corpus fingerprint misses content changes: NOT REPRODUCED

Repaired by T-1944 W2-006. `_CorpusIdentity` folds `_finding_content_digest`
over every field except `finding_id`; F01/F02 in TRIAGE.txt show changed body
and changed qualification each change the digest.

## AUT-005 — pagination helpers have no production caller: REPRODUCED

`iter_new_qualified_findings` is called only from
`.saipen/evidence/T-1932/closures/red_report.py`; the production campaign path
calls `discover()`, which loads the whole report. The incremental transport is
an unused helper.

## AUT-006 — no real autonomous campaign driver: REPRODUCED

`CampaignController.step` has exactly one caller, `tools/saipen.py:15339`
(manual `saipen campaign step`). bootstrap/schedule-run.ps1 never calls it, so
nothing drives successive generations. Live native turn-start proof is not
obtainable from this seat.

## AUT-007 — one analysis slice treated as a completed cycle: REPRODUCED

tools/saipen_engine/campaign.py: `ANALYSIS_PROGRESS` increments a counter but
falls into the `else` branch -> QUIESCENT_WAIT + DISCOVERY_NO_NEW_FINDINGS,
so a pending SAIPAL objective stops being schedulable.

## AUT-008/009/010 — end-to-end chain, installed-host parity, soak: NOT OBTAINABLE HERE

Each requires the installed native host or real measured runtime. Not claimed.
