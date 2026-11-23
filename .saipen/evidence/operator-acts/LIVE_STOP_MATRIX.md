# LIVE STOP MATRIX — SAIPEN × ZAICODE

Ticket: T-2107 (SRC-430, CONFORMANCE DEADLOCK REPAIR · NIGHT SHIFT 12)
Measured: 2026-11-19 during BUILD, against the live authoritative receipts
(SAIPEN `receipt-c03db428a1b2`, generated 04:41:19Z; ZAICODE
`receipt-35f98a64a00f`, generated 2026-11-18T18:07:40Z). Method: read-only
status/runtime/receipt inspection; no `saipen validate` was used to build this
matrix; no canonical state was hand-edited; no runtime install or publication
was performed.

Archival vs live: SAIPEN also carries `receipt-3c6251a5a67c` (03:36Z, 57
findings, repo engine). It is historical evidence and is **not** the live
authority; the live status reads `receipt-c03db428a1b2`. The change from 57 to 5
findings is itself proof that a receipt is a generation-bound snapshot, not a
standing truth.

This file is evidence under an existing evidence directory. It is not a new
global source of truth and it does not grant authority.

## 1. Per-project live stop matrix

| Field | SAIPEN | ZAICODE |
|---|---|---|
| Project root | `V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN` | `V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_ZAICODE` |
| Git HEAD | `dc39709c0c17a3272126c01a626ffcaa4176140b` | `2380d51e3968d605c620efdfa025d0f5101de465` |
| Dirty state | 4494 porcelain entries, of which 3778 are untracked at BUILD measurement; only 2 untracked files are validator-visible in the live receipt. VERIFY re-measure: 4499/3782 — the +5 are this ticket’s own evidence and tmp files. | 10927 porcelain entries |
| STATE | `phase: BUILD`, `task: T-2107`, `last_event: 21940` (after SCOUT checkpoint; it was 21938 before) | `phase: DONE`, `task: none`, `last_event: 9173` |
| BOARD | T-2107 claimed, `verify: the requested change is present and demonstrated against the user own description of it`; 14 blocked, 1 doing | no claimed ticket; 18 blocked, 227 done |
| LOG | tail `E-21940` (BUILD transition); `E-21939` SCOUT checkpoint | tail `E-9173` |
| Canonical HOME | `C:/Users/vac34/AppData/Local/saipen/scheduled-source` | same |
| Actual PATH launcher | `/c/Users/vac34/bin/saipen` → `C:\Users\vac34\AppData\Local\Programs\Python\Python311\python.exe` → `C:\Users\vac34\AppData\Local\saipen\scheduled-source\tools\saipen.py` | same launcher and same engine |
| Physical engine | `...\scheduled-source\tools\saipen.py` | same |
| Engine version | installed `8.1.0`; repo `8.1.1` | installed `8.1.0`; ZAICODE has no separate engine copy |
| Generation digest | ProgramData `sha256:528ad93c79d4ee9e504edd29e274b7ea299fccb1448b4da6c73955bcc1fa4b2c` (170 files); AppData `sha256:df039ef6c46770a910e03d2e713db0be350e7e22aabaee5a54f6e8712c9333d7` (170); repo `sha256:ff15edff257e07a5a68a4ae251b3ebdefefd22c9157c8ebe93238aa324c30cdb` (176) | running engine = AppData `df039ef6…`; the receipt’s EX-000004 detail names `sha256ad93c79d…` |
| Install fingerprint | ProgramData `install-v1:5e8fd0693c292d2d2b96015f3fed2cf33b959ca814cfae72a6aceef05278f081`; AppData `install-v1:a00090465b14c0426710ee2ecfa24a00af5499d3d19f064c86de8afb87f3f2fb`; repo `install-v1:de99cbb40f6092940d7a23216568355fa59b833f8c7d4e09fedbe7f3b5e1ca3b` | AppData `install-v1:a0009046…` |
| Conformance status | `CURRENT_FAIL`, live receipt `receipt-c03db428a1b2` (04:41:19Z), 5 problems: 1 `closure_provenance_drift` EX-000053, 1 unclassified FUTURE GATE FG-0046 → missing T-1936, 2 `runtime_manifest_untracked` (`tools/test_t10_submit_route.py`, `tools/test_t5_ratio_is_not_a_count.py`), 1 `coverage_gap` (`tools/regression_t2089/home_extensions/subs/PROTOCOL.md`). `install_home` AppData, `install_fingerprint a0009046…`, `content_hash a4cf2a017b1bda21`. The 57-finding receipt `3c6251a5a67c` is archival. | `CURRENT_FAIL`, receipt `receipt-35f98a64a00f`, 9 problems: 4 unclassified source-receipt references to missing Work (T-435/T-444/T-500), 1 `source_receipt_unresolved_work` (T-287), 2 unclassified safety-valve projection findings, 1 `closure_provenance_drift` EX-000004, 1 unclassified LOG commit on no remote. `content_hash 87b558c8bac67f3b`; the receipt names `goal_tickets=30` while STATE now carries 31. |
| Automation disposition (installed engine) | `CONTINUE`, `next_command: cc`, `reason_code: finish`, computed `PHASE BUILD T-2107`, `operator_action_due: false` | `CONTINUE`, `next_command: cc`, `reason_code: queued-source` (SRC-421), `operator_action_due: false` |
| Automation disposition (repo engine from repo root) | `BLOCKED`, `reason_code: reconcile-refused`, `next_command: null`; it reports the RUNNING install as the repo (`de99cbb4…`) while STATE names AppData (`a0009046…`). This is the designed evidence-attribution refusal, not a defect to disable. | not measured from the repo engine (it would report the same self-vs-canonical-home divergence) |
| Reconcile verdict | Home was converged by the supported route `saipen rebind-home --auto`: `HOST_BINDING_CONVERGED`, previous ProgramData → new AppData, `verdict: ACCEPTED`, `build_identity.identity_match: true`, `loaded_revision: UNPROVEN` (the scheduled-source tree is not a Git tree), schema/project/actor/no-pending PASS. | Installed engine accepts the project state; no reconcile refusal is present. The only open ingress is queued SRC-421. |
| Goal budget | `goal_authority: inactive` (“No persistent grant”) | `execution_intent: goal`; `goal_waves: 0`, `goal_tickets: 31`; caps in REGISTRY are waves 3 / tickets 20; `continuation_authority: operator_required`; `authority_source: E-8724`; `authority_until: budget`; `safety_valve_mode: hard_wait`; `goal_authority.state: bounded`, `checkpoint_due: true` |
| Operator authority | none required for T-2107; one decision is required for the 8.1.1 publication/install | E-8724 is bounded and requires operator; it is not a persistent grant. SRC-421 is `model_supplied`, so it cannot reauthorize the valve. |
| Next executable action | `PHASE BUILD T-2107` (this file and the decision packet) | Installed engine computes `saipen start --receipt SRC-421`; the honest boundary is `WAIT_AUTHORITY` until a new witnessed operator ingress reauthorizes or the queued source is admitted under a non-goal route. |
| Blocking authority | Conformance `CURRENT_FAIL` receipt `c03db428a1b2` + the release/publication gate. EX-000053 is generation-bound; the FUTURE GATE and coverage-gap findings are machine-actionable. The 56-file manifest class belongs to the archival `3c6251a5a67c` receipt, not the live one. | Safety valve (budget 31/20) + conformance `CURRENT_FAIL` receipt `35f98a64a00f`. The valve is the blocking authority for new goal work. |
| Independent permitted work | read-only inspection, diagnostics, code review, isolated/hermetic tests, performance measurement, release-candidate prep, safe conformance-repair analysis, this matrix and the decision packet, focused regression tests | read-only diagnostics, code review, isolated tests, independent non-goal tickets, safe analysis of the 9 findings and the SRC-421 design; no new goal tickets, no valve reset, no promotion of model_supplied ingress |

## 2. Generation chain — the actual root cause

Three generations are live at once:

1. **ProgramData 8.1.0** — `C:\ProgramData\SAI\SAIPEN\runtime\0012aaefb5fc1b95`,
   engine `sha256:528ad93c…`, install `install-v1:5e8fd069…`, 170 engine files.
2. **AppData 8.1.0** — `C:\Users\vac34\AppData\Local\saipen\scheduled-source`,
   engine `sha256:df039ef6…`, install `install-v1:a0009046…`, 170 files. This is
   the canonical HOME and the engine the PATH launcher executes. Its
   `tools/validate.py` carries T-2096 parity fixes; its other engine modules do
   not carry T-2056/T-2106.
3. **Repo 8.1.1** — `V:\...\_SAIPEN`, engine `sha256:ff15edff…`, install
   `install-v1:de99cbb4…`, 176 files. It carries T-2056 repair actions, T-2106
   host capability and valve alignment, and retry proof. It is **not installed**;
   the archival repo-hosted receipt `3c6251a5a67c` saw 56 manifest files
   untracked against the clone, while the live AppData-hosted receipt sees 2.

The live SAIPEN receipt `c03db428a1b2` (04:41:19Z, `install_home` AppData)
compares the EX-000053 recorded generation `sha256:d64ee12e…` with the running
generation `sha256:df039ef6…`; the archival repo-hosted receipt `3c6251a5a67c`
(03:36:03Z) compared it with `sha256ad93c79d…`. Neither named generation is on
disk (528ad93c / df039ef6 / ff15edff are the live ones). The ZAICODE receipt’s
EX-000004 detail names `sha256ad93c79d…` as the verification generation and
`sha256:df039ef6…` as the running engine. Therefore both provenance findings are
**generation-stale by construction**: the generation they name no longer exists
on disk, and a re-run of the validator against unchanged bytes cannot make them
resolve.

VERSION equality is not generation identity: ProgramData and AppData both say
8.1.0 and differ by engine digest; the repo says 8.1.1 and differs from both.
The install fingerprint and the engine digest are the usable identities.

## 3. Failure ownership split

### SAIPEN (5 live findings; the 57-finding `3c6251a5a67c` split is archival)

| Class | Count | Owner | Machine-actionable now? |
|---|---:|---|---|
| `closure_provenance_drift` EX-000053 | 1 | the closed external Work T-1653 (`external_implementation`); the receipt compares closure `d64ee12e…` with the running generation `df039ef6…` | **No, not truthfully** — re-resolve after the generation converges, or record the operator’s refusal. Creating a fresh ticket would duplicate the existing operator dependency. |
| unclassified FUTURE GATE FG-0046 → missing T-1936 | 1 | engine-ledger projection class, not yet mapped to a rule owner | **Partly** — inspect FG-0046 and either restore the named Work or correct the future-gate entry through the canonical path; do not mint a blind ticket. |
| `runtime_manifest_untracked` | 2 | import debt: `tools/test_t10_submit_route.py`, `tools/test_t5_ratio_is_not_a_count.py` exist only in this home | **No** — committing or dropping them is a publication decision and belongs to the T-2058 gate A route. |
| `coverage_gap` | 1 | coverage debt: `tools/regression_t2089/home_extensions/subs/PROTOCOL.md` | **Yes** — the artifact is machine-owned; extend the coverage manifest entry for the regression harness through the canonical path. |

The archival receipt’s 56 `runtime_manifest_untracked` findings belonged to the
pending 8.1.1 delivery as a single class; the live receipt shows only the 2
files that the current tracked/untracked split leaves visible. That difference
is a measurement of the same debt, not a repair.

The repo engine’s T-2056 projection offers
`saipen ticket add P1 "closure_provenance_drift EX-000053" --verify "…"` because
T-1653 is DONE_ONLY. The installed engine offers `action: null` at
`repair_status: ENGINEERING_REQUIRED`. Both are wrong for this specific finding:
a new ticket cannot install a generation and would duplicate the existing
operator dependency. This is recorded as a residual projection defect, not
executed.

### ZAICODE (9 findings)

| Class | Count | Owner | Machine-actionable now? |
|---|---:|---|---|
| source receipt references missing Work (SRC-327/328/329/353 → T-435/T-444/T-500) | 4 | intake/ledger hygiene in ZAICODE | **Yes** — inspect and repair the receipt-to-Work linkage with the existing source/ledger verbs; do not mint replacement tickets. |
| `source_receipt_unresolved_work` T-287 | 1 | ZAICODE Work ledger | **Yes** — resolve the receipt/Work link truthfully. |
| safety-valve projection (goal 31/20; `next_action` not `WAIT`) | 2 | engine/router projection; repo T-2106 owns the fix | **Yes in repo code** — already implemented and covered by 6/6 T-2106 tests; **not installed**, so the running engine still emits CONTINUE. |
| `closure_provenance_drift` EX-000004 | 1 | closed external lineage; generation-bound | **No, not truthfully** — the named generation `ad93c79d` is gone; re-resolve after install or record the refusal. |
| LOG hunt against a commit on no remote (17f91e02) | 1 | ZAICODE Git/LOG provenance | **Partly** — either make the commit durable (publish branch) or correct the LOG through the canonical path; not a new ticket. |

The 7 unclassified findings are not operator authority and are not “unknown
work” to be minted blindly. Four are ledger linkage, two are the valve
projection, one is LOG provenance.

## 4. Correct conformance scope

**Always strict (conformance may refuse):**
protected canonical mutations; generation-bound authority transitions;
publication; installation; release SHIP; crew convergence that requires
`CURRENT_PASS`; integrity-proof-dependent recovery.

**Independently eligible (conformance must not block):**
read-only inspection; diagnostics; code review; isolated testing; hermetic
regression development; performance measurement; release-candidate preparation;
independent authorized ticket work; safe conformance-repair analysis.

Measured leakage: the installed engine does **not** block the current BUILD
route (it says `CONTINUE` / `PHASE BUILD T-2107` even with `CURRENT_FAIL`), so
the scope is not uniformly too strict. The real defect is the opposite on the
installed generation: it under-reports the red on finish routes while the repo
generation over-reports it as a reconcile refusal when run from the repo. The
crew gate itself is narrow: it fires only for `action == "saipen crew"` and
`reason == "crew-converge"`; the idle gate fires only for `reason ==
"maintain"`. Neither owns the BUILD route. The fix is generation convergence,
not a new exemption.

## 5. Required CURRENT_FAIL route behavior (target contract)

For `CURRENT_FAIL`, the route must carry:

- exact failure class and finding keys;
- evidence fingerprint (`receipt_id` + `content_hash` + source head/tree);
- recheck condition (what must change before another validation is useful);
- repair owner (engine Work, publication, operator decision, external, or
  unknown);
- operator decision status (none / open / witnessed);
- next independently executable work;
- retry useful/useless with reason.

The installed engine currently emits `repair_status: ENGINEERING_REQUIRED`
with `action: null`; the repo engine emits the same status with a ticket-add
action. Neither names “re-run validate cannot change this” for the
generation-bound finding. The repo renderer does suppress the validate
recommendation when `retry_blocked` is true, but `retry_blocked` is only set for
the retry-proof statuses; a `CURRENT_FAIL` with immutable external bytes is not
covered. This matrix therefore records the recheck condition explicitly so no
consumer loops on the receipt.

## 6. ZAICODE goal authority

State is internally contradictory on the installed generation:

- `execution_intent: goal`, `goal_tickets: 31`, `goal_waves: 0`, caps 20/3,
  `continuation_authority: operator_required`, `safety_valve_mode: hard_wait`;
- `goal_authority.state: bounded`, `checkpoint_due: true`;
- yet `automation.disposition: CONTINUE`, `reason_code: queued-source`,
  `operator_action_due: false`, computed `saipen start --receipt SRC-421`.

The receipt already carries two findings naming this exact defect: `next_action`
is not the safety-valve `WAIT` form, and the resume key is not canonical. Repo
T-2106 fixes the projection and its 6 tests pass, including the 31-ticket drift
across reconcile/status/explain-next/start/cc. The installed generation lacks
that code. Until it is installed, the honest ZAICODE route is `WAIT_AUTHORITY`
for goal work, not `CONTINUE`.

No reauthorization is requested here. SRC-421 is queued and `model_supplied`;
it is not a witnessed operator carrier and cannot reset the valve. `goal_tickets`
is not zeroed, no synthetic continuation is created, and `model_supplied` is not
promoted.

## 7. Retry discipline

- Do **not** re-run `saipen validate` on `receipt-3c6251a5a67c` or
  `receipt-35f98a64a00f` while their inputs are unchanged. The evidence is a
  fixed point: same tree, same engine, same findings.
- Recheck only after one of: an authorized generation install/publication; a
  committed manifest file set; a witnessed operator decision; a repaired
  receipt/Work linkage; a published commit for the LOG hunt.
- The retry identity to carry forward is the receipt `content_hash` plus
  `source_head` + `source_tree_fingerprint`; do not invent a new cache. The
  existing `retry_blocked` / `retry_fingerprint` / `repair_status` fields remain
  the engine-owned carriers.

## 8. Release deadlock T-2058 (re-measured, not duplicated)

`T-2058` remains blocked on gate A: the pre-commit/ship gate refuses because
EX-000053’s closure is bound to an installed generation that has moved. Gate B
is `CREW_NOT_READY SC-7` because three closure-blocking tickets remain. The
measured facts above confirm the earlier
`.saipen/evidence/T-2058-release-index/BLOCKED.md` account: the blocker is the
generation install/publication decision, not a missing release ticket.
`publication_state: pending` is a normal state, not an error. No duplicate
release ticket is created here.

The cached operator decision `ing-4af01f8fbc59ef25` (OPTION A, 2026-11-17) is
**not authority**: it is `consumed: false`, expired, and names older
generations (`d64ee12e`, repo `51cc0aeb`). It cannot be used to install or
publish silently.

## 9. Host stop-code distinction

ZAICODE must not collapse every stop into one code. The matrix requires these
distinct classes, each with its own next action:

| Code | Meaning | Next action |
|---|---|---|
| `CONFORMANCE_UNHEALTHY` | CURRENT_FAIL with a live repair or a terminal engineering diagnosis | repair owner action, never a generic validate |
| `RECONCILE_REAUTH_REQUIRED` | generation-bound authority transition | witnessed operator decision |
| `SAFETY_VALVE_TRIPPED` | goal budget exhausted | `WAIT: safety valve …`; no auto-continue |
| `HOME_REQUIRED` | canonical home missing/divergent | supported rebind route |
| `WAIT_USER_DECISION` | one operator decision is open | exact human decision |
| `INSTALLATION_REQUIRED` | running engine lacks the required generation | one install decision |
| `SOURCE_IDENTITY_STALE` | receipt generation no longer reproducible | re-resolve or re-install; never inherit green |
| `TEMPORARY_TOOL_FAILURE` | transport/exec failure | retry the tool, not the authority |

## 10. Message queue boundary

- SRC-430 (this mission) was durably admitted while `saipen start` initially
  refused on home divergence; after the supported rebind it projected to T-2107.
  That is the queue working at a safe boundary.
- SRC-421 (ZAICODE, `APPEND_AFTER_CURRENT_TURN`) is durable and unprojected. It
  is `model_supplied`, so it is ingress data, not operator authority; it is not
  delivered mid-turn.
- The current operator question about context compaction arrived during the
  turn. It was handled as a separate read-only diagnostic; it did not mutate
  STATE/BOARD/LOG and did not reauthorize goal work.

## 11. ONE operator decision packet

**Decision:** authorize, or refuse, one canonical 8.1.1 generation publication
and install through the existing T-2058/saipen-inject route, with this exact
scope:

1. the import-debt files named by the live receipt
   (`tools/test_t10_submit_route.py`, `tools/test_t5_ratio_is_not_a_count.py`)
   are committed or their manifest entry is dropped, and the archival 56-file
   class is re-measured against the published generation rather than trusted —
   no other paths, no `git add -A`, no reset;
2. the installed generation becomes the repo 8.1.1 bytes (`VERSION 8.1.1`,
   engine `ff15edff…`), verified after install by the same engine digest;
3. EX-000053 and EX-000004 are re-resolved truthfully against the new installed
   generation, or recorded as refused — no fabricated PASS, no inherited green;
4. T-2058 publication proceeds only if the canonical gates pass; otherwise it
   stays `publication_state: pending`;
5. ZAICODE goal work stays at `WAIT_AUTHORITY`; this packet does not reauthorize
   the valve and does not promote SRC-421.

If the answer is no, the honest state is: CURRENT_FAIL remains, independent
work continues, and no validate loop is run.

## 12. Verification run

Commands executed in this BUILD (focused, independent):

```
python -B -m unittest -v tools.test_t2106_reauth_deadlock
python -B -m unittest -v tools.test_t2056_obstacle_actions \
  tools.test_t1817_finding_ownership tools.test_t1817_finding_route \
  tools.test_src085_conformance_disposition
```

Results: 6/6 T-2106 tests OK (8.790 s); 61/61 focused conformance/ownership
tests OK (36.519 s). These tests run the repo generation, not the installed one.
They prove the repo fix, not the installed runtime.

VERIFY and REVIEW cross-checked this file against the raw receipts
(16/16 and 10/10 assertions PASS) and re-measured all three generation
identities, which matched the table above exactly.

One measured proof of the generation split: a focused-unit record produced by
the repo engine (61/61 PASS, `record …050531Z`; citation refused `HOME_REQUIRED`) was
refused by the installed engine with `focused check has missing or incompatible
verification environment identity`, because the record names the repo verifier
bytes. The same command
run under the installed engine reproduced 61/61 PASS
(`record .saipen/evidence/focused-unit/3a821f81232fc6be-20261119T051047323863Z.json`,
`CHECKPOINTED`) and that citation admitted SHIP. Evidence identity is
generation-bound exactly like closures: the repo record cannot speak for the
installed generation, and vice versa.

Engine identity commands used the existing
`saipen_engine.install_identity.install_fingerprint` and
`saipen_engine.external._engine_identity_at` functions; no new identity source
was created.

## 13. Constraints honored

No `saipen validate` loop; no canonical STATE/BOARD/LOG hand edits; no safety
valve reset; no goal_tickets zeroing; no synthetic operator carrier; no silent
install; no copying repo bytes over scheduled-source; no `git add -A`; no
hidden publication; no duplicate release ticket; no fake CURRENT_PASS.
