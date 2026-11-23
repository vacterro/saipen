# T-1606 — operator WAIT and legacy action recovery

Source: SRC-167, exact audit/23 bytes SHA256
`e65de1f0c46a5857799fecdccfdd4f18961961805462d7b9cc053489c8e5f01c`.
Interpretation: immutable revision 1, nine actionable clauses plus one context clause.
Status: BLOCKED at the verification correction cap; not accepted or DONE.
The saved candidate passed focused controls but failed the complete family.
Only this attempt's tracked edits were restored from their inherited-dirty
snapshots; its new file was quarantined. Source and audit cleanup remain open.

## Root causes and resulting behavior

`patch_state` previously encoded any owned action without semantic validation;
strict readers checked WAIT but accepted arbitrary operator prose, while fast
checks and reconciliation carried weaker independent prefix rules. PHASE also
accepted an unknown uppercase phase without a ticket. `state.next_action_error`
now supplies the shared action grammar to the owned writer, strict reader,
proposed-state checks, producer checks and legacy classifier; PHASE reads the
registry enum. Existing release diagnostics remain, with their 341 fail-site
identities intact, while their STATE verdict consumes the shared reader.

WAIT requires its closed category and one-sentence body; PHASE requires a known
uppercase phase and a ticket exactly in the ticket-bearing phases; RUN requires
a nonempty command; RESUME requires T-### and a known uppercase phase; saipen
requires a registered command. Values remain exact rather than coerced. An
unowned legacy field remains byte-preserved for observable recovery, while an
ordinary strict transaction cannot commit a malformed checkpoint.

The emitted `WAIT_OPERATOR` constant was missing from the canonical refusal
registry, and the inventory missed named literal constants. Expanding that
static inventory exposed three same-class omissions: WAIT_FOREIGN_OWNER,
RUNTIME_UNAVAILABLE and SAIPEN_HOST_RUNTIME_UNAVAILABLE. All four emitted codes
are registered; unknown codes still remain marked refusals.

A printed `<next-action>` placeholder was not directly executable. Recovery
now prints a conservative user-brake replacement encoded as one UTF-8 hex token.
`resolve-next-action --hex` accepts 1..4096 bytes and the unchanged STATE grammar;
invalid hex/UTF-8, multiline values and malformed actions refuse without core
writes. Global flags precede `recover`; punctuation and repeated spaces survive.
Only an explicit invocation records the replacement, original STATE bytes are
archived, and the choice does not authorize work or resolve the original issue.

Real CLI controls also exposed ordinary continue pivoting normal intent while
WAIT bound, replacing a BLOCKED WAIT with `saipen status`. Bound WAIT is now
restated intact, and continue observes the brake before any intent pivot.
DONE with an empty TODO retains the existing three-category binding exception.

## Evidence and oracle ownership

The unchanged ten-control grammar verifier is
`895cb46be74dab33efc22399a84b6dc45334d3d367f98b42f1a7fa7b050b2dab`:
original 10 ran / 11 failing assertions / 0 errors / 0 skips;
current 10 ran / 0 failures / 0 errors / 0 skips.
Records: `grammar-original.json`, `grammar-current.json`.

The final real-CLI verifier is
`f892d7a4e2bb74bf1859c2a9d4481574b6b3141dc64617a03c174d0909123f4e`:
original 3 methods / 5 failing assertions / 0 errors / 0 skips;
current 3 methods / 0 failures / 0 errors / 0 skips.
Records: `transport-final-original.json`, `transport-final-current.json`.
It runs real CLI commands on isolated copies, restoring saved pre-fix production
files for the original subject. Router was pristine before this Work; its HEAD
source is retained independently and its only current diff is the two owned
WAIT-routing hunks. The original and current verifier/test configuration match.

The first transport trial omitted the copied home's VERSION/extensions and
raised one setup error: it is retained as invalid trial evidence and is never
spent as a regression pair. Later verifier revisions renewed their original
red controls. Old malformed WAIT/RESUME fixtures were retained as negative
controls, rather than dropped; the printed-command expectation changes have
independent execution evidence. Initial focused VERIFY failed six assertions
and core validation failed the new untracked manifest file; that failed pass
is preserved and grants no PASS. The first correction still exceeded the load
budget by 32 bytes; the next docs-only correction measured 47006 <= 47104 and
the unchanged registry suite passed all 16 controls. The final declared focused
family ran 178 tests with zero failures, errors or skips in the renewed VERIFY.
The new file has an intent-to-add index entry.

## Owned changed paths

- saipen/REGISTRY.json
- saipen/COMMANDS.md
- tools/saipen.py
- tools/validate.py
- tools/saipen_engine/state.py
- tools/saipen_engine/phases.py
- tools/saipen_engine/fast_check.py
- tools/saipen_engine/reconcile.py
- tools/saipen_engine/operations.py
- tools/saipen_engine/subs.py
- tools/saipen_engine/router.py
- tools/test_next_action_deadlock.py
- tools/test_next_action_grammar.py
- tools/test_refusal_registry.py
- tools/test_recovery_reachability.py

Saved originals preserve inherited dirty changes. Evidence is local under this
directory. No SAIPAL files, release roots, conflict decisions, historical LOG
lines or external publication were changed. Read-only SAIPAL STATE observation
was DONE/saipen continue: the audit's past operator prose is a reported shape,
not a claim about current downstream bytes. It motivated deterministic controls.

## Validation and lifecycle

Claim E-12225; source normalization and SCOUT E-12226; BUILD E-12227;
build checkpoint E-12228; grammar regression pair E-12229/E-12230;
first VERIFY E-12231; failed pass E-12232; bounded BUILD retry E-12233;
corrected build E-12234; renewed VERIFY E-12235; failed correction E-12236;
second correction BUILD E-12237; owned retry accounting E-12238;
final VERIFY E-12239. `verify_attempts: 1` records the single failed correction
cycle after the initial failure. `record_retry.py` used the existing immutable
checkpoint builder, generic single-record field renderer and journaled APPLY;
its declared owned retry field preserves the rest of the prepared checkpoint.
Ruff and all 341 validator fail-site identities pass. Security/performance
extensions are example templates and bind no project scanner or benchmark.
Final focused/full validation, independent REVIEW, SHIP and normal source/inbox
closure will be recorded here after they actually occur.

## Practical limits

The index is generation 2026-09-01 and deliberately excludes tools; Tier 2
claims use exact current source after coverage checks. A graph's clean coverage
signal does not prove completeness. The static refusal scanner covers literal
module constants, not arbitrary dynamic code construction. RUN command content
remains opaque; execution authority still belongs to existing effect gates.
An external raw file writer can construct invalid STATE bytes; strict consumers
refuse them and only the existing observable recovery boundary can migrate them.
Pending cohort publication and unrelated external/human boundaries remain separate.

## Complete-family failure and preserved recovery

The frozen six-shard family ran all 4908 tests in 1530.0 seconds and returned
FAIL with seven new red IDs, no baseline growth and no leaked sandboxes.
Record: `.saipen/evidence/core-unit/786656ef48db7083-20261004T012105Z.json`;
exact red sections: `.saipen/cache/core-unit/786656ef48db7083-20261004T012105Z.red.json`.
The initial diagnostic string begins `saipen action` and is mistakenly scanned
as a printed command. Two old obey/cc controls expect explicit user-brake
override, while the new ordinary-continue brake currently catches them too.
Ownership, producer, portable-handoff and baseline-reuse controls also failed;
their fixture/context and reader-order implications require exact verification.
No failed control was baselined or deleted.

A separate read-only reproduction found U+2028 accepted by next_action_error
and patch_state but rejected by strict frontmatter parsing. The shared BOARD
record_separator_in helper is a reuse candidate for all physical separators.
This is a real construction mismatch, not a completed repair.

Failure E-12240; correction cap accounting 1->2 E-12241; canonical block E-12242.
`verify_attempts: 2` remains on T-1606. Saved candidate and per-file hashes are
under `.saipen/kitchen/failed/T-1606/`; new file under its `untracked/` subtree.
`.saipen/kitchen/failed/T-1606.patch` is the captured Git delta on owned paths
and includes their inherited dirty base: restore used exact saved originals,
never that mixed delta or a blanket HEAD reset. Router alone was pristine and
restored from its retained HEAD source. The owned intent-to-add entry was reset.
Later resumption needs materially changed evidence resolving these failures;
the goal continues another currently runnable Work in the meantime.
