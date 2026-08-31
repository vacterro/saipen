# 10 — WAVE I: DOGFOOD / FINAL HARDENING

## Goal

Prove the entire transport loop before starting real SAIPAL deployment.

## Dogfood producers

Use at least:

1. manual audit file;
2. AUDAPACK-generated audit;
3. synthetic SAIPAL-like audit through enqueue API.

## End-to-end scenario

Producer creates audit.

Then:

```text
cc
```

Expected:

```text
discover
→ capture
→ normalize
→ Work
→ implement/reject
→ verify
→ evidence
→ close Source
→ hash recheck
→ journaled delete
→ preserved provenance
```

## Changed-generation scenario

Producer or human replaces `audit/N.md` before cleanup.

Old generation closes.

New bytes remain.

Next `cc` sees new generation.

## Active Work scenario

New audit arrives during VERIFY.

Current Work finishes legitimate continuation.

Audit is next before ordinary backlog.

## Multiple producers

AUDAPACK and synthetic SAIPAL enqueue concurrently.

Both files survive with unique monotonic IDs.

## Rejected audit scenario

Maintainer rejects source finding with evidence.

File still closes/deletes normally.

Producer disposition projection shows rejection.

## Recovery scenario

Crash after deletion before operation commit.

Restart.

No duplicate Work.

No phantom audit.

Provenance remains complete.

## Performance

Audit scan should be O(number of direct audit layers), not recursive project traversal.

No giant audit body loaded merely for `status`.

## Wave I completion bar

1. Manual producer works.
2. AUDAPACK producer works.
3. SAIPAL-like producer works.
4. Changed generation safe.
5. Active Work precedence safe.
6. Concurrent enqueue safe.
7. Rejection safe.
8. Crash recovery safe.
9. Cold restart reconstructs provenance.
10. Full validator/regression/golden suite green.
