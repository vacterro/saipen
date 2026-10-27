<!-- SAIPEN KNOWLEDGE CARD v1 -->
kind: trap
scope: protocol evidence files, project writer lock, whole-tree digest oracles, Windows
trigger: a critical section writes diagnostic bytes beside a permanent lock carrier and releases without withdrawing them
status: active
evidence: T-1827, .saipen/evidence/T-1827-writer-lock/, tools/saipen_engine/lock.py _write_holder_record/_clear_holder_record
supersedes: none

# A diagnostic sidecar written under a lock is project bytes that outlive the operation

The writer lock is a permanent zero-byte carrier, so its own existence is not project state. A holder record beside it is different: it is fresh bytes on every acquisition. Released without withdrawal, those bytes stay pinned to the last holder forever.

Why:
Two damages follow, and neither shows up in the test that introduced it. First, an oracle that digests the whole tree (`test_closure_provenance._tree_digest`, and any dry-run/refusal byte-purity control) sees its "unchanged after a REFUSED operation" assertion fail: the refusal is byte-pure for canonical files, but the earlier successful operation left a sidecar behind, and the digest moved between the `before` and `after` snapshots of the REFUSED one. Measured: same test passed in isolation and failed once in a 6-shard family run, then 1-in-6 in a tight repeat loop. Second, the record outlives its holder, so a later free lock still names a dead PID as "last holder" -- the precise stale-lock guess R002/R010 exist to remove.

How to apply:
- Write the record only while holding the mutex; delete it inside `release()`'s `finally`.
- Withdraw only your own bytes: re-read the record and compare `pid` AND `acquired_at` before unlink, so a successor that took the mutex in the window keeps its record.
- Keep the failure path covered: an acquisition that raises before the write publishes nothing, so a refused writer never leaves a record either.
- Test the cycle, not the hold: acquire/release leaves no sidecar, and a rewritten record survives the old holder's release.
- `core_unit`'s tree fingerprint excludes `.saipen`, so a filesystem-level log/board write under `.saipen` does not stale a family record -- but a digest oracle built by the test itself may not exclude it. Check each oracle's own exclusion list before assuming.
