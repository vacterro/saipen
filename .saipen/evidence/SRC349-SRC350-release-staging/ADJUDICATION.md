# SRC-349 / SRC-350 release staging — adjudicated, not staged

Measured 2026-10-31 after T-1973 closed. These are the last two `--gate ship`
problems on the tree. They are a staging gap, not a truth defect, and staging
them is a publication decision.

```
FAIL: binding ship gate requires every release metadata path staged:
      .../SRC-349.* (5 paths), .../SRC-350.* (5 paths), tombstones (2)
FAIL: staged release metadata differs from working-tree bytes:
      .saipen/intake/{active,contracts,coverage}/SRC-34[9].*, SRC-350.*,
      .saipen/intake/index.json            (9 paths)
```

Twenty-one paths, one slice.

## Every path verifies as a legitimate source closure

Both tombstones read `status: CLOSED`, `unresolved: 0`, `closure_event` set:

| source | closed_at | unresolved | linked_work | archived body sha256 |
|---|---|---|---|---|
| SRC-349 | 2026-10-31T06:24:20Z | 0 | T-1968 | `9f4ef072…0cc4b` |
| SRC-350 | 2026-10-31T06:23:08Z | 0 | T-1969 | `cd76b808…155e5` |

Each tombstone's recorded `source_sha256` **equals** the sha256 of its archived
body — computed here, not read off the record. Each `archive_ref` resolves to the
file that was hashed. Both coverage files carry one requirement each, marked
`VERIFIED` with the closing LOG line as its evidence, naming the ticket that
closed it.

## Who wrote them

T-1968 and T-1969 each closed through `saipen` on 2026-10-31 (E-19694 and
E-19702), and the archive carriers carry mtimes matching their own tombstone
`closed_at` to the minute (`06:23:08` / `06:24:20`). This is the canonical source
close doing its job — `saipen` moved each request out of `intake/active/` into
`archive/source/` when its Work finished.

That is why `git status` shows `AD` on the intake halves: the index still holds
the pre-archive intake bytes while the worktree holds the deletion. T-1972's own
stage predates both closures, so it could not have carried them.

## Why it is not staged here

`ship.md` step 6b.4 forbids `git add .` and `git add -A`, and requires every
staged path be attributed to a Work this ship owns. T-1973 is closed and its
scope is `external.py`, its oracle, and its evidence; it does not own a release
slice. Staging twenty-one archive paths under a closed ticket, minutes after
closing it, would be exactly the unattributed-tree-edit the campaign has been
fixing everywhere else.

The slice is mechanical and low-risk — but "mechanical" is not "authorized", and
the ship gate's whole-slice rule means whoever stages it is choosing what the
next publication unit contains.

## What clearing it needs

Stage the 21 paths as one explicit enumerated list (`git add -- <paths>`), which
is what T-1972 did for its own 1,386-path slice, and re-run
`python tools/validate.py --gate ship`. The two failures are then gone and the
gate is green with 18 warnings.

That is a publication action with a real decision inside it: these carriers
become permanent history for two closed sources. It belongs to whoever owns the
publication decision for this repository (T-1644, still open), not to a ticket
that closed on an unrelated surface.
