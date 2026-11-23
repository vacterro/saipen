# Compatible single-flight execution — T-1832

The existing core/focused runners and OS `FileWriterLock` now coordinate one
execution for compatible consumers. The identity binds source, baseline,
verifier bytes, effective stable child environment, interpreter, toolchain,
configuration and requested scope. Unknown script-runtime closure prevents
historical replay. Legacy evidence remains readable without being promoted to
newly proven compatibility. No second verdict store or execution controller
was introduced; shared results are intact existing execution records by digest.

Three actual CLI consumers demonstrably execute the probe once and independently
cite one record. Both concurrent fresh requests and real failed executions have
controls; failure is propagated as failure. Latest compatible red evidence does
not resurrect an older green. Configuration/runtime/profile/tool-content changes,
tampered receipts, scope mismatches, cancellation, dead owners, bounded waiters
and incompatible requests have negative or recovery controls.

T-1833 completed the POSIX registration-before-exec and owner-death process
boundary. T-1834 corrected two actual host diagnostic inputs
(`CODEX_TOOL_CALL_ID`, Windows `PROMPT`) in the executed child environment.
Actual interpreter differences still refuse compatibility: the evidence harness
was aligned with the observed managed runtime rather than weakening the gate.
In the final unchanged 13-check generation, first execution took 81.000 s of
request wall time; a separate request reused it in 6.016 s. T-1833 then cited
that same actual record independently in 5.718 s. This is a bounded repeat-
feedback saving, not a full-suite throughput or campaign verification-share claim.

Parent follow-up found that killing an owner left its small private guard
directory after its process group had been reaped. Two identical real Linux
controls failed before the correction and passed after it. The guardian now
unlinks only its known ready/info files and removes their empty private
directory; an early dead-parent bootstrap does the same. No unknown directory
tree is recursively removed and no broad temp sweep is introduced. All 20
parent controls pass Linux, and all eight owner-boundary controls still pass
after the cleanup change. The standalone before/after directory control also
passes. Legacy residue observed before this fix was preserved; this does not
claim a global cleanup of every historic directory or every pre-spawn crash.

`check_concurrent_pair.py` runs the identical final real three-consumer oracle
against a private indexed prefix executor and current executor, with the same
fixtures and configuration. Prefix fails at the missing coordination barrier;
postfix proves one execution/record for three independent consumers. It does
not claim a measured three-execution prefix count, which that red oracle does
not reach. `concurrent-pair.json` binds the subject and oracle hashes.

Final canonical package: 93 reported tests, PASS, record
`2c6df463f1f840ab-20261020T164558195840Z.json`; initial request 185.859 s, unchanged
review reuse 5.938 s. The package retains its reported platform skips; the Linux
20+8 controls above are actual executions, not substituted Windows PASSes.

T-1832 finished locally at E-16719. C-007 and C-008 already bind older shared
file generations, so their admission refusals were preserved. `continue`'s
documented finish-at-ship path performed the actual own_patch finish; canonical
`ticket bind-cohort` then bound that same reviewed unpublished Work to new
pending C-009 at E-16722, preserving original closure evidence. Publication and
complete stable-generation/platform acceptance remain owed by the larger
campaign. R003/R004/R006/R007/R008 and final mission delivery are not closed
by these bounded concurrency checks. Next: resumed T-1829 SCOUT, formal tier/
impact selection and final-batch provenance audit, with original requirements.
