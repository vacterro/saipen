# T-1603 current verification

The native complete scenario command ran on a consistent, settled copy of the
same source tree and baseline. Its genuine terminal result is exit 0, 44 of
44 groups, 1354 grouped checks and no executable failure. Both the snapshot
and live source fingerprints remained
`54ad859af386ae71ba05cd6bd0368cad8fa11b18c546eee41f958f1b56ccb7a9`.
The full native output is `full-current/verify-scenarios.txt`, SHA256
`85b695fddcdf9b87ceef4ed3d5453b8793ef853f09f08e229c8e9fa954fb3a31`.
`full-current/binding.json` binds the actual command, baseline, scenario bytes
and checkpoint files; `full-current/result.json` records the measured result.

The collector process exited 1 AFTER writing those proofs: EvidenceRun's
plain rmtree could not delete a copied read-only Git object. It is not reported
as a successful collector finalization. The temporary tree is partially
reclaimed and remains at the exact binding path. T-1604 owns that P2 cleanup
defect. The complete native gate is not rerun to repair post-test metadata.

The earlier aggregate is preserved separately: 43 of 44 groups, 1258 checks,
release fixture crash on copied operation
`transition-1137166d20694d3abdd14cf53cbc2d6e`. The real operation was recovered
canonically to COMMITTED. An unchanged known-good release-executor run then
passed 140/140 controls. The copy raced the live transition is a supported
inference from that exact operation id and timing; the failed copy itself was
not retained, so its entire operation manifest is not independently inspected.
The retry changed the settled checkpoint input and used a consistent snapshot.

The current VERIFY cycle includes the same fixed external driver on original
and repaired scenario subjects: 227 checks/eight failures versus 230 checks/
zero failures, unchanged verifier and four production/helper hashes. The
unsafe-authority and missing-reconcile negative controls remain red. The
original capture naming failure and its byte-identical relocation are preserved.

Complete core-unit record
`.saipen/evidence/core-unit/54ad859af386ae71-20261003T114625Z.json`:
4855 selected/executed test entries, red 0, new_red 0, real six-shard partition,
matching fingerprint and baseline. This record does not retain exact skipped
counts; it is a green family verdict, not 4855 individually proven PASS results.

The canonical audit_checks command exited 0 under process-local Git longpaths:
12/14 probes proven, zero failed, two host-capability UNPROVEN; 246/247 mutation
controls proven, zero broken, external-file-symlink case unconstructed because
of WinError 1314. That is not a full parity PASS. T-1602 remains blocked and its
denominator is not waived. Five current static evidence marker controls pass.

Publication, foreign working-tree edits, baseline, discovery and timeout stay
outside this repair. Current REVIEW must judge the diff and independent driver
before normal cohort evidence closure. Pending cohort membership is not publication.
