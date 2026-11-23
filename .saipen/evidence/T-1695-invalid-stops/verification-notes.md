# T-1695 invalid-data stop projection

Captured during VERIFY while the full family was still running.

Original request: `.saipen/intake/active/SRC-200.md`, retained byte-for-byte;
SHA256 `7df120d86970f5e6fe211c701181abaa86c0ba6cbaccf1bf0d53a849863e9fb4`.
Its two normalized clauses request continued local strengthening and truthful
continuation boundaries. This ticket does not claim to complete the older
global goal or the 62 parked tickets.

## Observations and change

The existing router classifies an unreadable audit layer as
`audit-inbox-invalid` and an unreadable unprojected Source as
`queued-source-invalid`. Both carry `RESTATE_AND_STOP`. Automation mapped
the first to CONTINUE and let the second fall through to CONTINUE. With a
clean audit and all eight closure conditions satisfied, the second became
COMPLETE despite the invalid Source.

The three-path owned delta changes those two existing reason mappings to
INVALID, before the existing closure promotion. The canonical response owner
projects their existing diagnostics into a named blocker and `NONE` next
action. Lifecycle phase is preserved. The router, pick rule, closure
conditions, WAIT categories, authority, validation rules and baselines are
unchanged. No additional remaining-work predicate is introduced.

## Regression instrument

Six permanent controls run through the real router and automation owner. An
actual invalid UTF-8 layer exercises audit classification; a queued invalid
projection exercises the router's own stop. The queued control explicitly
proves that the separate eight-condition closure gate would otherwise admit
completion. Two inverse controls protect active continuation and independent
workable audit-side Work.

The initial active-control fixture omitted the mandatory claim timestamp and
therefore reproduced a fixture binding error. It was corrected before the
production edit and before the authoritative red control. This was not a
failed production fix. The final verifier remained unchanged across the
preserved/current subjects: four assertion failures against the preserved
owners, six PASS against the repaired owners. `verify-pair.json` binds the
commands, subject hashes, verifier hash and output hashes. Existing 32 test
methods retain identical ASTs; only six methods were added.

Four public CLI scenarios independently exercise unreadable audit and
captured queued-Source bytes, each with idle and active lifecycle state.
Invalid data emits a visible diagnostic without cc or an invented human
decision; active Work continues silently. Both diagnostic digests pass the
public response classifier and style gate. These checks report admission
`NOT_CONSULTED`; they do not prove native host enforcement. Read-only status,
digest and check commands leave every scenario file byte-identical.

## Available verification

- Whole-source refusal, command-reachability and explicit UTF-8 contracts:
  21 tests PASS before the broader family.
- Focused automation, response, digest, fact-binding, audit inbox and the
  three whole-source modules: 213 tests, zero failures, one environment skip.
  Exact commands and output hashes: `verify-checks.json`.
- Canonical Ruff and whitespace checks: PASS.
- Full declared core-unit family: running; no PASS claimed by this note.

The legacy security and performance directories contain example templates,
not configured mandatory scanners or benchmarks. The source delta introduces
no credentials, dependencies, host integration or external writes.

## Preservation and remaining work

`scope.json` records raw pre/current hashes, exact paths and the inherited
staged-delta hash. `owned.patch` isolates this ticket from the inherited dirty
tree; `verify-integrity.json` proves unchanged existing controls and index.
`before-boundaries.json` records all 62 parked tickets and verifies all 15
preserved T-1606 candidate hashes against their manifest. The repair does not
lift T-1606's retry cap, grant publication or default-hook authority, supply
separated host authority, or settle other external requirements.

Graph evidence is Tier 2, generation `2026-09-01T13:16:39Z`. Tools are excluded
by design; material code claims use exact source, the owned patch and executed
controls. No graph-completeness claim is made. Existing automation-owner and
red-control knowledge already cover the decision; memory promotion is not
needed.

VERIFY and REVIEW remain open until their required completed gates are
recorded. No publication, staging, commit, tag, injection or push occurred.
