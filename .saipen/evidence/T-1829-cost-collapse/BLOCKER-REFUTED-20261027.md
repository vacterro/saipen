# T-1829 stale-blocker re-measurement, 2026-10-27

T-1829's recorded blocker claims: *"112 Git objects are still absent from the
object database (missing commit 380b30f6... plus 111 blobs) and no reachable
remote can supply them... this is genuine corruption."*

That claim is no longer true. Re-measured against the current object database:

## The named commit exists and is reachable

```
git cat-file -e 380b30f6374f31e37d10919d1a4ded36be9dc598   -> exit 0
git cat-file -t 380b30f6374f31e37d10919d1a4ded36be9dc598   -> commit
git merge-base --is-ancestor <that commit> HEAD             -> exit 0 (ancestor)
```

## The whole recorded missing-object set is now present

Two recorded inventories were checked object by object with `git cat-file -e`:

| Inventory | Entries | Now absent |
|---|---|---|
| `.saipen/evidence/T-1829-cost-collapse/missing-object-paths.json` | 112 | 0 |
| `.saipen/evidence/T-1829-cost-collapse/current-missing-edges.json` `.missing` | 114 | 0 |

So the campaign's own bounded local recovery (E-16888: "134 new original
objects (109 trees, 24 blobs, one commit), 527 total rehashed") finished the
job after the blocker was written, and the blocker was never re-measured
against the result.

## Object-store health

```
git count-objects -v   -> 4 packs, 56373 in-pack, 3637 loose, 0 garbage
git fsck --connectivity-only
  error: refs/codex/turn-diffs/captures/1785165795234/fb80dcb4-.../base:
         invalid sha1 pointer 9d3542bdcbde564af2cd22f6237802c2ba924c4f
  dangling blob x2059
```

- The single error line is the already-owned foreign ref (INV-22), unrelated to
  T-1829 and untouched here.
- The 2059 `dangling blob` lines are unreferenced-but-present objects. They are
  the opposite of missing: nothing reachable is absent.
- `git rev-list --objects HEAD` enumerates 39 119 objects, and HEAD connectivity
  had no missing-edge report.

Verdict: **the "genuine corruption / needs an intact original object backup or
restored original remote history" blocker is refuted by measurement.** No
history was rewritten and no object was manufactured to reach this conclusion;
the measurement only reads.

## What actually remains

T-1829's own `ACCEPTANCE.md` final gate order still lists real work, and two of
those gates are genuinely blocked on things outside this ticket:

1. **Gate 4/5 — one full core-unit family on the final stable generation, plus
   the independent families.** Measured earlier this session:
   `core_unit.py evidence` on this shared worktree runs 8110 tests with 172
   reds, all from other actors' in-progress modules. The family cannot be green
   while that WIP is in the tree, and expanding the baseline to hide it is
   explicitly forbidden by the ticket itself.
2. **Gate 6 / publication.** The same 206 foreign pre-staged paths that block
   T-1817 and T-1856 would enter any release, and GitLab is only the configured
   destination, not a publication receipt.

Those are the same two classes already recorded honestly on T-1856 and T-1817.
The stale object-corruption claim should be replaced by them, not kept.

## Not claimed

- No PASS of any campaign gate.
- No publication, no commit, no push, no tag.
- No repair of the INV-22 foreign ref.
