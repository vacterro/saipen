# T-1435 M12/M13 -- canonical FastPrompter repairs and AFTER ship gate (2026-09-21)

## Canonical repairs executed (no manual BOARD/STATE/LOG edit anywhere)

1. T-1226 legacy metadata (MR-000001, E-2437)
   Command: `saipen ticket repair-metadata T-1226 --field source_receipts
   --legacy-unbound --authority lineage-baeb688e509941f5903f854b37b6c05b`
   Result: METADATA_REPAIRED / LEGACY_UNBOUND_REFERENCE. Classification is
   LEGACY_UNBOUND because no canonical SRC for the historical
   `FASTPROMPTER - SMART_20260908_0645` token exists in this project's intake
   history; the exact original bytes are preserved in the immutable MR
   receipt and no SRC was invented. The second identical invocation returned
   ALREADY_APPLIED with the same receipt id (idempotence proven live).

2. saitranslate producer reconciliation
   Command: `saipen sub reconcile saitranslate --authority SRC-030`
   Result: SUB_RECONCILED / OUTCOME_A_STALE_STATE_CLEARED. Its BOARD is
   fully terminal, so the stale task residue was cleared and the phase stayed
   DONE. Its historical next_action WAIT exceeded CORE 1.2's one-sentence
   bound, so the producer-owned transaction re-bounded it to the first
   sentence (recorded in the event and in the returned `normalized_wait`).

3. saiwiki producer reconciliation
   Command: `saipen sub reconcile saiwiki --authority SRC-030`
   Result: SUB_RECONCILED / OUTCOME_B_RESUMED_NONTERMINAL (verdict
   DONE_CLAIM_FALSE: BOARD holds TODO W-039). The projection returned to PLAN
   with task none; W-039 was NOT touched. A second invocation is a no-op
   (SUB_RECONCILE_NOT_TERMINAL, zero writes).

4. Machine-local runtime artifacts (OPERATOR_AUTHORIZED_COMMAND)
   The ship gate named 258 tracked runtime files. The sanctioned maintenance
   `git rm -r --cached -- <paths>` was applied; `runtime_namespace.release_problems`
   went RUNTIME_NAMESPACE_TRACKED -> RUNTIME_NAMESPACE_CLEAN, and the live
   runtime files remain on disk (verified: locks/core.lock still present).

## AFTER ship gate (current reviewed runtime, same command as BEFORE-B)

exit 0; 0 un-downgraded FAILs; 47 remaining failures are exactly the
documented FastPrompter known-legacy classes (closure-evidence for historical
DONE tickets, [saio] mechanical provenance in sealed history, invalid
saitranslate legacy sub-board prefix, improve report) and the project shim
downgrades them to KNOWN-LEGACY; file fp-after-new.txt.

The five BEFORE blocker classes are all absent:
  - T-1226 legacy token: 0 occurrences
  - saitranslate STATE lifecycle FAIL: 0
  - saiwiki STATE lifecycle FAIL: 0
  - saiwiki BOARD open-work FAIL: 0
  - runtime namespace FAIL: 0

## Boundaries

No FastPrompter product runtime file was modified. No manual canonical edit.
No validator suppression or project-specific exception was added. No commit,
tag, push or publication was performed.

## T-1226 POST BOARD row

```
- [x] T-1226 [P1] Smart whole-block Ctrl+Shift+Q folding | verify: selected multi-paragraph chunk becomes ONE quote group (internal blanks become `>` continuations, indentation preserved), auto-collapses immediately to one fold anchor, whole-run unquote + round-trip exact, outside paragraph never swallowed, undo/redo never strands hidden lines, existing silo fold persistence works; 17 exact-ID quote/fold/fuzz tests passed + ruff + compileall + 135 unit tests passed; full smoke 19F/481P = legacy archive/transfer/gap classes (13 same-IDs fail on stashed tree baseline too, rest order-flaky standalone-pass) | owner: opencode | claim_time: 2026-09-08T06:45:00Z
```

## FastPrompter LOG tail (canonical events)

```
- 21.09.26 03:54 [E-2434] [parent: E-2433] [T-1303] [agent: buffy] [op: transition-4db9725513194732a5830756159801a9] RUN: transition to SHIP
- 21.09.26 03:54 [E-2435] [parent: E-2434] [T-1303] [agent: buffy] [op: checkpoint-4829f3ec02b64e16befb56e3ab419e49] RUN: SHIP -- verification-only compound qq+ee complete; no implementation delta; W-041 ready, TRANSLATE-019 bound; 23 tests PASS, 0 errors, 31 WARN; docs 28/32 backlog carried; sound_dependencies.py row added, 69 events, i18n modules synced, vocab rebuilt
- 21.09.26 03:55 [E-2436] [parent: E-2435] [T-1303] [agent: buffy] [op: ticket-6536cbb3fc0546b5b99bf2b7dacc9127] DEC: ticket block via SAIOPS (active) -- SHIP blocked: T-1303 is verification-only compound qq+ee producing producer-ready handoffs (W-041 + TRANSLATE-019), not a product deliverable with a publishable slice. No direct close under SRC-037: the sano target is explicit collect via qqq/eee, then verify, then merge/shipped publication after the source wiki/docs mirror lands.
- 21.09.26 05:54 [E-2437] [parent: E-2436] [T-1226] [agent: astra] [op: metadata-repair-a6a27664eb1b46fcbc49bb47c2d33f4c] DEC: actor astra (seat buffy); REPAIR-METADATA T-1226 -- field source_receipts; classification LEGACY_UNBOUND_REFERENCE; receipt MR-000001; original field value 'FASTPROMPTER — SMART_20260908_0645' preserved by hash; malformed value removed
```

## saitranslate POST STATE

```
---
phase: DONE
task: none
next_action: "WAIT: manual-verify -- TRANSLATE-018 draft @ 05df824/e8c53d82: UI surface closed (oracle VALIDATION PASSED, 0 errors, 0 false coverage claims, packs == modules, 1479 canonical keys) and 30 lanes' coverage_pct corrected + DE/EST/JA guide mirrors re-cut"
blocker: ""
agent: saitranslate
saipen_version: 7
mode: read-only
schema_version: 3
style_contract: ded-4ae736e4
updated: "2026-09-21T05:57:44Z"
transition_from: DONE
role_revision: "sha256:f241e6b83c39e9b46bfa586638efb0374bbb39889646f723b9189bbb4912c0c5"
---
```

## saiwiki POST STATE

```
---
phase: PLAN
task: none
next_action: "PHASE PLAN"
blocker: ""
agent: saiwiki
saipen_version: 7
mode: read-only
updated: "2026-09-21T05:54:49Z"
transition_from: DONE
role_revision: "sha256:54a42475a124ab0f27e83d600a284a9cc54d9668029c4828cfc48512b031df13"
---
```
