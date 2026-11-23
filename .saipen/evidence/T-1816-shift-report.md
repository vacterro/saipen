# SAIPEN autonomous engineering shift — report

Mode 2, P1: continuation and system stability. Prepared after T-1817 coverage
settled and T-1816 delivered its three SAIPEN-owned bullets.

## STATUS

Two tickets taken to complete delivery; **both are now blocked on the same
operator precondition** (206 foreign pre-staged paths), not on their own work.
`SRC-275` coverage is **7/7** with no `UNKNOWN` left. Three of the four
priorities in the brief are complete; T-1829 is not started because its blocker
is genuine and outside this repository.

## COMPLETED

**T-1817 — SRC-276 drift prevention.** All eight clauses VERIFIED before this
shift's final step. Three executed FAIL→PASS pairs (`900f8403` route resolver,
`5498482b` ownership projection, `5d8d93dd` acceptance bar) plus the
closure-outcomes pair `ea725e08`; one canonical focused record (`79392d7b`,
116 tests); an independent REVIEW rerun (71 tests OK). Deliverables
`.saipen/evidence/T-1817-zaicode-host-handoff.md` and
`.saipen/evidence/T-1817-diagnosis-delivery.md` are mechanically enforced by
`tools/test_t1817_handoff_artifacts.py`, which parses the source's own
`F-NN · P# ·` headings so a shortened diagnosis fails the build.

**T-1816 — SRC-275 P0 audit, all three SAIPEN-owned bullets.** Coverage 7/7
VERIFIED.

1. *Read-only provenance inventory*
   (`.saipen/evidence/T-1816-audapack-provenance-inventory.md`, oracle
   `tools/test_t1816_provenance_inventory.py`, 11 tests). The audited root was
   never written: four protected files hash identically before and after, and
   the dirty-path count was 218 both times. Measured findings, each labelled
   PROVEN / UNPROVEN / CONTRADICTED:
   - the committed ledger really is internally inconsistent — it cites
     `E-3133`, `E-3136`, `E-3145` as parents and contains none of them
     (PROVEN);
   - the working tree did **not** repair that. It renumbered: twelve ids that a
     committed ledger already used were reassigned to Oct-13 reconcile events,
     and none of the twelve original bodies survives anywhere in it (PROVEN, by
     comparing all 726 shared ids);
   - the displaced T-278 / T-292..T-299 history is **not lost** — the
     quarantine archive hashes to exactly the journaled
     `680044550b990b80…` and contains those rows. Its real defect is that
     `.saipen/recovery/` is git-ignored, so the only surviving copy was never
     committed (PROVEN);
   - `E-3133`'s asserted "explicit operator decision" has no independent
     witness artifact in the tree (UNPROVEN, not CONTRADICTED);
   - the message-414 `STATE.md` rewrite has no receipt and leaves no residue
     (UNPROVEN).

   The inventory corrects the audit on one point and must not soften another:
   damage magnitude was "content survived, id space did not"; but a
   hash-verified archive does not retroactively authorize a live write into a
   root under `FORENSICALLY_UNRECOVERABLE`.

2. *Effect-aware protected-root hold*
   (`tools/saipen_engine/protected_root.py`, controls
   `tools/test_t1816_protected_root_hold.py`, 18 tests). The measured defect was
   a refusal naming `Bash`/`Edit`/`Write` that an embedded Python write walked
   straight through — the gate was attached to a verb. This one is a pure
   function of `(root, hold, target path, effect)`; the response explicitly
   lists `tool_name`, `verb`, `declared_intent` and `command_text` as
   non-signals. Messages 402, 413, 414 and 431 are reproduced as negative
   controls. Fail-closed on an unreadable hold, a non-object hold, and an
   unknown mode; `.saipen/LOG.md` does not protect `.saipen/LOG.md.bak`; a
   directory entry protects the subtree; absolute targets inside the root are
   normalized before comparison while a foreign path is never absorbed.

3. *Per-RUN append-only improve provenance* (`tools/improve.py`
   `_run_provenance_block`, oracles `test_t1816_run_provenance.py` 5 tests and
   `test_t1816_run_append_only.py` 4 tests). Each RUN now records
   `run_source_head` / `run_source_tree_fingerprint` inside its own section.
   Appending RUN 2 leaves RUN 1's bytes and the report header byte-identical —
   the exact opposite of the observed "fix", which restamped the report-wide
   header and so erased the distinction the field exists to carry. An
   uncomputable identity is written as `UNAVAILABLE`, never omitted or guessed.

## CURRENT

T-1816 is **BLOCKED** on `PUBLICATION_STAGING_BLOCKED` — the same precondition
that holds T-1817. Delivery is complete; only the release is refused. The
declared core-unit family was executed three times against this tree and never
produced a citable PASS, so the ticket carries a focused PASS (admissible under
this project's `tools/verification_policy.json`: `ticket: focused`,
`publication: full`) and no full-family citation.

## VERIFICATION

| gate | result |
|---|---|
| T-1816 focused gate, current tree (fingerprint `e6d25247`) | **PASS, 74 tests**, record `e6d25247b797d13e-20261022T151343272626Z` |
| T-1816 earlier focused gate | PASS, 79 tests, record `24cdb47b7aa5cf8d` |
| T-1816 REVIEW independent rerun | PASS, 58 tests |
| improve family (`test_improve_*`, `test_src085_*`, `test_t1803_*`, `test_continue_*`) | PASS, 81 tests |
| protocol registry | PASS, 16 tests |
| effect authorization (sibling module) | PASS, 34 tests |
| SRC-275 coverage | 7/7 VERIFIED |
| audited AUDAPACK root | byte-identical before/after; no T-1816 file added |
| declared full family, tree `e6d25247` | **FAIL — 2 reds, both pre-existing** |
| declared full family, tree `25a139d1` | FAIL — 8 reds (6 sandbox-only; see below) |

Every quoted number comes from an executed run in this session. Nothing is
inferred from a previous session's claim.

**The full-family reds, attributed.** The final run on the stable tree reports
exactly two:

- `test_refusal_registry.RegistryCompletenessTests.test_every_production_refusal_code_is_registered`
  — six codes (`AMBIGUOUS`, `EVIDENCE_CORRUPTION`, `EVIDENCE_EXECUTION_FAILED`,
  `EVIDENCE_NOT_FOUND`, `EVIDENCE_STALE`, `EVIDENCE_UNAUTHENTICATED`) are emitted
  by production code but absent from `REGISTRY.json` `error_codes`;
- `test_t1844_origin_broker.OriginKernelWithSimulatedNativeIdentity.test_revoked_origin_refusal_remains_a_registered_native_code`
  — `HOST_PROVENANCE_UNAVAILABLE`, same cause.

Both fail identically **live**, are caused by uncommitted `intake.py` work that
introduced the codes without registering them, and predate T-1816: the 11:14
run on the same HEAD had one red, and `intake.py`'s working-tree copy then
diverged by 880 added lines. **They are not T-1816 damage, and T-1816 does not
fix them** — registering a code for another ticket's in-flight verb would be
exactly the kind of convenient green this audit condemns.

One intermediate run reported 782 reds. That was a copy/execution artifact, not
a tree state: every one of those tests failed with files missing *inside* the
sandbox (`tools/saipen.py`, `tests/scenarios/*/.saipen`) while the same files
were present in the live tree, and the six shards disagreed with each other
about which fixture existed. Its six scenario-dependent clusters all pass live
(`test_t1627_operator_question` 16 OK, `test_t1645_zero_hunt` 7 OK). The
artifacts are recorded, not silently dropped.

**A verification-economics defect worth its own ticket.** `environment_sha256`
hashes the entire inherited child environment. In Git Bash, `_` is set to the
path of the program that ran the command, so producing evidence through a
wrapper (`timeout 600 python tools/core_unit.py focused ...`) records
`_`: `.../timeout`, and every later gate invocation — a plain launcher call —
recomputes `_`: `.../python` and refuses the record as
`focused check has missing or incompatible verification environment identity`.
The identical command run without the wrapper is accepted immediately. This
cost one full 31-minute family run plus two focused reruns and is a real trap
for any agent that bounds a long command with `timeout`. Not fixed here: it is
outside T-1816's scope.

## GITHUB

No commit, no push, and no history rewrite in this shift. `REGISTRY.json` was
briefly rebuilt from `HEAD` while registering a rule owner, which would have
dropped staged operator work; it was restored byte-identically from the index
(`git show :saipen/REGISTRY.json`) and `git diff` against the index is empty. A
later `indent=2` re-serialization inflated it by ~9 KB and broke a load budget;
that was reverted from the index too. The registry now carries **zero** changes
from this ticket — the intended rule-owner marker was removed instead of
retrofitting it into a `frozen_at: 2026-08-30` semantic baseline.

## PERFORMANCE

Not measured this shift — **UNKNOWN**. The brief's "verify smarter, no test
loop" rule was followed: focused patterns during the build, one canonical
focused gate per stable generation, one independent REVIEW rerun, one declared
family run. The full suite was launched **once** and not re-launched against
intermediate edits.

## DEPENDENCIES

**T-1829** (Test Execution Cost Collapse) stays `BLOCKED_EXTERNAL` and was not
worked. The blocker is genuinely outside this repository: `git fsck` reports 112
missing objects and the object database holds 15612 objects in which the missing
parent appears zero times. GitHub access is restored (`ls-remote` returns 740
refs) but no additive recovery exists from it, and GitLab `main` still answers
`not our ref`. Closing it needs an intact original object backup or restored
original remote history — **no agent in-repo action can supply that.**

**T-1817** stays `BLOCKED` on `PUBLICATION_STAGING_BLOCKED`: 206 foreign staged
paths would enter the release. None of them belongs to T-1817. This is operator
staging, and the guard must not be bypassed.

**T-1816** now carries the same block. Its own delta is complete and verified;
only the release is refused. Note that this makes the staging set a single point
of failure for two independent tickets — clearing it once unblocks both.

## SECURITY

- The audited original AUDAPACK root was treated as read-only throughout; every
  probe was `git show` / `git log` / `git status` / SHA-256. The before/after
  hash proof is part of the delivered document, and the oracle's
  `tearDownClass` asserts it, so a future edit that mutates the root fails.
- No operator approval was invented. The inventory labels the asserted operator
  decision UNPROVEN and states plainly that a green acceptance check does not
  supply authority.
- `FORENSICALLY_UNRECOVERABLE` / `NO_GO` for the audited root stands. The
  inventory does not clear it, and the new hold gate is a mechanism for
  enforcing it, not a substitute for the operator's decision.
- The new gate is explicitly **not** a sandbox and claims no enforcement it
  does not have; an ADVISORY host acquires nothing from a green test.
- No ZAICODE process was stopped or inspected by name.

## NEXT EXACT ACTION

None available in-repo for T-1816. It is blocked on operator staging, exactly
like T-1817. The next **workable** ticket is T-1815 (`PHASE SCOUT T-1815`).

## NEED OPERATOR

Two decisions, both genuinely yours:

1. **206 foreign paths are pre-staged in the shared tree.** They now block both
   T-1816's and T-1817's release. Committing or clearing them lets both SHIP
   proceed; I will not discard operator staging or bypass the guard.
2. **AUDAPACK recovery archives are uncommitted and git-ignored.** The only
   surviving copy of the displaced T-278/T-292..T-299 history sits under
   `.saipen/recovery/`, excluded by `.gitignore:22`. Preserving it means
   committing recovery archives, which is a policy change inside a protected
   root — I will not make that call for you.

Also open, already known and unchanged: T-1829's missing git objects need an
external backup, not a repository action.

**Two defects found and deliberately not fixed** (both outside T-1816 scope,
both recorded above rather than silently worked around): the seven unregistered
refusal codes in `REGISTRY.json` caused by in-flight `intake.py` work, and the
`environment_sha256` / `_` wrapper sensitivity that makes wrapper-produced
verification evidence uncitable.

**Metadata note, not acted on:** the BOARD row carries `T-1816 [P2]`, but
`SRC-275` classifies DRIFT-01/DRIFT-02 as P0 and the ticket was claimed for the
P0 protocol-invariant work. The priority is a display field on an active row;
`ticket repair-metadata` refuses non-DONE rows by design, and hand-editing
BOARD is forbidden. Left as-is and recorded here rather than silently changed.
