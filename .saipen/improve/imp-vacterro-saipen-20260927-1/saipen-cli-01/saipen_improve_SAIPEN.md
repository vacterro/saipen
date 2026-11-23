agent: saipen-cli-01
role: core
model_or_runtime: unknown
project: vacterro-saipen
saipen_version: 8.0.1
protocol_fingerprint: sha256:fc88f2964a19110c15ea273253011fafa8873f3d72093e81ec50413d1565c653
source_head: 3088efffb61de1c4cea9cde2e15daf641654c4dc
source_tree_fingerprint: git-delta-v1:08880725c804b8c10c46f9eddfce1439e7bd19c597b901dd9e32a2649f1962fb
discovery_model: git-delta-v1
context_scope: SAIPEN audit, phase DONE
context_available: partial
report_status: complete

## RUN 1

IMP-001 [P2] [PROTOCOL_VIOLATION] [proven] [ticket]
expected: Every bug-fix ticket can declare regression: required through canonical intake or metadata, so VERIFY-to-REVIEW and finish enforce the same-verifier pre-fix FAIL/post-fix PASS pair.
actual: ticket add has no regression option or parameter and serializes only needs/verify; _regression_gate returns None when the field is absent. T-1533 omitted it and E-10317 passed VERIFY-to-REVIEW with only ordinary RUN evidence.
evidence: tools/saipen/COMMANDS ticket-add grammar and tools/saipen.py option parser expose only --verify/--needs; tools/saipen_engine/operations.py ticket_add has no regression input or field writer; _regression_gate:718-746 explicitly skips absent declarations. tools/test_regression_gate.py manually builds regression: required in its fixture. An isolated canonical ticket_add produced only verify. T-1533 source record has no regression field; LOG E-10317 is its successful VERIFY-to-REVIEW transition.
