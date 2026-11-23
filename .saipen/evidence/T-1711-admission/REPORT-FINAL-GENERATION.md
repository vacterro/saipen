# Active regression evidence admission / final T-1711 generation

The confirmed initial defect was a missing active execution contract. The live
SAI_WEBSITE T-31 readback at E-356 lacks anchored identities; its missing-pair
refusal is correct, and a later diagnostic supersedes ordinary approval. A stale
REVIEW slot was not reproduced. Disposable controls instead established unknown
self-declared digests, contradictory aliases and unrelated producing Attempts in
the old identity-only route. No consumer product or canonical memory was edited.

The existing work namespace now owns the supported active command:

```
saipen ticket regression T-N required --evidence executed
saipen work regression T-N --file .saipen/evidence/pair.json
```

The declaration is an optional monotonic strengthening before execution;
successful native execution also atomically adopts the executed profile. Its API
is `regression_execution.execute_pair(root, ticket, agent, contract_path,
dry_run=False)`. `operations.ticket_verify(..., regression="required",
evidence_profile="executed")` exposes the explicit declaration. Active owned
VERIFY and the existing regression requirement are mandatory. The execution
creates a measured pair/immutable receipt/profile, without an ordinary verdict
or phase transition. Remaining ordinary VERIFY checks are still due.

The exact thirteen changed paths and byte identities are retained in
`owned-application-prior-bound.json`, `owned-current-prior-bound/` and
`owned-changes-prior-bound.patch`. The earlier candidate carriers remain intact.

| File | Owned symbols / behavior |
| --- | --- |
| tools/saipen_engine/regression_execution.py | execute_pair, evidence_gate, _binding, _load, _measure, _records, parse_summary; actual managed paired execution, authority and exact material binding. |
| tools/saipen_engine/oracle.py | parse_identity rejects contradictory aliases and preserves equal aliases. |
| tools/saipen_engine/log.py | regression_evidence binds halves to one producing Attempt and spends an earlier episode once a new one opens. |
| tools/saipen_engine/operations.py | ticket_verify supports the executed profile; _regression_gate consumes measured evidence at REVIEW and finish. |
| tools/saipen_engine/board.py | ticket scalar validation restricts executed profile to regression-required Work. |
| tools/saipen_engine/board_compaction.py | Field storage and routing-critical projection preserve the profile. |
| tools/saipen_engine/journal.py | Registers the regression-execution operation id class. |
| tools/saipen.py | Existing ticket/work dispatch reaches the supported declaration and active execution. |
| saipen/REGISTRY.json | Declares the machine-owned board field. |
| saipen/COMMANDS.md | Publishes exact supported signatures; redundant descriptions shortened within existing budgets. |
| saipen/phases/verify.md | Defines the active contract and explicit legacy compatibility boundary. |
| extensions/schemas/board.schema.json | Describes/validates the executed profile. |
| tools/test_t1711_regression_execution.py | IdentityControls, AttemptControls and ExecutionControls; final 42-case oracle. |

The closed schema-1 input has exactly schema, command, format, context,
oracle_files, subject_files, before and timeout. Command is native argv;
`{python}` selects the current interpreter. Context declares all verifier
dependencies/configuration; oracle and subject lists name disjoint owned files.
Before maps each subject to preserved evidence bytes or null for prior absence.
Owned no-follow reads reject links/reparse points, traversal, canonical memory
and Git subjects; bounded inputs prevent unbounded collection. Timeout is
1..5400 seconds. Supported summaries are unittest, pytest, tap and
playwright-json; pin reporters, including `--test-reporter=tap` and
`--reporter=json`. Zero/skipped-only, startup failure and timeout refuse.

Both subjects run in disposable immutable copies with one measured runtime,
environment, argv and oracle. The original sources, authority and inputs are
rechecked after execution and guarded through the journaled commit. Receipt
integrity is checked before filtering; current own canonical pair events select
their producer instead of filename order. The gate rechecks project/lineage,
Work/owner, Source body/Contract, acceptance, current VERIFY boundary, producing
Attempt and its latest episode, runtime/environment, oracle, context, full input
contract, prior and current subject bytes. A completed producing candidate
Attempt keeps its genuine pair; another episode cannot inherit it. Exact replay
returns the existing carrier. A newer failure requires a fresh actual pair.

Independent preflight found three omissions in the first measured candidate:
changed prior material, changed full input contract, and a prior-material race
after the final binding read could still acquire approval. The candidate's full
6195/0 result is preserved at E-14402; it did not erase that finding. The final
expanded oracle has its own candidate red (42 tests/three failures), and the
correction binds contract_sha256 plus the measured prior digest at the gate and
uses the measured prior bytes for CAS rather than a later read.

The same final verifier is
2a13fba70e8fa5a133b6384778a4067cd5f10dd8b85b901610e6f734d6bec501.
Exact pre-T1711 subject
65a94a9b40a12795c54273ad89efb3f204f0da7f715121903b745c94094635ce
has 42 collected/42 failures. Corrected subject
81199a19d4b93ab9dd5db8307e90f93f41df2003832fadf2624a8985c37a9cf0
passes 42/42. `build-prior-bound-pair.json` and
`verify-prior-bound-pair.json` preserve actual equal-oracle paired execution;
E-14408/E-14409 anchor the new VERIFY generation. Earlier 28/37/39-case records
are historical and are not spent on this oracle. Root checkpoints are explicitly
externally executed attestations, distinct from native fixture execution receipts.

`public-launcher-workflow.json` independently executes the actual documented
bin/saipen.cmd backend for Python/unittest and Node/TAP: admission, byte-noop
replay, changed-prior REVIEW refusal without canonical writes, and successful
REVIEW after exact restoration. Eight native operations pass. Live root canonical
hashes remain identical. These fixtures demonstrate the consumer-compatible
contract; no real browser run, consumer project repair or deployed runtime is
claimed. Pytest/Playwright support is summary handling, not a claimed live run.

Whole-source/refusal/reachability/UTF-8/registry contracts pass 37; pinned Ruff
0.16.0 tools/tests and owned whitespace pass. The current native core has zero
problems/eight carried warnings after executed RV-000024 preserves T-1695 DONE.
The final complete family E-14411 passes 6198/0 on fingerprint e2a8fba4c1b7be3c;
independent REVIEW re-executes the identical 42-case pair in
review-prior-bound-pair.json. The final native metadata gate again has zero
problems/eight warnings. Local closure remains due; a separate closure carrier
will supply the terminal readback. E-14405 qualifies the previous family's six descendant PIDs:
observed before managed close, then reaped; no surviving PID was observed and no
sandbox leaked. No empty recorded process list is fabricated.

Compatibility is deliberate: absence of regression_evidence retains the existing
attested identity arithmetic and never claims engine execution. Old valid
records and unrequired Work keep their lifecycle; contradictory identities and
cross-Attempt halves are strengthened generally. Executed evidence is stricter:
changing complete contract bytes, prior/current input, runtime/environment,
Source/acceptance, cycle or Attempt spends that authority. This can require a
fresh pair after legitimate edits. Digests prove identity, not the substantive
quality of a test; independent oracle review remains necessary. Disposable
copies do not claim OS sandbox enforcement.

The blocked consumer owner's next lawful operation is to inspect its current
authority, prepare preserved pre-fix material and a complete immutable contract,
and invoke `saipen work regression T-31 --file .saipen/evidence/pair.json` while
its owned regression-required Work is VERIFY. It must then complete its ordinary
checks and record their actual verdict before requesting REVIEW. The local
source change must first be delivered through the separately authorized runtime
update; no installation, consumer edit, ACL grant or publication was performed.
