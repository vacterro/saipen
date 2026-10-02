# T-1570 isolated reconnaissance

Carrier: `.saipen/kitchen/t1570-no-publish-scope-20260930`.
This is supporting reconnaissance, not current-cycle closure evidence.

The real `release._preflight_plan` applies `intake.release_gate` before its
ordinary no-publish branch. That publication gate requires every unresolved
historical Work's reviewed scope to determine possible artifact overlap. The
live T-1567 helper consequently refused T-1304 before writes. Its refusal and
targeted local closure remain in E-10911 through E-10913; no historical scope
was invented.

The isolated candidate routes ordinary no-publish preflight through the existing
`intake.work_closure_gate` for its active ticket. Public and crew/cohort batch
closure retain `intake.release_gate`. Existing active-scope, identity, manifest,
local-validator and transactional finish machinery remain in place.

The unchanged five-test oracle collected five tests on both subjects:
`prototype-red.txt` records two behavioral failures; `prototype-green.txt`
records five PASS. Real source receipts, coverage, identity, scope, STATE and
BOARD checks are used. Only version-install parity is replaced because this
minimal source-receipt fixture has no versioned protocol install. Thus this
does not prove a complete production closure or its crash recovery.

Controls preserve missing active scope refusal, unresolved active-source
refusal, public unknown historical-scope refusal and batch refusal. Preflight
snapshots prove no writes. Earlier setup errors and dry-run-based experiments
were rejected as evidence; actual preflight is now measured directly.

Canonical lint discovery originally scanned no files inside this unconfigured
carrier. After copying the exact project `ruff.toml`, an explicit new-test
lint invocation passed. The canonical project configuration scans two owned
scripts only; that separate coverage debt is T-1571.

Before adopting this candidate, claim T-1570, regenerate current-cycle oracle
evidence, exercise real no-publish closure and crash recovery, and run the
declared whole core-unit family. The main source tree was not changed here.
