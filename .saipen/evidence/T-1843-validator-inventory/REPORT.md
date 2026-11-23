# T-1843 missing validator identity

The current validator adds fail site `2a3e0e9689b5a398` at line 6932,
`core-unit publication -- `. Its existing publication gate is unchanged.
The live inventory rejected the absent identity before this change.

The ticket-owned delta is one new adjudicated record and count 358 -> 359.
Comparison with the exact saved `prefix-ledger.json` proves every prior
record and disposition unchanged, with no removed identity or BASELINE growth.
Both versions retain LF representation. The larger Git HEAD delta is inherited;
this Work does not claim or rewrite it.

The new record explicitly says INTENTIONALLY_NO_MUTATION_CASE. A standalone
file mutation cannot establish the coherent current full-family receipt,
source, baseline and environment that the publication condition needs as a
known-good control. The reason names the existing dedicated policy fixtures:
focused-only proof refuses publication, a current full record succeeds, stale
source and a new red refuse, and release execution refuses before invoking its
external validator. No unexecuted mutation CASE or full publication proof is
claimed by this disposition.

The original ticket's positional `audit_checks.py validator-check-inventory`
spelling is unsupported: main ignores that positional token and runs the
entire unrelated sweep. Its exact preimage is retained by canonical ticket
verification history. The corrected minimum uses the real named probe API and
its existing discovery tests. Full final-batch audit and publication remain
independent obligations; no CLI or verifier was changed to hide a failure.

Native executed regression `regression-execution-4f7daefad05f4e6c87c8852d5a775227`
uses the unchanged existing live-ledger test and exact saved preimage. The
post-change real `audit_checks.check_inventory_probe` returned None, including
its added, removed, same-count swap and positional-stability instrument
controls. Final focused record, review and canonical core evidence are in LOG.
