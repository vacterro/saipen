# T-1698: invalid named audit diagnostic identity

Two invalid named drops produced identical `layer:null` identities in both
status and routing summaries. The underlying snapshot and inspection APIs
retained the correct path and refusal, so this was a P2 diagnostic defect.
No unsafe capture, deletion, execution or lifecycle completion was observed.

The shared `_invalid_summary` adds `path` for named drops only. Numbered
summaries keep their existing exact shape. Scope: audit_inbox.py and its
existing test_audit_inbox.py; four permanent regressions, no new module,
dependency, registry change, deployment or publication.

`regression.py` is the unchanged four-case verifier. It loads only the
selected production module into the existing package and uses the unchanged
AuditInboxFixture. Pre: four collected, two named assertion failures and two
passing numeric/byte controls, no errors. Post: all four pass. The original
production and test bytes survive under pre/. E-14091/E-14092 anchor the pair.

The composed cleanup/admission ordering hypothesis was rejected by direct
source evidence: CLI ingest returns immediately after settling closed layers.
Actual cleanup E-14086 removed only the proven SRC-197 generation; the next
canonical continuation selected existing T-1698, ahead of fresh named drops.

Two attempted checkpoints during our own executed T-1695 reverify safely
returned WRITER_BUSY with zero writes; they were retried after its lock released.
RV-000007 re-executed the inherited current-tree closure checks; the historical
post-DONE evidence debt remains explicitly carried, never rewritten.
