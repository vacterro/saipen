# T-1851 current implementation checkpoint

Parent T-1817 / SRC-276 remains blocked on this concrete F-05 child. All eight
parent clauses and the complete external/host/history mission remain open.
The real SMART_VAC_MEDIA_COMPRESSOR project has not been mutated.

Actual before control: public registrar accepted nonexistent SRC-047; real
validator exited 0 and downgraded provenance failure to WARN. Parent evidence
is `T-1817-current-audit/authority-gap-before.json`. New unchanged six-case
negative oracle also went red before the implementation and green after.

Current implementation adds `debt_authority.py`, uses the existing separated
broker's new prepare/verify debt domain calls, and requires an exact original
native `resolve-gate` authority-only Source. A journal or matching file/hash
does not prove permission. The broker retains the exact approved record and
operation independently. Reader reports KNOWN/UNKNOWN; unknown legacy records
cannot downgrade a failure or be laundered by rebind. A genuinely fresh scoped
decision can append a new record explicitly superseding an unchanged old
unknown record; it never promotes the old Source or rewrites old bytes.

Pure preview, authority capture support, public registrar, registration
semantic verification, immutable event hashes, Source/history read pins,
revocation, exact replay, registered worker, lineage-preserving move and
same-effect retry before a journal exists are implemented. Existing positive
fixtures now obtain explicit simulated-native authority through the actual
broker. The new tests are explicitly simulated native identity, not host UI
acceptance. Both new 27-case selection and unchanged old 28 acceptance/rebind
assertions passed; whole tools/tests Ruff passed at that revision.

Latest added crash tests revealed a mistaken test assumption: canonical
journal recovery ABORTS a PREPARED operation with zero materialized targets.
It correctly does not roll that operation forward. Three tests currently fail
because they expected roll-forward/refusal instead of this safe ABORTED
outcome. Do not weaken or change the generic journal rule. Complete domain
retry of the same already approved effect after a proven abort under a fresh
operation attempt, retaining the original reservation scope and old journal.
Also test actual post-write/VERIFIED crash recovery and revoked/changed-Source
refusal, and check the real target after any ALREADY_APPLIED result.

Still due: finish crash/retry and malformed-input controls, canonical public
preview/help/interface notes, final code inspection and lint, current native
executed same-oracle pair, affected broker/Source/acceptance/portability checks,
focused receipt under the SAME DEFAULT environment used by the launcher,
current external T-1653 renewal after the final engine edit, Core conformance,
independent REVIEW and local pending-cohort closure. No SHIP or full-family
publication claim yet. Authority owner loss remains UNKNOWN under the existing
kernel; no new signer, key file, MFA or proof-env bypass is introduced.

Before-images are in this directory's `before/`. All original staging was
saved in `original-index.bin`; only two newly introduced files were added to
the index, and their later working edits are still unstaged. Other inherited
source/index changes must remain intact. No full-family run is live now.
