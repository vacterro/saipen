# T-1348 current module identity evidence

The four-file patch keeps one live object for direct owned tools modules under
their flat and package import spellings. The existing canonical engine finder
is preserved. Foreign flat modules/packages retain their own resolution; an
explicit second execution through a file-location spec remains detectable.

Implementation scope: tools/__init__.py, tools/_module_identity.py,
tools/test_tool_module_identity.py, tools/test_module_duplication_guard.py.
CLI `_AGENT_OVERRIDE` is explicitly observed across both import orders.
Reload re-executes owned source in the existing object and resets that flag.

## Fixed native comparison

`pair.py` SHA256 912b01db167c03885051a2ff7dfb86bdfbe6e92b58f00670e8fef718e9a4b2b5
uses one command, four oracle files, fixtures and timeout300 on three subjects.
Both build-pair and independently allocated review-pair collect 35 tests:
original 9 failures, preserved earlier candidate 2 reload failures, corrected
0 failures. The original and earlier artifacts are retained unchanged.

Verifier: 54dc2e106871b3c9e25fc5a9898596de5c2189420fdc17af06b8b4afd00ec252.
Original subject: e8da2b7d2ad80a567f4758a1eed1ed8899f2c4b2477f19ceb178e8b1a365ca34.
Corrected subject: 0844adfd4892eae01d4cd93139f8163bb8a079160b4f7a123e37f1621749f803.

The updated verifier adds reload execution counts, refuses discovery import
errors/nonzero subprocess exits, requires mixed-import uniqueness, and retains
a real forced duplicate as the detector's negative control. Old prospective
FAIL/PASS is not spent on this new verifier. Canonical native regression pair
arithmetic reports ADMISSIBLE; this legacy row has no regression-required field.

`check_proof.py` SHA256 2e37cff77182f0b25e2b7b75b6f96143ae77271afcdce51c195d7bae7e90c6f4
passes 8/8 for the native corrected receipt and fails 2 checks for the original
receipt. Current source/oracle hashes and retained native output are bound.
Both new pair allocations were finalized and reclaimed. Root .saipen metadata
was excluded from snapshots; nested scenario metadata remained present.

## Current complete family and independent review

Fresh native full family: 4876 collected/run, red0/new_red0, six shards,
timeout5400, duration774.6 seconds, no leaks, unchanged baseline.
Record: .saipen/evidence/core-unit/73a0535196e5c013-20261003T164017Z.json.
SHA256: 7c00355242378e7c871807521e794a653c184801f6286861b11e7e892836b823.
Fingerprint: 73a0535196e5c013219b88b35cf4e275d74e5f1a911edbf4bb22e4b5a55ff13c.
The later native citation honestly reuses that completed unchanged source.
REVIEW independently reran all 35 live identity tests; review-live.txt is green.
Source parse/import, Ruff0.16.0 tools/ tests/, and diff-check pass.

The first core validation failed two untracked owned runtime files. Only those
two files received intent-to-add entries after the live family ended. No staged
blobs, existing index entries, source bytes, commit, tag or remote changed.
The tracking wrapper's exact-flag assertion failed after its preservation
checks passed; retained track_owned.py is not represented as successful.
Read-only inspect_tracking.py checks the actual intent bit instead. Native
verify-core.txt now reports zero blocking findings and 31 existing warnings.

Bounded four-file review: no P0/P1 findings; review pass1. One memory-promotion
check: NO; this is a cheap source-level import trap already pinned in code and
tests. Graph generation2026-09-01 is stale and tools/ excluded; all material
source claims use exact current reads and native controls.

Closure is local shared cohort C-004, pending publication. It proves acceptance
against current bytes and does not retire/supersede a historical ticket or grant
publication/admission authority. The preserved older prospective temp root and
its historical automatic-cleanup refusal were not retried or bypassed.
