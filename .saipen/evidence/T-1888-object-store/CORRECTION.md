# T-1888 — the recorded damage does NOT reproduce; only one foreign ref is broken

Read-only re-measurement of the git object store on 2026-10-24, before treating
T-1888/T-1887 as a repair job. **Everything the ticket records as damage,
except one foreign ref, is healthy.** No mutation was performed; the foreign ref
was not removed (INV-22).

## What the ticket claims

> 889 of 1133 HEAD-reachable commits and 395 of 396 tags are unreadable,
> packed-refs names 5 packs but only 3 exist, and one foreign ref
> `refs/codex/turn-diffs/captures/.../base` points at a missing object.

## What is actually true

| Claim | Measured now | Verdict |
|---|---|---|
| 889/1133 HEAD commits unreadable | `git rev-list HEAD` = **1133**; `git cat-file -e` on every one = **0 unreadable** | **does not reproduce** |
| 395/396 tags unreadable | `git for-each-ref refs/tags` exits **0** with **396** rows; every tag row peels to a commit (`objecttype tag` + `*objecttype commit`) | **does not reproduce** |
| packed-refs names 5 packs, only 3 exist | `packed-refs` (684 lines) names **0** `.pack` files; disk holds **4 packs with 4 idx** | **does not reproduce** |
| one foreign ref points at a missing object | **confirmed**: `refs/codex/turn-diffs/captures/1785165795234/fb80dcb4-.../base` → `9d3542bd…`, absent locally, absent from both remotes | **true** |
| `git fetch --refetch` fails on that ref | **confirmed**: `fatal: bad object refs/codex/...`, `did not send all necessary objects` | **true** |

## Where the inflated numbers most likely came from

The T-1885 investigation proved the mechanism: a single `git for-each-ref` with
no pattern **refuses the whole ref set** when any one ref is unreadable, exiting
128 with **no rows at all**. Any script that builds a peel/readability map from
that call and counts "absent from the map" as "unreadable" reports a large
fraction of a healthy store as destroyed. That is the same silent-zero defect
T-1885 fixed in the validator, observed from the other side.

The exact 889-vs-1133 split is consistent with such a partial/absent map, not
with real corruption: a store missing 889 of its own HEAD commits could not
produce a working 1133-commit `rev-list`, a clean `cat-file -e` on every one, a
successful `git log -S` over history, and 396 fully peeled tags at the same
time.

## The ticket's own verify clause, measured

| Clause | State |
|---|---|
| `git fsck --connectivity-only` reports no missing objects reachable from HEAD | **satisfied for HEAD**; fsck's only complaint is the foreign ref (`invalid sha1 pointer 9d3542bd…`) |
| `git for-each-ref refs/tags` succeeds and no unreadable-tag warning | **already satisfied** — exit 0, 396 rows, no `could not be peeled to commits` warning in the validator |
| `git log -S` works on a known historical string | **already satisfied** — `git log -S "T-1479"` returns `8ddab6a3` |

## Consequence for the decision the operator is being asked for

The recorded blocker would justify a full `git fetch --refetch` recovery. The
measured state does not: **nothing reachable from HEAD is missing, no tag is
unreadable, no pack is absent.** Exactly one stale foreign ref names an object
that exists on neither `origin` nor `github-backup`, and that object is
therefore unrecoverable.

The narrow, honest remediation is to drop that single stale ref:

```
git update-ref -d refs/codex/turn-diffs/captures/1785165795234/fb80dcb4-2cd2-4789-9618-a9409baff787/base
```

That ref belongs to another actor's tooling (`codex/turn-diffs`), so removing it
is INV-22 territory: it needs the operator's explicit decision naming that ref.
This campaign did not run it and did not edit `packed-refs` by hand.

After that ref is gone, `git for-each-ref` enumerates normally again, which is
what the remaining symptoms actually come from — the nine `xpatch-survival`
warnings in the validator all read `Git history unreadable: fatal: bad object
refs/codex/...`, i.e. the same single cause.

## Reproduction

```bash
git rev-list --count HEAD                                  # 1133
git cat-file -e <each of git rev-list HEAD>                # all succeed
git for-each-ref refs/tags; echo $?                        # 0, 396 rows
git for-each-ref; echo $?                                  # 128, fatal bad object
git fsck --connectivity-only                               # only the foreign ref
git log -S "T-1479" --oneline -- tools/saipen_engine/core_unit.py
```

## What this does NOT claim

- Not that the store is pristine: the foreign ref is genuinely broken and does
  break whole-ref enumeration and `git fetch`.
- Not that the earlier measurement was dishonest — it is the exact false-zero
  shape T-1885 documented, and the ticket was written from it.
- Not that the repair is therefore optional: `git fetch` is broken until the ref
  goes, and that is an operator decision, not an agent one.
