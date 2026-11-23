# SRC-276 R004 / F-07: confirmed current typed-outcome gap

Read-only next-Work investigation while T-1851's exact subject is frozen.
No live project, production source or current claim changed here.

The actual existing close_receipt path reaches
intake._settle_closed_residue_locked (intake.py:4382) for an existing tombstone.
It validates only the archived body digest, optionally removes stale active
bytes, and always returns SOURCE_CLOSED with recovered=true. It does not
validate the archived metadata, contract or coverage before that success.

probe-closure-outcomes.py used the repository's existing SourceReceiptTests
fixture to close a valid disposable source, then repeated closure in five
separate fixtures. Exact results: closure-outcomes-before.json.

* Healthy repeat: ok=true, recovered=true, residue_removed=false, no file
  changes, archive validates. This performed no repair.
* Missing .meta.json, .contract.json or .coverage.json: each repeat still
  returns ok=true/recovered=true, changes no file, and the real intake
  validator still reports one archive problem. This is not a repaired archive.
* Missing archived body: current close correctly refuses; preserve this
  control, full sidecar integrity and no fabricated replacement metadata.

This proves a current gap in the engine response/postcondition. It neither
proves that a current real SRC-003 bundle is broken (it is healthy) nor
attributes historical loss to a specific writer. Original source scope stays
intact; no duplicate ticket or blanket historical reconstruction is justified.

After T-1851 closes and T-1817 actually resumes, route this under its existing
R004/F-07 ownership. The minimal contract should explicitly distinguish an
unchanged ALREADY_CLOSED verified archive, RESIDUE_SETTLED, and actual
REPAIR_APPLIED, with full current artifact verification before any archive
success. Keep compatibility of existing outer codes where feasible, but never
let a legacy recovered boolean imply an unperformed repair. Test both actual
positive outcomes and all missing/corrupt sidecar no-write refusals through the
native close path; use the identical oracle against pre-fix bytes.

The other parent requirements (historical authority, routing/deduplication,
typed finding ownership, separate ZAICODE delivery and full equivalent cc all
acceptance) remain open. This probe is evidence, not their completion.
