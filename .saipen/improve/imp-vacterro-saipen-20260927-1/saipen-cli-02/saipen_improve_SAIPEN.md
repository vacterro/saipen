agent: saipen-cli-02
role: core
model_or_runtime: unknown
project: vacterro-saipen
saipen_version: 8.0.1
protocol_fingerprint: sha256:fc88f2964a19110c15ea273253011fafa8873f3d72093e81ec50413d1565c653
source_head: 3088efffb61de1c4cea9cde2e15daf641654c4dc
source_tree_fingerprint: git-delta-v1:319ec5af76af00d20a3004a8c724dde676601ffb4e00992bb2f1671af71ca275
discovery_model: git-delta-v1
context_scope: SAIPEN audit, phase DONE
context_available: partial
report_status: complete

## RUN 1

IMP-001 [P2] [PROTOCOL_VIOLATION] [proven] [ticket]
expected: Canonical ticket intake can explicitly persist regression: required so VERIFY-to-REVIEW and finish enforce the same-verifier pre-fix FAIL/post-fix PASS pair.
actual: ticket_add accepts no regression argument and serializes only needs/verify; _regression_gate skips tickets with no declaration. T-1533 omitted the field and E-10317 transitioned it to REVIEW on ordinary RUN evidence alone.
evidence: tools/saipen_engine/operations.py:6161+ exposes only priority/description/needs/verify and writes those fields; tools/saipen.py:8751 and :9518+ only parse --verify/--needs; _regression_gate:718-746 returns None when regression is absent. tools/test_regression_gate.py manually constructs regression: required instead of using canonical intake. T-1533 has no regression field in .saipen/BOARD.md; .saipen/LOG.md E-10317 records its successful VERIFY-to-REVIEW transition. The prior isolated ticket_add reproduction produced only verify.
