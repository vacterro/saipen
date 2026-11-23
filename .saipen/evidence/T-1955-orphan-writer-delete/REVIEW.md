# T-1955 REVIEW -- independent re-measurement

## What this ticket changed

Two files, 265 deletions, zero additions:

| file | change |
|---|---|
| `tools/saipen_engine/operations.py` | -264 lines: `_plan_producer_integration` and `record_producer_integration` (with its `@_state_guard`) |
| `tools/saipen_engine/journal.py` | -1 line: the `"producer-integration-",` row in `OP_CLASSES` |

The second edit is not something I planned in SCOUT. VERIFY found it: the
registry's converse test
(`test_t1577_op_id_provenance.RegistryCoversEveryWriter.test_every_registered_class_has_a_live_writer`)
went red naming exactly `['producer-integration-']`, because that table may
"neither be padded with a hand-typed class nor keep one whose writer is gone".
Deleting the only writer left the row false. The ticket's stated verify text
only named the two `git grep` censuses, so this is a case where the ticket
under-specified its own blast radius and the test caught it.

## Re-measured independently

**Symbol census** (the ticket's own verify criterion, re-run after the
baseline work, not copied forward):

```
$ git grep -n "record_producer_integration|_plan_producer_integration" -- tools/
ZERO
```

**The live path is intact.** `producer.py:2155` still emits its receipt; its
`op_id` derivation at `:2147` is untouched. Cluster coverage green:

```
tools.test_v7_producer_parallelism + test_producer_terminal_consistency
  + test_producer_gate_policy + test_t1430_crew_run_receipt      75 tests OK
tools.test_t1577_op_id_provenance + test_t1746_crew_terminal_outcome
  + test_intent_audit_fixes + test_t1561_probe_fixture          126 tests OK (3 skipped)
```

**The registry row's removal is safe, not merely convenient.** No op id of the
removed class exists in this repository's history:

```
grep -rn "producer-integration-[0-9a-f]\{8\}" .saipen/     -> nothing
find .saipen -type d -name "producer-integration-*"        -> nothing
```

So no LOG line and no journal operation record loses its resolution; the
grammar narrows only for ids that were never minted.

## The family gate is red, and the red is not mine

First family run: `FAIL`, `ran: 8404`, `red: 1`,
`new_red: ['test_host_bootstrap.ActivationDeliveryTests.test_32_installed_desktop_loader_reads_the_injected_block']`,
`fixed: 6`.

I did not accept "probably unrelated". Measured:

1. The test reads the **installed** FreeBuff Desktop bundle
   (`%LOCALAPPDATA%/Programs/@codebufffreebuff-desktop/resources/orchestrator/orchestrator.js`),
   not this repository. It extracts `loadUserKnowledgeFiles` and
   `selectKnowledgeFilePaths` from it by string anchor.
2. That file's mtime is **2026-10-29 08:27:12** -- after the family PASS at
   07:41 on the same HEAD `b152e6de` and after my 06:28 PASS.
3. Both anchors are gone from the replaced bundle: `loadUserKnowledgeFiles`
   count 0, `selectKnowledgeFilePaths` count 0. `KNOWLEDGE_FILE_NAMES` survives
   as a bare declaration, and the only reader left is
   `loadClaudeProjectInstructions(cwd)` -- a **project-root** loader, not the
   home one. The extractor therefore exits 3 `EXTRACT_FAILED` before it ever
   examines our activation block.
4. The production loader still exists in `resources/app.asar` at byte
   1481642, with the identical signature. So the surface moved between
   artifacts rather than plainly vanishing, and the test cannot tell those two
   cases apart.
5. **The decisive control:** I reverted both my edits to HEAD
   (`git checkout HEAD -- tools/saipen_engine/operations.py tools/saipen_engine/journal.py`,
   restoring 1 `record_producer_integration` occurrence) and re-ran the test. It
   failed identically: `AssertionError: 3 != 0 : EXTRACT_FAILED`. I restored my
   patch immediately after and re-confirmed the same failure.

A test that fails the same way with the change reverted is not evidence about
the change. The baseline was grown by exactly this one id with that reason
recorded, which also drops the 6 `test_legacy_lifecycle_compat` reds the old
baseline carried -- they now pass, so leaving them would have been the stale
claim.

## Reviewed against the alternative

The alternative remedy was to wire the orphan as the canonical writer. I did
not, and the reason survives REVIEW: the orphan's `op_id` is
`"producer-integration-" + uuid4_hex()`, a fresh random value each call, while
`producer.py:2133-2145` documents that an identity-only deterministic `op_id`
was already the E-3836 treadmill root cause and that the live form binds the
input source. Adopting the orphan would have undone that fix. There is no
version of "wire it up" that does not also rewrite its `op_id` and its
receipt-metadata finalizer to match the live path -- at which point it is a
duplicate of the live path, which is exactly the maintenance trap HUNT-015
raised. Delete is the smaller, truthful change.

## Self-audit

`git diff --stat` on the ticket's own footprint shows only
`tools/saipen_engine/operations.py` and `tools/saipen_engine/journal.py`.
Every other modified path in the working tree (`tools/test_next_action_deadlock.py`,
`tools/test_state_scalar_quoting.py`, `tools/validate.py`,
`tools/saipen_engine/state.py`, `phases.py`, `host_authority_*.py`,
`saipen/REGISTRY.json`, the intake deletions) predates this ticket and belongs
to earlier uncommitted T-1606/SRC-167 work -- confirmed by `git grep -l "SRC-167"`
against those paths in the T-1954 self-audit and unchanged since.

## Follow-ups filed, not absorbed

- **T-1956** (P2): re-point `test_32` at the artifact that now builds the
  desktop prompt, and decide whether the home knowledge surface still reaches
  it. Filed rather than fixed here: fixing it needs the host's own bundle
  layout resolved, which is a different question from deleting a dead writer.
