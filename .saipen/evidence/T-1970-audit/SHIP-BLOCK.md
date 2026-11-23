# T-1970 SHIP measurement — PUBLICATION_BLOCKED_EXTERNAL

`validate.py --gate ship`: **51 PASS, 6 FAIL**, exit 1.
Raw: `.saipen/evidence/T-1970-audit/ship-gate.log`.

The six are byte-for-byte the same six that blocked T-1966, T-1967, T-1968 and
T-1969:

1. `SRC-037 archive bundle invalid` — 4 contract clauses vs 16 coverage requirements.
2. `EX-000029` — verified against engine `06c1149a`, running engine `96e9c936`.
3. `release index is empty` — the 4,221-path release-metadata slice is unstaged.
4. `staged release metadata differs from working-tree bytes` — 623 paths named,
   **zero of them under `.saipen/intake/contracts/SRC-351*`,
   `.saipen/intake/coverage/SRC-351.json`, or `.saipen/evidence/T-1970-audit/`**
   (measured: `grep -c SRC-351` on that failure line returns 0).
5. `cross-doc drift [root-file-set]` — `SAIPENFUTURE_CONTEXT_GRAPH_20260909_1811.md`.
6. `coverage gap` — that same stray root file.

## The blocker that actually belongs to T-1970

T-1970's own verify criterion is: *every actionable clause of SRC-351 is terminal
with evidence; linked Work DONE; source closure succeeds; audit/29.md consumed by
the journaled audit inbox cleanup.*

That cannot be satisfied, and the reason is not a defect in this ticket:

```
saipen source close SRC-351
  -> SOURCE_UNRESOLVED
     unresolved: R006 R007 R008 R009 R010 R011
```

`BLOCKED` is not a terminal disposition (`saipen_engine/intake.py:121
TERMINAL_DISPOSITIONS`). `UNAVAILABLE_ENVIRONMENT` is not available for these
clauses either: it requires a `when_environment` normalized in advance and a
successful absence probe, and the host is **present**, not absent.

The six unresolved clauses are owned by two other parties:

| clause | owner | what they must do |
|---|---|---|
| R006 | FreeBuff | decide exact namespace ownership before semantic skill matching |
| R007 | FreeBuff | stop treating a protocol `NO_HOME` as a working-directory cue |
| R008 | FreeBuff | re-read `~/.agents/skills/` at session start |
| R009 | FreeBuff | stop offering a substitute for an explicit SAIPEN command |
| R010 | FreeBuff | one live `/saipen continue` in `_BZ_REA` |
| R011 | SAIPAL | reconcile the five `NO_DRIFT` receipts append-only |

## Why inventing closure was not an option

- `NOT_APPLICABLE` would be a lie: these clauses are exactly applicable, to
  another repository.
- `DEFERRED` cannot waive closure by rule (`SOURCES.md`).
- A `when_environment` retrofit is refused by design: *"an agent cannot retrofit
  environmental optionality onto unfinished work."*
- Leaving them `BLOCKED` and calling the source closed would be the
  "false product DONE" the campaign forbids.

## Deliverables that are ready and unsent

- `.saipen/evidence/T-1970-audit/FREEBUFF-ROUTING-HANDOFF.md` (R006-R010)
- `.saipen/evidence/T-1970-audit/SAIPAL-RECONCILIATION-REQUEST.md` (R011)
- `.saipen/evidence/T-1970-audit/COVERAGE-REPORT.md` (the 13-clause ledger)

## What IS done and proven

Seven of thirteen clauses verified from measurements taken this cycle: the typed
`FOREIGN_PROTOCOL_COMMAND` refusal, its named owner and full invocation, SAIPEN
verbs unaffected (`cc`/`continue` exit 0), three damaged-registry forms degrading
to `None`, the router/refusal/naming suites PASS at 52, the ADVISORY/NONE host
declaration matching the audit's §10 claim, and `model_supplied` refused an
operator-origin upgrade at 30 passing witness tests.

Remotes untouched. HEAD `66ef622a`.
