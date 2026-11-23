# T-2040 release-completion fixture correction and proposal repair

## Scope and authority

This artifact separates a stale-test correction from a reproduced production defect. T-2040 remains active BUILD. No live maintenance grant, release approval, publication, commit or shared-index mutation is represented by these checks. Git commits, tags and pushes in the test are confined to disposable local repositories and local bare remotes; `GIT_ALLOW_PROTOCOL=file` prevents remote transports. Native process identity for positive maintenance controls is explicitly simulated through the existing test owner; real broker/Source mechanics in that fixture are not human consent.

## Corrected verifier

`tools/test_release_completion.py` previously asserted a historical 864-entry index, cached diff, remote heads/ancestry, baseline red set and obsolete STATE prose against the live repository. Those observations were neither hermetic regressions nor current authority/publication proof. The inspected AM file was preserved before replacement:

- `.saipen/evidence/T-2040/release-completion-fixture-20261108/test_release_completion.py.before`
- SHA256 `7d68bf3d1d6e59c4ff9cdafbfa577f4aa45d63e38e1e78e63fce81614e2b9a58`
- E-20764 records the correction boundary. An older FAIL cannot be paired with this changed oracle.

The new sixteen-test verifier uses existing unittest/project helpers, explicit host/environment isolation, temporary project identities and local Git remotes. It proves:

1. Exact foreign index preservation, binary staging, rename/delete manifest integrity and mismatched-content detection.
2. Concurrent index changes refuse without restoring over another writer.
3. Real local divergence and exact merge base; integration changes only an isolated worktree.
4. Only reviewed bytes and deletions transfer; unreviewed/archive/traversal paths do not.
5. Baselines do not hide new reds, timeout, zero tests or contradictory exits.
6. Focused-unit evidence cannot authorize full publication.
7. Proposal fields reflect current verified inventory; unavailable inventory refuses.
8. Host capability declarations do not prove broker availability.
9. confirm/TTY/model-supplied/forged carrier inputs do not authorize a release.
10. Unapproved execution remains held; dry-run is not publication.
11. Publication observation binds ticket/project and independently observed destination branch/tag/Git.
12. Local no-publish closure remains local; caller verified/release_id prose proves nothing.
13. STATE authority prose is not a standing maintenance grant.
14. A simulated native grant fails after revocation, material policy change or authority-source drift.
15. Actual canonical claim of independent Work proceeds beside external publication hold, preserving foreign fixture staging.

The first corrected fifteen-test control had two failures: the actual production count defect and a malformed fixture DONE/pending row missing explicit `closure_mode: own_patch`. Only the fixture was corrected; production closure validation was not weakened. Formatting and an added unavailable-root control changed the oracle again, so the final pair below has its own pre-fix red.

## Reproduced owner defect and smallest repair

`tools/saipen_engine/isolated_release.py::generate_release_approval_packet` hardcoded `864 staged paths in primary shared index`. It also returned a proposal for a missing project without a verified inventory. The final oracle reproduced both assertion failures, not startup/timeout/zero-test controls.

The repair reuses `inventory_staged_entries`. Only `VERIFIED_COMPLETE` supplies `index_metadata.staged_entries_count`; incomplete inventory raises `IsolatedReleaseError(INCOMPLETE_INVENTORY)`. Existing decision-request, ancestry and authorization gates are unchanged.

Preserved owner: `.saipen/evidence/T-2040/release-completion-fixture-20261108/isolated_release.py.before`, SHA256 `bcfad9b99bcddca20b89d8274e986e19b90b3b9b60324c9b6b95ed319729613a`. E-20766 records rollback and actual two-failure control. Post-repair owner SHA256 `45d5ce0b6d45b7bc5836853221ce744c66ae385aa5cb5fdaf199aa3326b050b7`.

## Actual same-oracle evidence

Command: `C:\Users\vac34\AppData\Local\Programs\Python\Python311\python.exe -B -m unittest discover -s tools -p test_release_completion.py -v`.

Runtime: Python 3.11.9. Same argv, environment, fixtures, mocks, timeout and verifier bytes. Final oracle SHA256 `4b3052073fd8b9b8edb078cc3f440231c15e93fe652c95f4d9de40e7432c91c7`.

- `final-oracle-before.log`: 16 tests, 7.233s, FAILED (failures=2), exit 1.
- `final-oracle-after.log`: 16 tests, 7.513s, OK, exit 0.
- Matching JSON carriers record selected file identities before/after execution; all six selected files were unchanged during each run. Only the isolated-release owner differs between the two runs.
- E-20767 records the green RUN.
- Installed ruff 0.16.0 passes the owned test. The production file has 34 current lint diagnostics, inherited outside the narrow repair; no whole-file or whole-tree lint PASS is claimed.

These are selected manual execution artifacts, not native executed-regression admission or full-family publication evidence. Native VERIFY admission, affected consumers, campaign requirement mapping and complete lifecycle remain separate mandatory work.
