# T-1852 generated host-policy correction

The current root correction is exactly the existing generator's output, SHA256
`8cd916664244d868b4bc53ac3352d54db5b447ca9d3915a92176421be426e3bd`.
`applied.patch` contains the attributable seven-line addition. A direct
before/after comparison proves that every character outside the generated
HOST-INTEGRATION-01 region is unchanged. The unchanged oracle SHA256 remains
`0c46f099fa16f2a4d8b8a22b80ca0c13e845a52dc55971d43736d632ed7294a4`.

The added entry faithfully compiles host_taxonomy's existing FreeBuff missing
operator-provenance diagnostic: STRICT blocks, DEGRADED permits with an
UNVERIFIED diagnostic, and the existing native integration action is retained.
The generator and taxonomy remain the owners. No hand-maintained rule, new
runtime branch, fixture change or changed expectation was introduced.

## REVIEW pass 1 (revision 8cd91666, tree 1174a8d3cb7552cb)

Independent re-run of the ticket verify agreed with VERIFY. All 16
NativePolicyTests passed in 8.0 s through the actual Node plugin, and the
generator check returned `ok: true`. No test, fixture, oracle or verification
command moved in this ticket: `tools/test_t1628_opencode_policy.py` is still
`0c46f099…`, identical to the digest captured in `scope.json` before the fix.
Because the oracle is unchanged and the pre-fix FAIL was measured by that same
unchanged oracle against preserved pre-fix bytes, VERIFY-ORACLE-01 holds.

Self-audit of the exact ticket delta (parse-level comparison of the generated
JSON facet in `plugin-before.js` against the current file):

- top-level keys identical: version, default_mode, strict_mode, aliases,
  labels, gap_codes, identity_observation;
- `failures` gained exactly one key, `FREEBUFF_OPERATOR_PROVENANCE_MISSING`,
  and removed none;
- all 42 pre-existing failure rows are byte-equal before and after.

The new row's decisions are computed by `host_taxonomy.decide`, not authored
here: `decide(SMART/strict)` is `BLOCK`, `decide(DEGRADED)` is
`ALLOW_DEGRADED`, matching the generated values, and `operator_action` equals
`taxonomy.get(...).operator_action` verbatim.

Reachability observation, recorded rather than treated as a defect: the native
transport maps only `gap_codes` (ENGINE_UNREACHABLE, PLUGIN_RESTART_REQUIRED)
plus BINDING_CONFLICT/POLICY_INVALID into the table, so this row — like 38 of
the 42 rows that already existed before this ticket — is canonical-table data
rather than a live `integrationGap()` return value. That is the pre-existing
generator contract: `test_compiled_facet_is_exactly_the_current_canonical_decision_table`
requires the generated block to mirror the complete taxonomy, which is
precisely why omitting the T-1850 code made it red. No new reachability was
claimed or lost by this fix, and no follow-up is warranted.

Consumers checked: `integrationDecision` is a plain table lookup. It selects
`failures.POLICY_INVALID` only when the *policy itself* is invalid, falls back
to `decision: "BLOCK"` and the generic `saipen host doctor` action when a code
has no row, and otherwise reads `row.decisions[policy.mode]` — which is exactly
what the new row provides. No consumer needs a change for an added row, and no
path can reach an undefined decision.
`integrationSystemMessage` branches only on `ALLOW_DEGRADED` versus block, so
the added row needs no change there either.

No P0/P1/P2/P3 finding. No implementation audit applies beyond the above; this
is the executing agent's own inspection, not an independent review. Memory
promotion: NO — the existing installed-plugin generation card already states
the operational constraint, and the reachability observation is a property of
the pre-existing generator contract rather than a new reusable lesson.

Review passes: 1. Verdict: DEC: SHIP.
