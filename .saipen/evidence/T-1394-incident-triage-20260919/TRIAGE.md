# T-1394 — protocol-incident pile triage (2026-09-19)

Executor: glm-5.3-max. Engine subject: HEAD `dc3b2f88` (live repo bytes are
authority). Live measurements: `PROBE-release-gate.txt` + `PROBE-mint-board.md`
+ `PROBE-mint-contract-SRC-001.json` beside this file; disposable project
`V:\_TEMP_\saipen-mint-probe`.

## Census

- ORIGINAL_CENSUS (E-7055, 18.09.26 11:01): 16 reports (3 packets + 4 evidence
  bodies + 8 future_gate + 1 __SAIMAIL__).
- CURRENT_CENSUS (2026-09-19, live roots): 10 packets + 19 report bodies
  (9 `.saipen/evidence` RAPORT/SAIPAL bodies, 2 `__SAIMAIL__/spec` proposals,
  8 future_gate bodies in the >= 2026-09-16 window).
- NEW_SINCE_E7055 (mtime > 11:01): 5 packets (canonical-line,
  diagnostic-verbs, guard-readonly-probe-gap, routeless-finish,
  saipen-guard-restart-race stub) + 4 bodies (RAPORT-CANONICAL-LINE-BOUNDS
  15:17, RAPORT-GUARD-PRODUCER-DIVERGENCE 14:02, RAPORT-ROUTELESS-FINISH
  15:14, PROPOSAL-TICKET-DESCRIPTION-MUTATION 22:17). The three 0918 packets
  bound by INDEX.md (saipenview-guard-restart 13:56, ingress-shell-operator
  14:20, ship-source-coverage-deadlock 20:30) are also post-E-7055 arrivals,
  already indexed there.

## Packet integrity

All 5 INDEX-bound packet digests and all 15 INDEX-bound body digests recomputed
2026-09-19: every one matches. No tampering, no moved body. The INDEX is STALE,
not corrupt: it predates the five new packets and four new bodies below.
`claimed/ resolved/ invalid/ evidence/` are empty. INDEX.md was refreshed with
the new rows by this ticket (see below); historical E-7055 rows untouched.

## Triage table

| INCIDENT_ID | SOURCE_PATH (root) | ORIG_SEV | CURRENT_REPRO | DISPOSITION | OWNER_TICKET | ROOT_CAUSE / EVIDENCE |
|---|---|---|---|---|---|---|
| SAI-DEFECT-20260918-ingress-shell-operator-as-request | inbox packet + RAPORT-SAIPEN-INGRESS-SHELL-OPERATOR | P1 | YES (end-to-end) | NEW_TICKET | T-1398 | ingress_payload() reads everything after the verb as request; "2>&1" minted T-1/SRC-001 user_explicit:true (PROBE §1-2) |
| SAI-DEFECT-20260918-ship-source-coverage-deadlock | inbox packet + RAPORT-SAIPEN-SHIP-SOURCE-DEADLOCK | P1 | YES (end-to-end) | NEW_TICKET | T-1399 | release_gate iterates every board link; unrelated blocked T-1/SRC-001 froze finished T-2 (PROBE §3) |
| SAI-DEFECT-20260917-saimail-receipt-quarantine-export | inbox packet + __SAIMAIL__ PROPOSAL-RECEIPT-QUARANTINE | P0 | PARTIAL/EXTERNAL | NEW_TICKET | T-1400 | 5 codec.redact_credentials patterns cannot see credential-in-filename; no distribution state; export ships every active body (report §1-7 re-confirmed at HEAD) |
| SAI-DEFECT-20260917-wintage-guard-filepath (GUARD-20260917 A/B) | inbox packet + RAPORT-SAIPEN-GUARD-20260917 | P1 | NO | ALREADY_FIXED | T-1376/T-1377/T-1378/T-1380 + T-1367 field proof | _windows_path_tokens admits backslash --file; hex route canonical; T-1367 six homes CURRENT, repeated_refusal empty after T-1397 (PROBE §4) |
| SAI-DEFECT-20260918-saipenview-guard-restart | inbox packet + RAPORT-SAIPEN-GUARD-RESTART + producer-divergence body | P1 | NO (today) | ALREADY_FIXED (instance) | T-1389 (+T-1367) | all three guard copies byte-identical 8f3d9004, legacy copy absent (PROBE §5); PLUGIN_RESTART_REQUIRED stays fail-closed BY DESIGN and names "restart OpenCode"; dual-producer single-writer question preserved as architecture note, no current RED |
| SAI-DEFECT-20260918-canonical-line-token-and-quote-bound | inbox packet + RAPORT-SAIPEN-CANONICAL-LINE-BOUNDS | P2 | YES | NEW_TICKET | T-1401 (token bound); quote sub-claim -> T-1386 | 13-token documented grammar -> None (PROBE §4); quoted non-ingress args -> None, same quoted-canonical-arg root as open T-1386 |
| SAI-DEFECT-20260918-diagnostic-verbs-refused-idle | inbox packet + RAPORT-SAIPEN-CANONICAL-LINE-BOUNDS | P2 | YES | DUPLICATE_ROOT (same fallthrough owner as T-1401) | T-1401 | permissions/explain-next DIAGNOSTIC yet not_shell_canonical; measured False vs status True |
| SAI-DEFECT-20260918-guard-readonly-probe-gap | inbox packet + RAPORT-SAIPEN-GUARD-PRODUCER-DIVERGENCE | P2 | YES | NEW_TICKET | T-1402 | _READ_ONLY_SHELL_VERBS closed set: whoami/hostname/get-location/get-date absent (PROBE §4); independent of producer divergence |
| SAI-DEFECT-20260918-routeless-finish-source-gate | inbox packet + RAPORT-SAIPEN-ROUTELESS-FINISH | P2 | PARTIAL | NEW_TICKET (residual) | T-1403 | T-1379/T-1377 closed request-clause shape with route; router finish branch consults no closure gate; generic SOURCE_UNRESOLVED finish refusal still route-less (operations.py:3003) |
| SAI-DEFECT-20260918-saipen-guard-restart-race | inbox stub | - | NO (self-superseded) | INVALID (moved to invalid/) | - (see SAI-DEFECT-20260918-saipenview-guard-restart) | stub's own header: duplicate of saipenview-guard-restart; evidence preserved in producer-divergence body |
| RAPORT-WINTAGE-R015-20260917 | evidence (no packet) | - | NO (residue only) | EXISTING_TICKET (mapped evidence) | T-1315 | closed-tombstone re-affirmation refused NO_ACTIVE_WORK; product work complete; recovered-terminal-source attribution family |
| SAIPAL-deadlock-state-history-binding-20260916 | evidence (no packet) | - | NO | ALREADY_FIXED | T-1382 | operations.py:351 comment names this exact incident; allow_unbound_history escape + controls (180d76a6/5d79ae78/142ea2a9) |
| PROPOSAL-SAIPEN-TICKET-DESCRIPTION-MUTATION | __SAIMAIL__/spec (no packet) | - | YES (gap by construction) | FUTURE_GATE_ONLY | - (backlog) | no canonical ticket-description mutation verb; architecture capability, filed 22:17 after E-7055 |
| FUTURE GATE — REPAIR-VERB DEADLOCK (SAITULS) | future_gate | P1-claimed | covered at HEAD | ALREADY_FIXED | T-1382 | 142ea2a9 names _SAITULS duplicate ids; reachability + judge-on-changed controls |
| FUTURE GATE — RECONCILE DEADLOCK (FastPrompter) | future_gate | P1-claimed | covered at HEAD | ALREADY_FIXED | T-1382 | repair judged on what it changed + reconcile SRC-043 scoped carve-out (reconcile.py:1455-1475) |
| FUTURE GATE — TICKET ADD PREPENDS | future_gate | - | design | FUTURE_GATE_ONLY | - | ordering is a product decision |
| FUTURE GATE — CONTINUE CONVERGE INTENT | future_gate | - | design | FUTURE_GATE_ONLY | - | intent semantics decision |
| FUTURE GATE — GREENFIELD BIRTH | future_gate | - | YES (gap by construction; `saipen init` -> NOT_SAIPEN_PROJECT measured) | FUTURE_GATE_ONLY | - | preserved gate, product decision |
| FUTURE GATE — AUDIT CONTRACT optional ROOTS | future_gate | - | design | FUTURE_GATE_ONLY | - (adjacent T-1374) | audit-export contract design |
| FUTURE GATE — AUDIT CONTRACT OMITS evidence/** | future_gate | - | design | FUTURE_GATE_ONLY | - (adjacent T-1374) | audit-export contract design |
| FUTURE GATE — CLAIM-PATH OVERSIZE + IDLE CONVERGE | future_gate | - | compaction now exists | FUTURE_GATE_ONLY | - | board compaction field-proven by T-1394's own externalized record |

## Summary counts

- refreshed census: 29 bound files / 19 distinct incident bodies
- already-fixed: 6 (GUARD-20260917 A/B, SAIPAL deadlock, 2 recovery future
  gates, guard-restart divergence instance)
- existing-ticket mappings: 4 (T-1315, T-1382, T-1386 quote sub-claim, T-1363
  family context for T-1402)
- duplicate groups: 1 (diagnostic-verbs + canonical-line-token-bound share the
  canonical-grammar fallthrough owner -> T-1401; restart-race stub ->
  saipenview-guard-restart)
- invalid: 1 (restart-race stub, self-superseded, moved to invalid/)
- new tickets: 6 — T-1398 P1 ingress, T-1399 P1 release deadlock, T-1400 P1
  receipt distribution state, T-1401 P2 grammar bound + verb table, T-1402 P2
  read-only classification policy, T-1403 P2 routeless finish residual
- future-gate-only / backlog preserved: 7
- current unique reproducible roots: 5 (T-1398..T-1402 measured RED; T-1403
  measured PARTIAL with code-level evidence)

## Dedupe record (root-cause standard)

- canonical-line + diagnostic-verbs: shared failing invariant "a recognized
  canonical `saipen` grammar falls to action=shell and an unrelated idle
  refusal"; shared owner `_saipen_cli_tokens`/`is_shell_canonical_verb`
  fallthrough; one classification-consistency repair covers both.
- quote sub-claim NOT folded into T-1401: open T-1386 already owns
  quoted-canonical-argument admission for non-ingress verbs (checkpoint shape
  measured there; `source disp --evidence "..."` is the same root).
- ship-deadlock (T-1399) and routeless-finish (T-1403) NOT merged: shared
  lower layer (source coverage readiness) suspected but not proven; different
  consumers (release_gate repo scope vs router/gate agreement); per handoff
  they stay separate until a single closure-readiness owner is designed.
- guard-restart vs readonly-probe-gap: independent (freshness/provenance vs
  classification set), confirmed by different probe families.

## §24 repair selection

Two current P1 roots: T-1398 (ingress authority mint) and T-1399 (release
deadlock). T-1398 qualifies under every §24 criterion (authority/provenance
breach, unambiguous owner, bounded scope, no operator semantic decision, no
foreign live owner, measured current RED end-to-end). T-1399 fails "no operator
semantic decision" — its truthful resolution paths (operation-scoped release
truth, liveness for unrelated parked work) are design choices. Repair executed
under T-1398 only.
