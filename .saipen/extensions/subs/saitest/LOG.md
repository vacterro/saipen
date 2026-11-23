# Log
- 20.08.26 22:04 [E-001] [TEST-003] [agent: saitest] RUN: two bounded read-only scenarios against 3a343e8d / git-delta-v1:9964e4c9d5e4 -> 2/2 REPRODUCED; TEST-3 ready.
- 20.08.26 22:31 [E-002] [TEST-004] [agent: saitest] RUN: independent rerun against 3a343e8d / git-delta-v1:0e4e6d78f40f -> Ruff 89 and release parity 32 locales both REPRODUCED; TEST-4 ready.
- 20.08.26 22:50 [E-003] [TEST-005] [agent: saitest] RUN: canonical validator rerun against 3a343e8d / git-delta-v1:188e314f78fa -> 4/4 HUNT-12 failures REPRODUCED; Ruff remains clean; TEST-5 ready.
- 20.08.26 23:04 [E-004] [TEST-006] [agent: saitest] RUN: independent validator rerun against 3a343e8d / git-delta-v1:4ec002cc5f2d -> exactly one failure, locale parity across 32 files; TEST-6 ready.
- 20.09.26 13:07 [E-005] [parent: E-004] [agent: saitest] RUN: TEST-11 ready; three clean cases, T-1347 reproduced.
- 16.11.26 02:13 [E-006] [TEST-015] [agent: saitest] RUN: 3/3 bounded scenarios REPRODUCED at tree 6a857897; audit SOURCE_UNRESOLVED, validator 29/34 with 25 manifest paths, concurrent GC WRITER_BUSY; kitchen/TEST-15.md
- 16.11.26 02:32 [E-007] [TEST-015] [agent: saitest] RUN: reran T-2062 concurrent scenario against pen patch; 8/8 rounds preserve both closure counts, protected-budget debt, zero durable failures; kitchen/TEST-15.md

- 16.11.26 10:00 [E-008] [TEST-016] [agent: saitest] RUN: 4/4 bounded scenarios REPRODUCED at tree c9c3e86c; audit SOURCE_UNRESOLVED dead end, same validator bytes 3/17 vs 27/35 by home, crew dry-run idempotent with no writes, TEST-99 refused STALE_PACKAGE; kitchen/TEST-16.md

- 16.11.26 15:48 [E-009] [TEST-017] [agent: saitest] RUN: 5 bounded scenarios at tree 1a368781; S1 dead end NOT_REPRODUCED (router no longer owns ingest, executor still refuses), S2 home split REPRODUCED 3/18 vs 29/38, S3 plan idempotent no writes, S4 TEST-99 STALE_PACKAGE, S5 present-row restore NOT_REPRODUCED as reachable; TEST-16 superseded; kitchen/TEST-17.md

- 21.11.26 06:12 [E-010] [agent: saitest] RUN: TEST-21 -> ready; adversary scenarios at 6e4cf7d01 (1MB disposition, unicode confusables, empty map, forged-witness splice, string top-level, genuine-witness control) all fail-closed/designed, none reproduced; kitchen/OUTBOX.md

- 21.11.26 08:40 [E-011] [agent: saitest] RUN: TEST-22 -> ready; scenario replica at c6b779715 identical to the expected matrix; kitchen/OUTBOX.md
- 21.11.26 21:42 [E-012] [agent: saitest] RUN: TEST-23 -> ready; five scenarios at 13f2e7579 / tree 28904dfc12dd4d11: registry land clean (0/7 marks, canary holds, canonical bytes), crew-run ALREADY_BOUND, post-DONE block-for refused, enum refusal live; kitchen/OUTBOX.md
- 22.11.26 00:23 [E-013] [agent: saitest] RUN: TEST-24 -> ready; five scenarios at 5706afe0d / tree c66baf69: crew-run HUNT-029 ALREADY_BOUND idempotent, own TEST-23 STALE_PACKAGE refusal live, post-DONE block-for T-2137 ILLEGAL_TICKET_LIFECYCLE, closure-gate exact (re.IGNORECASE disclosed, 5/5 near-misses fail closed), registry canary 0/7+marked; kitchen/OUTBOX.md
- 22.11.26 05:11 [E-014] [agent: saitest] RUN: TEST-25 -> ready; five scenarios at 975477b04 / tree c66baf69: fresh-epoch idempotence ALREADY_BOUND, superseded-triple STALE_PACKAGE live, post-DONE lifecycle refused, T-2062 oracle OK, canary 0/7+marked; kitchen/OUTBOX.md
- 22.11.26 03:55 [E-015] [agent: saitest] RUN: TEST-26 -> ready; five scenarios at 3373fe9f4 / tree c66baf69: fresh-epoch idempotence ALREADY_BOUND (HUNT-031), superseded-triple STALE_PACKAGE live (HUNT-030), post-DONE lifecycle refused, T-2062 oracle OK, canary 0/7+marked; kitchen/OUTBOX.md
- 22.11.26 04:19 [E-016] [agent: saitest] RUN: TEST-27 -> ready; five scenarios at 7ee2ab0dd / tree c66baf69: fresh-epoch idempotence ALREADY_BOUND (HUNT-032), superseded-triple STALE_PACKAGE live (HUNT-031), post-DONE lifecycle refused, T-2062 oracle OK, canary 0/7+marked; kitchen/OUTBOX.md
- 22.11.26 09:15 [E-017] [agent: saitest] RUN: TEST-28 -> ready; five scenarios at 2e458d5b2 / tree c66baf69: fresh-epoch idempotence ALREADY_BOUND (HUNT-033), superseded-triple STALE_PACKAGE live (HUNT-032), post-DONE lifecycle refused, T-2062 oracle OK, canary 0/7+marked; kitchen/OUTBOX.md
