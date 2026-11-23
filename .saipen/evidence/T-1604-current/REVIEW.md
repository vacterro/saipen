# T-1604 producer cleanup review

Exact implementation scope: `tools/saipen_engine/evidence.py` and
`tools/test_evidence_hygiene.py`. The producer retries only a genuinely
read-only `PermissionError`, verifies the resolved path against its original
allocation, refuses symlinks/foreign paths, preserves existing mode bits and
lets every remaining failure propagate. Registered trees, registered leaves
and final owned-root removal share this bounded retry. Retention and migration
pruning are unchanged.

Independent REVIEW reran the fixed native Windows oracle on the original
module and live repaired module. The same verifier
`ede023edfb5ebcfc8f736f39d58879b39fae413c565375e47694964c54e6e587`
produced three actual read-only cleanup failures on original subject
`b928417bf1092f6ddbf5baf07532fb7dec00af873c3bf9cf19ed2580d7153ab0`
and four green controls on repaired subject
`1778719abd6df1663841f58aa78499bf0c186cf63e3b4a8b717f45640a165e1a`.
Both retained durable proof and protected the foreign object's bytes/mode.
Review also reran all 27 repository hygiene tests, including nine added
ownership, real read-only object and error-propagation controls.

Fresh complete family record
`.saipen/evidence/core-unit/5e8c632d2983e78c-20261003T153839Z.json`
has 4,864 discovered/executed tests, zero red/new red, unchanged baseline,
no leaked sandboxes, six shards and the unchanged 5,400-second timeout.
Record SHA256:
`84e0f76e45a4225bc538201ab849b48771df692ec6558971cb3711ffe032849c`.
Current source fingerprint:
`5e8c632d2983e78cdf26defbb8a1a9f3c886477efc13eaafcc8cc91eee62b323`.
Pinned Ruff 0.16.0 passed the full `tools/ tests/` scope; core conformance
passed with zero blocking findings and 31 existing warnings.

The two original T-1603 terminal execution roots were reclaimed after exact
absolute ownership and link checks, using existing `core_unit.reclaim`.
The failed relocation attempt's empty fresh root was removed non-recursively
after its sole file matched retained ownership proof. `reclaimed.json` records
the removals and unchanged hashes of all six original durable proof files.
No completed scenario gate was restarted. The original wrapper finalization
failure remains a historical failure; cleanup success does not rewrite it.

The six-check readback in `reviewed-bindings.json` independently confirmed
current source/family binding, absent owned roots and preserved durable proof.
The identical readback rejected the original native subject receipt with two
failures (`known-bad-bindings.json`), so it is not an always-green instrument.

The early lint claim in E-12069 was premature; E-12071 explicitly corrected
its false clause before the successful final lint/family verification.
The failed directory relocation is preserved in the original ownership
artifact and corrected cleanup plan at E-12079.

P0/P1 findings in the exact patch: none. Review passes: 1.
Memory promotion: NO; this bounded standard-library repair adds no separate
decision-bearing reference card.
Verdict: SHIP. Bind the two actual repair paths into the unpublished C-003
scenario/evidence batch. No commit, tag or push is authorized.
