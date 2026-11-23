# T-1629 scoped README candidate

The live CLI owns T-1683. This package changes no live README, kitchen locale,
canonical project state, or producer readiness record.

Eight candidate paths and their exact pre-task hashes are in paths.json and
baseline.json; candidate/ holds the reviewable result and owned-review.patch
shows the bounded delta. Match the baseline before integration and claim T-1629
through the canonical CLI.

The English README replaces the two contradictory daemon claims and places
one truthful local-helper sentence before Quick start. The Estonian, Дед and
Japanese root mirrors and Estonian, Russian, Дед and Japanese kitchen copies
carry equivalent statements. Quick start contains no helper implementation
details. Prior source-digest markers remain unchanged: these are bounded
statement corrections, not full refreshes of the stale translations. Apply
kitchen changes only through the owning producer/collection route; do not
assert READY or update an entire locale's freshness marker for this edit.

No new unit test is needed for this documentation correction. Exact fragment,
placement, UTF-8 and marker-preservation checks are in verification.json.
The required current-tree full-family lifecycle evidence has not been run.
