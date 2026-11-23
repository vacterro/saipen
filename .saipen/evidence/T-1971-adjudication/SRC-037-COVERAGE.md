# T-1971 -- adjudication of SRC-037's overwritten archive coverage

## The measured shape

`saipen source status SRC-037 --json` -> `SOURCE_CORRUPTION`, detail
"source SRC-037 Contract/coverage clause identities differ",
`terminal: true`, `recoverable: false`.

The bundle on disk:

| file | bytes | sha256 | vs HEAD intake |
|---|---|---|---|
| `.saipen/archive/source/SRC-037.contract.json` | 951 | `1ce989ef…` | identical |
| `.saipen/archive/source/SRC-037.md` | 1719 | `b1393000…` | identical |
| `.saipen/archive/source/SRC-037.meta.json` | 1048 | `91210e0f…` | differs (closure rewrite) |
| `.saipen/archive/source/SRC-037.coverage.json` | 8772 | `6eacdf24…` | **differs** |

All four intake carriers are absent from the worktree.

The contract declares 4 clauses, `SRC-037:R001` .. `SRC-037:R004`
(invariant / requirement / acceptance-criterion / non-goal, all `actionable`).
The archive coverage declares **16** requirements with `work` fields T-71..T-86
and evidence `tests/probe_audit_inbox_fixes.js` -- a JavaScript project. Those
ticket ids exist on `_PLUG_SCRIPT/_FREEBUFF_SAI`'s BOARD (T-71 "CORE-001: Fix
idle_guard.js inverted state check" through T-86 "PERF-005: Bounded
deduplicated journal diagnostics"), not here.

## The truthful bytes still exist in the repository

`.saipen/intake/coverage/SRC-037.json` **at HEAD** holds 4 requirements whose
ids are exactly `SRC-037:R001` .. `SRC-037:R004`. Identity comparison against
the contract's 4 clause ids: **True**. Its bytes are
`b11d8cf9fda1098a9665e99e76fadd71bde621ed9435a3db16753da954151f01`
(1,700 bytes). The archive copy carries no `source_sha256` field at all, which
is itself a signature of a foreign overwrite -- every canonical coverage file
on this surface carries one.

So the truth about this receipt is recoverable from committed bytes without
guessing or inventing a single disposition. That is a fact about the data, not
a licence to hand-edit a canonical file.

## Every CLI repair route measured and refused

| route | answer | why |
|---|---|---|
| `saipen source reconcile SRC-037` | `SOURCE_CORRUPTION`, `recoverable: false` | survey refuses, strong proof does not agree |
| `saipen source reconcile SRC-037 --confirm` | (not attempted) | wrong shape: `reconcile_receipt` reads `intake/active/*` and WRITES the archive; this receipt has no intake carriers and a present archive (`intake.py:6053-6210`) |
| `saipen source retire SRC-037 --reason EMPTY_STALE_SOURCE` | `ALREADY_RETIRED` | "SRC-037 already carries a tombstone; retirement never rewrites it" |

The docs put the remaining candidate in terms of policy, not a verb:
SOURCES.md:203 -- "Evidence-backed system correction can retire an
empty false-authority projection/non-Work without claiming implementation."
That is the reasoning gate; it is not a command.

## What this ticket has NOT done, and will not do without a decision

- The corrupt bytes are **not** deleted. A byte copy is preserved at
  `.saipen/evidence/SRC-037-coverage-overwrite/corrupt-coverage-preserved.json`
  (sha256 `6eacdf24…`).
- `.saipen/archive/source/SRC-037.coverage.json` has **not** been hand-edited.
- The tombstone has **not** been rewritten, and no counter was adjusted.

## The coupling T-1972 created

T-1972's staging decision pinned this corrupt file into the index, because the
ship gate demands every one of the 1,386 changed release-metadata paths staged
and this is one of them. That is the gate's whole-slice rule working as
designed, and it creates a real ordering constraint: **no commit may land on
this index until this ticket resolves the bundle**, or the corruption becomes
permanent history.

## The decision this ticket needs

One of:

(a) **Implement a canonical verb** for the archive-present/intake-absent
    contradiction -- the mirror of what `reconcile_receipt` already does in the
    opposite direction -- and let it restore the archive coverage from the
    committed intake bytes under the writer lock, journalled.
(b) **A journalled, evidenced restore** of the archive coverage from
    `git show HEAD:.saipen/intake/coverage/SRC-037.json`, recorded as a system
    correction with that exact provenance, not as an authored ledger.
(c) **Retire the receipt** with a recorded reason, accepting that a CLOSED
    tombstone already exists and must then be superseded explicitly.

(a) is the only option that fixes the class rather than the instance, and this
campaign's charter is "close remaining causal gaps; do not rebuild existing
systems" -- a verb is an addition, not a rebuild. (b) is the minimum honest
unblock. (c) discards a real verified receipt and should be last resort.

## Addendum: `source normalize` measured too

The fourth candidate route has now been tested rather than reasoned about:

    $ saipen source normalize --dry-run --json
    {"ok": true, "code": "ALREADY_NORMALIZED", "expanded": {}, "rewrites": 0}

`normalize` maps to `intake.normalize_receipt_ranges` (`saipen.py:6732-6744`)
and is about receipt-id RANGE expansion, not coverage content. It has nothing to
say about this bundle.

That closes the full list of `source` verbs that could plausibly repair an
archive bundle: `reconcile` (refuses), `reconcile --confirm` (wrong shape),
`retire` (refused, tombstone exists), `normalize` (unrelated). The canonical
writer of archive coverage is `_write_coverage` (`intake.py:658`), which
addresses `.saipen/intake/coverage/<id>.json`, and the only code that writes
`.saipen/archive/source/<id>.coverage.json` is the archive/close transaction
and the recovery transaction at `intake.py:6233`.

**Conclusion: repairing this bundle requires a code change or a deliberate
journalled restore. It cannot be done with the commands this CLI offers today.**

## RESOLVED (journalled restore from committed truth)

The repair executed was option (b) from the list above: a restore of the archive
coverage from `.saipen/intake/coverage/SRC-037.json` **at HEAD**, using the
engine's own primitives -- `intake.project_writer_lock` and
`intake._atomic_write` -- so the write is serialised against every other
canonical writer and lands atomically. No ledger content was authored,
invented, or re-derived by hand; the bytes written are the bytes git already
holds for this receipt.

    BEFORE .saipen/archive/source/SRC-037.coverage.json
      6eacdf2473f9fb22801251615f58789b6eea18535440e8674750c7b16ac8ea72   8772 bytes
    RESTORE source: HEAD:.saipen/intake/coverage/SRC-037.json
      b11d8cf9fda1098a9665e99e76fadd71bde621ed9435a3db16753da954151f01   1700 bytes
    AFTER
      b11d8cf9fda1098a9665e99e76fadd71bde621ed9435a3db16753da954151f01   1700 bytes

Pre-restore validation, run offline against the genuine contract before touching
the file:

    coverage ids: ['SRC-037:R001','SRC-037:R002','SRC-037:R003','SRC-037:R004']
    contract ids: ['SRC-037:R001','SRC-037:R002','SRC-037:R003','SRC-037:R004']
    _validate_contract_coverage: PASS
    summary: {'requirements': 4, 'actionable': 4, 'unresolved': []}

Independent corroboration that 4/4 is the truth, from three sources that do not
share a writer:

1. the contract's 4 clause ids, in the archive bundle;
2. the tombstone (`4 actionable, 0 unresolved, CLOSED`) committed earlier;
3. HEAD's intake coverage, which is what was restored.

### Preservation

The corrupt bytes are **not** lost. A byte-identical copy sits at
`.saipen/evidence/SRC-037-coverage-overwrite/corrupt-coverage-preserved.json`,
verified by `sha256sum` to be `6eacdf24…413e...` both before and after this
repair. The overwrite is still forensically readable in full: 16 requirements,
work T-71..T-86, evidence `tests/probe_audit_inbox_fixes.js`.

### Measured result

    $ saipen source reconcile SRC-037 --json
    {"ok": true, "code": "ALREADY_RECONCILED", "terminal": true,
     "contradictions": [], "findings": {"index_tombstone": "present"}}

`tools/validate.py --gate ship` (`ship-gate-final.log`):

| | PASS | FAIL |
|---|---|---|
| start of T-1971 | 52 | 6 |
| after relocating the stray root file | 52 | 2 |
| after this restore | **52** | **1** |

The single remaining failure is EX-000029's closure provenance -- the
installed engine generation moved (`06c1149a…` -> `96e9c936…`), so a previously
verified external implementation must be re-resolved truthfully rather than
inherit a stale green. That is a real finding about a different subject and is
not claimed here.

### Honest scope note

This repaired the **instance**. The **class** -- no canonical verb exists for the
archive-present/intake-absent contradiction -- is unchanged and remains the
larger finding recorded above. Option (a), implementing that verb, is still
unbuilt; the restore above had to reach for `intake._atomic_write` directly
because no command offers it.
