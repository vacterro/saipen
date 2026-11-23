# T-1904 SCOUT — measured before implementation, session stopped by operator

Status: claimed, phase SCOUT. No engine edit is in the tree: the draft
`_ProjectBinding` change to `tools/saipen_engine/log.py` was written and then
reverted byte-for-byte when the operator issued `saipen stop`. `log.py` holds
only its pre-existing uncommitted diff, and `test_log_detail_evidence` is
11 tests OK (1 skipped: this host cannot create symlinks).

## Baseline (`continue --json`, 5 runs, live tree)

    2.604  2.598  2.624  2.651  2.657
    median 2.624 s   min 2.598   max 2.657

## Profile (cProfile, 3.959 s profiled — profiler overhead inflates it)

    _continue                                  3.784
    _next_action                               2.022
    reconcile_protocol_state                   1.702
    _route_once                                1.117
    fast_check.validate_project                0.770
    operations._read                           0.657
    snapshot.capture                           0.578
    read_history_snapshot_and_logs_digest      0.564
    queued_source_projection                   0.309   (was 0.713 before T-1903)

**Three complete history passes per `continue`**, each parsing all 18 103 events:

| pass | entry point | cost |
| --- | --- | --- |
| mutation preconditions | `operations._read` | 0.540 s |
| post-read validation | `fast_check.validate_project` | 0.600 s |
| routing snapshot | `snapshot.capture` | 0.593 s |

## Hot spot A — project identity re-proved per compacted event

    18 103 events per pass, 555 carry `detail_ref` (551 valid, 4 invalid)
    _restored_detail_text calls per continue:  54 309  (18 103 x 3)
    _read_detail_text calls per pass:           1 665
    _owned_detail_bytes calls per pass:         1 092  (metadata + payload)

Each `_read_detail_text` re-derives the project's identity before it will trust
one event's bytes:

    root.resolve()                0.0937 ms -> 555 calls = 0.0443 s
    project_lineage_identity()    0.1563 ms -> 555 calls = 0.0980 s
    ----------------------------------------------------------------
    0.142 s per pass, 0.427 s over the three passes of one `continue`

This is repetition of one fact about the PROJECT, not about the event. A hoist
is only sound if the carrier cannot move under the pass, so the planned design
was not a cache: prove once, defer every restoration, re-prove at the end of the
pass, and discard all restorations if the carrier moved. That is strictly safer
than the per-event read it replaces, which today honours a mid-pass rewrite for
the early events and refuses it for the late ones.

Per-event bytes stay re-read and re-hashed either way; only "which project is
this" is shared.

## Hot spot B — the two `validate_project` reads are NOT interchangeable

Reusing `_read`'s `HistorySnapshot` inside `validate_project` measures well:

    baseline validate_project                 0.492 s -> 0 errors
    reusing the already-read snapshot         0.100 s -> 0 errors
    saving per call                           0.393 s
    identical verdict                         True

**But it is blocked, and the block is real, not theoretical.** The two readers
derive `max_ticket_id` by different rules over the same bytes:

    read_history_snapshot          `ticket:` FIELD of each parsed event     -> 1903
    read_history_snapshot_and_logs_digest   `[T-\d+]` ANYWHERE in the line  -> 1903

    ids the bracket rule sees and the field rule does not:
        1304, 1375, 1493, 1494, 1607, ...

Today the two values happen to coincide (both 1903), but they are computed from
different evidence and the bracket set is a strict superset. Substituting one
snapshot for the other would silently change which ticket ids the validator
considers reserved the first time a `[T-####]` mention appears in prose without
a matching `ticket:` field. Landing that requires deciding which rule is
canonical and pinning it — its own ticket, not a drive-by.

## Dead end confirmed (do not revisit)

`_DETAIL_CACHE` is written 54 309 times per `continue` and read by **nothing**
outside `test_log_detail_evidence`, which clears it. It is not a missed cache
hit: the comment at its definition states entries are never reused as authority
so same-process tampering cannot hide behind a previously valid resolution.
Removing the writes would be safe but saves only dict stores, not I/O — not
worth a ticket against the measured 2.624 s.

## Next exact action when this ticket is resumed

Implement hot spot A with the deferred-restoration + end-of-pass re-proof
design, then measure `continue` against the 2.624 s median. Hot spot B needs a
rule decision first and should be filed separately.
