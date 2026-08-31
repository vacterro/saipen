# 01 — VERIFIED CURRENT FINDINGS

## F1 — Native Audit Inbox is real

Current binding:

- `audit/1.md` → SRC-012 → T-1222 → DELETED
- `audit/2.md` → SRC-013 → T-1223 → ACTIVE
- `audit/3.md` → SRC-014 → T-1224 → DELETED

This is the intended migration shape.

Do not rebuild the Audit Inbox from scratch.

## F2 — Focused Audit Inbox tests are green

The current supplied tree passes 57 Audit Inbox tests.

Preserve these as baseline.

## F3 — Sealed LOG history is missing from the working tree

Git reports tracked deletion of:

`.saipen/logs/LOG-001.md`
through
`.saipen/logs/LOG-015.md`

The filesystem currently contains no sealed LOG segment.

Active `.saipen/LOG.md` starts:

`E-4483 parent E-4482`

and E-4482 is absent from the working tree.

This is why validator fails the LOG graph.

Do not "repair" E-4483 by changing its parent.

Restore/reconcile the missing sealed history through the canonical ownership path.

## F4 — Current validator still has three FAIL classes

Current core gate reports:

- dangling E-4482 ancestry;
- historical Improve sweep ticket-link failures;
- `_AUDAPACK_MANIFEST.json` root-file-set contamination.

Fix owners, not checks.

## F5 — Current release metadata also has drift warnings

Current warnings include:

- VERSION 7.231.11 while CHANGELOG head is 7.231.10;
- tag v7.231.11 without CHANGELOG entry;
- stale `.saipen/kitchen/digest.md`;
- oversized active BOARD;
- oversized active LOG;
- stale/uncollected SubSaipen packages.

Do not mix all of these into the active phase-compression edit.

Handle them in release/cleanup wave after correctness is restored.

## F6 — Active phase compression is only partially done

Current phase total:

~100,304 bytes.

Largest current files:

- ship ~12.8 KB
- translate ~10.9 KB
- verify ~10.2 KB
- markhunt ~10.2 KB
- clean ~9.8 KB
- add ~8.1 KB
- hunt ~7.5 KB

Only ship/translate/markhunt/clean are modified in the current working tree.

The entire 16-phase target is therefore not yet finished.

## F7 — T-1226 acceptance is mathematically inconsistent

T-1226 says roughly:

- compress ship to <=9 KB;
- translate to <=8 KB;
- markhunt <=10 KB;
- clean <=10 KB;
- entire phase corpus <=70 KB.

The other twelve current phases alone are ~56.6 KB.

At the listed four-file targets, total phase corpus would still be about 93–94 KB.

Therefore the ticket cannot honestly satisfy both its local and global verification conditions.

Repair the Work contract before further aggressive deletion.

## F8 — SRC-013 contains premature VERIFIED dispositions

Current coverage marks many criteria VERIFIED using the same generic E-4799 evidence.

At least these require re-evaluation:

### R003
"each phase has one compact consistent structure"

Current phase documents visibly do not share one structure. Many have only one heading; only a subset has Purpose/Entry/Procedure/Exit sections.

### R010
"phase lifecycle does not depend on user-visible narration"

The requested dedicated readiness test is not present. Existing narration test covers continue-fallback payload only.

### R016
"validator, scenarios and golden tests remain green"

Current core validator is not green.

### R017
"a clean checkout reproduces the same result"

The supplied worktree is substantially dirty and includes untracked/moved runtime artifacts. This criterion cannot currently be claimed proven.

Other VERIFIED clauses should also be audited for actual clause-specific evidence rather than inherited generic wording.

## F9 — Audit Inbox has a blocked-layer routing hole

Current projection selects the first ACTIVE audit layer and returns it.

The router then checks whether its linked Work is workable.

If that lower ACTIVE layer is blocked/unworkable, the router falls through to ordinary BOARD selection.

It does NOT ask the inbox for a later workable audit generation.

This violates the intended:

`lowest-numbered WORKABLE audit`

semantics.

Required missing regressions:

- audit/1 ACTIVE blocked, audit/2 ACTIVE workable → audit/2 must own continuation;
- audit/1 ACTIVE blocked, audit/2 NEW → audit/2 ingestion must own continuation before ordinary BOARD.

## F10 — Status invalid-list duplication bug

The current Audit Inbox projection constructs `invalid` with a duplicated nested iteration.

With multiple invalid layers this can produce N×N repeated diagnostics.

Fix while hardening the module.

## F11 — Shared producer allocator is absent

There is no central monotonic:

`audit enqueue`

boundary yet.

SAIPAL/AUDAPACK must not each invent their own numbering and atomic-write behavior.

## F12 — HUSH remains planned

This is correct.

Do not flip REGISTRY to implemented until a real task-local policy exists.
