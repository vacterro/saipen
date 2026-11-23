# TEST-19 -- adversarial scenarios at dc39709c / tree cf7cd4a7

- source_head: dc39709c0c17a3272126c01a626ffcaa4176140b
- source_tree_fingerprint: git-delta-v1:cf7cd4a7512b88c0b0f2e57a05d17aef9e41b432f907486635c87aa3ab53aa42
- role_revision: sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08
- epoch context: the active SC-3 crew epoch (SC-0/SC-1/SC-2 satisfied at E-21498; this run is the stage's own evidence)
- mode: read-only toward the main tree; probes are read-only or refused before writing

## S1 -- damaged state: the audit-route dead end stays gone at the moved tree (family 6/7)

Re-run of the TEST-18 scenario after the tree moved f3dab073 -> cf7cd4a7:

- projection still routes `saipen audit ingest` for layer
  `audit/SAIHANDOFF_BZ_REA_AGENT_DRIFT_RECOVERY.md` and work `T-2016`
  (`## BLOCKED`), next_action `saipen crew`;
- `audit_route_owns(projection, tickets=board)` -> **False**;
- `route_violation(projection, 'saipen crew', tickets=board)` -> **None**;
- executor: `saipen audit ingest --dry-run --json` -> `SOURCE_UNRESOLVED`,
  "linked Work T-2016 is not DONE", receipt SRC-386, exit 1, no writes
  (`_test19_s1_route.txt`, `_test19_s1_executor.json`).

**Verdict: NOT_REPRODUCED** (the dead end remains gone; the executor refusal
is the canonical rule). Control note unchanged: calling `route_violation`
without `tickets` reports a violation, because the ingest ownership rule needs
the board to know the linked work is open -- the validator always passes it,
and the bare call is not a production path.

## S2 -- environment: the two validator homes at this tree (family 4/7)

Same project, same rule text, different home manifest:

- installed home (`saipen validate --json`): exit 1, **2 problems / 16
  warnings** (`_test19_s2_installed.json`);
- repo generation (`python -B tools/validate.py`): **29 problems / 37
  warnings** (`_test19_s2_repo.txt`).

The installed gate's class set is the publication/home-identity pair; the repo
gate additionally carries the runtime-manifest untracked paths, the EX-000053
provenance binding and the stale sub-package warnings. The counts moved with
the tree; the asymmetry itself is unchanged and remains owned by
T-2058/T-1449/T-2052 -- no new ticket.

**Verdict: REPRODUCED** (asymmetry survives the move; both counts measured).

## S3 -- order and repetition: crew planning is idempotent (family 3/7)

Two consecutive `saipen crew --dry-run --json` at the same snapshot: both exit
0, both `CREW_PLAN`, `first_unsatisfied` SC-3, action `RUN_ROLE saitest`,
`completes_in_current_agent`. After key-sorted canonicalization the two plans
are byte-identical except the UI stage's scanned-file counter embedded in its
NOT_APPLICABLE reason (64505 -> 64506: the first capture itself added a file
to the scanned set -- a counter artifact, isolated by the in-memory control).
`.saipen/STATE.md`, `.saipen/LOG.md` and `.saipen/BOARD.md` hashes are
unchanged before and after (`_test19_s3_pre.sha`, `_test19_s3_post.sha`,
`_test19_s3_plan_a.json`, `_test19_s3_plan_b.json`).

**Verdict: REPRODUCED** (positive): replay neither advances the stage nor
writes state.

## S4 -- input abuse: a foreign/unknown package is refused (family 1/7)

`saipen crew record-run saitest --package TEST-99 --json` -> `STALE_PACKAGE`,
exit 1, "TEST-99 is not a current saitest package: it must be ready or
reviewed and carry the live source triple and the current role revision";
`changed_files: []`, `current: []`; STATE/LOG hashes unchanged
(`_test19_s4_probe.json`, `_test19_s4_pre.sha`, `_test19_s4_post.sha`).

**Verdict: REPRODUCED** (refusal holds).

## S5 -- boundary: the restore surface and the gated row (family 2/7)

Synthetic-board boundary on `board_scrub.restored_board_text`:

- a text that already contains the exact row is duplicated (1 -> 2
  occurrences, `present_row_duplicated True`);
- an absent row is inserted once (`absent_row_inserted 1`) into the correct
  section.

Production preconditions on the live project (`operations.restore_board_rows`
rationale probe, read-only): `dangling_work_count 0`,
`gated_tickets ['T-1936']`, `missing_pinned_rows ['T-1936']`,
`nothing_to_restore False`, `pruned_recoverable {'T-1936': True}`
(`_test19_s5_restore.txt`). So the only row this live board would currently
restore is the PROMOTED future gate FG-0046's slice ticket T-1936, recovered
from the pruned-row store -- an absent-row INSERT, never a duplication; the
duplicating helper branch is unreachable through the canonical verb.

New measured fact: the whole restore surface (`gated_tickets`, `pruned_rows`,
`restored_board_text`, `restore_board_rows`) exists only in this worktree
generation. The installed 8.1.0 engine (`scheduled-source/tools/`) contains
none of those names, so the installed validator keeps reporting the FG-0046
gate finding (T-1936 pinned by the promoted gate, absent from BOARD) with no
reachable repair: the fix that would clear it is in the worktree payload,
and worktree mutation is refused `HOME_REQUIRED home-divergent`. That is the
same installed-generation lag class already carried by T-2071/T-2072; it is
recorded here, not re-ticketed.

**Verdict: REPRODUCED** (helper duplication measured; live effect is
insert-once of a pruned row) **and the installed generation has no restore
path at all** -- the T-1936 gate finding is not agent-repairable at the
installed home.

## Limits and controls

- Every probe ran read-only against the live project or on synthetic
  fixtures under `kitchen/`; no load exceeded a single process, < 10 s per
  probe, no network, no recursion.
- No file outside this namespace was written. TEST-19 proposes no payload and
  no new ticket.
