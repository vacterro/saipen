# Improve spec red controls -- mechanical coverage inventory (T-560)

Every one of the 25 Improve spec red controls has a NAMED mechanical check or
probe that goes red when its rule is removed. One owner per rule; a probe
listed here must be a behavioral control (creates the bad condition, demands
the refusal), never a proxy assertion.

| # | Rule | Named check / probe | Class |
|---|---|---|---|
| 1 | reload-before-audit | `[improve-report]` source_head freshness check; probe `a report auditing a stale head fails` | validator + probe |
| 2 | previous-conclusions-not-trusted | same source_head check (a stale head is an audit that did not reload) | validator + probe |
| 3 | partial-scope-cannot-claim-full | `validate_report` partial-scope-over-complete-context; probe `a partial scope cannot claim complete context` | probe |
| 4 | later-rule-not-violation | closed class set includes `LATER_RULE` (schema-level); `validate_report` enforces the closed set | validator |
| 5 | accidental-success | `[sweep-ticket-link]` ACCIDENTAL_SUCCESS with reproduced=y; probe `ACCIDENTAL_SUCCESS recorded as PASS fails` | validator + probe |
| 6 | vague-finding-rejected | `validate_report` expected/actual/evidence triple requirement; probe `a finding without evidence is rejected` | probe |
| 7 | sub-cannot-modify-main | path-safe containment red controls (T-588, `safeid`); PROTOCOL.md boundary | engine controls |
| 8 | one-report-owner | `validate_manifest` shared-report-path refusal; probe `one report has one owner` | validator + probe |
| 9 | append-preserved | `append_run` immutable RUN-section probes (second run appends, never overwrites) | probe |
| 10 | no-ticket-before-verification | `[sweep-ticket-link]` CONFIRMED with reproduced!=y; probe `an unverified finding cannot produce a ticket` | validator + probe |
| 11 | duplicates-one-ticket | dedup scenario: three reports one root cause -> ONE ticket, validator green; two tickets mutation red | probe |
| 12 | invalid-no-ticket | `[sweep-ticket-link]` INVALID disposition carrying a ticket; probe `an INVALID finding must never produce a ticket` | validator + probe |
| 13 | already-fixed-no-ticket | same check for ALREADY_FIXED | validator |
| 14 | confidence-never-overrides-Core | `[sweep-ticket-link]` reproduced!=y even for `[proven]` confidence; probe `confidence: proven does not override Core` | validator + probe |
| 15 | cross-project-recurrence-required | `[sweep-ticket-link]` PROTOCOL_VIOLATION ticket without `recurrence:`; probe | validator + probe |
| 16 | weak-model-test-required | `[sweep-ticket-link]` PROTOCOL_VIOLATION ticket without `weak_model:`; probe | validator + probe |
| 17 | verify-is-delta-only | `[improve-boundary]` doc marker (`delta-only`) | validator (doc drift) |
| 18 | verify-cannot-recurse | `[improve-boundary]` doc marker (`must not recurse`) | validator (doc drift) |
| 19 | original-finding-preserved | `[sweep-ticket-link]` edited-away finding loses disposition; probe `an edited-away original finding loses its disposition` | validator + probe |
| 20 | ticket-links-to-IMP | `[sweep-ticket-link]` source_reports resolution; probe `an unresolvable source_reports ref fails` | validator + probe |
| 21 | improve-does-not-enter-ADD | `[improve-boundary]` doc marker (`never silently enters ADD`) + `[improve-meta-control]` | validator (doc drift) |
| 22 | report-is-not-BOARD-state | `[improve-report]` board-heading rejection; probe `a report treated as canonical BOARD state is rejected` | validator + probe |
| 23 | cleanup-refuses-unswept | `[improve-boundary]` doc marker (`refuses while any finding is unswept`); complete_cycle sweep-coverage gate (T-601) | validator (doc drift) + engine |
| 24 | archive-preserves-provenance | `[sweep-ticket-link]` SWEEP-deletion breaks provenance; probe `deleting SWEEP.md breaks archived-report provenance` | validator + probe |
| 25 | partial-evidence-cannot-close | `[sweep-ticket-link]` CONFIRMED with reproduced=partial; probe `partial/timed-out evidence cannot mark an IMP fixed` | validator + probe |

Probe evidence: `run_improve_probes()` in `tools/run_scenarios.py` (68
behaviors at T-560). A control is red-tested when its probe asserts the
validator/engine REFUSES the exact bad condition; a mutation that removes the
underlying check flips the probe.
