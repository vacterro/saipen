# T-1969 — finding revision identity (campaign P0-B)

Both defects were reproduced against the pre-fix tree and are closed by the same
change. Scope: `tools/producer_backends/saipal_adapter.py`.

## D1 — a changed finding under an unchanged id was suppressed forever

The publisher mints its operation id as `f"{producer}-{fid.lower()}"` — the
finding id **alone** — and
`deliver_finding_to_audit_inbox` passes the bare id as `producer_item_id`.

`iter_new_qualified_findings` then built its suppression set from
`_committed_publication_finding_ids`, which returned those bare ids, and
subtracted it from every page:

    acknowledged = set(ack["ids"]) | committed
    fresh = [row for row in page
             if str(row.get("finding_id")) not in acknowledged ...]

So the unit of suppression was *a name*, not *a revision*.

The allocator does have the right guard — `audit_enqueue.enqueue` refuses a retry
whose bytes changed:

    if record.get("sha256") not in (None, digest):
        return _fail("CONFLICT", "a retry cannot change the audit body")

That guard was **unreachable from the walk**: the row was dropped before
publication was ever attempted. The guard is real and provably never asked.

Measured consequence: a finding revised under its own id yields **nothing**, and
the walk reports success. That is the campaign's "zero silently lost findings"
clause failing in its worst direction — not a crash, a quiet clean walk.

## D2 — a legacy ack row matched every corpus

    if source_digest is not None and row.get("source_digest") not in (None, source_digest):
        continue

The `None` inside the tuple is the whole defect: a row written *without* a
source digest was never skipped, for **any** corpus. One legacy row suppressed
its ids in every future report, including a different corpus where the same ids
are unrelated findings.

## The change

**D1.** `_committed_publication_ids` now returns `{finding_id: {published digests}}`
instead of `{finding_id}`. `record["sha256"]` is the layer digest of the audit
body — the same value the producer carries as `artifact_digest` — so the
comparison is exact, not heuristic. Suppression asks for the *pair*:

    digests = committed.get(fid)
    if not digests:
        return False          # an old row with no digest is RE-YIELDED
    digest = row.get("artifact_digest")
    return isinstance(digest, str) and digest in digests

`_committed_publication_finding_ids()` survives as the digest-blind id set, used
only by ack-journal compaction, which legitimately asks "has this id ever been
published?" rather than "is this revision out?".

**D2.** `_acknowledged_ids` keeps a row that names its corpus, and scopes a
digest-less row through the allocator: it may only suppress ids the allocator can
prove a committed publication for. With no provable digest the answer is empty,
which fails toward re-yielding — the walker's standing trade, because a duplicate
attempt is idempotent while a skip is unrecoverable.

## Controls

`tools/test_t1969_finding_revision_identity.py` — 4 tests, 2 defects + 2
negative controls. The controls matter as much as the defects: a fix that merely
re-yields everything would pass the defect tests and break idempotency.

| test | pre-fix | post-fix |
|---|---|---|
| changed bytes under a committed id are still yielded | **FAIL** | ok |
| an unchanged committed finding is still suppressed | ok | ok |
| a legacy row does not suppress a different corpus | **FAIL** | ok |
| a scoped row still suppresses its own corpus | ok | ok |

Pre-fix control is **in place**: only the two functions were reverted to their
old bodies with T-1967's machinery intact (`.saipen/evidence/T-1969-revision/prefix-inplace-red.log`).
Reverting to HEAD instead was rejected as confounded — HEAD predates T-1967's
`record_qualification`, so all four tests errored for an unrelated reason and the
control proved nothing.

## One existing test had to change, and why

`test_t1944_wave2.test_a_committed_allocator_operation_is_an_acknowledgment`
asserted suppression using a report row with **no `artifact_digest`**. That row is
not publishable at all — `deliver_finding_to_audit_inbox` answers
`ARTIFACT_DIGEST_MISSING` — so the fixture described a row this producer can never
emit, and honouring it would have preserved the defect. The test now carries the
digest of the bytes it actually published, keeping its original claim (the
allocator, not the cursor, is the durable truth) while making the fixture
representable.

## Limits

UNIT/CONTRACT only, over an injected page iterator. This proves the suppression
logic; it does not exercise transport, and it says nothing about an installed
host. No claim is made here about SAIPAL's own repository.
