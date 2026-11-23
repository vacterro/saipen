# T-1790 — bounded foreign-clause dependency route

## Requirement and implementation

The requested child closure route over 34 foreign clauses must stay below 200
characters and retain the owner, receipt and clause count. It must show the
first three clauses rather than enumerating all of them.

`tools/saipen_engine/closure_readiness.py` now limits the note to three clause
samples, the complete count, a remaining-clause count, and the primary owner
with the number of other owners. The structured `unresolved` list remains
complete. Both the router and finish gate already consume this shared decision;
their source was read and no duplicate formatter was introduced.

The pre-existing T-1789 changes in the same file were preserved. This Work owns
only the display-summary delta and the new
`tools/test_t1790_dependency_route_budget.py`. The exact inherited subject is
preserved in `before/closure_readiness.py`.

## Evidence

- Initial fixed-oracle execution on the inherited implementation failed all
  three cases: 34 clauses produced a 514-character route; 34 distinct foreign
  owners produced 749 characters; the singleton omitted its count.
- Focused verification and neighboring ownership/readiness/whole-source
  contracts passed 33 tests. Ruff's one unused-name finding was corrected by
  adding the required receipt-retention assertion to the many-owner oracle.
  The final oracle was then measured against BOTH subjects, not paired with
  an earlier verifier.
- Ruff over `tools/ tests/`, owned-path whitespace checks and all protocol
  budgets passed on the final bytes.
- Native pair:
  `.saipen/evidence/regression/regression-execution-86b4a9cf6bcf4a3699070510498b2201.json`.
  Same verifier
  `78404aca1672117105185b867dfb0ecca1984e73ab618adfde09daab08d12d7c`:
  before exit 1, 3 cases / 3 failures; after exit 0, 3 cases / 0 failures.
  The large-set case executes the emitted canonical block command and proves
  that source coverage bytes do not change. The many-owner case separately
  bounds the owner inventory. All foreign clause IDs remain in structured data.
- The first canonical validation exposed two closure prerequisites: the new
  runtime-manifest test file lacked an index entry, and T-1695's focused receipt
  was stale under this host environment. Its failed result is preserved in
  `local-validation.json`.
- Only the new test path received an intent-to-add index entry. All 5,211
  foreign index entries stayed identical, and the tested content fingerprint
  stayed `afba273e0b7ef3cae3871f8bd5bae7e7c5dc97d33cd4b9b89e7eb3107a1a6edf`
  before and after. This does not stage its contents or publish anything.
- Canonical focused remeasurement of T-1695 executed the unchanged stored
  contract: 38 tests, zero failures, `RV-000056`, `CURRENT_PASS` for its focused
  closed contract (`PASS_WITH_CARRIED_DEBT` overall). DONE history was preserved.
- Canonical validation after those prerequisites returned `VALID`,
  `CURRENT_PASS`, zero problems and nine warnings; typed result preserved in
  `local-validation-after-remediation.json`. The first failure remains intact.

## Family and independent review

The original `python tools/core_unit.py evidence T-1790` process completed
PASS: 6,661 discovered and executed tests, zero red, zero new red, no partition
error, no leaked sandboxes. The typed record is
`.saipen/evidence/core-unit/afba273e0b7ef3ca-20261015T153829Z.json`, SHA-256
`cf4aceb2da0bd993bf0d6ae33623b60c7abe32d6e74f9ae56cbf38ee46dd1a22`.
Its content fingerprint matches the real current tree exactly. The six recorded
descendant PIDs were all absent at the subsequent process check.

REVIEW independently reran all three final owned cases: PASS, zero failures.
`independent-review.txt` preserves that execution. The oracle was strengthened,
not weakened, and the original implementation fails under its final bytes in
the native pair. No P0/P1 issue was found in the display-only delta; memory
promotion NO because existing knowledge already covers the lesson.

Canonical E-15899 records the independent SHIP decision, E-15900 enters SHIP,
and E-15901 binds exactly the two reviewed paths. E-15902 records
`ship v8.1.0 -> skipped publish (no-publish: policy)`. The final SHIP validator
again returned CURRENT_PASS (zero problems, nine warnings), preserved in
`ship-validation.json`. Canonical finish `finish-fb759286c81d4dc5a7ec5f63e5e33781`
completed at E-15903: T-1790 DONE, phase DONE, task none. No commit, tag or
remote was changed by this Work. The overall `cc all` goal remains active.

## Discovery limitations

Tier 2 graph discovery and required coverage checks returned `Transport closed`.
The complete modified module, neighboring tests and exact relevant caller
ranges were read directly. No graph completeness claim is made.
