# T-2058 release index — provenance verification (2026-11-17)

Operator mandate: OPTION A, conditional T-2058 + 8.1.1 release preparation.
Baseline: HEAD `dc39709c0c17a3272126c01a626ffcaa4176140b`; index snapshot 8332
entries with the 7 pre-existing staged entries preserved; worktree untouched
after the measurement.

## Authorized set measured from the canonical surfaces

Release surface (`release_contract.release_metadata_paths`, 4441 paths) had
exactly 1589 dirty changes:

| status | count | composition |
| --- | --- | --- |
| ` D` | 618 | intake/active 197, intake/contracts 322, intake/coverage 99 |
| ` M` | 9 | VERSION, README.md, README.ee.md, README.ded.md, README.ja.md, CHANGELOG.md, .gitattributes, intake/index.json, intake/audit_inbox.json |
| `??` | 962 | archive/source 744, intake/tombstones 135, intake/active 32, intake/contracts 31, intake/coverage 16, intake/appends 2, intake/distribution 2 |

Delivery paths (recorded release scopes T-2070 / T-2072 at source_head
`dc39709c`, tree `git-delta-v1:1a368781`):

| path | bytes | sha256 | scope |
| --- | --- | --- | --- |
| tools/saipen_engine/audit_route.py | 8823 | a934c36b76aa77682948457a1d7eecd751d2c00b56136bbc3cd5eeb2ec908d0e | T-2070, T-2072 |
| tools/saipen_engine/future_gate.py | 72767 | 40e698a7d30b9edff706e9a4df01b065c728eeaaf2c17e33c4c521333d5a0587 | T-2072 |
| tools/test_audit_route.py | 14196 | af750c505b1a5d66b2aba7cba3eef2aaf8d177a8494bcbed91c582764f515de9 | T-2070, T-2072 |
| tools/test_t2052_pruned_slice_closure.py | 4961 | ff281848ef6a784e36343ea6159f67c53da8303087d8fae9ae40a915df970066 | T-2072 |

All four live hashes equal the recorded scope hashes.

## Per-change reconciliation of the 1589-path wave

Every change is a canonical intake transition: a receipt that was ACTIVE in
`.saipen/intake/` moved to `.saipen/archive/source/` and/or was summarized by a
tombstone, with the coverage dispositions preserved.

- 98 retired source bodies: archived body sha256 == HEAD blob sha256.
- 99 retired meta records: identity fields (`receipt_id`, `source_sha256`,
  `linked_work`, `received_at`) unchanged; only canonical retirement fields
  added (`status: CLOSED`, `storage_status: ARCHIVED`, `archive_ref`,
  `closed_at`/`reread_at` `2026-11-14T22:52:17Z`).
- 322 contract records: JSON-equal to the archive `.contract.json` /
  `.rNNN.json` counterpart.
- 99 coverage records: JSON-equal to the archive `.coverage.json`; the
  tombstone carries the same `receipt_id` and matching
  requirements/actionable/unresolved counts.
- 122 new archive meta records: `source_sha256` == sha256 of the archived body.
- 16 new active receipts: `source_sha256` == sha256 of the live body.
- 824 new JSON files parse; `intake/index.json` and `intake/audit_inbox.json`
  parse.

Two exceptions were inspected and are consistent with the canonical archival
semantics, not data loss:

1. `SRC-167`: the archived coverage carries *enriched* dispositions
   (`UNKNOWN` -> `VERIFIED`/`IMPLEMENTED` with evidence ids E-19105/06/13/16),
   i.e. the archive holds the newer truth.
2. `SRC-130`: `archive_ref` names `.saipen/quarantine/source/SRC-130.md` —
   the exact body is quarantined outside the two owned trees by contract, so
   no `.saipen/archive/source/SRC-130.md` is expected.

## Measurement with the exact release index staged

Index staged with `git add --pathspec-from-file` over the 1593-path allowlist,
then `python tools/validate.py --gate ship` (log:
`ship-gate-indexed.log`):

- 1 problem, 18 warnings. The only problem is `EX-000053` (see BLOCKED.md).
- The archive wave, version metadata, badge parity, release-index binding and
  the runtime-manifest ship-mode checks all passed.
- Scoped tests on the delivered bytes: 36 tests OK
  (`tools.test_audit_route`, `tools.test_t2052_pruned_slice_closure`).

The index was then restored with `git restore --staged --pathspec-from-file`;
`git ls-files -s -z` is byte-identical to the pre-measurement snapshot
(8332 entries, 7 pre-staged entries intact). The 63 parked paths recorded in
`T-2058-narrow-delivery/sha256-before.json` still match byte-for-byte (0
mismatches), so the worktree is the same restored baseline.

## Reproducing the measurement

```
git add --pathspec-from-file=.saipen/evidence/T-2058-release-index/allowlist-nul.bin --pathspec-file-nul
python tools/validate.py --gate ship
git restore --staged --pathspec-from-file=.saipen/evidence/T-2058-release-index/allowlist-nul.bin --pathspec-file-nul
```
