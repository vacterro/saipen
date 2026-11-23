# Verification tiers and retained invariants

This is an implementation audit for SRC-285 R003/R004, not additional law.
The owners remain `phases/verify.md`, `phases/ship.md`, `focused_unit`,
`core_unit`, the declared test families and the existing release executor.

| Concept | Existing implementation / current addition | What it proves |
|---|---|---|
| STATIC | repository syntax/import/schema checks; impact `--plan` is analysis only | only the checks actually executed; a plan has `executed: false` and creates no verification citation |
| FOCUSED | existing `core_unit.py focused` and focused record family | selected patterns on an immutable current generation, runtime/environment and baseline; reviewed local ticket scope |
| IMPACT | `core_unit.py impact`, current plan plus existing full discovery/shard filter | certified closed static subset, exact canonical occurrences, imported TestCase provenance, fixture order and visible import errors; record remains `focused-unit` |
| FULL | existing complete declared family execution and records | full coverage of the named family; `unit` is the full core-unit family, not a substitute for other canonical families |
| RELEASE | existing release executor, ship validator, portability/distribution/security acceptance and CI contracts | every independently required release gate; neither focused nor impact evidence replaces any full-family or whole-suite requirement |

An entire-canonical-suite request still requires all families declared by
`test_runner._families`. Calling the core-unit family FULL does not claim that
consumer-unit, portable floor, scenarios, lint or installed acceptance ran.
CI/local family-interface parity and final multi-family execution are still
open campaign work. No shortcut is inferred from a level name.

## Old and new lifecycle invariant

Before T-1828's opt-in policy, every local SHIP transition of a project declaring
the core-unit family required a current-cycle complete core-unit record. The
safety property was that a publishable source generation could not outrun its
full evidence. It also forced an expensive repeat at small ticket boundaries.

The existing opt-in policy permits reviewed focused evidence for local ticket
completion while keeping a complete passing full-family record of the final
batch mandatory at publication. Projects without the exact policy retain the
legacy full local gate; malformed policy refuses. Pending local completion is
not publication. Earlier cohort/member hashes and finish history are preserved.
Generation changes require fresh appropriate evidence; compatible unchanged
records may be shared, with a separate citation for each legitimate consumer.

This wave does not weaken that amendment. It adds an explicit IMPACT subset
within the focused family, verifies its generation/inventory/selection manifest,
and rejects attempts to relabel its output or configuration as full evidence.
The same full-scope predicate is consumed by full record production, cache load,
reuse, local full SHIP and full publication checks. A controlled negative
oracle found the pre-guard publication predicate accepting an incompatible
scoped configuration; current checks reject it. Exact evidence is in
`scope-pair.json` and `prefix-relabelled-scope.log`.

Supported publication routes retain the existing `focused_unit.publication_gate`
checks in the release executor and `tools/validate.py --gate ship`. Local
transition uses `core_unit.ship_gate`. Raw Git actions outside those routes,
unproven host enforcement and unresolved operator hook/publication decisions
do not become covered by this audit; no mechanical host guarantee is invented.

## Impact input and uncertainty

Plans bind changed paths, current source fingerprint, source inventory digest,
canonical test-module inventory, selection reasons and verification contracts.
Default changes come from tracked plus untracked Git changes. Explicit scopes
do not certify unlisted changes; visible Git-changed test files are still added.
No Source or operator authority is inferred from a plan or its digest.

Only a closed static import/call domain may narrow automatically. Unknown
imports, file/reflection effects, namespace/callback escape, mutable shared
objects, dynamic loaders, magic module identity, fixtures and safety-contract
boundaries escalate. Opaque Python is not declared dynamically complete.
Once FULL is inevitable, stopping additional dependency analysis changes no
required test coverage; the output explicitly reports incomplete scanning.

The actual SAIPEN repository currently escalates to the full unit family.
This is a measured coverage limitation, not an automatic narrowing success.
Manual FOCUSED remains available under its existing explicit reviewed scope;
it is not renamed IMPACT to bypass uncertainty. No multi-hour suite is launched
merely to print an escalation; execution must use the required existing full
interface at a justified stable boundary.
