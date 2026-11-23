# T-1852: generated OpenCode policy parity

Actual current complete T-1851 family, source ce7fb7fc2e8c58a6, reports the
unchanged NativePolicyTests.test_compiled_facet_is_exactly_the_current_canonical_decision_table
as FAIL. Independently executed unchanged native test in the external scratch
copy also fails: the compiled table lacks FREEBUFF_OPERATOR_PROVENANCE_MISSING.
T-1850's current 7-line host_taxonomy delta added that registered diagnostic.
Its pending C-019 scope did not include the generated plugin facet. Current
BOARD search found the earlier DONE T-1628/T-1688 and DONE T-1850 owners, no
unfinished corrective Work for this newly observed exact parity failure.

Existing native_host_policy generator check also returns false. Running its
ordinary --write operation only in scratch makes the same unchanged native
test pass. All 16 existing NativePolicyTests then pass, including actual Node
plugin effects under degraded/strict, foreign and ambiguous bindings, policy
changes and unreadable payloads. Logs are currently preserved under the parent
T-1851-debt-authority/policy-facet-{before,after,compatibility}.log. Before-image,
candidate, unchanged oracle digest and generated-region-only proof are bound
here by prepare.py. The root plugin is still unchanged while that family lives.

Bounded correction: after the full family's actual terminal result, use the
canonical active-parent block-for/claim lifecycle to admit this Work; regenerate
the root plugin with the existing owner, do not hand-maintain taxonomy data.
Preserve every plugin byte outside the generated region and the original
T-1850 diagnostic and strict/degraded decisions. No test/oracle edit is needed.
Then native executed regression, affected checks, conformance, self-audit,
REVIEW and pending-cohort closure; restore T-1851's saved VERIFY phase. This is
not a waiver of the final complete-batch gate or of either parent's mission.
