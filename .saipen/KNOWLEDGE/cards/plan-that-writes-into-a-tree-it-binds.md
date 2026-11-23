<!-- SAIPEN KNOWLEDGE CARD v1 -->
kind: trap
scope: engine operations built on OperationPlan, read-only tree dependencies, journal recovery, crash injection tests, sealed LOG segments
trigger: writing an operation whose target lives inside a directory the plan also binds as a read dependency, for example a new file under .saipen/logs
status: active
evidence: T-1640, tools/saipen_engine/operations.py (_sealed_segment_bindings, seal_log), tools/test_t1640_log_seal.py (InterruptedSealTests, BindingTests), .saipen/evidence/T-1640-caps/mutate1640.out.txt
supersedes: none

# A plan that writes into a tree it binds refuses its own recovery

When an operation's target lives inside a directory the plan binds as a tree digest, replace that one binding with a token per existing file plus an expected-absent token for the new file, and prove the tokens against the digest the snapshot was validated on.

Why:
Every plan binds `.saipen/logs` as one tree digest, and recovery rechecks every read-only dependency before it rolls a partly applied operation forward. A seal writes its first target into that tree, so after a crash the digest the plan was made against no longer matches, by the operation's own doing, and recovery answers CONFLICT on a seal it interrupted. Apply itself is green, because the dependency is checked once before the first write; only the interrupted shape shows it. Measured as mutation M1 of T-1640: with the tree binding kept, the crash-after-first-target case does not converge.

How to apply:
Read each file of the tree once, recompute the tree digest from those same bytes through `hash_tree_dependency(read_file=...)`, and refuse with STALE_STATE if it differs from the snapshot's digest; only then use the per-file tokens. Drive `NITRO_CRASH_AFTER_PREPARE`, `_GENERIC`, `_LOG`, `_BOARD`, `_STATE` and `_VERIFIED` through `auto_recover_pending` in the operation's own test, because a plan that only ever applies cleanly proves nothing about its bindings.

The same operation showed a second rule. A plan that REMOVES lines from an append-only file shows the write gate a text those lines have left, so the gate must be put to the file as it stands before the plan is built; otherwise a defect is found by the post-write verifier, after the bytes moved.
