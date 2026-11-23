# Campaign XI P1 scoreboard -- T-2162 (final, measured from full evidence records)

Work: T-2162 -- declare test_outbox_write_time_bar.py + test_sub_dispose_after_collect.py [] in tools/sandbox_scope.json
Patch files: tools/sandbox_scope.json (+2 entries, no other bytes; alphabetical positions audited)
Measured cause: T-1889 DEFAULT-IS-FULL plus one-undeclared-pattern-makes-the-whole-run-full forced the 23-test corridor through a full sandbox copy (67.86 s of a 105.83 s wall) while the selected tests execute in ~18-21 s; only the two named modules lacked declarations.

## Before (mode FULL, same runner, same machine, same selection)
  4404dda4f5d33ff2-20261122T091934843665Z.json: dur 105.828 s | exec 18.094 | copy 67.859 | cleanup 17.234 | ran 23 | mode FULL | undeclared ['test_outbox_write_time_bar.py', 'test_sub_dispose_after_collect.py'] | record 4404dda4f5d33ff2-20261122T091934843665Z.json
  decomposition: execution 18.094 + environment identity 2.468 + copy 67.859 (subject_copy 16.328 + canonical_copy 51.203) + hash 0.141 + cleanup 17.234

## After (3 fresh runs, mode DECLARED, patched manifest as the only changed variable)
  63c8a2c81a81cbf4-20261122T094835048547Z.json: dur 25.109 s | exec 21.484 | copy 0.609 | cleanup 0.141 | ran 23 | mode DECLARED | undeclared [] | record 63c8a2c81a81cbf4-20261122T094835048547Z.json
  63c8a2c81a81cbf4-20261122T094913426185Z.json: dur 23.656 s | exec 20.14 | copy 0.656 | cleanup 0.125 | ran 23 | mode DECLARED | undeclared [] | record 63c8a2c81a81cbf4-20261122T094913426185Z.json
  63c8a2c81a81cbf4-20261122T094951341930Z.json: dur 23.578 s | exec 20.156 | copy 0.578 | cleanup 0.11 | ran 23 | mode DECLARED | undeclared [] | record 63c8a2c81a81cbf4-20261122T094951341930Z.json

Membership parity: per-pattern ran counts identical before/after (test_outbox_write_time_bar.py: 6, test_producer_gate_policy.py: 11, test_sub_dispose_after_collect.py: 1, test_t1430_crew_run_receipt.py: 5); 23 tests in both; zip per-run entries identical; no skip fields in either record (0 -> 0).
Tree identity: before fingerprint 4404dda4f5d33ff2; after fingerprint 63c8a2c81a81cbf4 (the delta is the manifest itself -- the tested instrument declaration).
Wall result: 105.83 s -> 25.109, 23.656, 23.578 s (best 23.578 s, ~78% lower); COPY 67.86 s -> 0.609, 0.656, 0.578 s (target <5 s met); target wall <30 s MET.

Machinery battery (same patched tree, mode FULL -- honest: the machinery modules test_sandbox_work_surface.py and test_t1505_core_unit_sandbox_reclaim.py are themselves undeclared):
  63c8a2c81a81cbf4-20261122T095216194446Z.json: dur 129.265 s | exec 21.032 | copy 84.141 | cleanup 21.218 | ran 46 | mode FULL | undeclared ['test_sandbox_work_surface.py', 'test_t1505_core_unit_sandbox_reclaim.py'] | record 63c8a2c81a81cbf4-20261122T095216194446Z.json
  ran 46 verdict PASS: T-1889 refusal battery intact (malformed manifest refusal, subject-dropping entry refusal, missing-subtree refusal, INV-20 narrow-record replay guard, pre-T-1889 record refusal once a manifest narrows); refusal-registry semantics unchanged.

Correctness equivalence: identical selection, runner, machine, day; the manifest is the only changed variable; membership and skip counts asserted equal from the record files themselves.
Negative controls: the T-1889 suite battery (in the machinery run) plus the resolver's own DEFAULT-IS-FULL behavior observed live: the machinery run stayed FULL exactly because two machinery modules are undeclared -- the decision remains load-bearing, not decorative.
Windows acceptance: DECLARED copies fewer trees through the same Windows filesystem path; no junction/symlink handling changed; both modules build isolated tmp roots; sub_dispose_after_collect reads only the shipped source-tree scenario fixture (tests/scenarios/saiui-adoption).
Source publication status: sealed in this Work's ship commit (repo manifest + evidence).
Installed runtime status: untouched (the runner reads the manifest from the tested subject; installed engine generation unchanged -- no provenance drift from this patch).
Next bottleneck: (1) the two remaining undeclared focused modules (test_sandbox_work_surface, test_t1505_core_unit_sandbox_reclaim) need their own narrowed-run evidence; (2) Campaign XI 17C repetition audit (7 full-family + 85 focused records); (3) 17D per-test profiling of test_t1613_publication_convergence (251.1 s) and test_t1553_mid_session_activation (179.5 s).

