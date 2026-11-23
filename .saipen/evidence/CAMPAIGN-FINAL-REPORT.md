# Campaign final report — close remaining causal gaps

Campaign date 2026-10-31. Mode 2 extended continuation. Charter: **close
remaining causal gaps; do not rebuild existing systems.**

Everything below is measured on this tree. Where a claim could not be measured,
it is written as a limit, not as a green.

---

## 1. Outcome

Ten tickets closed. The ship gate went from **6 problems to 2**, and both of
the two that remain are the release-staging slice rather than a truth defect.

```
board   128 [x]   104 [ ]        (every open row carries a measured blocker)
TODO    empty     DOING empty    (every open row is in ## BLOCKED)
gate    Validation complete. Agent is conformant. (19 warning(s))
ship    Validation FAILED: 2 problem(s), 19 warning(s)
        both = SRC-349/SRC-350 intake-to-archive bytes not staged for release
```

Closed this campaign: T-1856, T-1966, T-1967, T-1968, T-1969, T-1971, T-1972,
T-1973, T-1974, T-1975. All record `closure_mode: own_patch` and
`publication_state: pending`. Nothing was committed. Nothing was pushed. No tag
exists.

The goal was **not** marked complete, and T-1859 / T-1819 / T-1822 were not
closed.

---

## 2. The last truth defect, and how it was resolved

At the time this report was first drafted the gate carried one closure-
provenance failure:

```
FAIL: closure provenance does not resolve: EX-000029 was verified against
installed engine generation sha256:06c1149a… but the running engine is
sha256:6f2cd4c3…; external implementation differs from its carrying commit:
Scripts/accounts/SaiAccounts.cs; external verifier context/runtime/argv
changed since the receipt
```

That line is now **gone**, and the route that cleared it matters more than the
line did. Full measurement and resolution:
`.saipen/evidence/T-1973-external-closure-drift/MEASUREMENT.md` and
`RESOLUTION.md`.

The ticket's own verify clause permitted two outcomes: a fresh verification
against the generation this tree actually runs, **or** a canonical
re-resolution naming why the old proof no longer applies. Four routes were
considered and three refused:

| route | outcome |
|---|---|
| re-verify with `ticket renew-external` | refused: `external implementation differs from its carrying commit` — the sibling repo's 39 uncommitted lines are another project's authority |
| edit `.saipen` memory to satisfy the gate | refused by design: `regression_execution._paths` does not accept `.saipen` as an execution subject |
| hold the engine digest still | impossible: `engine_identity()` hashes 171 engine files, so every ticket that edits the engine moves it |
| **`ticket resolve-external` re-resolution** | **used** — writes EX-000031 through the documented re-resolution path |

The decisive new fact was not the digest treadmill but the external product
itself: `sai-accounts.exe` shipped new code at 08:25 today (`5568338e` →
`39f20e2a`). T-1973's verify clause forbids re-asserting `T-289@d93b212f`
"without new evidence from the external product", and this is exactly that
evidence — the product moved, so the closure must be re-measured rather than
inherited.

One honest limit remains, and it is the treadmill again: `engine_identity()`
binds a receipt to the exact engine bytes. EX-000031 binds
`sha256:9a54fd45563659ad`, and any later engine edit re-opens the same
finding. This is a property of the design, not a defect this campaign can
remove: the digest is doing its job, and the answer is to re-resolve after the
last engine edit, which is what was done.

---

## 2b. A real defect found inside the recovery surface itself

While making the re-resolution, `saipen ticket resolve-external --revalidate`
answered `discovered 0 / inspected 0 / resolved [] / still_blocked []` in the
same second that `validate.py --gate ship` printed a FAIL over the same
closure. Both read the same predicate, `external.resolution_problems`; only the
reporting loop disagreed.

The cause was a two-way split written as one guarded branch
(`if engine_moved and not other_problems:`). Every problem class outside an
engine move — a moved artifact, a changed verifier argv, a corrupted
predecessor — fell through with no counter and no finding, so the surface told
the operator there was nothing to repair over work it had just measured as
non-green.

Fixed in `tools/saipen_engine/external.py`: the non-engine-move branch now
increments `inspected` and appends an `EXTERNAL_CLOSURE_DRIFTED` finding naming
the Work. Covered by `tools/test_t1973_revalidate_accounting.py`, whose two
tests are a red→green pair (one fixture shows the finding, one control asserts
silence plus `inspected == 0`) measured through
`revalidate-accounting-contract.json`: before exit 1 / 2 ran / 1 failed, after
exit 0 / 2 ran / 0 failed, verifier `3a3bdb94`. The pair was proved genuine by
stripping only the guard and reproducing the `0 not greater than 0` failure.

---

## 2c. T-1975 — the refusal named a command its own tool always refuses

The SRC-188:R009 clause could not be settled, and the refusal that blocked it
was itself broken. `saipen source disp` answered `EVIDENCE_UNAUTHENTICATED` and
printed:

```
python tools/core_unit.py focused T-1653 --pattern verify_accounts_readiness.py
```

Run verbatim, that command is refused:

```
patterns must select test_*.py filenames inside tools/
```

`intake.set_disposition` built its `--pattern` from **any** `.py` filename in
the verification text (two identical sites, `intake.py:2546` and `:2689`);
`focused_unit._patterns` selects bare `test_*.py` names only. The receiver of a
refusal was handed a route that could never succeed — the class the KNOWLEDGE
card `name-the-route-the-guard-admits` already records.

Fixed with one helper beside `_valid_receipt_id`. A `test_*.py` oracle keeps
the focused route it printed before. Any other module is **not** redirected to
`core_unit.py evidence`, and that distinction is the substance of the ticket:
the declared family is discovered with `-p test_*.py`, so a family record can
never prove a file the family does not run, and the core-unit branch's oracle
check is a tautology — it builds `proven_oracles` *from* `test_files`. Naming it
there would have traded one unrunnable route for a wrong one that silently
discharges the clause. Only a sealed closed contract selects its oracle by
name, so that is what the refusal names.

The REVIEW self-audit caught both of those defects in my own first draft, which
is why the ticket took a second pass through BUILD→VERIFY. Measured pair, first
draft: `before exit 1 / 4 ran / 2 failed`, `after exit 0 / 4 ran / 0 failed`,
verifier `63cfb244`. Final bytes: `before exit 1 / 4 ran / 2 failed`, `after
exit 0 / 4 ran / 0 failed`, verifier `9fe1ee94`. Family on final bytes:
`8548 ran, 3 red (all declared baseline), new_red empty`, record `cd6cbf63`.

A second catch came from the existing suite rather than from me:
`tools.test_canonical_command_reachability` failed the family run because the
route carried a 40+ character angle-bracket explanation, which
`guard_events._saipen_cli_verb` substitutes as typed input and refuses. The
placeholder is now short and the sealing requirement lives in the refusal
detail. That test earned its keep.

---

## 3. A correction I owe

Earlier in this campaign I recorded that `SaiAccounts.cs` had **moved** from
`d771f95c` to `f9cffd24`. That was wrong.

`git rev-parse` and `git show <commit>:<path> | sha256sum` are two different
numbers — a blob OID and a content digest. I compared one to the other. The
committed blob is `0eac11ca`, identical at `d93b212f` and at HEAD `555911f`,
and its content digest **is** `d771f95c`. The `f9cffd24` I reported is a
39-line uncommitted worktree edit in a different repository.

Both `MEASUREMENT.md` and the T-1974 adjudication were corrected. The finding
stands — the worktree really does differ from its carrying commit — but the
cause is an uncommitted sibling edit, not released drift.

---

## 4. T-1974 — the only ticket that needed new code

Nine untracked `tools/` files, staged by explicit enumerated path. The gate
went from **10 problems to 1**.

Three genuine defects were found and fixed:

1. **`_imported_names`** treated `from m import a as b, c` as binding `a as b`.
   It now strips ` as ` and skips `*`.
2. **`_submodule_paths`** did not resolve `from pkg import mod` when `mod` is a
   submodule. It now checks `tools/pkg/mod.py` and
   `tools/pkg/mod/__init__.py` against HEAD.
3. **A regression I introduced.** See §5.

Measured pair, one verifier both halves
(`regression-execution-339a01f14ff34a00af644c02242901f9.json`):

```
before  FAIL   11 of 13 failed   0 skipped
after   PASS   13 ran   0 failed  0 skipped
```

The red half was then rewritten to build its own git fixture, so it exercises
13 behavioural tests in a sandbox with no repository rather than skipping two.

---

## 5. The family run caught what nothing else could

My own fix to `validate.py` broke T-1592's test loader.

`test_t1592_manifest_orphan_advice.py` slices `_uncommitted_symbols` out of
`validate.py` by source and execs it. That works only while the function is
self-contained. After T-1974 made it call `_imported_names` and
`_submodule_paths`, the slice raised `NameError`.

```
T-1974 files      all green
regression pair   PASS 13/13
family run        FAIL — 2 new red, 8541 ran
```

Both new reds were `test_t1592_manifest_orphan_advice`. **The commit would have
been red in every clone.** The fix extends the loader to follow an explicit
`_HELPERS` list while leaving every assertion untouched; the pre-fix bytes are
preserved at `.saipen/evidence/T-1974-untracked-tools/prefix-t1592-orphan-advice.py`
(`5cde0812…`).

This is the single most valuable finding of the session and the reason the
family run is not optional.

---

## 6. Stale-blocker sweep — the dominant yield

Five tickets closed purely because the ship-gate problems they cited had
already been fixed by T-1971 and T-1972. **Each was re-measured before
unblocking.** None was unblocked on the assumption that a sibling had fixed it.

I then swept the full open board rather than stopping at the ones that worked:

| class | open | verdict after measurement |
|---|---|---|
| `ACTIVE_DEPENDENCY` | 23 | **none expired** — all 19 dependency roots still open |
| `BLOCKED_EXTERNAL` | 22 | real external input |
| `WAIT_USER_DECISION` | 9 | operator decisions |
| `MARKHUNT_TRIAGE_REQUIRED` | 8 | protocol forbids agent triage (`markhunt.md:30`) |
| everything else | 43 | structural, measured individually |

The 23 `ACTIVE_DEPENDENCY` tickets were checked by resolving every
`blocker: ACTIVE_DEPENDENCY:T-####` target against the board: T-1375, T-1426,
T-1428, T-1446, T-1548, T-1551, T-1562, T-1563, T-1602, T-1610, T-1644, T-1663,
T-1672, T-1719, T-1764, T-1766, T-1769, T-1783, T-1794 — **all 19 still open**.
No dependency chain expired, so no chain could be unblocked.

`saipen continue` and `saipen next` independently agree: `top_workable_ticket:
null`, `continuation_authority: operator_required`. `saipen host doctor`
reports `DEGRADED_ALLOWED` by operator policy at
`C:\Users\vac34\.saipen\authority.json`.

---

## 7. T-1971 — the two contaminants, adjudicated

**SRC-037's archive coverage** had been overwritten with 16 clauses belonging
to a JavaScript project (`tests/probe_audit_inbox_fixes.js`, work T-71…T-86, in
`_FREEBUFF_SAI`). The truthful 4-clause coverage exists at HEAD in
`.saipen/intake/coverage/SRC-037.json` (`b11d8cf9…`), ids exactly
`SRC-037:R001`…`R004`.

Every CLI repair route was measured and refused before any write:
`source reconcile` → `SOURCE_CORRUPTION` (recoverable: false);
`reconcile --confirm` → wrong shape (reads `intake/active/*`, none exist);
`source retire` → `ALREADY_RETIRED`; `source normalize --dry-run` →
`ALREADY_NORMALIZED`, and it is about receipt-id ranges, not coverage content.

The repair was option (b): a restore from committed truth using the engine's own
`intake.project_writer_lock` and `intake._atomic_write`. No ledger content was
authored by hand. The corrupt bytes are preserved at
`.saipen/evidence/SRC-037-coverage-overwrite/corrupt-coverage-preserved.json`
(`6eacdf24…`). Nothing was deleted.

**Declared provenance limit:** this is a journalled restore from committed
bytes, not an authored ledger. If a future reader needs to know whether the
16-clause content was ever legitimate, the answer is no — and the evidence for
that is the absence of `source_sha256` on the archive copy, which every
canonical coverage file carries.

**The stray root file** `SAIPENFUTURE_CONTEXT_GRAPH_20260909_1811.md` (21,470
bytes, `fb2e2381…`) was adjudicated deliberately, not deleted on suspicion. Its
first 633 lines are byte-identical (CRLF-normalised) to an archived
`.workbuddy-ai/` version; 134 appended lines are coherent roadmap prose. I had
earlier attributed it to host-hook contamination citing `validate.py`'s
`HOST_HOOK_RUNS_PAYLOAD` line — the validator's own word is "Likely", and
`host_hooks.stray_hint` builds that hint from settings parsing alone without
ever observing a write. **That attribution was withdrawn** in
`STRAY-ROOT-FILE.md`. Hook payload execution produces empty stray files, not
21 KB of structured prose.

---

## 8. T-1972 — the release slice, staged but not published

The ship gate's `release index is empty` and `staged release metadata differs
from working-tree bytes` both required the whole 4,242-path
`release_metadata_paths` slice staged at once. All 1,386 `need_staging` paths
were adjudicated — 618 intake deletions each with a verified archive
counterpart, 636 untracked archive carriers each bound to a tombstone id, and 5
modified canonical state files — then staged as an explicit enumerated list. No
`git add .`, no `git add -A`.

**Both failures are gone.** The pre-ship index tree is backed up as
`86b0736715f4c4ec40649539ea9e84a6823fefc0`.

**The ordering constraint this created is real:** staging pinned SRC-037's
corrupt coverage bytes (`6eacdf24…`) into the index, because the gate demands
the whole slice. No commit may land on that index until the bundle is resolved,
or the corruption becomes permanent history.

---

## 9. The hook finding has expired

Earlier in this campaign I recorded the ZAICODE guard hook as undeployed: the
repository copy at `extensions/adapters/zaicode/saipen-guard.py` differed from
the installed `C:/Users/vac34/.zcode/hooks/saipen-guard.py`, which made the
correct status INTEGRATION_VERIFIED rather than INSTALLED_VERIFIED.

Re-measured this turn: **both are `a04a2ef4…`, 34,924 bytes.** The installed
copy is dated 2026-10-31T00:24. The gate is now deployed, and the earlier
finding should not be carried forward as though it still held.

The repository copy carries a staged modification relative to its last commit
(`7949027c`), so it is deployed but not yet committed.

---

## 10. T-1970 — 7 of 13 clauses done, deliberately left blocked

SRC-351 was seeded with an empty contract residue; T-1970 replaced it with 13
semantically extracted clauses as immutable revisions r001–r013. Seven are
VERIFIED from fresh measurement:

- typed `FOREIGN_PROTOCOL_COMMAND` naming owner and full invocation;
- `cc`/`continue` unaffected, exit 0;
- three damaged-registry forms degrade to `None`;
- router/refusal suites PASS, ran 52;
- FreeBuff `ADVISORY`/`NONE` matches the audit's own §10 claim;
- `model_supplied` refused an operator-origin upgrade, 30 passing witness tests.

Six remain genuinely external — R006/R007/R008/R009/R010 are FreeBuff host
dispatch work (decide namespace before skill matching; stop treating `NO_HOME`
as a directory cue; reload the skill inventory at session start; stop offering
a substitute; one live `/saipen continue` in `_BZ_REA`), and R011 is SAIPAL-side
append-only reconciliation of five `NO_DRIFT` receipts.

`source close SRC-351` correctly returns `SOURCE_UNRESOLVED`. `NOT_APPLICABLE`
would be a lie; `DEFERRED` cannot waive closure.

**Two handoffs are written and NOT sent**, both marked "prepared locally, not
sent": `.saipen/evidence/T-1970-audit/FREEBUFF-ROUTING-HANDOFF.md` and
`SAIPAL-RECONCILIATION-REQUEST.md`. A prior session decided not to send them.
Sending them creates work for other agents and would preempt active work in
those repositories. **I did not reverse that decision**, because no evidence
has appeared that the receiving owners are free.

---

## 11. The audit inbox is not workable, and that is structural

`saipen continue` routes to `saipen audit status`, which reports 12 ACTIVE
layers, all linked to Work items that are themselves unworkable. The launcher's
detail is `IDLE_OPERATOR_REQUIRED`.

This is the correct answer, not a routing defect: every audit layer is the
Source of a ticket whose own blocker is external or a human decision. Consuming
the layer would consume a receipt whose work is not done.

---

## 12. Three baseline reds, honestly characterized

The latest family record
(`1540d4ad61677568-20261031T060507453778Z.json`) is `status: FAIL`, `ran:
8542`, `exit 1`. The three reds are all
`test_t1816_provenance_inventory`:

```
test_committed_ledger_cites_the_missing_ids_as_parents        FAIL
test_committed_ledger_still_misses_exactly_the_cited_events   FAIL
test_working_tree_renumbers_committed_ids_instead_of_repairing FAIL
```

They are not noise and they are not mine. T-1816's oracle measures an external
managed root, `V:\___VAC\__K\__CODE\_PY\_AUDAPACK`, whose `.saipen/LOG.md` has
moved on: it now runs to E-4385 and carries `E-3133` twice, where the inventory
recorded E-3133/E-3136/E-3145 as absent. `git status` in that root shows
`M .saipen/BOARD.md`, `M .saipen/LOG.md`, `M .saipen/STATE.md` — an uncommitted
external ledger. Eight of the module's eleven tests still pass, including the
one proving the audit left the root untouched.

The two reds T-1816's own blocker named (`test_refusal_registry`,
`test_t1844_origin_broker`) are now **green** — 54 tests OK. So T-1816's stated
reason for staying blocked has expired, but it stays blocked for a different,
worse reason: the staged set grew from 206 foreign paths to **786**, so
`saipen ship` refuses even more firmly.

---

## 13. What T-1816 and T-1817 need

Both are `PUBLICATION_STAGING_BLOCKED`. Measured now:

```
staged paths: 786
  768 .saipen
   17 tools
    1 extensions
```

Their delivery is complete (SRC-275 7/7 VERIFIED; SRC-276 8/8 VERIFIED, focused
116 PASS, four executed FAIL→PASS pairs). They are blocked on a shared-tree
condition the campaign may not clear unilaterally: the staged set includes
work from other tickets, so committing it would publish work whose own
publication decision has not been made.

**Operator action:** decide whether the whole 786-path staged set is one
publication unit.

---

## 14. Verification economics — measured, not asserted

The core-unit family run is the only gate that has ever caught a defect the
per-file runs missed this campaign (§5). Its economics on this tree:

```
requested (reused)   5.8 s      fingerprint unchanged
executed             2084.8 s   ~35 min, 8542 tests
```

The engine legitimately returns `reused: true` when the tree fingerprint is
unchanged (`1540d4ad61677568`). That is correct behaviour and worth keeping:
eight closures in one session would otherwise have cost roughly four and a half
hours of wall clock. The reuse is keyed on a content fingerprint, not on a
claim, so it cannot hide a change.

---

## 15. What was deliberately not done

- Nothing committed, tagged, or pushed. All eight closures are
  `publication_state: pending`.
- No counter edited to make the board look better.
- No immutable history deleted. Both contaminants preserved with digests.
- No canonical file hand-edited outside the engine's own writer lock and
  atomic write.
- Staging by explicit enumerated path only.
- T-1859, T-1819, T-1822 left open as instructed.
- T-1970's two handoffs left unsent.
- The goal not marked complete.

---

## 16. Exact blockers only a human can clear

1. **SRC-349 / SRC-350 release staging** — the only two gate problems left.
   Their intake→archive migration (10 untracked archive carriers, 12 deleted
   intake files, 9 modified canonical bytes) is a release decision: decide
   whether this slice is staged as one publication unit. No agent may stage a
   release slice on the operator's behalf, and `git add .` is forbidden by
   `ship.md` 6b.4.
2. **T-1816, T-1817 and every SHIP-stage ticket** — decide whether the
   786-path staged set is one publication unit. The ship gate's whole-slice rule
   means no subset can be published alone.
3. **T-1972's index** — no commit may land until SRC-037's bundle is resolved
   and accepted, or the `6eacdf24…` corruption enters permanent history.
4. **T-1644** — this repository's publication policy (full / tag-only / hold).
   Nine tickets and their dependents wait on it, including T-1607 and T-1880.
5. **T-1768** — restore verified host admission (`saipen host repair` after
   `saipen host doctor`) or state that this mission may run under
   `DEGRADED_ALLOWED`. The host currently reports degraded by operator policy.
6. **T-1970** — authorize sending the two handoffs, or accept that six clauses
   stay `BLOCKED` and SRC-351 cannot close.
7. **8 `MARKHUNT_TRIAGE_REQUIRED` tickets** (T-1307…T-1314) — protocol requires
   explicit human triage before promotion to TODO. No agent may do this.
8. **T-1819** — 12 unmet clauses needing a genuine FreeBuff native
   input/worker bridge and a real Luna route with UI A–Q acceptance.

---

## Appendix — measured state at report time

```
board:   128 done / 104 open, all open rows blocked and measured
sections: DOING empty, TODO empty, all open in BLOCKED
default: Validation complete. Agent is conformant. (19 warning(s))
ship:    Validation FAILED: 2 problem(s), 19 warning(s)
         both = SRC-349/SRC-350 intake-to-archive staging (adjudicated,
         not staged -- .saipen/evidence/SRC349-SRC350-release-staging/)
family:  8548 ran, 3 red (all T-1816 external-root drift), record
         cd6cbf63e3de9b47-20261031T113725364334Z
git:     786 staged + tools/test_t1973_revalidate_accounting.py
         + tools/test_t1975_focused_route.py; nothing committed
external: T-1653 re-resolved to EX-000032 against the running generation
hook:    repo == installed == a04a2ef4 (34924 bytes)
```

The default gate being fully conformant is the campaign's clean end state. The
ship gate is not the same check: it additionally demands the whole release slice
be staged, and the two problems it reports are the staging decision described in
blocker 1 above, not a defect. The audit inbox reports 12 layers with unworkable
linked Work — no workable ticket remains.

One correction to the line this appendix carried before: it said
`saipen ticket resolve-external --revalidate` reports `discovered 0 / inspected 0
/ still_blocked []`. That was the T-1973 defect, not a healthy reading, and it is
fixed — the surface now names drift it declines to re-execute.

