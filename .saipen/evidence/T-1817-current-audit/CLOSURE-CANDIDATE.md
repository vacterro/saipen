# Prepared outside the frozen tree: SRC-276 R004 / F-07

This is preparation for the existing blocked parent, not a new claim, applied
root change, lifecycle pass or completion. Scratch binding is closure-scratch.json.
The root's intake.py and all 11 reviewed T-1851 files still match their captured
hashes. Exact candidate, unchanged oracle, before-image and patch are here:
closure-intake-candidate.py, test_src276_closure_outcomes.py,
closure-intake-before.py and closure-candidate.patch.

The candidate reuses _closed_archive_bundle to prove body, metadata, contract,
coverage and revision integrity before returning success or removing residue.
Missing or corrupt sidecars refuse without writes. It checks actual destination
artifacts after an archive move and preserves the existing interrupted-close
recovery. Outer SOURCE_CLOSED codes remain compatible; explicit outcomes are
CLOSED for a first close, ALREADY_CLOSED for a verified unchanged repeat,
RESIDUE_SETTLED for actual hot-surface cleanup and REPAIR_APPLIED for an
actually settled interrupted close. archive_verified is true only after the
complete artifact check. A no-op now returns recovered=false.

Same 11-test oracle and environment: before 10 failures / 1 pass, after all 11
pass. Cases cover healthy no-op, missing body/meta/contract/coverage, malformed
metadata, weakened coverage, real residue cleanup, preservation of residue
beside a corrupt archive, interrupted-close repair and actual native public CLI
refusal. The known-good missing-body refusal remains passing before and after.
Existing source_receipts suite: 170 pass. Existing strict-bundle and settlement
tamper classes: 11 pass. Logs and subject/oracle hashes are bound in
closure-scratch-proof.json. The first attempted scratch command had a copy-path
error and was interrupted; it is not evidence. The recorded pair is the later
complete 11-test discovery with the same unchanged oracle on both subjects.

After T-1851 finishes, resume T-1817 at its actual saved phase. Confirm the
existing source/ownership scope and root preimage before adopting this draft
under an admitted implementation Work. Finish attributable documentation,
failure-path inspection, native executed regression receipt, affected checks,
conformance, REVIEW and local closure through the ordinary lifecycle. A scratch
result substitutes for none of those gates. Reuse unchanged evidence only where
the engine's own identity rules permit it. No live SRC-003 archive or accepted
debt record was edited, no historical authority fabricated and no host UI
acceptance or complete equivalent cc all acceptance claimed.
