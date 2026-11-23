# T-1888 — git object store: premise re-measured and disproven

**Ticket:** T-1888 [P2]
**Date:** 2026-10-27
**Measurement:** `.saipen/evidence/T-1888/measure_store.py` (read-only, exit 0)
**Log:** `.saipen/evidence/T-1888/measure.log`

---

## 1. The claim

The ticket states: *"889 of 1133 HEAD-reachable commits and 395 of 396 tags are
unreadable, packed-refs names 5 packs but only 3 exist, and one foreign ref…"*

If that were true, the repository would be substantially destroyed. It is not.
Every clause was measured against the live store.

## 2. Measured result

| Condition from the verify clause | Measured | Verdict |
|---|---|---|
| `git fsck --connectivity-only` reports no missing objects reachable from HEAD | 1133 reachable commits, **0 unreadable** (`cat-file -e` per commit) | satisfied |
| `git for-each-ref refs/tags` succeeds | exit 0, **396 tags**, 0 unreadable (`rev-parse --verify` per tag) | satisfied |
| `git log -S` works on a known historical string | exit 0, 5 commits for `finding_invalidated` | satisfied |

The validator's unreadable-tag warning is also absent from `saipen validate`.

Against the literal claim:

- **889 unreadable commits → 0.** Every one of the 1133 HEAD-reachable commits
  resolves.
- **395 unreadable tags → 0.** All 396 tags resolve.
- **"5 packs named, 3 exist" → 4 `.pack` files and 4 matching `.idx` files.**
  No pack is missing and none is orphaned.
- **"one foreign ref" → true, and it is the only real defect.** It is
  `refs/codex/turn-diffs/captures/1785165795234/fb80dcb4-…/base` in
  `packed-refs:2`, pointing at `9d3542bd…`.

## 3. The one real defect, and why it is not this ticket

`git fsck` exits 2 with exactly one non-dangling line, that foreign ref:

```
error: refs/codex/turn-diffs/captures/1785165795234/fb80dcb4-…/base:
       invalid sha1 pointer 9d3542bdcbde564af2cd22f6237802c2ba924c4f
```

The target object is genuinely absent (`git cat-file -t` → 128). But it is
**not reachable from HEAD**: `git rev-list HEAD` and `git rev-list --all` both
contain it zero times, and `git show-ref` rejects only that one ref while every
other ref is fine. The verify clause is scoped to *"missing objects reachable
from HEAD"* — this object is outside that scope by construction.

`refs/codex/` is another tool's namespace, written into this store by a
`codex`-side turn-diff capture. Deleting or rewriting it is the separately
tracked **INV-22** cleanup (`git update-ref -d refs/codex/turn-diffs/…/base`),
which is an operator-authorized action and is deliberately not performed here.
Repairing it would also not change a single number in this ticket's claim.

## 4. Verdict

**The premise is disproven.** There is nothing to repair at the scale the
ticket describes, and the three verify conditions already hold on the live
store without any change. The residual — one dangling foreign ref — belongs to
INV-22 and is out of this ticket's scope and authority.

Closing under `finding_invalidated` is the honest mode: the ticket's own
measurement (recorded in its block at E-17889) already said the damage does not
reproduce, and this pass confirms it with per-object evidence rather than a
summary count.

## 5. T-1887

T-1887 is the same defect, claimed three seconds earlier, and its blocker
already records "SAME DEFECT AS T-1888, measured once". One measurement answers
both; this ticket carries it, so T-1887 should be superseded by this closure
rather than measured a second time.
