# The ship gate has six failures and five tickets parked behind them

Measured 2026-10-30/31 across T-1966, T-1967, T-1968, T-1969 and T-1970.
Every one of those tickets records `PUBLICATION_BLOCKED_EXTERNAL`, and every
one was blocked by the same list. That is not five pieces of bad luck.

```
52 PASS / 6 FAIL   (T-1969, T-1970)
51 PASS / 6 FAIL   (T-1970 measured again the same cycle)
 4 FAIL            (T-1968, before two contamination artifacts appeared)
```

## The six, and who actually owns each

| # | failure | owner | is it real drift? |
|---|---|---|---|
| 1 | `SRC-037 archive bundle invalid` | nobody | **no — contamination** |
| 2 | `EX-000029 closure provenance drift` | release owner | yes, stale since 18:26 |
| 3 | `release index is empty` | release owner | yes, nothing staged |
| 4 | `staged release metadata differs` | release owner | yes, 623 paths |
| 5 | `cross-doc drift [root-file-set]` | nobody | **no — contamination** |
| 6 | `coverage gap` | nobody | **no — same file as 5** |

So the honest count is **two contaminants, one stale verdict, and one
un-staged release slice** — not six independent release defects.

## Contaminant 1 — SRC-037's coverage was overwritten with another project's work

`.saipen/archive/source/SRC-037.coverage.json`, mtime
`2026-10-30T18:50:46`, sha256 `6eacdf24…c8ea72`:

| surface | clauses | source_sha256 |
|---|---|---|
| `SRC-037.md` (body) | — | `b1393000…db3656d` |
| `SRC-037.contract.json` | 4 (evidence-ownership) | `b1393000…db3656d` |
| `SRC-037.meta.json` | — | `b1393000…db3656d` |
| tombstone | 4, `unresolved: 0`, CLOSED 02:41:56 | `b1393000…db3656d` |
| **`SRC-037.coverage.json`** | **16 (unrelated)** | **absent** |

The 16 clauses are not about evidence ownership at all. They describe
`HandledDigestRing`, `CdpClient.send` deadlines, SSE cancellation and
`_atomicReplace` ENOTSUP dedupe, their evidence cites
`tests/probe_audit_inbox_fixes.js`, and their `work` field names **T-71…T-86** —
a JavaScript project's tickets, in `_FREEBUFF_SAI`, which does have T-71 through
T-86 on its board.

Nothing else under `.saipen/` was written in the 18:45–18:55 window. One file.
No journal event records it (`grep SRC-037 .saipen/LOG.md` → 0 hits).

`saipen source reconcile SRC-037` answers `SOURCE_CORRUPTION`,
`recoverable: false`, `terminal: true`. The corrupt bytes are preserved verbatim
at `.saipen/evidence/SRC-037-coverage-overwrite/corrupt-coverage-preserved.json`
(`6eacdf24…c8ea72`) — nothing was deleted, and no canonical file was hand-edited.

## Contaminant 2 — a root file that arrived during a family-gate run

`SAIPENFUTURE_CONTEXT_GRAPH_20260909_1811.md`, mtime `2026-10-31T02:21:10`,
21,470 bytes, sha256 `fb2e2381…395e412`, untracked, absent from HEAD.

It is **not** a copy of any archived `.workbuddy-ai/` version: all seven on disk
are 19,079 bytes / 633 lines / `db73173e…`; this is 768 lines. It is a newer
expansion. It appeared at the repo root where no code writes that name, in the
only second anything was written in that 40-minute window, while this session
executed **zero** commands between 01:03:11 and 03:22:27.

`validate.py` names the likely writer class itself, in its own failure text
(`HOST_HOOK_RUNS_PAYLOAD`): the Claude settings hooks are invoked through
`cmd.exe /c` and the hook payload — text an agent read — is then executed as
commands.

## Why this matters more than "five tickets are blocked"

These two contaminants are the same defect as the campaign's subject. The
FreeBuff audit (SRC-351) is about a protocol command being answered by the wrong
owner. Here a *project* answered work belonging to another project: a
JavaScript repository's tickets written into `_SAIPEN`'s closed archive, and
foreign text written into `_SAIPEN`'s repository root, both attributed to nobody,
both blocking release for five tickets.

The asymmetry that let it persist: the ship gate can detect that a closed
bundle disagrees with itself, but nothing in it records *who wrote* the
disagreeing bytes. `closure_event` for SRC-037 is `null`. So the gate says
"this is broken" and cannot say "this is not yours".

## What is deliberately not done here

- Neither contaminant was deleted. Both are preserved with their digests.
- No `git add`, no staging of the 4,221-path release slice, no tag, no push.
- No counter was edited to make the ticket count look better.
- T-1966, T-1967, T-1968, T-1969 and T-1970 each record their own
  `PUBLICATION_BLOCKED_EXTERNAL` with their own measured evidence; none claims
  DONE.

## What recovery actually needs

1. The release owner decides what the 4,221-path intake→archive migration is
   (618 deletions, 636 untracked carriers, `.saipen/intake` wholesale in
   `release_metadata_paths`) and stages it deliberately. Until then failures 3
   and 4 cannot clear, and `git add .` is forbidden by `ship.md` 6b.4.
2. `EX-000029` is re-resolved against the running engine, not inherited.
3. Both contaminants are adjudicated by whoever owns the host hooks and the
   cross-project write path — after which either the SRC-037 bundle is restored
   from a truthful 4-clause ledger, or the receipt is retired with a recorded
   reason. This ticket cannot decide it: `_FREEBUFF_SAI`'s own SRC-037 covers an
   empty requirement set, so there is nothing to hand back to.

---

## 2026-10-31 update: the blocker now has owners and two fewer failures

When this document was written the ship gate answered **52 PASS / 6 FAIL** and
none of the six belonged to the ticket that tripped them. That is no longer the
shape.

T-1972 measured the release-metadata slice (`release_metadata_paths`, 4,242
paths), adjudicated all 1,386 `need_staging` paths -- 618 intake deletions each
with a verified archive counterpart, 636 untracked archive carriers each bound
to a tombstone id, and 5 modified canonical state files -- and staged them as an
explicit enumerated list. Result: **`release index is empty` and `staged release
metadata differs from working-tree bytes` are both gone.** 52 PASS / 4 FAIL.

The 4 remaining failures are now attributed:

| failure | owner |
|---|---|
| SRC-037 archive bundle invalid (Contract/coverage identities differ) | T-1971 |
| EX-000029 closure provenance -- engine generation moved | release/closure owner |
| cross-doc drift [root-file-set] -- stray root file | T-1971 |
| coverage gap -- same stray root file | T-1971 |

## Correction to the stray-file attribution in this document

The earlier section called the stray root file host-hook contamination, citing
`validate.py`'s `HOST_HOOK_RUNS_PAYLOAD` line. That was my inference. The
validator's own word is "Likely", and `host_hooks.stray_hint` (`host_hooks.py:
119-132`) builds it from settings-file parsing alone -- it never observes a
write. Content contradicts the hook theory: the file is 21,470 bytes of
structured roadmap prose, its first 633 lines are byte-identical (CRLF
normalised) to
`.saipen/evidence/tool-module-identity/subject/.workbuddy-ai/SAIPENFUTURE_CONTEXT_GRAPH_20260909_1811.md`,
and 134 appended lines cover work-attempt identity, "Re-derive on wake",
hypothesis/dead-end memory, integration invariants, collision projection and
delta context -- coherent writing, not payload fragments executed as commands.
Full analysis: `.saipen/evidence/T-1971-adjudication/STRAY-ROOT-FILE.md`.

Hook payload execution produces the empty-stray shape T-1475 names (`BLOCKED`,
`M``). It does not produce this.

## The ordering constraint T-1972 created

Because the ship gate demands the whole 4,242-path slice staged, T-1972's stage
pinned SRC-037's corrupt coverage bytes (`6eacdf24…`) into the index. That is
the gate's whole-slice rule working as designed, and it means **no commit may
land on that index until T-1971 resolves the SRC-037 bundle**, or the
corruption becomes permanent history. The pre-ship index tree is backed up as
`86b0736715f4c4ec40649539ea9e84a6823fefc0`
(`.saipen/evidence/T-1972-release-slice/pre-ship-index-tree.txt`).
