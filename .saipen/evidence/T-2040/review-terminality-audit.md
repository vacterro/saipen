# Wave B: SubSaipen review terminality audit

Scope: active BUILD T-2040/SRC-400; SRC-401 campaign handoff. Read-only canonical inspection. No start/continue, completion, supersession, grant capture, Git mutation, desktop interaction. Findings describe recorded evidence, not reconstructed history. Inherited/concurrent edits preserved.

## Durable facts

Live T-2034–T-2039 remain BLOCKED; active seat remains T-2040. Latest saihunt/HUNT-017, saipython/PY-15, saitest/TEST-12 OUTBOX records say reviewed, critical=false, P3, payload=[]. Empty payload does not itself mean no finding. Their reports claim bounded negative findings/PASS; these are sensor reports, not independent Core proof.

Recorded HEAD for both generations: `66ef622a43ab59512735ac78ce10d1250e26f9df`.

Older tree: `git-delta-v1:a842b8116f88f7c8d7ca04aa1f8ab6ed268d0d7370c738539f4a96ed3ab0e075`.
Latest recorded tree: `git-delta-v1:ad029851d6daceeff2ec767c44677a1c3a1e66fc4c125cd809e52e8cb749c485`.
Neither is asserted to equal the current dirty worktree.

| Ticket | Producer/package | Generation | Immutable identity | Durable collect | Terminal/status events |
|---|---|---|---|---|---|
| T-2034 | saihunt/HUNT-017 | older | sha256:152a2573793798d18c437ae3dd285e5a0a87539edb6be95c10b1fcbc686aada4 | E-20702/sub-collect-72689c64 | BLOCKED E-20719; successor claim T-2037 |
| T-2035 | saitest/TEST-12 | older | sha256:fe2e219af33d50968e9fb6ede219fd0a49ac3ffb1f7c19797a58ad026976adb4 | E-20703/sub-collect-b1a6563d | BLOCKED E-20720; successor claim T-2039 |
| T-2036 | saipython/PY-15 | older | sha256:e58660396b1a656a05ae9a5dc677777e724274119c423c4fbb41be8b4e7dddd7 | E-20704/sub-collect-d0a6ff6a | BLOCKED E-20721; successor claim T-2038 |
| T-2037 | saihunt/HUNT-017 | latest | sha256:4906773024d4b5ba37019c841f9d64515644f02d794851047fc4310ea380a75e | E-20709/sub-collect-64e829c3 | BLOCKED E-20722; disposition E-20725/sub-disposition-2c86739d |
| T-2038 | saipython/PY-15 | latest | sha256:240ab835a13e0b70d82487759fe8a780bf450e74344d5a7e1eb5de748326fcbc | E-20710/sub-collect-64e829c3 | BLOCKED E-20723; disposition E-20726/sub-disposition-3da2cee1 |
| T-2039 | saitest/TEST-12 | latest | sha256:a28ec28020e02fab71a67de7660e8d2623b39c43df42c934b1b4364d6477d940 | E-20711/sub-collect-64e829c3 | BLOCKED E-20724; disposition E-20727/sub-disposition-8ace3ad5 |

Role revisions: saihunt `sha256:4edb04181cb07e0946afd06fbe711166fa9dcc403e56b52e9be3844f0a71b0a5`; saipython `sha256:3069120b1a83291867c000dd5d7edb141d5fedf7895e5dc8f07d06624d05d9ff`; saitest `sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08`.

Physical receipts: `.saipen/recovery/settled/<operation>/operation.json`, COMMITTED, applied targets, lineage `lineage-b512942bac884a8691f6c98afcd6ddb9`. Latest combined collect positionally binds saihunt/saipython/saitest to T-2037/2038/2039. Historical collect metadata has no hypotheses array; do not project current fields backward. Compaction originals for T-2037/2038/2039 preserve package/source/role and independent-review verify contracts; no hidden result.

**Independent Core review: UNPROVEN.** Searched active/sealed ticket LOG chains and ticket evidence/compaction/receipts. Collection followed by blocking; no qualifying ticket-local independently executed review/disproof found. E-20712–20718 generic convergence PASS/CLEAN is not bound to these package/ticket identities. E-20722–20724 say no defects/awaiting operator archive confirmation; ticket_move and sub_disposition receipts establish lifecycle/status recording only. Absence of sufficient durable proof does not prove no review ever occurred elsewhere.

## Exact defects and smallest patch boundary

Line references are pre-patch observations under `tools/saipen_engine/`; concurrent edits may shift them.

- `subs.py:4138–4204 _collect_review_state`: `disposed = bool(ticket and terminal.get(ticket) is True)` promotes lifecycle terminality to review proof.
- `subs.py:4700–4943 sub_disposition`: selection correctly permits collected source aging; guard at 4825–4834 only requires DONE/BLOCKED. Metadata lacks explicit role revision and review evidence binding.
- `subs.py:4076–4099 _collect_linkage`: positional arrays lack equal-length/unique/conflicting-link checks. `_durable_collect_witness:3986–4040` also permits hypothesis/BOARD fallbacks; neither may qualify independent review or silently substitute a changed digest.
- `journal.py:4005–4119 verify_sub_collect`: any COMMITTED disposition identity legitimizes reviewed status, without qualifying its Core proof.
- `journal.py:4122–4152 verify_sub_disposition`: accepts *any* reviewed package in a target OUTBOX, not the exact metadata-bound package/ticket/role/collect/review tuple.

Minimum authorized implementation: one shared exact-package, durable-collect, ticket-local independent-review predicate in subs; consume it in health/disposition and journal postconditions. BLOCKED/DONE remains lifecycle state, not review proof. Preserve genuine reviewed BLOCKED decisions, pruned/reopened lifecycle semantics, finding_invalidated, corruption refusal, source-aging disposal. No canonical evidence repair.

Other report-only risks: producer.py identity implementation is source-generation-bound despite stale comments near publish (~1373). crew.py `_producer_integration_edge` SETTLED branch (~1995) assumes identity-preserving source rebind without checking receipt input source against package base source. Integration is never hypothesis review proof.

## Closure and authority

No generic review-only closure mode. Existing `finding_invalidated` is correct ONLY for an actually disproven ticket premise with same-ticket typed E evidence (`operations.invalidation_error:9096–9206`), normal active/VERIFY/REVIEW/SHIP gates. A clean surveillance result is not automatically premise disproof. own_patch would invent delta; inherited_verified/cohort require real implementation/publication attribution.

None of the six is currently eligible for ordinary ticket done: BLOCKED, another active ticket, missing qualifying same-ticket disproof/phase chain. Latest three are future independent no-change review candidates, not proved completed. Older three are distinct generations, not label duplicates. superseded_verified requires DONE successor, targeted PASS, later completion, exact authenticated OLD–NEW grant; none established here.

SRC-400/SRC-401/SRC-075 are model_supplied. SRC-075's T-1412–T-1417 capsule is unrelated and is not native authority. No exact native supersession grants for the three older/latest pairs found. Local audit/implementation permission is not protected authority. Preserve T-2028/T-2033 protected-authority blocks; never promote model_supplied or fabricate publication/grants.

## Safe previews and recording boundary

Executed read-only: `saipen sub dispose saihunt HUNT-017 --dry-run --json`; `saipen sub dispose saipython PY-15 --dry-run --json`; `saipen sub dispose saitest TEST-12 --dry-run --json`. All refused PACKAGE_INCOMPLETE with changed_files=[] because latest entries are already reviewed. `saipen crew --dry-run --json`: CREW_PLAN, crew_complete=false, action_required=true; initial action not captured by selected output keys. Environment: GIT_OPTIONAL_LOCKS=0, PYTHONDONTWRITEBYTECODE=1.

Closure grammar, NOT executed: `saipen ticket done T-### --closure-mode finding_invalidated --invalidated-by E-### --dry-run --json`; `saipen ticket supersede T-OLD --by T-NEW --evidence E-### --authority SRC-### --dry-run --json`. Do not use placeholders as real authority.

Static dry-run concern routed to Wave C: `_plan_finish_ticket` (~7920–7966) calls intake.discharge_request_clauses (~3438–3490), which invokes ensure_request_clause/set_disposition while planning. Linked-Source finish dry-run byte-purity is unproven; no affected live preview executed.

Recording investigation: ordinary checkpoint rejects nonactive T-2037–2039 under T-2040 (`_plan_checkpoint:5692–5712`); `work reverify` accepts DONE only (`debt.reverify_work:1620–1678`). Do not invent a VERIFY boundary or record generic T-2040 PASS as ticket-local proof. Existing focused/core-unit canonical citation owner is being checked for lawful retrospective live-ticket evidence. Actual independent execution, package-specific reproduction/rejection and honest disposition remain required.

Controls to retain/extend: tools/test_sub_dispose_after_collect.py; tools/test_t925_sub_terminal_durability.py; tools/test_finding_invalidated_closure.py; tools/test_v7_producer_parallelism.py. At audit persistence no tests run, no production/canonical edits by this worker. Subsequent coordinator scope authorizes minimum subs.py/journal.py guards plus hermetic tests, audit first, failing control before passing same oracle; operations.py/replenishment.py reserved Wave C.
