# Blocker inventory (engine projection, measured 17.11.2026)

Source: `saipen status --json` -> `blocker_projection`, aggregated by class over root AND
dependent tickets. Source head `dc39709c0c17a3272126c01a626ffcaa4176140b`, tree
`git-delta-v1:0f69fe84ecb98bfc84e2c33be0bb35ef7310de8bbd75c223f7d6b77232be14d2`
(re-measured this session), conformance `CURRENT_FAIL` (2 installed pre-fix gaps).

Rows on BOARD: DOING 0, TODO 0, DONE 137, BLOCKED 144. Groups: 117; every group
reports `external_input_required: true`, so no canonical ticket mutation is agent-authorized.

| class | rows | root/dependent tickets | required operator act |
|---|---|---|---|
| WAIT_USER_DECISION | 38 | T-1375, T-1431, T-1449, T-1607, T-1644, T-1675, T-1756, T-1763, T-1766, T-1767, T-1768, T-1780, T-1788, T-1816, T-1817, T-1880, T-2034, T-2035, T-2036, T-2037, T-2038, T-2039, T-2041, T-2... | sealed native operator carrier (host ingress) carrying the per-row decision; for the T-2058 class authorize Gate A EX-000053 (8.1.1 install + publication staging) |
| ACTIVE_DEPENDENCY | 1 | T-2062 | operator decision on the root rows |
| extern | 1 | T-2054 | operator decision on the root rows |
| BLOCKED_AUTHORITY_GATE | 1 | T-2033 | operator decision on the root rows |
| BLOCKED_EXTERNAL | 36 | T-1317, T-1507, T-1558, T-1562, T-1563, T-1602, T-1647, T-1651, T-1663, T-1664, T-1671, T-1672, T-1677, T-1729, T-1738, T-1740, T-1754, T-1762, T-1764, T-1765, T-1769, T-1770, T-1783, T-1... | registered external proof: lineage-<32hex> + <T-###>@<commit> + executed PASS (resolve-external); the external project must commit first |
| requires | 1 | T-2028 | operator decision on the root rows |
| inherited_verified | 1 | T-2024 | operator decision on the root rows |
| closure | 1 | T-2026 | operator decision on the root rows |
| duplicate | 1 | T-2018 | operator decision on the root rows |
| HOST_CAPABILITY_MISSING | 3 | T-2010, T-2011, T-2012 | host-side capability install (successor-turn scheduler transport) |
| accidental | 2 | T-2002, T-2008 | operator decision on the root rows |
| SEQUENCED_AFTER | 3 | T-1509, T-1728, T-2005 | operator decision on the root rows |
| PUBLICATION_BLOCKED_EXTERNAL | 1 | T-1970 | operator publication decision |
| HOST_EXECUTION_UNAVAILABLE | 3 | T-1548, T-1551, T-1863 | host-side execution surface restore |
| blocked | 1 | T-1857 | operator decision on the root rows |
| recorded | 1 | T-1838 | operator decision on the root rows |
| SRC | 1 | T-1822 | operator decision on the root rows |
| DUPLICATE_CONTINUATION | 4 | T-1704, T-1706, T-1727, T-1773 | operator decision on the root rows |
| HELD | 6 | T-1257, T-1719, T-1720, T-442, T-473, T-575 | operator release of the hold |
| DEFERRED_BY_OPERATOR | 1 | T-1724 | operator re-activation of the deferred Work |
| PRIORITY_STEERING | 2 | T-1722, T-1723 | operator priority steering |
| AMENDMENT_ONLY | 1 | T-1710 | operator decision on the root rows |
| ROADMAP_INCOMPLETE | 1 | T-1702 | operator decision on the root rows |
| OUT_OF_SCOPE | 1 | T-1621 | operator decision on the root rows |
| WAIT_USER_CONFIRMATION | 2 | T-1652, T-1655 | sealed native operator carrier with the confirmation |
| CONTEXT_MISSING | 2 | T-1610, T-1611 | operator decision on the root rows |
| QUEUE_NOT_TERMINAL | 1 | T-1450 | operator decision on the root rows |
| MARKHUNT_TRIAGE_REQUIRED | 8 | T-1307, T-1308, T-1309, T-1310, T-1311, T-1312, T-1313, T-1314 | operator triage of the marked-hunt rows |
| SUPERSEDED | 2 | T-1564, T-1566 | operator decision on the root rows |
| INVALID | 4 | T-1155, T-1172, T-1195, T-1321 | operator decision on the root rows |
| STALE | 6 | T-1327, T-1425, T-1426, T-1428, T-1429, T-1446 | operator decision on the root rows |
| ORACLE_CHANGED | 1 | T-1541 | operator decision on the root rows |
| CONTRACT_CONFLICT | 1 | T-1532 | operator decision on the root rows |
| SUPERSEDED_PENDING | 1 | T-1493 | operator decision on the root rows |
| PAUSED | 1 | T-1323 | operator resume |
| PERMANENT_WARNING_OWNER | 3 | T-1119, T-406, T-407 | operator decision (permanent-warning owner) |

Total projected rows: 144 (matches the 144 BLOCKED rows; dependents are attributed
to their group's class).

## The four acts that lift the whole set

1. **Gate A EX-000053** - authorize the 8.1.1 generation install and publication staging;
   lifts T-2058, T-1449, T-2062 (and the three review rows' inherited_verified route).
2. **Sealed native operator carrier** - one authenticated host ingress per decision row
   (WAIT_USER_DECISION / WAIT_USER_CONFIRMATION); no chat text or agent text can substitute.
3. **External proof** - for each BLOCKED_EXTERNAL row, a registered external implementation
   (`lineage-<32hex>`, `<T-###>@<commit>`) plus an executed PASS; the external project must ship first.
4. **Steering** - release HELD/PAUSED rows, decide MARKHUNT triage, and settle the T-1816/T-1817
   foreign staged-batch ownership or authorize an isolated release.

Nothing on this board is closable by an agent verb today: `claim`/`transition`/`done`/`checkpoint`
need a workable row, `unblock` needs operator authority, `supersede`/`bind-cohort` need a DONE
successor, and `resolve-external` refuses operator-gated rows (`OPERATOR_DECISION_REQUIRED`).


## Addendum: 11 rows are orphaned by the 12.11 retirement batch

Measured this session from BOARD `source_receipts` plus the tombstones: these blocked
tickets name only receipts that were retired `INVALID` / `ORPHANED_RECEIPT` on
2026-11-12, so `work_closure_gate` refuses each with `SOURCE_RECEIPT_MISSING` and no
agent verb can revive them (`source retire` is terminal; measured previously on both
engine generations):

| ticket | retired receipt | retirement event |
|---|---|---|
| T-2016 | SRC-386 | E-19341 |
| T-2018 | SRC-388 | E-19342 |
| T-2022 | SRC-392 | E-19343 |
| T-2024 | SRC-394 | E-19344 |
| T-2026 | SRC-395 | E-19345 |
| T-2028 | SRC-397 | E-19346 |
| T-2029 | SRC-398 | E-19347 |
| T-2033 | SRC-399 | E-19348 |
| T-2041 | SRC-402 | E-19350 |
| T-2043 | SRC-403 | E-19351 |
| T-2044 | SRC-404 | E-19352 |

Consequence: the blocker prose on these rows predates the retirement (it still cites
open clauses or external halves), but the binding is gone, so the visible reason is
stale. One operator act reopens the class: reissue the receipts with a genuine
operator carrier (the retired witnesses were `model_supplied`) and re-link the Work,
or accept the carried obligations. Until then each row is fail-closed and no
`resolve-external`, `inherited_verified` or `own_patch` closure can be truthful.

## Addendum 2: T-2005/T-2006 rest on model-supplied sources

Measured this session: SRC-379 (`external_audit`) and SRC-380 (`user_instruction`)
both carry `request_provenance.witness: model_supplied`; SRC-380's kind claims a
user instruction but no carrier backs it (the T-1844/P0-07 pattern). For both
tickets `work_closure_gate` returns `SOURCE_UNRESOLVED` with 0 registered
requirements, so no requirement can be registered or dispositioned by an agent
without fabricating the operator's authority. The BOARD prose ("the operator's
newest attached spec") is not supported by the source receipt itself. Operator
act: attach/authorize the spec through native ingress (or reissue SRC-379/380 with
a carrier); only then do T-2005/T-2006 have a closable contract.

## Addendum 3: T-2002 closed by canonical retirement; T-2008 has no receipt to retire

Measured this session. T-2002's blocker ("accidental CLI token parse; no work owed")
carries none of the unblock-gated tokens, so `saipen ticket unblock T-2002
"accepted as an accidental probe; no work owed"` succeeded (E-21639) and the row
became TODO. That is not closure: the row is non-Work. The engine's own canonical
verdict for it is retirement, so the row was re-blocked with the classification
payload `INVALID_INVOCATION -- accidental CLI token parse; no work owed` (E-21640,
op ticket-c4f0c7b8) and then retired:

- `saipen ticket retire T-2002 --reason INVALID_INVOCATION --evidence E-21640`
  -> ok, event E-21641, record `.saipen/archive/retired/T-2002.json`,
  `authority_grant: system:INVALID_INVOCATION` (no operator authority minted).
- Precondition `system_correction_error` passed on facts read from disk: SRC-376
  integrity OK, linked exclusively to T-2002, `witness: model_supplied`, contract
  and coverage both empty; SRC-376 was retired INVALID by the same event.
- Board after: DOING 0, TODO 0, DONE 137, BLOCKED 143.

T-2008 cannot follow the same route. Its row has no `source_receipts` field at all,
and `system_correction_error(root, T-2008, ...)` returns "system correction requires
an integrity-checked source receipt" before any classification is considered. No
agent act can close it: unblock would only re-open a non-Work row, `ticket done`
would be an accept-empty lifecyle, `ticket supersede` needs a DONE successor
(T-2009 does not exist on the BOARD, and creating one to retire this row would be
ticket manufacture). Operator act, if the row is to leave BLOCKED at all: attach a
receipt for the admission probe through native ingress (or decide the protocol
should accept receipt-less INVALID_INVOCATION retirement); until then T-2008 is a
permanent fail-closed non-Work tombstone row by design.

## Addendum 4: T-1970's source bundle was lost from the tree, and two clauses regressed

Measured while trying T-1970 this session, then repaired under the ticket itself
(unblock E-21642, claim E-21643, re-block E-21644):

- The working tree held `.saipen/intake/contracts/SRC-351.json` and its coverage
  as untracked seeded-empty residue (0 clauses / 0 requirements, dated 13.11
  06:57, no LOG event). T-1970's own blocker prose and E-19598/E-20974 record the
  real bundle: 13 clauses plus immutable revisions r001..r013. The residue was
  preserved under `.saipen/evidence/T-1970-audit/working-tree-residue/` and the
  bundle restored with `git restore --source=06fa9f073 --worktree`; all 15 files
  hash-match that commit (contract 075daab8..., coverage 3cbf15eb...).
  `work_closure_gate` went from 0 to 13 requirements.

- The restored set claimed R001/R002 VERIFIED against a tree that implemented the
  typed foreign-protocol refusal. Current HEAD and the running 8.1.0 engine do not
  implement it: live `saipen saipal continue` answers VALIDATION_FAILED "unknown
  command: saipal", and `exact_namespace` / FOREIGN_PROTOCOL_COMMAND exist only in
  the unpublished commit 6ad3ad6a9 (not an ancestor of HEAD), stash trees
  1dd70f6cd/06fa9f073, and T-2040 registry snapshots. R001/R002 were re-recorded
  BLOCKED on `.saipen/evidence/T-1970-audit/CLAUSE-REGRESSION-MEASUREMENT.md`.

- Current SRC-351 coverage: 13 requirements, 5 terminal (R003, R004, R005, R012,
  R013 re-checked against current bytes), 8 BLOCKED: R001/R002 (SAIPEN-side, needs
  re-landing or reimplementation of the unpublished feature) and R006-R011 (six
  externally owned: FreeBuff host R006-R010, SAIPAL R011; handoffs written and
  unsent). Ship gate still 51 PASS / 6 FAIL, none in T-1970's scope.

Operator acts: decide whether to re-land the unpublished exact-namespace feature
(or authorize its reimplementation), route the two handoffs to their receiving
owners, and resolve the shared publication gate (the same six FAILs as
T-1966..T-1969). No agent act makes all 13 clauses terminal.

## Addendum 5: T-1859 is operator-witness gated; its environment half is repaired

Measured 2026-11-17 while trying T-1859 (the authenticated-ingress incident):

- `saipen host doctor` reported the live authority service down
  (`running: false`, `generation_current: null`, expected `svc-29bc598bc7951d8ee87c0db0`)
  with 8 installed hosts stale, including the deployed `zcode-production` adapter.
  That is the incident's own failure mode: a dead authority service records genuine
  operator prompts as `model_supplied`.
- `saipen host repair` restored it canonically: `HOST_REPAIRED`, authority running
  (pid 34688, instance broker-420d203c539e843260112b10, generation current),
  `zcode-production` no longer in `needs_action`. Only the second Claude profile
  (`C:\Users\vac34\.claude-account2`, `STALE_RUNTIME`) remains; it is not the
  T-1859 surface. Evidence: `.saipen/evidence/T-1859-ingress/HOST-REPAIR-20261117.md`.
- The ticket still cannot close. `saipen acceptance T-1859 --dry-run` reports AC-01
  `UNVERIFIED` (LIVE), with AC-02/03/04 satisfied. AC-01 needs two operator facts:
  (a) an operator-signed `acceptance_witness` Source (contract
  `002caf94...35cab`, build boundary 19475, surface the operator's own; the gate
  refuses model-written files by construction), and (b) a genuine operator `cc`
  through the deployed ZAICODE UI INTO AUDAPACK while that project is in goal mode
  with a spent bounded grant. Measured read-only today,
  `_PY\_AUDAPACK\.saipen\STATE.md` still has `execution_intent: converge` and no
  `goal_waves`/`goal_tickets`/`authority_source`, so the renewal conjunct has no
  object.
- Same operator act also owns T-2014 (ACTIVE_DEPENDENCY:T-1859, SRC-384:R003) and
  unblocks T-1863's R004/R006 (a real GUI cc through this AC-01). No agent may
  create AUDAPACK's goal authorization or submit the cc; both would manufacture the
  witness the acceptance gate authenticates.


## Addendum 6: conformance CURRENT_FAIL is the 8.1.1 install gate; T-2016 is a retired-receipt deadlock

Measured 2026-11-17 while trying T-1859 again:

- `saipen validate --json` (installed 8.1.0, receipt `receipt-4b00e19d6bc4`,
  gate core, exit 1) reports exactly 2 blocking findings:
  1. `STATE.md audit route not followed` -- the inbox routes `saipen audit ingest`
     for `audit/SAIHANDOFF_BZ_REA_AGENT_DRIFT_RECOVERY.md` (SRC-386, work T-2016)
     while `next_action` is `saipen crew`;
  2. `FUTURE GATE: FG-0046 names slice ticket T-1936, which is not on BOARD`.
- Both are already fixed in the worktree candidate and absent from the install:
  `tools/saipen_engine/board_scrub.py` has `gated_tickets` (T-2071, 1 occurrence)
  while the installed copy has 0; `tools/saipen_engine/audit_route.py` carries the
  T-2070 ingest guard while the installed copy still guards only `PHASE` actions;
  `saipen source recover --confirm` -> `restore_board_rows` (T-2050/T-2071) exists
  only in the worktree `tools/saipen.py`/`operations.py`. The same diagnosis is in
  LOG E-21439 (17.11 03:36) with the worktree validator reporting neither finding.
- New this cycle: why the routed ingest cannot be followed even honestly.
  `SRC-386` was retired `ORPHANED_RECEIPT` at 2026-11-12T13:28:07Z (E-19341;
  tombstone intact, archived coverage empty). `saipen source reconcile SRC-386`
  reports `terminal: true, recoverable: false, contradictions: []`. But
  `saipen audit ingest --dry-run` refuses `SOURCE_UNRESOLVED: linked Work T-2016 is
  not DONE` (`audit_inbox.delete_gate`), and T-2016 can never be DONE: its verify
  demands every SRC-386 clause terminal, source closure and layer consumption, no
  verb dispositions clauses of a retired receipt, and R004 is not actually an
  external await. T-2016's blocker was therefore refreshed with the retirement facts
  (E-21649 unblock decision, E-21650 re-block).

Operator acts (no agent act exists):
- authorize the 8.1.1 generation install through `saipen-inject` (EX-000053, gate A
  of the T-2058 packet) -- that alone lifts both conformance findings and restores
  `saipen continue` routing;
- decide T-2016: restore the SRC-386 bundle under authority, re-scope the ticket to
  a new source, or accept the carried obligation.


## Addendum 7: the engine itself refuses T-2016 closure

Measured 2026-11-17 16:58 while the verifier pressed for closure:

- `saipen ticket done T-2016 --dry-run --json` -> `SOURCE_RECEIPT_MISSING`
  (`source_status: None`, coverage `{requirements: 0, actionable: 0, terminal: 0}`),
  and its own `canonical_next_command` is
  `saipen ticket block T-2016 "source closure not ready (SOURCE_RECEIPT_MISSING)"`.
- `saipen work contracts T-2016` -> 0 rows; `saipen acceptance T-2016 --dry-run`
  -> 0 criteria. `saipen checkpoint DEC T-2016` is refused with
  `STALE_WORK_CONTEXT` because the project has no active task; there is no
  ticket-bearing DEC surface for a blocked row.
- Conclusion: the BLOCKED state written at E-21650 is the only legal disposition
  the CLI offers. Closing would require minting a new source authority for a
  retired receipt, which the operator reserves; no patch or file can substitute.
