# OUTBOX

## TEST-28: adversary scenarios at 2e458d5b2 / tree c66baf69 -- fresh-epoch crew-run idempotence re-measured, superseded-triple STALE_PACKAGE refusal observed live, post-DONE lifecycle refused, T-2062 oracle green on the committed tree, registry canary green
- **status:** reviewed
- **summary:** At the 2e458d5b2 identity five bounded scenarios probed the fresh epoch machinery: a second identical crew record-run answers ALREADY_BOUND exit 0; the superseded HUNT-032 package is refused STALE_PACKAGE with the exact triple reason; a post-DONE block-for replay against T-2156 is refused with no board write; the serialized-GC regression oracle answers OK on the committed tree; the seven registration codes answer structured refusal with zero unregistered_code marks and the canary marked.
- **main_project_refs:** [tools/test_t2062_gc_serial.py, tools/saipen_engine/gc.py, tools/saipen_engine/result.py, .saipen/BOARD.md]
- **critical:** false
- **severity:** P1
- **producer:** saitest
- **source_head:** 2e458d5b228c4fa6973dcae569165deff86d3d2a
- **source_tree_fingerprint:** git-delta-v1:c66baf69a8306f3b95dfc7badb5f72b088f8de8408e933efadc4d149721a1195
- **role_revision:** sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08
- **coverage:** second execution of the epoch-fresh `crew record-run saihunt --package HUNT-033`; `crew record-run saihunt --package HUNT-032` superseded-triple refusal; `ticket block-for T-2156 T-2117 <reason>` post-DONE lifecycle refusal; in-tree run of the T-2062 serialized-GC oracle; in-process Result.refuse on the seven registered codes plus the unknown-code canary.
- **payload:** []
- **verified:** PASS -- all five scenarios ended in exactly one verdict: S1 NOT_REPRODUCED (ALREADY_BOUND exit 0, idempotent); S2 REPRODUCED (STALE_PACKAGE refusal fires as designed on the one-epoch-behind package); S3 NOT_REPRODUCED (lifecycle refusal, no board write); S4 NOT_REPRODUCED (serialized-GC oracle OK on the committed tree); S5 NOT_REPRODUCED (0/7 marks, canary marked).
- **instructions:** Core reviews kitchen/TEST-28.md and `_test28_scenarios.txt`. No new ticket is proposed; the payload is empty; saitest is read-only. The entry supersedes TEST-27. Bind this package to the active crew epoch with `saipen crew record-run saitest --package TEST-28`.
- **details:** Scenario commands, observed outputs and verdicts are in `kitchen/TEST-28.md`; the capture is `_test28_scenarios.txt`. No main-project file was written.
## TEST-27: adversary scenarios at 7ee2ab0dd / tree c66baf69 -- fresh-epoch crew-run idempotence re-measured, superseded-triple STALE_PACKAGE refusal observed live, post-DONE lifecycle refused, T-2062 oracle green on the committed tree, registry canary green
- **status:** reviewed
- **summary:** At the 7ee2ab0dd identity five bounded scenarios probed the fresh epoch machinery: a second identical crew record-run answers ALREADY_BOUND exit 0; the superseded HUNT-031 package is refused STALE_PACKAGE with the exact triple reason; a post-DONE block-for replay against T-2153 is refused with no board write; the serialized-GC regression oracle answers OK on the committed tree; the seven registration codes answer structured refusal with zero unregistered_code marks and the canary marked.
- **main_project_refs:** [tools/test_t2062_gc_serial.py, tools/saipen_engine/gc.py, tools/saipen_engine/result.py, .saipen/BOARD.md]
- **critical:** false
- **severity:** P1
- **producer:** saitest
- **source_head:** 7ee2ab0ddb10b19254ff425224ecdf73a91d0df3
- **source_tree_fingerprint:** git-delta-v1:c66baf69a8306f3b95dfc7badb5f72b088f8de8408e933efadc4d149721a1195
- **role_revision:** sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08
- **coverage:** second execution of the epoch-fresh `crew record-run saihunt --package HUNT-032`; `crew record-run saihunt --package HUNT-031` superseded-triple refusal; `ticket block-for T-2153 T-2117 <reason>` post-DONE lifecycle refusal; in-tree run of the T-2062 serialized-GC oracle; in-process Result.refuse on the seven registered codes plus the unknown-code canary.
- **payload:** []
- **verified:** PASS -- all five scenarios ended in exactly one verdict: S1 NOT_REPRODUCED (ALREADY_BOUND exit 0, idempotent); S2 REPRODUCED (STALE_PACKAGE refusal fires as designed on the one-epoch-behind package); S3 NOT_REPRODUCED (lifecycle refusal, no board write); S4 NOT_REPRODUCED (serialized-GC oracle OK on the committed tree); S5 NOT_REPRODUCED (0/7 marks, canary marked).
- **instructions:** Core reviews kitchen/TEST-27.md and `_test27_scenarios.txt`. No new ticket is proposed; the payload is empty; saitest is read-only. The entry supersedes TEST-26. Bind this package to the active crew epoch with `saipen crew record-run saitest --package TEST-27`.
- **details:** Scenario commands, observed outputs and verdicts are in `kitchen/TEST-27.md`; the capture is `_test27_scenarios.txt`. No main-project file was written.
## TEST-26: adversary scenarios at 3373fe9f4 / tree c66baf69 -- fresh-epoch crew-run idempotence re-measured, superseded-triple STALE_PACKAGE refusal observed live, post-DONE lifecycle refused, T-2062 oracle green on the committed tree, registry canary green
- **status:** reviewed
- **summary:** At the 3373fe9f4 identity five bounded scenarios probed the fresh epoch machinery: a second identical crew record-run answers ALREADY_BOUND exit 0; the superseded HUNT-030 package is refused STALE_PACKAGE with the exact triple reason; a post-DONE block-for replay against T-2152 is refused with no board write; the serialized-GC regression oracle answers OK on the committed tree; the seven registration codes answer structured refusal with zero unregistered_code marks and the canary marked.
- **main_project_refs:** [tools/test_t2062_gc_serial.py, tools/saipen_engine/gc.py, tools/saipen_engine/result.py, .saipen/BOARD.md]
- **critical:** false
- **severity:** P1
- **producer:** saitest
- **source_head:** 3373fe9f455c092a865f75f93102fdaf40c64920
- **source_tree_fingerprint:** git-delta-v1:c66baf69a8306f3b95dfc7badb5f72b088f8de8408e933efadc4d149721a1195
- **role_revision:** sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08
- **coverage:** second execution of the epoch-fresh `crew record-run saihunt --package HUNT-031`; `crew record-run saihunt --package HUNT-030` superseded-triple refusal; `ticket block-for T-2152 T-2117 <reason>` post-DONE lifecycle refusal; in-tree run of the T-2062 serialized-GC oracle; in-process Result.refuse on the seven registered codes plus the unknown-code canary.
- **payload:** []
- **verified:** PASS -- all five scenarios ended in exactly one verdict: S1 NOT_REPRODUCED (ALREADY_BOUND exit 0, idempotent); S2 REPRODUCED (STALE_PACKAGE refusal fires as designed on the one-epoch-behind package); S3 NOT_REPRODUCED (lifecycle refusal, no board write); S4 NOT_REPRODUCED (serialized-GC oracle OK on the committed tree); S5 NOT_REPRODUCED (0/7 marks, canary marked).
- **instructions:** Core reviews kitchen/TEST-26.md and `_test26_scenarios.txt`. No new ticket is proposed; the payload is empty; saitest is read-only. The entry supersedes TEST-25. Bind this package to the active crew epoch with `saipen crew record-run saitest --package TEST-26`.
- **details:** Scenario commands, observed outputs and verdicts are in `kitchen/TEST-26.md`; the capture is `_test26_scenarios.txt`. No main-project file was written.
## TEST-25: adversary scenarios at 975477b04 / tree c66baf69 -- fresh-epoch crew-run idempotence re-measured, superseded-triple STALE_PACKAGE refusal observed live, post-DONE lifecycle refused, T-2062 oracle green on the committed tree, registry canary green
- **status:** reviewed
- **summary:** At the feat(t2062) identity five bounded scenarios probed the fresh epoch machinery: a second identical crew record-run answers ALREADY_BOUND exit 0; the superseded HUNT-029 package is refused STALE_PACKAGE with the exact triple reason; a post-DONE block-for replay against T-2146 is refused with no board write; the serialized-GC regression oracle answers OK on the committed tree; the seven registration codes answer structured refusal with zero unregistered_code marks and the canary marked.
- **main_project_refs:** [tools/test_t2062_gc_serial.py, tools/saipen_engine/gc.py, tools/saipen_engine/errors.py, tools/saipen_engine/result.py, .saipen/BOARD.md]
- **critical:** false
- **severity:** P1
- **producer:** saitest
- **source_head:** 975477b0465203ed8f5969de2de6df0904b23c0c
- **source_tree_fingerprint:** git-delta-v1:c66baf69a8306f3b95dfc7badb5f72b088f8de8408e933efadc4d149721a1195
- **role_revision:** sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08
- **coverage:** second execution of the epoch-fresh `crew record-run saihunt --package HUNT-030`; `crew record-run saihunt --package HUNT-029` superseded-triple refusal; `ticket block-for T-2146 T-2117 <reason>` post-DONE lifecycle refusal; in-tree run of the T-2062 serialized-GC oracle; in-process Result.refuse on the seven registered codes plus the unknown-code canary.
- **payload:** []
- **verified:** PASS -- all five scenarios ended in exactly one verdict: S1 NOT_REPRODUCED (ALREADY_BOUND exit 0, idempotent); S2 REPRODUCED (STALE_PACKAGE refusal fires as designed on the one-epoch-behind package); S3 NOT_REPRODUCED (lifecycle refusal, no board write); S4 NOT_REPRODUCED (serialized-GC oracle OK on the committed tree); S5 NOT_REPRODUCED (0/7 marks, canary marked).
- **instructions:** Core reviews kitchen/TEST-25.md and `_test25_scenarios.txt`. No new ticket is proposed; the payload is empty; saitest is read-only. The entry supersedes TEST-24. Bind this package to the active crew epoch with `saipen crew record-run saitest --package TEST-25`.
- **details:** Scenario commands, observed outputs and verdicts are in `kitchen/TEST-25.md`; the capture is `_test25_scenarios.txt`. No main-project file was written.
## TEST-24: adversary scenarios at 5706afe0d / tree c66baf69 -- the T-2137 closure land probed (post-DONE lifecycle refused, closure-gate exactness fail-closed), crew-run idempotence re-measured on the fresh HUNT-029 package, stale-package refusal observed live against saitest's own superseded TEST-23, registry canary green
- **status:** reviewed
- **summary:** At the chore(t2137) identity five bounded scenarios probed the closure land and the session's own machinery: a second crew record-run of the freshly bound HUNT-029 answers ALREADY_BOUND exit 0; the role's own superseded TEST-23 is refused STALE_PACKAGE with the exact reason text; a post-DONE block-for replay against T-2137 is refused ILLEGAL_TICKET_LIFECYCLE with no board write; the finding_invalidated gate regex is exact for its designed accept set (re.IGNORECASE disclosed) and fail-closed on unicode-confusable, plural-subject, split-token, no-verb and wrong-noun near-misses; the seven-code structured-refusal registry answers clean with the canary marked.
- **main_project_refs:** [saipen/REGISTRY.json, tools/saipen.py, tools/saipen_engine/errors.py, tools/saipen_engine/result.py, tools/saipen_engine/operations.py, .saipen/BOARD.md]
- **critical:** false
- **severity:** P1
- **producer:** saitest
- **source_head:** 5706afe0d814e734b389d5979bde5bff0d149876
- **source_tree_fingerprint:** git-delta-v1:c66baf69a8306f3b95dfc7badb5f72b088f8de8408e933efadc4d149721a1195
- **role_revision:** sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08
- **coverage:** second execution of the epoch-fresh `crew record-run saihunt --package HUNT-029`; `crew record-run saitest --package TEST-23` staleness refusal; `ticket block-for T-2137 T-2140 <reason>` post-DONE lifecycle refusal (both the no-reason early gate and the lifecycle gate); in-process `_PREMISE_DISPROOF_RE` exactness probe (8 designed-accept forms incl. the disclosed re.IGNORECASE uppercase form, 5 adversarial near-misses); in-process Result.refuse on the seven registered codes plus the unknown-code canary.
- **payload:** []
- **verified:** PASS -- all five scenarios ended in exactly one verdict: S1 NOT_REPRODUCED (ALREADY_BOUND exit 0, idempotent); S2 REPRODUCED (STALE_PACKAGE exit 1 with the exact reason, the staleness gate fires as designed); S3 NOT_REPRODUCED (ILLEGAL_TICKET_LIFECYCLE exit 1, no board write; the first no-reason attempt was refused by the reason-validation gate, both attempts refused); S4 NOT_REPRODUCED (8/8 designed-accept forms match, 5/5 adversarial near-misses fail closed; the probe's first run misread the uppercase match as a leak and was corrected after reading re.IGNORECASE in source); S5 NOT_REPRODUCED (0/7 unregistered_code marks, canary marked, every code answers its own identifier).
- **instructions:** Core reviews kitchen/TEST-24.md and the _test24_* captures. No new ticket is proposed; the payload is empty; saitest is read-only. The entry supersedes TEST-23, which is the stale previous-epoch package. Bind this package to the active crew epoch with `saipen crew record-run saitest --package TEST-24`.
- **details:** Scenario commands, observed outputs and verdicts are in `kitchen/TEST-24.md`; captures are `_test24_scenarios.txt` (CLI runs S1-S3), `_test24_gate.txt` (S4 corrected regex probe), `_test24_fixed.txt` (S5 refusal refresh). No main-project file was written; the role wrote only inside its own namespace.

## TEST-23: adversary scenarios at 13f2e7579 / tree 28904dfc -- seven-code registry land probed, crew-run and block-for idempotence re-measured, OUTBOX enum refusal observed live
- **status:** stale
- **summary:** At the fix(t2136) identity five bounded scenarios probed the shipped land and the session's own machinery: the seven newly registered refusal codes answer structured results with zero unregistered_code marks while the unknown-code canary keeps its mark, REGISTRY.json holds its canonical byte form, a second crew record-run answers ALREADY_BOUND exit 0, a post-DONE block-for replay is refused ILLEGAL_TICKET_LIFECYCLE, and the strict OUTBOX status enum refusal fired live this epoch.
- **main_project_refs:** [saipen/REGISTRY.json, tools/saipen_engine/errors.py, tools/saipen_engine/result.py, tools/saipen_engine/crew.py, tools/saipen_engine/operations.py, .saipen/BOARD.md]
- **critical:** false
- **severity:** P1
- **producer:** saitest
- **source_head:** 13f2e7579b29a2892a7130796558ecf5e441bba0
- **source_tree_fingerprint:** git-delta-v1:bdd63a980a507dc5457e35a5d9b718de7d950aa9757e8f097946bbf4426f26f3
- **role_revision:** sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08
- **coverage:** Result.refuse on each of the seven registry additions plus the unknown-code canary; canonical byte comparison of saipen/REGISTRY.json against json.dumps(indent=1); second execution of the HUNT-028 crew record-run; post-DONE replay of ticket block-for; the live STALE_PACKAGE enum refusal measured earlier this epoch.
- **payload:** []
- **verified:** PASS -- all five scenarios ended in exactly one verdict: S1 NOT_REPRODUCED (0 of 7 marked, canary marked), S2 NOT_REPRODUCED (byte equality True), S3 NOT_REPRODUCED (ALREADY_BOUND exit 0), S4 NOT_REPRODUCED (ILLEGAL_TICKET_LIFECYCLE exit 1, no write), S5 REPRODUCED (closed-enum refusal with the exact parser cause line).
- **instructions:** Core reviews kitchen/TEST-23.md and the _test23_* captures. No new ticket is proposed; the payload is empty; saitest is read-only. Bind this package to the active crew epoch with `saipen crew record-run saitest --package TEST-23`.
- **details:** Scenario commands, observed outputs and verdicts are in `kitchen/TEST-23.md`; captures are `_test23_scenarios.txt` and `_test23_fixed.txt`. No main-project file was written; the role wrote only inside its own namespace.

## TEST-20: bounded host/runtime test sweep at dc39709c / tree 0f69fe84 -- five scenarios, 81 cases green, both conformance gates red only on their owned classes
- **status:** reviewed
- **summary:** At the live identity 0f69fe84 (HEAD unchanged at dc39709c, tree moved since TEST-19's cf7cd4a7) five bounded scenarios were re-run: host bootstrap/install identity/runtime home 55 cases OK (skipped=1), T-2077 unblock-gate 4 OK, T-1430 crew-run receipt 5 OK, refusal-registry plus generation binding 17 OK, and both conformance gates measured red only on their owned classes (installed 2 problems/16 warnings of installed pre-fix gaps; repo 31 problems/39 warnings of the untracked runtime-manifest class, plus a stale saiwiki package warning).
- **main_project_refs:** [tools/test_host_bootstrap.py, tools/test_install_identity_doctor.py, tools/test_t1854_runtime_home.py, tools/test_t2077_unblock_gate.py, tools/test_t1430_crew_run_receipt.py, tools/test_refusal_registry.py, tools/test_t2076_installed_generation_binding.py, tools/validate.py]
- **critical:** true
- **severity:** P2
- **producer:** saitest
- **source_head:** dc39709c0c17a3272126c01a626ffcaa4176140b
- **source_tree_fingerprint:** git-delta-v1:0f69fe84ecb98bfc84e2c33be0bb35ef7310de8bbd75c223f7d6b77232be14d2
- **role_revision:** sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08
- **coverage:** five bounded scenarios at the declared identity: the 55-case host bootstrap/install-identity/runtime-home set, the T-2077 unblock-gate regression (4 cases), the T-1430 crew-run receipt (5 cases), the refusal-registry plus installed-generation-binding group (17 cases), and both canonical conformance gates (installed `saipen validate --json`, repo `tools/validate.py`). No main-project write.
- **payload:** []
- **verified:** PASS -- bounded scenario run completed at the declared identity. Scenario 1: `Ran 55 tests in 17.470s -- OK (skipped=1)`. Scenario 2: `Ran 4 tests -- OK`, dependency holds lift while a genuine operator head still refuses with WAIT_USER_DECISION and zero writes. Scenario 3: `Ran 5 tests -- OK`. Scenario 4: `Ran 17 tests -- OK`, registry and generation-binding controls green. Scenario 5: installed gate `CONFORMANCE_UNHEALTHY`/`CURRENT_FAIL`, `Validation FAILED: 2 problem(s), 16 warning(s)`, structural pass, install identity MATCH, repair ENGINEERING_REQUIRED with engine_work_count 0; repo gate `Validation FAILED: 31 problem(s), 39 warning(s)`, all 31 the untracked runtime-manifest class, plus `[producer-package-stale]` saiwiki W-051 (f6e0d368 vs live 0f69fe84). This is not a repository harness PASS and not a conformance verdict.
- **instructions:** Core review `kitchen/TEST-20.md` and the `_test020_*` captures. Treat the two installed-gate problems as installed-generation gaps carried by the T-2058 install route, the 31 repo problems as the known untracked runtime-manifest class under T-1449/T-2058/T-2052/T-2040, and the saiwiki W-051 warning as a stale producer package for its own collection gate. No new ticket is proposed and the payload is empty; saitest is read-only. Bind this package to the active crew epoch with `saipen crew record-run saitest --package TEST-20`.
- **details:** Scenario commands and limits are in `kitchen/TEST-20.md`; captures are `_test020_role_revision.txt` and `_test020_tests.txt`. No main-project file was written; the role wrote only inside its own namespace.

## TEST-19: adversarial scenarios at dc39709c / tree cf7cd4a7 -- routing dead end stays gone; home asymmetry re-measured at 2/16 vs 29/37; plan replay, unknown-package refusal and the restore surface re-probed, with the installed generation found to have no restore path
- **status:** reviewed
- **summary:** Five bounded scenarios at the tree that carries T-2077: the audit-ingest routing dead end remains gone, the two-home verifier asymmetry persists at 2/16 vs 29/37, two dry-run plans are byte-identical apart from the scanned-file counter artifact with no state writes, an unknown package is refused with no writes, and the restore boundary shows the live board would only insert the pruned T-1936 row -- while the installed 8.1.0 engine contains no restore surface at all, so the FG-0046 gate finding is not agent-repairable at the installed home.
- **main_project_refs:** [tools/saipen_engine/audit_route.py, tools/saipen_engine/audit_inbox.py, tools/saipen_engine/board_scrub.py, tools/saipen_engine/operations.py, tools/saipen_engine/crew.py, tools/validate.py, .saipen/BOARD.md]
- **critical:** true
- **severity:** P1
- **producer:** saitest
- **source_head:** dc39709c0c17a3272126c01a626ffcaa4176140b
- **source_tree_fingerprint:** git-delta-v1:cf7cd4a7512b88c0b0f2e57a05d17aef9e41b432f907486635c87aa3ab53aa42
- **role_revision:** sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08
- **coverage:** route ownership and violation probes against the real inbox and BOARD plus the executor refusal on the same layer; both canonical gates at this tree; two consecutive crew dry-run plans with STATE/LOG/BOARD hashes; unknown-package refusal; synthetic-board restore boundary plus the live restore-precondition probe and an installed-engine surface census.
- **payload:** []
- **verified:** PASS -- bounded scenario run completed at the declared identity. S1 NOT_REPRODUCED (router owns False; violation None with tickets; executor SOURCE_UNRESOLVED). S2 REPRODUCED (installed 2 problems/16 warnings; repo 29/37). S3 REPRODUCED AS SAFE (plans differ only in the 64505-to-64506 scanned-file counter; state hashes unchanged). S4 REPRODUCED (STALE_PACKAGE, changed_files [], no writes). S5 REPRODUCED (helper duplicates 1-to-2; live preconditions restore only the absent pruned T-1936; installed engine has no gated_tickets/pruned_rows/restored_board_text/restore_board_rows). This is not a repository harness PASS.
- **instructions:** Core reviews `kitchen/TEST-19.md` and the `_test19_*` captures. Reproduced asymmetries remain owned by T-2058/T-1449/T-2052; the installed-generation restore gap belongs to the already-measured installed-runtime lag class (T-2071/T-2072), so no new ticket and no payload are proposed. Bind this package to the active crew epoch with `saipen crew record-run saitest --package TEST-19`.
- **details:** Verdicts, exact commands and limits are in `kitchen/TEST-19.md`; captures are `_test19_s1_route.txt`, `_test19_s1_executor.json`, `_test19_s2_installed.json`, `_test19_s2_repo.txt`, `_test19_s3_plan_a.json`, `_test19_s3_plan_b.json`, `_test19_s3_pre.sha`, `_test19_s3_post.sha`, `_test19_s4_probe.json`, `_test19_s4_pre.sha`, `_test19_s4_post.sha`, `_test19_s5_restore.txt`. No main-project file was written by this role.

## TEST-18: adversarial scenarios at dc39709c / tree f3dab073 -- the T-2047 tree keeps the routing fix; both homes re-measured; plan replay and package refusal hold
- **status:** reviewed
- **summary:** Five bounded scenarios at the tree that carries the T-2047 crew-run guard: the audit-ingest routing dead end stays gone (router owns False with the board passed, executor refusal unchanged), the two-home verifier asymmetry persists as an owned publication condition (installed 3/19, repo 29/39), two dry-run crew plans are byte-identical with no state writes, an unknown package is refused with no writes, and the duplicating restore helper remains unreachable through the canonical verb.
- **main_project_refs:** [tools/saipen_engine/audit_route.py, tools/saipen_engine/audit_inbox.py, tools/saipen_engine/board_scrub.py, tools/saipen_engine/operations.py, tools/saipen_engine/crew.py, tools/validate.py, .saipen/BOARD.md, .saipen/LOG.md]
- **critical:** true
- **severity:** P1
- **producer:** saitest
- **source_head:** dc39709c0c17a3272126c01a626ffcaa4176140b
- **source_tree_fingerprint:** git-delta-v1:f3dab073ebbfbd9021d22a0e63c2cbba72094bb6ff587c16e670aa98bd38e1d7
- **role_revision:** sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08
- **coverage:** route ownership and violation probe against the real inbox and BOARD; executor refusal probe on the same layer; both canonical gates at this tree; two consecutive crew dry-run plans with STATE/LOG hashes; unknown-package refusal; synthetic-board restore boundary plus the production refusal path; the T-2047 guard's contract tests carried in the cited focused record.
- **payload:** []
- **verified:** PASS -- bounded scenario run completed at the declared identity. S1 NOT_REPRODUCED (router owns False; violation None with tickets; executor SOURCE_UNRESOLVED). S2 REPRODUCED (installed 3 problems/19 warnings; repo 29/39; both measured). S3 REPRODUCED AS SAFE (plans byte-identical, no writes). S4 REPRODUCED (STALE_PACKAGE, no writes). S5 NOT_REPRODUCED AS REACHABLE (helper duplicates 1-to-2; production refuses NOTHING_TO_RESTORE first). 131 focused cases across five cited records PASS at this tree. This is not a repository harness PASS.
- **instructions:** Core reviews `kitchen/TEST-18.md` and the `_test18_*` captures. Every reproduced asymmetry is a publication/home-identity condition already owned by T-2058/T-1449/T-2052; no new ticket and no payload are proposed. Bind this package to the active crew epoch with `saipen crew record-run saitest --package TEST-18`.
- **details:** Verdicts and exact commands are in `kitchen/TEST-18.md`; captures are `_test18_s1_route.txt` and `_test18_s5_restore.txt`. One control note: the ingest-ownership rule needs the BOARD to know the linked work is open, so `route_violation` without `tickets` reports a violation that the production caller never produces. No main-project file was written.

## TEST-17: adversarial scenarios at dc39709c / tree 1a368781 -- the audit-route dead end is gone; verifier-home asymmetry, plan idempotency and stale-package refusal reproduced
- **status:** stale
- **superseded_by:** TEST-18 -- the worktree moved from tree 1a368781 to f3dab073 when the T-2047 guard landed, so this package no longer describes the current source
- **summary:** Five bounded scenarios: the T-2070 payload removes the routing dead end (router no longer owns the ingest action, executor still refuses an open link -- the two sides now agree); the two-home verifier asymmetry survives as an owned publication condition; two dry-run plans are byte-stable; an unknown package is refused with no writes; an already-present restore row is unreachable through the canonical verb.
- **main_project_refs:** [tools/saipen_engine/audit_route.py, tools/saipen_engine/board_scrub.py, tools/saipen_engine/operations.py, tools/saipen_engine/audit_inbox.py, tools/validate.py, .saipen/intake/audit_inbox.json, .saipen/BOARD.md]
- **critical:** true
- **severity:** P1
- **producer:** saitest
- **source_head:** dc39709c0c17a3272126c01a626ffcaa4176140b
- **source_tree_fingerprint:** git-delta-v1:1a368781b8bbe259b5218e35666c2732b2531304247854b750c561f1f888ada9
- **role_revision:** sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08
- **coverage:** five bounded scenarios across four closed families: damaged-state routing (S1), environment/verifier-home identity (S2), order/repetition crew-plan idempotency (S3), input-abuse stale-package refusal (S4), boundary restore-of-present-row (S5); exact commands, outputs and limits in kitchen/TEST-17.md.
- **payload:** []
- **verified:** PASS -- S1 NOT_REPRODUCED: projection work T-2016, audit_route_owns False, route_violation(saipen crew) None; the executor still refuses SOURCE_UNRESOLVED for open T-2016 (correct); repo gate carries no audit-route FAIL. S2 REPRODUCED: installed gate 3 problems/18 warnings vs repo gate 29 problems/38 warnings, class difference exactly the payload-repaired pair vs the manifest/EX pair. S3 REPRODUCED: two `saipen crew --dry-run --json` both SC-3, snapshot state b34059ae2a84a881 / board 43311369612a2f7d / stable true / log_tail 21291, STATE+LOG hashes unchanged. S4 REPRODUCED: `crew record-run saitest --package TEST-99` -> STALE_PACKAGE, exit 1, no writes. S5 NOT_REPRODUCED as reachable: the direct helper duplicates an already-present row, but `restore_board_rows` refuses NOTHING_TO_RESTORE first and never passes a present row. No project file modified.
- **instructions:** Core review kitchen/TEST-17.md. S1 closes the dead end TEST-16 reproduced: no decision is needed any more, the payload is the resolution. S2 remains under T-2058/T-1449/T-2052 ownership. S5's direct-helper duplication is recorded with its unreachability proof; no ticket is proposed, and no payload. After review, bind this package with `saipen crew record-run saitest --package TEST-17`.
- **details:** Scenario records, exact outputs and limits are in kitchen/TEST-17.md; captures are `_test17_route_restore_probe.txt`, `_test17_s1_ingest_probe.json`, `_test17_crew_a.json`, `_test17_crew_b.json`, `_test17_pre.sha`, `_test17_post.sha`, `_test17_s4_probe.json`. No main-project file was written by this role.

## TEST-16: current-source adversarial scenarios at dc39709c / tree c9c3e86c -- audit route is a dead end; manifest debt invisible to the installed gate; crew plan idempotent; unknown package refused
- **status:** stale
- **superseded_by:** TEST-17 -- the worktree moved from tree c9c3e86c to 1a368781 and the audit-route dead end it reproduced no longer reproduces
- **summary:** Four bounded scenarios reproduced: `saipen audit ingest` refuses SOURCE_UNRESOLVED while the validator demands it as the routed action; identical validator bytes at two homes report 3 vs 27 problems because each reads its own manifest; consecutive crew dry-runs write nothing and keep SC-3; record-run refuses an unknown package.
- **main_project_refs:** [tools/saipen_engine/audit_inbox.py, tools/validate.py, tools/saipen_engine/crew.py, .saipen/intake/audit_inbox.json, .saipen/BOARD.md]
- **critical:** true
- **severity:** P1
- **producer:** saitest
- **source_head:** dc39709c0c17a3272126c01a626ffcaa4176140b
- **source_tree_fingerprint:** git-delta-v1:c9c3e86c3626f36973a4e75543aeebc51f174d8fa3c2271c89e1afe963a229a1
- **role_revision:** sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08
- **coverage:** four bounded scenarios: damaged-state/audit route, environment/verifier-home identity, order/repetition crew-plan idempotency, input-abuse stale-package binding; exact commands, outputs and limits in kitchen/TEST-16.md.
- **payload:** []
- **verified:** PASS -- S1 REPRODUCED: `saipen audit ingest --dry-run --json` -> SOURCE_UNRESOLVED, linked Work T-2016 not DONE, exit 1. S2 REPRODUCED: identical validator bytes (sha256 fb495f7e...) report 3 problems/17 warnings at the installed home and 27 problems/35 warnings at the repo home; the 26 untracked runtime-manifest paths are visible only to the repo home. S3 REPRODUCED: two consecutive `saipen crew --dry-run --json` leave STATE.md and LOG.md byte-identical and both report first_unsatisfied SC-3; only the scanned-file counter moved 61721 -> 61722 because the captures themselves added files. S4 REPRODUCED: `saipen crew record-run saitest --package TEST-99` -> STALE_PACKAGE, exit 1, no writes. No project file modified; every probe was read-only or refused before writing.
- **instructions:** Core review kitchen/TEST-16.md. The audit-route dead end needs a decision: either the routed action becomes executable once the source is CLOSED_PENDING_DELETE (settle the journaled cleanup without requiring T-2016 DONE), or the validator stops demanding an action its executor refuses. Preserve T-2016's BLOCKED_EXTERNAL ownership and T-1449's manifest ownership. No new ticket or payload is proposed. After review, bind this package with `saipen crew record-run saitest --package TEST-16`.
- **details:** Scenario records, exact outputs and limits are in kitchen/TEST-16.md; raw captures are `_test16_audit_probe.json`, `_test16_validate_installed_full.txt`, `_test16_validate_repo_full.txt`, `_test16_crew_a.json`, `_test16_crew_b.json`, `_test16_pre.sha`/`_test16_post.sha`, `_test16_s4_probe.json`.

## TEST-15: current-source adversarial scenarios at dc39709c -- audit dead end, runtime manifest and concurrent GC checkpoint reproduced
- **status:** stale
- **superseded_by:** TEST-16 -- the source tree moved from 6a857897 to c9c3e86c, so this package no longer describes the current source
- **summary:** Three bounded scenarios reproduced the audit ingest refusal, 25 untracked runtime-manifest entries and the concurrent GC failure; an independent 8-round rerun against the saipython pen patch had no maintenance failure.
- **main_project_refs:** [tools/saipen_engine/audit_inbox.py, tools/validate.py, tools/saipen_engine/gc.py, tools/saipen_engine/lock.py, .saipen/BOARD.md]
- **critical:** true
- **severity:** P2
- **producer:** saitest
- **source_head:** dc39709c0c17a3272126c01a626ffcaa4176140b
- **source_tree_fingerprint:** git-delta-v1:6a857897f61278f309f56252e9d382c1f3221c91920708dc17e2d65ee16566bd
- **role_revision:** sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08
- **coverage:** three bounded scenarios in damaged-state, environment and order/repetition families, plus an 8-round concurrent-GC rerun against the pen patch; exact commands, outputs, verdicts and limits are in kitchen/TEST-15.md.
- **payload:** []
- **verified:** PASS -- all three baseline scenarios executed with exact outputs and verdicts; the concurrent case passed 8/8 rounds against the saipython pen patch; read-only/copy cases touched no project files.
- **instructions:** Preserve T-2062 ownership for concurrent GC maintenance; attach the audit and validator evidence to existing cc all/T-1449 and source/audit owners. No new ticket or payload is proposed.
- **details:** Scenario 1 reproduces `SOURCE_UNRESOLVED` for SRC-386/T-2016; scenario 2 reproduces 29 validator problems/34 warnings including 25 untracked runtime-manifest paths; scenario 3 reproduces concurrent `WRITER_BUSY` on baseline. The same two-closure case passes 8/8 rounds against `.saipen/extensions/subs/saipython/kitchen/PY-15.patch` (sha256 `AFB610B95DAE93BA7E3EB88FDEA241D428DD5C39A9225B65F2F587737C35CC7A`). Full evidence is in kitchen/TEST-15.md.

## TEST-14: bounded adversarial scenarios at 66ef622a — 17 validation problems reproduced, 1 audit dead end verified
- **status:** stale
- **superseded_by:** TEST-15 -- current source head/tree differ from this package
- **summary:** Three bounded adversarial scenarios: (1) audit ingest routes to retired SRC-386 whose linked Work T-2016 is not DONE, SOURCE_UNRESOLVED; (2) manifest names 11 untracked files, 2 subSaipen OUTBOX entries, translation badge drift; (3) OUTBOX schema gate verified via crew-run witness.
- **main_project_refs:** [tools/validate.py, tools/saipen_engine/audit_inbox.py, kitchen/OUTBOX.md]
- **critical:** true
- **severity:** P2
- **producer:** saitest
- **source_head:** 66ef622a43ab59512735ac78ce10d1250e26f9df
- **source_tree_fingerprint:** git-delta-v1:374d12a0eb91a5d768a66863eec29c4ea0fa03a0a02190301ca437dabb5fa208
- **role_revision:** sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08
- **coverage:** three adversarial scenarios: audit refusal, manifest untracked, OUTBOX gate
- **payload:** []
- **verified:** PASS -- audit ingest SOURCE_UNRESOLVED for SRC-386/T-2016; validate.py 17 problems 25 warnings; outbox check crew-run witness valid
- **instructions:** Core review kitchen/TEST-14.md; audit dead end requires Work completion; manifest untracked files need commit or drop; translation badge drift needs update.
- **details:** Three bounded scenarios with REPRODUCED verdict; no main project modified.


## TEST-11: continuation is read-only; T-1347 false positive reproduced
- **status:** reviewed
- **summary:** Three bounded continuation/help scenarios are NOT_REPRODUCED; thread.join misclassification is REPRODUCED and already belongs to T-1347.
- **main_project_refs:** [tools/saipen.py, tools/test_concurrency_independence.py, tools/test_opencode_bound_launch_smoke.py]
- **critical:** true
- **severity:** P2
- **producer:** saitest
- **source_head:** b7f5b51280b8f49c5fedbf7a00aeb6d4f45743ba
- **source_tree_fingerprint:** git-delta-v1:4c6fd9b3f13a1d7a0b203e00a759dae5eac1474eabb77cb3e39dad9da1953eb9
- **role_revision:** sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08
- **coverage:** four bounded order/repetition/input/timing-classification scenarios in kitchen/TEST-11.md
- **payload:** []
- **verified:** PASS -- all four scenarios have evidence and a verdict; concurrency suite itself has 1 known failure and 1 opt-in skip among 9 tests, not full-green.
- **instructions:** Core review kitchen/TEST-11.md; preserve T-1347 ownership. saipython may prepare the narrow detector fix in its pen.
- **details:** No main source changed. Repeated diagnostic hashes agree. Exact commands and limitations are preserved in TEST-11.md.


## TEST-1: No findings to reproduce
- **status:** stale
- **superseded_by:** TEST-2
- **summary:** No new findings from saihunt.
- **main_project_refs:** []
- **critical:** false
- **severity:** P3
- **producer:** saitest
- **source_head:** 4451d07340163642c9a6203b33bf7a80585fb3ac
- **source_tree_fingerprint:** git-delta-v1:a5dd07bf4c846840c46fd542a758184c06d6a0a5f8cf459e8209ff1b3a0354ba
- **role_revision:** sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08
- **coverage:** None.
- **payload:** []
- **verified:** PASS
- **instructions:** None.
- **details:** No action needed.

## TEST-2: Reproduction sweep at 00aa12db
- **status:** stale
- **summary:** Hunt HUNT-9 found zero new findings. All existing audit repairs verified via test suites (92 checks green). No reproduction targets.
- **main_project_refs:** []
- **critical:** false
- **severity:** P3
- **producer:** saitest
- **source_head:** 4451d07340163642c9a6203b33bf7a80585fb3ac
- **source_tree_fingerprint:** git-delta-v1:ccb6e0f9a721e7c2129e14998c54f1d2cd703605adb61d9e70311bd126857d43
- **role_revision:** sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08
- **coverage:** Full test suite regression.
- **payload:** []
- **verified:** PASS -- conformance 29/29, core-audit 17/17, v7-producer 14/14, second-wave 4/4, perf 28/28
- **instructions:** None.
- **details:** No new reproduction targets; all audit repairs verified.

## SAITEST-99: autonomous prepare at 00aa12db9f01
- **status:** stale
- **summary:** Autonomous preparation by protocol intent handler.
- **main_project_refs:** []
- **critical:** false
- **severity:** P3
- **producer:** saitest
- **source_head:** 4451d07340163642c9a6203b33bf7a80585fb3ac
- **source_tree_fingerprint:** git-delta-v1:f91c6d2e1abf19c297f58e798ea002d1418f477b9abb7399c625f454810e18e0
- **role_revision:** sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08
- **coverage:** Autonomous preparation.
- **payload:** []
- **verified:** PASS -- autonomous preparation complete
- **instructions:** None.
- **details:** Prepared by autonomous protocol intent handler.

## SAITEST-100: autonomous prepare at 00aa12db9f01
- **status:** stale
- **summary:** Autonomous preparation by protocol intent handler.
- **main_project_refs:** []
- **critical:** false
- **severity:** P3
- **producer:** saitest
- **source_head:** 4451d07340163642c9a6203b33bf7a80585fb3ac
- **source_tree_fingerprint:** git-delta-v1:1f0d71818c866058858b0b0a5c9e245ba04925ed02597d3d9843b8a3d0c2f7e9
- **role_revision:** sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08
- **coverage:** Autonomous preparation.
- **payload:** []
- **verified:** PASS -- autonomous preparation complete
- **instructions:** None.
- **details:** Prepared by autonomous protocol intent handler.

## SAITEST-101: autonomous prepare at 00aa12db9f01
- **status:** stale
- **summary:** Autonomous preparation by protocol intent handler.
- **main_project_refs:** []
- **critical:** false
- **severity:** P3
- **producer:** saitest
- **source_head:** 4451d07340163642c9a6203b33bf7a80585fb3ac
- **source_tree_fingerprint:** git-delta-v1:85393eb352407d6600458d397fae3dc4c070e7941e2788d880fc130e828a581f
- **role_revision:** sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08
- **coverage:** Autonomous preparation.
- **payload:** []
- **verified:** PASS -- autonomous preparation complete
- **instructions:** None.
- **details:** Prepared by autonomous protocol intent handler.

## TEST-3: HUNT-10 failures independently reproduced
- **status:** stale
- **summary:** Independent bounded runs reproduce Ruff's 89 findings and the release-executor scenario abort caused by stale locale badges.
- **main_project_refs:** [tools/freshness.py, tools/test_second_wave_audit_fixes.py, tools/test_v7_producer_parallelism.py, tools/run_scenarios.py, tools/saipen_engine/release.py]
- **critical:** true
- **severity:** P1
- **producer:** saitest
- **source_head:** 4451d07340163642c9a6203b33bf7a80585fb3ac
- **source_tree_fingerprint:** git-delta-v1:9964e4c9d5e4335b64c3d6faa7c25942e7dd71b4995646e7c5e5229f20ef1f25
- **role_revision:** sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08
- **coverage:** HUNT-10 Finding 1 lint gate and Finding 2 release-executor scenario; exact run record in kitchen/TEST-3.md.
- **payload:** []
- **verified:** PASS -- both assigned scenarios ended REPRODUCED with exact commands and observed failures; the project working tree was invoked read-only.
- **instructions:** 1. Core accepts both reproductions as defects; 2. saipython prepares minimal Python/lint fixes; 3. saitranslate refreshes all locale badges/content; 4. saitest reruns both exact commands after integration.
- **details:**
  Scenario A REPRODUCED: minimal input is the current tools/ and tests/ tree. Exact command `python -m ruff check tools/ tests/`. Observed: exit nonzero, 89 diagnostics including E501, F401, F841, F811, F821, RUF100, RUF059, RUF015, SIM105, SIM108, SIM103, RUF023, RUF028, RUF010, and RUF102.
  Scenario B REPRODUCED: minimal input is the release-executor probe family reading the current source and mutating only its temporary fixture clones. Exact command `python -c "import sys; sys.path.insert(0,'tools'); import run_scenarios as r; r.run_release_executor_probes()"`. Observed: exit 1 at tools/run_scenarios.py:6683; tools/saipen_engine/release.py:3303 raises `ReleaseRefusal` because copied locale badges remain old while the fixture increments VERSION to 7.226.1.

## TEST-4: HUNT-11 failures independently reproduced after T-1115
- **status:** stale
- **summary:** Independent current-source reruns still reproduce exactly Ruff's 89 diagnostics and the 32-locale release parity refusal.
- **main_project_refs:** [tools/freshness.py, tools/test_second_wave_receipt_fixes.py, tools/run_scenarios.py, tools/saipen_engine/journal.py, tools/saipen_engine/subs.py, tools/saipen_engine/release.py]
- **critical:** true
- **severity:** P1
- **producer:** saitest
- **source_head:** 4451d07340163642c9a6203b33bf7a80585fb3ac
- **source_tree_fingerprint:** git-delta-v1:0e4e6d78f40ffa3cd8fa5ea9c0d5ca1e64307f1c1f98d8803c75e224100a0440
- **role_revision:** sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08
- **coverage:** HUNT-11 Finding 1 lint gate, Finding 2 release-executor parity, and separation from the green T-1115 recovery regression.
- **payload:** [kitchen/TEST-4.md]
- **verified:** PASS -- 2/2 assigned scenarios REPRODUCED with exact commands and observed failures; tests mutate only temporary fixtures; TEST-4.md records the run.
- **instructions:** 1. saipython recuts the Ruff patch over this source; 2. saitranslate repairs locale parity; 3. Core applies and independently reruns both commands.
- **details:** Scenario A: `python -m ruff check tools/ tests/ --output-format concise` exits 1 with exactly 89 diagnostics. Scenario B: `run_release_executor_probes()` exits 1 at tools/run_scenarios.py:6683 and release.py:3303 because 32 locale fixture badges lack v7.226.1. T-1115 remains independently green (receipt 26/26, CORE 17/17, conformance 29/29), so neither failure is recovery-fix noise.

## TEST-5: HUNT-12 validator failures independently reproduced
- **status:** stale
- **summary:** A fresh canonical validator run independently reproduces all four post-PY-7 failures while Ruff stays clean.

- **main_project_refs:** [tools/improve.py, tools/validate.py, README_AR.md, README_ZH.md]
- **critical:** true
- **severity:** P1
- **producer:** saitest
- **source_head:** 4451d07340163642c9a6203b33bf7a80585fb3ac
- **source_tree_fingerprint:** git-delta-v1:188e314f78fa94f6e953b760887e106af6910f2a2cc35af91b4f97f081e63b47
- **role_revision:** sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08
- **coverage:** HUNT-12 findings 1-4 and the repaired Ruff gate; exact run record in kitchen/TEST-5.md.
- **payload:** [kitchen/TEST-5.md]
- **verified:** PASS -- 4/4 assigned validator scenarios REPRODUCED; Ruff exits 0; commands are read-only against the project.
- **instructions:** Core repairs the three non-translation failures; saitranslate repairs locale parity; rerun this exact validator command after integration.
- **details:** `python tools/validate.py` exits 1 with exactly four failures: T-1100 lacks a current-cycle VERIFY boundary; improve admission contract tokens drifted; 32 locale README badges are stale; and warning slug `log-soft-cap` lacks a live owner. `python -m ruff check tools` exits 0.

## TEST-6: HUNT-13 sole locale failure independently reproduced
- **status:** stale
- **summary:** A fresh canonical validator run reports exactly one failure and names the same 32 stale locale README badges.
- **main_project_refs:** [tools/validate.py, README_AR.md, README_ZH.md]
- **critical:** true
- **severity:** P1
- **producer:** saitest
- **source_head:** 4451d07340163642c9a6203b33bf7a80585fb3ac
- **source_tree_fingerprint:** git-delta-v1:4ec002cc5f2d23a8858d6c959ec2704e25be28f555a0396e5502685a0a4f3eb6
- **role_revision:** sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08
- **coverage:** HUNT-13 locale parity finding and negative controls for T-1100, admission drift, warning ownership, and Ruff.
- **payload:** []
- **verified:** PASS -- `python tools/validate.py` exits 1 with exactly one failure listing 32 locales; `python -m ruff check tools` exits 0.
- **instructions:** Core accepts the reproduction and routes the 32 locale files to SC-8 saitranslate.
- **details:** REPRODUCED: translation README badge drift affects ar, bg, cs, da, de, ded, el, es, et, fi, fr, he, hi, hr, hu, id, it, ja, ko, nl, no, pl, pt, ro, ru, sk, sv, th, tr, uk, vi, and zh. All three previous non-translation failures are absent.

## TEST-7: regression sweep at 49e66f45 — no failure reproduced
- **status:** reviewed
- **summary:** Independent regression sweep over the post-audit tree; all assigned scenario families NOT_REPRODUCED
- **main_project_refs:** []
- **critical:** false
- **severity:** P3
- **producer:** saitest
- **source_head:** 4451d07340163642c9a6203b33bf7a80585fb3ac
- **source_tree_fingerprint:** git-delta-v1:55f536106504e1e87a44617c149d6c741e6227860e93ddfb56bdd0cb08576776
- **role_revision:** sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08
- **coverage:** Scenario families 1-7 regression against the current tree: core/intent/autonomy/conformance/producer/second-wave/external-audit suites + canonical validator + compileall
- **payload:** []
- **verified:** PASS -- 111 pytest tests, tools/validate.py conformant, compileall PASS; no scenario reproduced a failure against this tree
- **instructions:** Core records a no-op saitest disposition for the crew SC-3 stage.
- **details:** NOT_REPRODUCED across all seven scenario families: the audit regression suites (core 10, intent 40, autonomy 13, conformance 29, second-wave 36, v7-producer 17, external 20) pass, the canonical validator reports conformant, and bytecode compiles clean. No new defect was triggered against the current tree.


## TEST-8: regression sweep at aa96d34a - no failure reproduced
- **status:** reviewed
- **summary:** Independent regression sweep over the post-fdc73e06 tree; all assigned scenario families NOT_REPRODUCED
- **main_project_refs:** []
- **critical:** false
- **severity:** P3
- **producer:** saitest
- **source_head:** 078f5cd6d12e36d24677fc79b86f0457dd70f4ea
- **source_tree_fingerprint:** git-delta-v1:55f536106504e1e87a44617c149d6c741e6227860e93ddfb56bdd0cb08576776
- **role_revision:** sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08
- **coverage:** Scenario families 1-7 regression against the current tree: core/intent/autonomy/conformance/producer/second-wave/external-audit suites + canonical validator + compileall
- **payload:** []
- **verified:** PASS -- 108 pytest tests, tools/validate.py conformant, compileall PASS; no scenario reproduced a failure against this tree
- **instructions:** Core records a no-op saitest disposition for the crew SC-3 stage.
- **details:** NOT_REPRODUCED across all seven scenario families: the audit regression suites (core 10, intent 40, v7-producer 17, second-wave 7, external 21, autonomy 13) pass, the canonical validator reports conformant, and bytecode compiles clean. No new defect was triggered against the current tree.

## TEST-9: current reconciliation regression sweep at c7ea5b1b
- **status:** stale
- **summary:** Bounded regression scenarios do not reproduce the former continue-validation deadlock; ambiguity remains safely blocked
- **main_project_refs:** [tools/saipen.py, tools/saipen_engine/reconcile.py, tools/saipen_engine/paths.py, tools/validate.py, tools/test_reconciliation.py]
- **critical:** false
- **severity:** P2
- **producer:** saitest
- **source_head:** c7ea5b1bb5f8e953c07140cda4f636a382c08310
- **source_tree_fingerprint:** git-delta-v1:cd09a9a79f60d10339408b270b06f59207d15697fa4953d175fa915f891c6249
- **role_revision:** sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08
- **coverage:** counter drift, BOARD checkbox drift, legacy evidence/provenance, deterministic and ambiguous receipt links, recovery contract, cc/continue routing, global tool-root resolution with Windows paths
- **payload:** []
- **verified:** PASS -- `tools.test_reconciliation` 4/4 and full discovered suite 377/377; ambiguous receipt scenario ends with the precise semantic blocker and never guesses
- **instructions:** Core to collect via `saipen sub collect saitest` as SC-3 evidence; no project payload changes are required
- **details:** Scenario 1 NOT_REPRODUCED: deterministic drift repairs and continuation proceeds. Scenario 2 NOT_REPRODUCED: legacy metadata remains truthful and does not globally block current continuation; no evidence is synthesized. Scenario 3 REPRODUCED as the intended safety behavior: ambiguous active receipt refuses with `BLOCKED_AMBIGUOUS_SOURCE_RECEIPT`. Scenario 4 NOT_REPRODUCED: repair is idempotent. Scenario 5 NOT_REPRODUCED: canonical loaded SAIPEN root is used without a project-local probe. Scenario 6 NOT_REPRODUCED: recover CLEAN/REPAIRED is not followed by validation failure for a repairable condition.

## TEST-10: regression sweep at 005a8ac2 — no failure reproduced
- **status:** stale
- **superseded_by:** TEST-11 -- source identity changed; old observations preserved.
- **summary:** Independent regression sweep over the post-T1363 tree; all test suites green, no failure reproduced
- **main_project_refs:** []
- **critical:** false
- **severity:** P3
- **producer:** saitest
- **source_head:** 005a8ac2bdc0bd01fb78a6b693aeac8405283cc7
- **source_tree_fingerprint:** git-delta-v1:728bf9859f927b777aef7a962819e4f731adafc2fbb314669fcec29a98ed2f8b
- **role_revision:** sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08
- **coverage:** Scenario families regression against current tree: test suite + validate.py + ruff
- **payload:** []
- **verified:** PASS -- test suite green, validate.py PASS, ruff clean, no failure reproduced
- **instructions:** Core to collect via `saipen sub collect saitest` as SC-3 evidence; no project payload changes are required
- **details:** Sweep bound to current source head 005a8ac2bdc0bd01fb78a6b693aeac8405283cc7. All signals green.


## TEST-21: adversarial gate scenarios at 6e4cf7d01 -- no failure reproduced
- **status:** reviewed
- **summary:** Independent adversary run against the T-2122 red_owners attribution gate at HEAD 6e4cf7d01; six scenarios across four closed families, all fail-closed or designed-allow, none reproduced a failure
- **main_project_refs:** [tools/saipen_engine/focused_unit.py]
- **critical:** false
- **severity:** P2
- **producer:** saitest
- **source_head:** 6e4cf7d01eaf39f65349c1fa9275193e247d1465
- **source_tree_fingerprint:** git-delta-v1:b13b1eb97d1895f5a714d11cc803b60647ee7c92049c72d41a1e12393165f32a
- **role_revision:** sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08
- **coverage:** seven closed scenario families, exercised: input abuse, boundary, adversarial content, plus a designed-allow and a designed-refuse control
- **payload:** []
- **verified:** PASS -- all scenarios executed read-only against a hermetic temp project (temp prefix saitest-adversary-, never the working tree), bounded to 6 single-process runs, total wall under 1 s
- **instructions:** Core to bind via `saipen crew record-run saitest --package TEST-21`, then collect as SC-3 evidence
- **details:** Scenarios against _red_owners_attribution_problem (T-2122 gate), each an independent fresh invocation, verdict NOT_REPRODUCED (no defect): (1) input abuse A: red_owners entry with a 1,000,000-char unknown disposition -> refused "not in the closed vocabulary", 0 ms, no hang; (2) input abuse B: unicode-confusable owner names (Cyrillic e, Armenian ց) with undecided dispositions naming NON-carried tests -> None/allow, correctly inert because the gate only rules on names the record carries; (3) boundary C: empty red_owners map {} with a carried red -> allow by design (no claims to validate); (4) adversarial content D: forged journal witness via a longer-ticket bracket line ([T-9999] vs claimed T-999) -> refused "not witnessed", the bracket-closed substring check defeats the splice forgery; (5) adversarial content E: top-level red_owners string -> refused "malformed (must be an object)"; (6) control F: resolved owner with a genuinely witnessed [T-999] journal row -> allowed, the designed allow path stays open. No scenario crashed, hung, or admitted bytes that must refuse.


## TEST-22: gate scenario replica at c6b779715 -- no failure reproduced
- **status:** reviewed
- **summary:** Second-pass adversary replica of the T-2122 attribution-gate scenarios at HEAD c6b779715; all four verdicts identical to the TEST-21 family matrix, none reproduced a failure
- **main_project_refs:** [tools/saipen_engine/focused_unit.py]
- **critical:** false
- **severity:** P2
- **producer:** saitest
- **source_head:** c6b779715707cc61fbe45a7057beefd736bc07a8
- **source_tree_fingerprint:** git-delta-v1:b13b1eb97d1895f5a714d11cc803b60647ee7c92049c72d41a1e12393165f32a
- **role_revision:** sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08
- **coverage:** input abuse, adversarial content, designed-allow control; hermetic temp project, 4 bounded fresh invocations
- **payload:** []
- **verified:** PASS -- fresh replica executed this pass at the current tree: enormous(1MB) unknown disposition REFUSE; forged-witness splice ([T-9999] vs claimed T-998) REFUSE; genuine-witness resolved ALLOW; top-level string red_owners REFUSE; matches the expected matrix exactly
- **instructions:** Core to bind via `saipen crew record-run saitest --package TEST-22`, then collect as SC-3 evidence
- **details:** Read-only invocations against the unmodified current-tree engine with a hermetic temp journal; no scenario crashed or admitted bytes that must refuse; nothing new to hand saipython
