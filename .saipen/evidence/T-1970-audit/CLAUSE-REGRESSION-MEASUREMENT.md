# T-1970 / SRC-351 — the restored clause set no longer matches the current engine

Measured 2026-11-17, project root `V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN`,
by ticket T-1970 (claimed at this measurement).

## Why this file exists

The working tree held a seeded-empty SRC-351 contract (`clauses: {}`) and coverage
(`requirements: {}`), both untracked and dated 2026-11-13 06:57. T-1970's own
blocker prose and E-19598/E-20974 record the real bundle: 13 semantically
extracted clauses with immutable revisions r001..r013, restored on 13.11 from
commit `06fa9f073`. The residue was preserved before repair:

| file | sha256 before restore |
|---|---|
| `.saipen/intake/contracts/SRC-351.json` | `fd32481aae5f94ee97858181970ca7abea50467ec01814fb525d33b5e39557d0` |
| `.saipen/intake/coverage/SRC-351.json` | `05f91c8e61028a816986361fd0003937049a8319bcfe998f3397abd76f1b652c` |

Copies: `.saipen/evidence/T-1970-audit/working-tree-residue/`.

Restored with `git restore --source=06fa9f073 --worktree --` (contract, coverage,
and `SRC-351.r001.json` .. `SRC-351.r013.json`). Restored bytes match the source
commit exactly:

| file | sha256 after restore |
|---|---|
| `.saipen/intake/contracts/SRC-351.json` | `075daab86018dac5551d281e13a7142ee24776a9dbadc0e20434ee833715ba64` |
| `.saipen/intake/coverage/SRC-351.json` | `3cbf15eb46e0d1b598ec395012297a14297effa9cf11688ec78d3d70097ddd29` |

`work_closure_gate(".", "T-1970")` then reports 13 requirements, 7 terminal,
6 unresolved (R006..R011), `contract_derived: true`.

## The measurement that broke the restored VERIFIED set

The restored coverage records R001 and R002 VERIFIED on 2026-10-31 against a tree
that implemented the typed foreign-protocol refusal. The current HEAD and the
running engine do not implement it:

```
$ saipen saipal continue --json
{ "ok": false, "code": "VALIDATION_FAILED", "detail": "unknown command: saipal" }

$ grep -rIl exact_namespace C:/Users/vac34/AppData/Local/saipen/scheduled-source
(no matches)

$ grep -rIl exact_namespace . --include=*.py --include=*.json --exclude-dir=.git
.saipen/evidence/T-1970-audit/clause-plan.json
.saipen/evidence/T-2040/... (registry snapshots only)

$ git merge-base --is-ancestor 6ad3ad6a9 HEAD        # rc=1, not an ancestor
$ git show 6ad3ad6a9:saipen/REGISTRY.json | grep -n 'FOREIGN_PROTOCOL_COMMAND|exact_namespace'
1070:  "FOREIGN_PROTOCOL_COMMAND",
1502: "exact_namespace": {
1524:  "refusal_code": "FOREIGN_PROTOCOL_COMMAND",
$ git show HEAD:saipen/REGISTRY.json | grep -c exact_namespace
0
```

The feature exists only in the unpublished commit `6ad3ad6a9` ("ship v8.1.0" that
is not an ancestor of HEAD), its stash trees `1dd70f6cd` / `06fa9f073`, and the
T-2040 registry snapshots. It is absent from the current repo tools, the current
`saipen/REGISTRY.json`, and the installed home
(`C:\Users\vac34\AppData\Local\saipen\scheduled-source`, VERSION 8.1.0).

R001 ("a foreign protocol command is refused with a typed FOREIGN_PROTOCOL_COMMAND
that names the protocol owner, the full invocation and the route...") and R002
("the refusal names the owning protocol... and carries next_action guidance") are
therefore unsatisfied under the running engine. They were re-dispositioned
VERIFIED -> BLOCKED on this evidence (see the coverage revisions appended after
this file). R003 (verbs unaffected), R004 (absent block degrades to the old
refusal without inventing an owner — the only behaviour the current engine has),
R005 (suites pass: 37 tests OK in test_router_closure_readiness +
test_refusal_registry + test_refusal_routes; 24 OK in
test_foreign_owner_terminal_route + test_protocol_registry), R012 (registry still
declares freebuff ADVISORY/ADVISORY/NONE) and R013 (WITNESS_MODEL still refuses
promotion; 13 tests OK in test_ingress_authority) remain true of current bytes.

## Consequence for T-1970

The ticket is not blocked only on six external clauses anymore. Two SAIPEN-side
clauses regressed when the unpublished feature was dropped from the published
baseline. Closing SRC-351 now needs: (a) an operator decision on whether to
re-land the unpublished exact-namespace feature (or authorize its
reimplementation) and (b) the six externally owned clauses (FreeBuff R006-R010,
SAIPAL R011), whose handoffs remain written and unsent.
