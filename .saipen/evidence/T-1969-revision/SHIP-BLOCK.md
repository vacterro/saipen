# T-1969 SHIP measurement — PUBLICATION_BLOCKED_EXTERNAL

Measured this cycle with the reviewed bytes in the worktree, before any staging.
`validate.py --gate ship`: **52 PASS, 6 FAIL**, exit 1.
Raw output: `.saipen/evidence/T-1969-revision/ship-gate.log`.

## The ticket's own change

Three paths, all reviewed:

| path | change |
|---|---|
| `tools/producer_backends/saipal_adapter.py` | `_committed_publication_ids` returns `{finding_id: {digests}}`; digest-paired suppression in the walker via `_already_delivered`; `_acknowledged_ids` receipt-scopes legacy rows through `_legacy_rows_for_corpus` |
| `tools/test_t1969_finding_revision_identity.py` | 4 controls in 2 classes + LIMITS docstring |
| `tools/test_t1944_wave2.py` | one fixture now carries the digest it publishes |

Ticket-scoped verification: focused gate **PASS ran=62**, record
`.saipen/evidence/focused-unit/cce1f156938e929d-*.json`; 609 T-19xx tests pass;
both defects red-before under a precise in-place revert and green-after.
Recorded as `verify -> PASS conf: high`, scope THIS TICKET'S OWN CHANGE ONLY.

Family gate: **not green, not claimed green.** Two runs produced two *different*
host-observation reds (`test_host_authority_broker` at jobs=6,
`test_t1966_broker_liveness` at jobs=1). Root cause traced to the ambient host
binary `9router` launched by a test's `Get-Command` agent-detection probe —
environment, not this change; both modules pass standalone and 3/3 together.
See `.saipen/evidence/T-1969-revision/FAMILY-GATE.md`.

## The six ship-gate failures

Four are the same foreign release-drift that blocked T-1966, T-1967 and T-1968:

1. `SRC-037 archive bundle invalid` — 4 contract clauses vs 16 coverage
   requirements. Somebody else's half-landed source close.
2. `EX-000029` — verified against engine `06c1149a`, running engine is
   `96e9c936`. Already stale at 18:26 on 2026-10-30, before this build.
3. `release index is empty` — the 4,221-path release-metadata slice is not
   staged.
4. `staged release metadata differs from working-tree bytes` — 618 worktree
   deletions and 636 untracked archive carriers across `.saipen/intake`.

The other two are a **single stray root file**, `SAIPENFUTURE_CONTEXT_GRAPH_20260909_1811.md`:

5. `cross-doc drift [root-file-set]`
6. `coverage gap -- 1 shipped document(s) are read by no check`

## Why that stray file is not this ticket's and was not deleted

I investigated instead of deleting, and the evidence says do not delete:

- It is `??` untracked and absent from HEAD.
- It is **not** any archived copy: every `.workbuddy-ai/` copy on disk is
  `19,079` bytes / 633 lines / sha256 `db73173e…`; the stray is `21,470` bytes
  / 768 lines / sha256 `fb2e2381…`. It is a *newer, expanded* revision, not a
  leaked sandbox copy. No file anywhere under `_AI_STUFF_AGENTIC` has that size.
- Its mtime is `2026-10-31T02:21:10`, and it is the **only** file in the whole
  repository modified in the 02:00–02:40 window.
- My session executed **zero** commands between `01:03:11` and `03:22:27`
  (exec-log mtimes are continuous right through the gap), so this session did
  not write it and no SAIPEN run I drove wrote it.
- No code in `tools/`, `bootstrap/` or `extensions/` references that filename,
  and `.workbuddy-ai/` does not exist in this worktree.

`validate.py` itself names the likely writer class in the failure text
(`HOST_HOOK_RUNS_PAYLOAD`): the Claude settings hooks under
`C:\Users\vac34\.claude\settings.json` are invoked as `cmd.exe /c` and the hook
payload, which is text an agent read, is executed as commands. That is an
ambient-host injection path, exactly the class this campaign is about.

Deleting it would destroy the only artifact of that injection and would hide
the incident. It stays, and the two FAILs stay with it as its evidence.

## Decision

`PUBLICATION_BLOCKED_EXTERNAL`. Not a code defect in this ticket: the six
failures intersect T-1969's three-path scope in exactly zero paths. Recovery is
outside this ticket's ownership — it needs (a) whoever owns the SRC-037 close to
finish it, (b) a release-metadata staging decision for the 4,221-path slice, and
(c) whoever owns the host hooks to stop executing hook payloads as shell.

Remotes untouched. HEAD `66ef622a`; origin behind 5 / ahead 9; github-backup
behind 2 / ahead 1.
