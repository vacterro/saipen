agent: astra-01
role: core
model_or_runtime: unknown
project: vacterro-saipen
saipen_version: 8.0.1
protocol_fingerprint: sha256:a99343a0497b866dffac98b0ba3b6f964061c96c426a816003cdc0d1ce4cd143
source_head: 6c6e2a457125c3a526688cf86892cf660d2f7211
source_tree_fingerprint: git-delta-v1:2967326a976b3b78e29823e80b417c39000eb127b0852b2dd340f59a3263e544
discovery_model: git-delta-v1
context_scope: SAIPEN audit, phase DONE
context_available: partial
report_status: complete

## RUN 1

Core semantic audit at source_head 6c6e2a457125, scope: the source req/disp --dry-run planners after T-1277's grammar-parity fix. One reproduced finding, the state-scoped remainder of the same class.

IMP-001 [P3] [LOGIC_ERROR] [reproduced] [ticket]
expected: `saipen source req/disp ... --dry-run` refuses what the apply path refuses, so an agent consulting the dry-run to avoid breaking something is not told yes where apply says no (the whole point of T-1277).
actual: T-1277 shared the GRAMMAR authority (rid/class/text/disposition), but left the STATE checks in the mutator, and the dry-run planner does not perform them, so three state refusals still diverge: (1) `source req SRC-017 R1 requirement dup --dry-run` returns DRY_RUN_PLAN while apply REFUSEs VALIDATION_FAILED 'requirement SRC-017:R1 exists' (existing rid); (2) `source disp SRC-017 R999 IMPLEMENTED --dry-run` plans green while apply REFUSEs 'unknown requirement SRC-017:R999' (disp on a nonexistent clause); (3) the same shape for any rid absent from the coverage ledger. These are read-only checks (the clause set is already loaded to compute the plan's targets), so the dry-run CAN perform them without a write.
evidence: apply-path refusals live at intake.py:1944 ('requirement {rid} exists') and intake.py:2162 ('unknown requirement {rid}'); the dry-run req planner (saipen.py _source_dry_run_plan, req branch) reads the contract to compute new_revision but never checks `rid in ledger['requirements']`, and the disp branch never checks membership. Reproduced live on SRC-017 (which has R1..R10): existing-rid req and nonexistent-rid disp both plan green, both apply refuse.
action: ticket -- have the dry-run planners read the coverage ledger they already touch and mirror the two membership refusals (req: refuse an existing rid; disp: refuse an absent rid), so dry-run==apply extends from the grammar to the read-only state checks. Not a correctness hole (apply still refuses), a dry-run-trust one, exactly the class T-1277 was raised for.
