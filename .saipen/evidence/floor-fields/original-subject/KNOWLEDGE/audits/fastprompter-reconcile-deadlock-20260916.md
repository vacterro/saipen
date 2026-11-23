# FastPrompter reconcile deadlock — REPAIR_GATE vs pre-existing BOARD residue (2026-09-16)

Status: OPEN — blocks the entire FastPrompter project (every writer tool refused)
Reporter: detached OpenCode session, bound project `V:\___VAC\__K\__CODE\_PY\_FastPrompter`
  (lineage `lineage-c13f771bc2924a5a81b65fc79e5aca08`, STATE.agent `buffy`, phase SCOUT, task T-1269)
Environment: installed surface `C:\Users\vac34\.config\opencode\skills\saipen`
  runtime generation `gen-sha256:aeeacd78f36a613e7eac7dbacfb96e2838fa0566b142ff6fa752f5f39082abf3`
  (stale vs canonical `...3a9f601a...`; engine diff only `tools/saipen_engine/audit_manifest.py` + its test)
Protocol version claimed by project STATE: `saipen_version: 7`, `schema_version: 3`,
  `style_contract: ded-4ae736e4`, `last_event: 1937`

## One-line summary

`reconcile_protocol_state` validates the WHOLE proposed BOARD (`validate_texts`,
`reconcile.py:2068`) and vetoes on ANY pre-existing semantic error, while its only
deterministic repair atoms do not cover the specific pre-existing error class present
here. The KEEP/REPAIR route it prints (`--apply-approved-repair <id>`) therefore cannot
commit, and every alternate route that could remove the offending field is itself gated
behind the ownership state the same unrepaired BOARD carries. No legal action remains.

This is the CORE §1.6 "NO LEGAL ACTION" class the T-1318 audit named, re-entered through
a different pair of surfaces: **reconciliation range** vs **ownership pre-flight**.

## Exact reproduction (read-only commands, all run from the bound project)

```
saipen continue --json
  -> RECONCILE_REAUTH_REQUIRED
     repair_id 32ab60fb2b221a9dee09a1e868409adbbfc06898f7349a37e5219301ff2332b9
     canonical_next_command:
       saipen recover --apply-approved-repair 32ab60fb2b221a9dee09a1e868409adbbfc06898f7349a37e5219301ff2332b9

saipen recover --apply-approved-repair 32ab60fb2b221a9dee09a1e868409adbbfc06898f7349a37e5219301ff2332b9 --json
  -> ok:false  code:VALIDATION_FAILED
     detail: proposed reconciliation fails fast validation:
       BOARD proposed T-1268 sits under ## DONE with no | verify: evidence --
       ## DONE is a claim that the ticket's own verify condition was met
```

The plan id the router printed, replayed byte-for-byte, is refused by the same engine
that printed it. The approval digest matched (no STALE_APPROVED_REPAIR); the failure is
strict-proposal validation, not staleness.

## The three interlocking facts

### 1. T-1268 — `## DONE` with no `| verify:` (the veto)
`BOARD.md:28`:

```
- [x] T-1268 [P1] [closed 14.09.26 E-1935] ... | owner: buffy
```

Record ends `| owner: buffy`; there is NO `| verify:` field.
`board.board_semantic_errors` (`board.py:436`) flags it:
`"T-1268 sits under ## DONE with no | verify: evidence"`.

`_board_lifecycle_repairs` (`reconcile.py:665`) generates NO atom for T-1268:
the phantom-DONE class (`reconcile.py:810-844`) is explicitly SKIPPED when the record
carries `owner` (`reconcile.py:815: if has_closure or owner or claim_time: continue`).
So reconciliation neither removes the record nor fixes the missing field — it is honest
about not owning it — but still lets `validate_texts` veto the entire commit.

### 2. T-1269 — INVALID half claim (blocks the only field-repair verb)
`BOARD.md:5`:

```
- [ ] T-1269 [P1] ... | owner: buffy
```

`owner` without `claim_time` on a claimable section. `_board_lifecycle_repairs` DOES
produce the correct atom: `kind: claim-clear` removing BOTH halves (SRC-043), plus
`section-move` for T-1270 and `claim-clear` for T-1260. These atoms are inside the SAME
plan that fails on T-1268, so they never commit.

Consequent: `saipen ticket verify T-1268 <text>` — the canonical verb that would ADD the
missing `| verify:` field (`operations.py:4426`, `ticket_verify`) — refuses via
`_seat_agent` → `OwnershipSplitError` (`operations.py:475`, `ownership.py:205`):
"pre-existing INVALID active ownership (half owner/claim_time pair ...)". Every
non-transferring mutation preserves STATE.agent, and it must validate the BEFORE
ownership snapshot first; T-1269's half claim makes that snapshot unreadable. Same
refusal for `saipen claim T-1269`, `ticket block`, `transition`, `checkpoint`,
`ticket compact` (compact answers `ALREADY APPLIED`/`already within cap`, no help),
`fleet preflight` (`FLEET_INSPECTION_UNTRUSTED`), `fleet prepare`
(`PROTOCOL_STATE_INVALID`), `undo` (`CONFLICT`, foreign watcher changes).

### 3. The global writer lock
`admission.protocol_snapshot` (`admission.py:691-774`) refuses `PROTOCOL_STATE_INVALID`
for every action except `saipen_op` once the checkpoint is invalid; the checkpoint is
invalid because of the FLOOR errors above. The OpenCode guard therefore refuses every
consequential tool (`Bash`, `Edit`, `Write`) on the bound project, and refuses direct
writes into `.saipen/**` with `PROTECTED_CANONICAL_NAMESPACE`. There is no in-session
write surface left.

## Why this is a protocol defect, not a project-data problem

Two legitimate rules collide with no ordering that resolves them:

- **Ownership preservation** (`ownership.preexisting_split_error`): a corrupt BEFORE
  ownership snapshot must be exposed/refused, and only explicit claim/adoption or
  canonical reconcile may repair execution authority. Correct rule.
- **Reconciliation range** (`reconcile.py:2068` `validate_texts`): the proposal must be
  WHOLLY clean, so a pre-existing error in an unrelated record vetoes the repair the
  engine itself computed.

The engine already solved this exact collision elsewhere — `compact_board`
(`operations.py:4234`) under T-1354 computes `before_errors` and CARRIES pre-existing
findings (`inherited_findings`, `carried_findings`, `carried_finding_count`) instead of
vetoing; only errors the repair INTRODUCES refuse (`operations.py:4356-4401`). The
lifecycle reconciliation did NOT receive the same treatment. That asymmetry is the bug:
the same project state that `ticket compact` calls "carried, not legitimized" makes
`recover` refuse forever.

Result, verbatim the CORE §1.6 prohibition: "A refusal that names a remedy no surface
exposes drives the operator to hand-edit BOARD.md, which is the one path OPS.md 4a
forbids." Here the printed `next` command cannot succeed, and the only field-level
repair for T-1268 is itself gated behind T-1269's claim the same stuck plan would clear.

## Smallest honest repairs (choose one; all are engine-side)

Option A — **scope the reconciliation proposal validator** (preferred, mirrors T-1354):
In `reconcile_protocol_state`, when `approved_repair_id` matches, compute the proposal's
errors and subtract the set that was already present in the BEFORE surface (the same
`before_errors`/`inherited_findings` pattern `compact_board` uses). Refuse only on
INTRODUCED errors; carry the inherited residue into the result and the journaled receipt.
This keeps T-1268 readable and unlegitimized while allowing the claim-clear atoms to
commit.

Option B — **add a deterministic lifecycle atom for "DONE record with owner but no
verify"** so the missing field is repaired by the plan instead of vetoing it. This is
riskier: fabricating `verify` text is forbidden (OPS §10: the engine never invents test
results/evidence), so the atom can only move such a record out of `## DONE` or refuse as
an explicit operator decision — it cannot invent the evidence. Likely B alone is
insufficient and A is still needed.

Option C — **break the ownership/reconcile ordering knot**: allow the claim-clear
(`_apply_lifecycle_repairs`) to commit independently of the strict proposal validator
when the ONLY remaining errors are pre-existing and unrelated to the rows the repair
touches. Equivalent to A at a finer grain.

Red control to demand: a fixture with BOTH a `## DONE` record missing `| verify:` AND a
`## DOING` record carrying a half `owner`/`claim_time` pair must reach
`REPAIRED`/`REPAIR_REQUIRED` and leave the DONE record's missing field visible as carried
debt — never `VALIDATION_FAILED`, and never a silently normalized DONE.

## Secondary observation (not blocking, but adjacent)

The installed OpenCode runtime is stale vs the canonical source
(`runtime --check-freshness`: `HOST_RUNTIME_STALE`, diff only
`tools/saipen_engine/audit_manifest.py` and its test). This did not cause the refusal,
but a stale install during a protocol-state incident reduces confidence in which engine
bytes produced the plan id. Worth resyncing the six installed homes once the engine
change above lands.

## No project bytes were modified

Every command above was read-only. The plan id `32ab60fb...` was never applied. The
FastPrompter tree is untouched by this investigation.
