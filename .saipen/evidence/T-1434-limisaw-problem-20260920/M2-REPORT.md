# T-1434 / SRC-088 — Milestone 2 evidence: external implementation resolution

Date: 2026-09-20. Session astra. Phase BUILD. Continuation of SRC-088.

Mission: a locally reported defect implemented by an EXTERNAL authority and
verifiable against the installed implementation must close truthfully, with
the EXTERNAL_IMPLEMENTATION_LOCAL_VERIFICATION provenance class -- no fake
local commit, no own_patch, no fake DONE successor, no rewritten report.

## Defect reproduced before patch

- LIMISAW T-73 / T-66 / T-67 sat under `## BLOCKED` with `BLOCKED_EXTERNAL`
  blockers whose own text proves the fix exists upstream (T-73 cites SAIPEN
  T-1411, commit cc86601f, oracle 16/16 OK; T-66/T-67 cite the shared-engine
  conformance-truth divergence fixed by T-1417). The protocol could not
  represent "reported locally / implemented upstream / verified locally":
  closure provenance (`closure.py` SOURCE_GRAMMAR = release|T-###|SRC-###)
  had only local-implementation or in-repo-successor shapes, so each ticket
  was permanently blocked or required false provenance.
- Ignored-carrier cross-repo note (M6 signal): resolving against an explicit
  foreign `--project-root` from a session carrying ambient SAIPEN_PROJECT_*
  carriers is refused PROJECT_LINEAGE_MISMATCH (paths.py:648-655); the M2
  LIMISAW acceptance ran with the carriers cleared, the same discipline the
  M1 measurement used. Recorded for the M6 audit, not fixed here.

## Implemented primitive

Command (public, registered, guard-canonical):

    saipen ticket resolve-external <T-###> --authority lineage-<32hex>
        --implementation T-###@<commit> --reason
        PROTOCOL_HOME_FIX_VERIFIED|DEPENDENCY_UPGRADE_VERIFIED|UPSTREAM_FIX_VERIFIED
        --run <command> [--run <command>]... [--verification cmd:PASS]...
        [--contract sha256:...] [--timeout SECONDS]

Semantics:
- only `## BLOCKED` Work is resolvable (TODO/DOING refuse
  EXTERNAL_RESOLUTION_REQUIRES_BLOCKED); a DONE row with the identical
  authority/implementation/reason tuple and a current receipt returns
  ALREADY_APPLIED with zero writes; a DONE row with any other closure refuses
  TICKET_ALREADY_DONE;
- the defect contract is the ticket's OWN `verify:` text; `--contract` must
  match its digest or the request refuses EXTERNAL_CONTRACT_MISMATCH;
- the local verification contract is EXECUTED (`--run`, real exit codes,
  timeouts honest FAILs); a FAIL writes its own append-only FAIL receipt and
  changes no lifecycle byte (ticket stays BLOCKED);
- a PASS writes ONE immutable `EX-NNNNNN` receipt under
  `.saipen/recovery/conformance/external/` in the SAME journaled transaction
  as LOG + BOARD + STATE, moves the ticket to `## DONE` with
  `closure_mode: external_implementation`, `implementation_delta: none`,
  `external_authority`, `external_implementation`, `external_evidence`,
  `resolution_reason`, removes only the live blocker fields, and preserves
  the original blocker as a digest (`prior_blocker_sha256`) plus all
  historical LOG bytes (append-only; asserted as a prefix in the suite);
- the receipt binds the installed engine GENERATION
  (`installed_identity.engine_digest` over every engine source + VERSION).
  The ONE shared predicate `external.resolution_problems` is called by BOTH
  the closure resolver and `validate.py`; when the installed generation
  moves (rollback or upgrade) the closure is non-green with
  "the dependency moved ..." -- re-resolution is the lawful repair and writes
  a NEW receipt against the new generation, keeping the DONE row and history.
- `saipen ticket done --closure-mode external_implementation` refuses and
  names the dedicated operation: a local-completion command can never claim
  local implementation for externally implemented work.

Files (this change):
- tools/saipen_engine/external.py NEW (grammar, receipt build/load/integrity,
  engine identity, shared resolution predicate),
- tools/saipen_engine/operations.py (plan/apply resolve-external + grammar
  refusal + `_move_ticket` resolve action + lineage ensure),
- tools/saipen_engine/board.py (CLOSURE_MODES + four fields + grammar
  validation + accessors),
- tools/saipen_engine/closure.py (resolver branch),
- tools/saipen_engine/board_compaction.py (dispositions),
- tools/saipen.py (dispatch + usage),
- tools/validate.py (closure-provenance branch; closure-evidence exemption
  for the mode),
- saipen/REGISTRY.json (10 new stable refusal/result codes),
- saipen/COMMAND_EFFECTS.json (`ticket resolve-external` = EXECUTION),
- extensions/schemas/board.schema.json (enum + four properties),
- tools/test_external_resolution.py NEW (10 families).

## Verification (current bytes)

- `python tools/test_external_resolution.py` -> 10/10 OK. Families:
  upstream fix verified locally (BLOCKED->DONE + receipt + append-only LOG);
  failed local verification (FAIL receipt, zero lifecycle change);
  missing/malformed upstream identity refused; mismatching defect contract
  refused; dependency rollback -> resolver non-green (shared predicate);
  duplicate resolution idempotent (bytes unchanged, receipt unchanged);
  own_patch-for-external rejected both directions; TODO work refused;
  validator accepts a current resolution and FAILs a tampered receipt
  (integrity digest mismatch); re-resolution after generation move writes a
  second receipt and RE-RESOLVED evidence.
- Neighboring families: test_work_reverify_cli 14/14, test_reverify 17/17,
  test_closure_provenance 28/28, test_router_closure_readiness 6/6,
  test_command_routing 63/63, test_effect_authorization 34/34,
  test_guard_events 55/55, test_session_binding 17/17,
  test_t1411_stale_complete_resolution 16/16, test_t1412_conformance_truth
  10/10, test_public_closure_cli 9/10 (1 pre-existing T-7
  SOURCE_SCOPE_MISSING), test_check_inventory 37/42 (5 pre-existing fail
  site 17c1825e57d0436e, unchanged). Carrier-set runs keep the recorded
  T-1361 PROJECT_LINEAGE_MISMATCH cluster (pre-existing environment class).
- ruff: clean on every changed file.

## Real LIMISAW acceptance (canonical operations only, carriers cleared)

Before: T-73, T-66, T-67 BLOCKED_EXTERNAL. Executed:

    saipen ticket resolve-external T-73 --authority lineage-b512942... --implementation T-1411@cc86601f --reason PROTOCOL_HOME_FIX_VERIFIED --run "<T-1411 oracle>"
    saipen ticket resolve-external T-66 --authority lineage-b512942... --implementation T-1417@3b0650f1 --reason PROTOCOL_HOME_FIX_VERIFIED --run "<conformance-truth ValidateSurfaceTests>"
    saipen ticket resolve-external T-67 --authority lineage-b512942... --implementation T-1417@3b0650f1 --reason PROTOCOL_HOME_FIX_VERIFIED --run "<conformance-truth StatusSurfaceTests>"

Results: EXTERNAL_RESOLVED each; E-652/E-653/E-654; EX-000001..3;
T-73/T-66/T-67 now `## DONE` with external_implementation provenance.
Validator after: 25 problems (21 closure-evidence + 2 source receipts + 1
improve report + 1 sweep-ticket-link), warnings 22 -> 21, no new FAIL class;
the closure-provenance gate passes with three external DONE rows. Zero
LIMISAW product source touched; no LIMISAW Board/State/Log bytes were
hand-edited (all three transactions journaled by the engine).

T-68 (install-fingerprint improve draft) deliberately NOT resolved: SRC-088
orders individual evaluation and its own contract was not exercised here.

## Milestone exit check

- a local reported defect is truthfully satisfied by an external
  implementation without fabricated local provenance: yes (3 real tickets);
- rollback semantics: resolver/validator go non-green when the installed
  generation moves; re-resolution is the finite canonical repair;
- executable by construction: parser/registry/effects/router/schema/docs
  updated together; every refusal has a stable code.

## Exact next action

M3 (SRC-088): conservative canonical source retirement/tombstoning with
machine-readable reasons, LIMISAW SRC-007 as the real fixture; regression
matrix in SRC-088 M3.
