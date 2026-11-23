# T-1597 isolated native preparation

This is not a claim, a live edit, acceptance, or DONE. Live phase is T-1515 VERIFY; the owner is freezing production during its six-shard declared-family run. Preparation lives only in this evidence directory.

The current `HeldSandboxTests` has three test methods although T-1597's compact minimum says four. Its `hold` sleeps 0.5 seconds, then returns without observing that the child acquired its Windows current-directory handle. `held_within` subsequently calls the destructive `reclaim` while waiting; an unready child permits deletion and the fixture goes falsely red.

`held_startup_probe.py` proved this with a real owned Windows process: the directory was reclaimable before the primary thread started, then non-reclaimable after the child printed READY. Only an owned disposable process and directory were affected and both were reclaimed. CREATE_SUSPENDED and ResumeThread follow their [Microsoft creation-flags contract](https://learn.microsoft.com/en-us/windows/win32/procthread/process-creation-flags) and [ResumeThread contract](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-resumethread).

`held_startup_oracle.py` holds four checks fixed: the three unchanged existing test bodies and one independent readiness-before-reclaim check. It creates real native children suspended, resumes them after exactly two seconds, and keeps command/configuration/timeout unchanged between subjects. Construction failures, missing tests, skips and resume failures refuse rather than count as a pass.

| Subject | Ran | Failures | Errors | Skips | Result |
| --- | --- | --- | --- | --- | --- |
| Current original holder fixture | 4 | 3 | 0 | 0 | FAIL |
| Isolated candidate holder fixture | 4 | 0 | 0 | 0 | PASS |

Both records bind verifier `03562694cfe74c437cd520c1560759375824ed0aa1b96825becdd0216e90f76f`. Original subject: `2afaef42922d0316ee84c052da824988297ea5ac9638bd34087ab4da9841e340`; candidate: `d4dadf5def93eb12c650924c8306a2f35c6aaeabffa8de801528b3c7c06110b1`. The common existing test bodies are compared structurally before execution; the success definition did not move.

The candidate replaces elapsed-time readiness with a bounded READY signal, owns the child's lifetime through stdin until cleanup, and preserves the existing stale/live-owner and handle-release controls. Startup failure/timeout remains a test failure. No production reclamation behavior changed. The live test file was not edited.

Before integrating: take the actual T-1597 lifecycle, confirm the live original still matches, preserve any concurrent edits, carry the fixed native regression into repository-style verification, run affected neighbors and the unchanged six-shard family, and complete VERIFY/REVIEW/SHIP through canonical operations. Reconcile the stale four-test wording truthfully. This preparation grants no source/operator authority and waives no global goal budget or publication gate.
