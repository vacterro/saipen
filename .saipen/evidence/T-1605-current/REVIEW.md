# T-1605 closure-binding review

The implementation adds explicit recovery of verified unpublished own_patch
DONE into a pending shared cohort. It preserves the canonical original finish,
its row in an immutable recovery artifact, active Work and goal counters.
It neither replays completion nor grants publication.

Review found three missing read dependencies in the inherited implementation:
intake changes after planning, publication after planning, and a registry change
between its first read and target construction. Three unchanged concurrent-writer
controls fail on the preserved pre-CAS implementation and pass on the repair.
The planner now uses existing safe file/tree CAS tokens captured before these
decisions. The journal, source paths and canonical checkpoint remain bound too.

The fixed four-case oracle includes the real public CLI on canonical-writer
fixtures. The original implementation fails that public positive with unknown
ticket action, and lacks the three recovery planner controls. The intermediate
implementation passes the public positive but fails all three writer controls.
The final implementation passes all four. All receipts use verifier SHA256
f69693107ae648e708f326da20bf1f6cde76dae4eeb355f7136efbfff4de03c4.
The complete focused module has 54 passing tests, including 20 binding controls.
Ruff 0.16.0 passes the full tools/ and tests/ scope; whitespace checks pass.

The graph generation is 2026-09-01T13:16:39Z and deliberately excludes tools/.
Graph absence is not used as evidence; all relevant implementation and helpers
were inspected directly. Existing unrelated dirty files and staged additions
were preserved. No dependency was added and no release operation was attempted.

The first complete family correctly failed two integration checks: the writer
prefix was unregistered and new normative documentation exceeded the old total
bound by 1,122 bytes. The actual 32-hex writer is now registered. The aggregate
capacity was explicitly re-derived to the smallest whole KiB (303), with the
original failure retained; no rule or document was dropped. `load-budget.md`
records this contract change separately from unchanged-oracle regression proof.

The fresh final family record is
.saipen/evidence/core-unit/32267b416e4798f7-20261003T191632Z.json,
SHA256 ca3a591de92efac01ec4978f3a8aac10382882a6a69361f7eff2236178714de1:
4,896 tests, zero red/new red, no leaked sandboxes, unchanged baseline, six
shards and the same 5,400-second timeout. Core validation is CURRENT_PASS,
zero blocking findings and 31 retained warnings.

After entering REVIEW, the independent combined run passed all 96 closure,
registry and provenance tests. Fresh native original/current allocations again
produced FAIL/PASS with the same fixed verifier. The budget control accepts
309,346 bytes and rejects the disposable 310,273-byte subject (cap + 1).
An earlier phase-transition refusal was WRITER_BUSY because the preceding
checkpoint process was still finishing; it changed zero bytes. The checkpoint
was awaited and REVIEW was entered canonically before these repeated checks.

Final owned scope: operations.py, saipen.py, journal.py,
test_closure_provenance.py, test_protocol_registry.py, COMMANDS.md, OPS.md and
COMMAND_EFFECTS.json. No remaining P0/P1 findings. Review passes: 1.
Memory promotion: NO; the existing contracts already own these CAS decisions.
Verdict: SHIP by explicit pending C-004 cohort closure; publication remains
excluded. The previous default own_patch T-1306 row is a concrete candidate
for this recovery operation, with its original lifecycle preserved.
