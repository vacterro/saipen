# Concurrent REVIEW evidence writers

At 2026-10-03T21:02Z, two independent Python wrappers were running the identical canonical full audit against this project:

* This turn's tool session 7030: wrapper PID 26584, audit child PID 26368, started 20:52:09Z.
* A second writer: wrapper PID 12924, audit child PID 14092, started 20:52:20Z.

Both legacy wrappers target `REVIEW-audit-longpaths.stdout`, `.stderr` and `.json`. Shared raw output therefore cannot be attributed uniquely to either invocation. These files must not be described as an immutable per-run transcript. The host tool session's actual exit status and the unchanged native verification records are separate evidence.

The second writer also appended E-12195 through E-12199 after this turn's REVIEW transition E-12193. The live canonical state remains REVIEW T-1283, goal_tickets 13; stale remembered phase/event values were discarded. No production edit is safe while either audit remains in flight.

The wrapper now accepts an optional validated run identifier that changes only destination filenames. Audit argv, cases, predicates, native Git configuration and timeout stay identical. Already-running wrappers retain their loaded legacy filename behavior. Future evidence runs can use separate output paths without altering the verifier.
