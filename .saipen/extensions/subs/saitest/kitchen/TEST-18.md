# TEST-18 -- adversarial scenarios at dc39709c / tree f3dab073

- source_head: dc39709c0c17a3272126c01a626ffcaa4176140b
- source_tree_fingerprint: git-delta-v1:f3dab073ebbfbd9021d22a0e63c2cbba72094bb6ff587c16e670aa98bd38e1d7
- role_revision: sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08
- epoch context: converge_intent-f74cb6f3247c405fbf754e4a71a9eee5 (SC-3; T-2047 guard in the worktree)
- mode: read-only toward the main tree; probes are read-only or refused before writing

## S1 -- damaged state: the audit-route dead end (family 3/7)

Re-run of the TEST-17 scenario at the moved tree. The projection still routes
`saipen audit ingest` for layer `audit/SAIHANDOFF_BZ_REA_AGENT_DRIFT_RECOVERY.md`
and work `T-2016`, whose BOARD section is `## BLOCKED`:

- `audit_route_owns(projection, tickets=board)` -> **False**; the ingest branch
  requires the linked Work to be DONE, so the router falls through.
- `route_violation(projection, 'saipen crew', tickets=board)` -> **None**
  (`_test18_s1_route.txt`).
- executor: `saipen audit ingest --dry-run --json` -> `SOURCE_UNRESOLVED`,
  "linked Work T-2016 is not DONE", exit 1, no writes.

**Verdict: NOT_REPRODUCED** (dead end gone from the router side; the executor
refusal is the canonical rule and remains measured). Control note: calling
`route_violation` without `tickets` reports a violation, because the ingest
ownership rule needs the board to know the work is open -- the validator always
passes it, and the bare call is not a production path.

## S2 -- environment: the two validator homes (family 7/7)

Same project, same rule text, different home manifest:

- installed home (`saipen validate --json`): 3 problems / **19** warnings --
  SRC-418/T-2072, audit route, FG-0046/T-1936.
- repo generation (`python -B tools/validate.py`): 29 problems / **39**
  warnings -- SRC-418/T-2072, 27 runtime-manifest untracked paths, EX-000053
  provenance (engine generation now `37dbbc7a…` after the T-2047 edit).

Both counts are measured at this tree. The audit-route class survives only in
the installed generation (pre-fix engine); the manifest and EX classes exist
only in the repo generation.

**Verdict: REPRODUCED** (asymmetry survives the guard; publication/home
identity condition owned by T-2058/T-1449/T-2052 -- no new ticket).

## S3 -- order and repetition: crew planning is idempotent (family 3)

Two consecutive `saipen crew --dry-run --json` at the same snapshot: both exit
0, both `CREW_PLAN`, `first_unsatisfied` SC-3, action `RUN_ROLE saitest`; the
two plans are byte-identical after key-sorted serialization; `.saipen/STATE.md`
and `.saipen/LOG.md` hashes are unchanged before and after.

**Verdict: REPRODUCED** (positive): replay neither advances the stage nor
writes state.

## S4 -- input abuse: a foreign/unknown package is refused (family 1)

`saipen crew record-run saitest --package TEST-99 --json` -> `STALE_PACKAGE`,
exit 1, "TEST-99 is not a current saitest package: it must be ready or
reviewed and carry the live source triple and the current role revision";
STATE/LOG hashes unchanged.

**Verdict: REPRODUCED** (refusal holds).

## S5 -- boundary: restoring a row that is already present (family 2)

Direct helper boundary on a synthetic board: `board_scrub.restored_board_text`
on a text that already contains the exact row duplicates it (1 -> 2
occurrences) and the result no longer parses as a board; an absent row is
inserted once. The production path `operations.restore_board_rows` computes its
missing set and refuses with `NOTHING_TO_RESTORE` before any insert, so the
duplicating helper is not reachable through the canonical verb.

**Verdict: NOT_REPRODUCED AS REACHABLE** (helper-level behaviour recorded;
production refusal precedes it).

## T-2047 control carried into this tree

The new guard's two contract tests are part of the 131 cited focused cases at
this tree. Live replay measured both generations on the same binding: the
installed pre-fix engine appended duplicate E-21380 for E-21379, while the
repo-generation engine returned `ALREADY_BOUND` with the LOG hash unchanged
(recorded in the saihunt package addendum).

No file outside this namespace was written. Test-18 proposes no payload and no
new ticket.
