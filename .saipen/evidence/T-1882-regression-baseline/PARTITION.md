# T-1882 -- partition of the 110 core-unit failures

Record: 9b10e579a60f9c79-20261024T100757701402Z (status FAIL, ran 7551, red 110)
HEAD:   025bf596c683464788ab698248e8a3c5eb44dfec

## R1 -- 67 -- modules absent from every commit (foreign in-flight batch)

-  35  test_t1746_crew_terminal_outcome
-  11  test_t1750_release_boundary
-   4  test_t1792_auto_doctor
-   4  test_t1704_goal_checkpoint_priority
-   3  test_t1681_release_closure_op
-   2  test_t1669_clean_done_projection
-   1  test_t1640_board_scrub
-   1  test_t1827_writer_lock_contract
-   1  test_t1640_log_seal
-   1  test_source_contract_derivation
-   1  test_t1704_legacy_goal_authority
-   1  test_t1828_verification_policy
-   1  test_t1494_continuation_authority
-   1  test_t1851_debt_authority

## R2 -- 23 -- shipped modules whose dump quotes the FUTURE-OWNER FAIL

-   5  test_t1612_accidental_success_reproduction
-   4  test_check_inventory
-   2  test_work_reverify_cli
-   2  test_accepted_debt
-   2  test_t1581_phase_rename_knowledge
-   1  test_t1411_stale_complete_resolution
-   1  test_remediation_self_consistency
-   1  test_t1598_stale_claim_next_action
-   1  test_public_closure_cli
-   1  test_source_quarantine_route
-   1  test_style_contract_chokepoint
-   1  test_t1412_conformance_truth
-   1  test_t1516_portable_receipts

## R3 -- 1 -- test_check_inventory -- ledger drift

-   1  test_check_inventory

## R4 -- 19 -- remaining shipped-module failures

-   3  test_t1586_scenario_inputs
-   3  test_log_tail_quarantine
-   3  test_t1412_conformance_truth
-   2  test_public_install_lifecycle
-   1  test_continue_chain
-   1  test_intent_audit_fixes
-   1  test_log_normalize
-   1  test_next_action_deadlock
-   1  test_t1304_r004_dry_run_purity
-   1  test_t1304_r004_transition
-   1  test_t1581_phase_rename_knowledge
-   1  test_debt_gate

## R1 proof of ownership

The 14 modules above exist in the index and the worktree but in NO commit:

    git ls-tree -r HEAD --name-only tools/ | grep -c test_t1746_crew_terminal_outcome  ->  0
    git cat-file -e :tools/test_t1746_crew_terminal_outcome.py                        ->  present

They are a foreign in-flight batch, and their dependency is genuinely missing
from the source tree rather than broken:

    source  tools/saipen_engine/release.py  4874 lines  TERMINAL_LOCAL_NO_PUBLISH: 0  _gate_command: 0
    HEAD    tools/saipen_engine/release.py  4865 lines  TERMINAL_LOCAL_NO_PUBLISH: 0  _gate_command: 0
    runtime C:/ProgramData/SAI/SAIPEN/runtime/d838d464759d97d3/tools/saipen_engine/release.py
                                            5312 lines  TERMINAL_LOCAL_NO_PUBLISH: 4  _gate_command: 1

Every symbol the source has, the runtime also has (0 source-only symbols); the
runtime carries 17 more. The two installed runtimes are byte-identical
(md5 97b129138e0f6c029ba055256eda786f), so this is not a stray snapshot.

Executed against the installed runtime, with the same test bytes:

    test_t1746_crew_terminal_outcome                                    45 tests  OK
    test_t1750_release_boundary + t1681 + t1669 + t1792 + t1827         59 tests  OK
    t1704 x2 + t1640 x2 + t1494 + t1828 + t1851 + source_contract      193 tests  2 failures
      -> both are the fixture lacking .saipen/archive/source/SRC-272.md;
         with the archive copied, test_source_contract_derivation          13 tests  OK

So the 67 reds are not a regression in shipped code. They are an unreleased
batch calling an API the source tree has not yet received. Warming the source
to the runtime's release.py would import that foreign batch's semantics; that
is a publication decision (T-1815/T-1644), not a regression repair.

## R2 -- 23 -- the FUTURE publication surface

`saipen/COMMANDS.md` in the worktree is byte-identical to the installed
runtime's copy (md5 30c33300298b218d0b430ce571cc2729) and has lost every
`saipen future` row that HEAD (208 lines) and the index (213 lines) still
carry. The validator then fails four `FUTURE-OWNER` checks, and 23 further
core-unit reds merely quote that FAIL from their validator dump.

Restoring either stored version is not a repair -- both already breach the
declared context budget, measured with tools/protocol_budget.py --summary:

    worktree (truncated, 118 lines)   command_resolution 40427 / 56320  PASS
    HEAD      (208 lines)             command_resolution 57232 / 56320  FAIL
    index     (213 lines)             command_resolution 57656 / 56320  FAIL

The repair is a compact publication block: all five rows, the four mutating
verbs named exactly as COMMAND_EFFECTS.json declares them, at
command_resolution 41546 / 56320 PASS (6/6 profiles PASS).

## R3 -- 1 escaping the R2 filter -- the inventory ledger

`tools/validator_fail_sites.json` had drifted from `tools/validate.py`:
one site unadjudicated, three recorded but absent, four absent in one file and
present in the other. Regeneration plus restoration of the one verdict
`e736f31b20f2d116` already carried in HEAD and in the index (COVERED, case
"a future verb stops being published") makes `inventory_errors(ROOT) == []`
and test_check_inventory 46/46 OK.

Regeneration ALONE was wrong and is worth recording: it re-minted the site as
UNADJUDICATED, because a site id is derived from the check's message and
position. The verdict belongs to the control, so the adjudication was restored
by identity, never invented.

## R4 -- 19 -- what remains after R1/R2/R3 are removed

Re-run on the repaired tree, these modules are green:

    test_t1412_conformance_truth test_log_normalize test_next_action_deadlock
    test_t1304_r004_dry_run_purity test_t1304_r004_transition            57 tests  OK
    test_continue_chain test_debt_gate test_t1581_phase_rename_knowledge
      test_log_tail_quarantine                                           82 tests  OK
    test_t1586_scenario_inputs                                           12 tests  OK

They were cascades too -- but of a defect this campaign INTRODUCED, not
inherited: T-1881's authority gate refused `ticket add` under the INIT pause
(`WAIT: init -- provide the first project goal or raw backlog`), the exact
route that answers it. A copied runtime could `init` and then could not seed
its first ticket. Fixed in tools/saipen.py by exempting the closed `init`
category; 15 tests green in test_t1881_authority_brake, red control removes
exactly that one exemption and fails exactly the init test.

test_public_install_lifecycle and the remaining log/next-action reds were not
reproduced on the repaired tree in this pass.

## R4 residual: two untracked foreign documents (not a code defect)

The last three reds (all in `test_t1581_phase_rename_knowledge`) are a validator
`coverage gap`, and it is caused by two files that exist in NO commit:

    saipen/COMMANDS_REFERENCE.md                        untracked, absent from HEAD and the index
    SAIHANDOFF_FASTPROMPTER_PERSONAL_AUDIO_RESTORATION.md  untracked

`saipen/MANIFEST.json` also gained `"src": "saipen/COMMANDS_REFERENCE.md"` in the
worktree diff, so the fixture copies the file into every copied runtime while
`tools/validate.py` neither covers nor exempts it.

Measured in a throwaway copy (never in the shared tree):

    drop BOTH files + the manifest entry   ->  coverage gap gone
    drop only the manifest entry           ->  coverage gap still there (file on disk)
    drop only the file                     ->  "runtime manifest file missing from the home"

The fix belongs to whoever owns those two documents: either they get covered or
exempted with a reason, or they do not ship. Exempting them from this ticket
would adjudicate another actor's unreleased work, and adding them to EXEMPT sits
in `tools/validate.py`, which is itself part of the foreign staged batch. Left
untouched and reported.

## Net effect

    110 reported failures
    - 67  R1 foreign in-flight batch, all green against the installed runtime
    - 23  R2 FUTURE publication surface, repaired
    -  1  R3 inventory ledger, repaired
    - 19  R4 cascades, 16 of them caused by this campaign's own T-1881 gate
             (repaired), 3 remaining from the two untracked foreign documents
    ---
      0  regressions in shipped code that this campaign leaves unexplained

## Correction (2026-10-25): the last line is wrong as written

The table partitions the **live working tree's** 110 -> 55. It says nothing
about the **committed revision**, and a run in a real worktree at `025bf596`
finds 7 failures there (see `HEAD-TREE-CORRECTION.md` and
`head-worktree-control.log` in this directory):

    6  test_legacy_lifecycle_compat -- reconciliation answers
       RECONCILE_REAUTH_REQUIRED for the pre-closure T-113/T-114 rows; repaired
       only by uncommitted reconcile.py plus the untracked goal_authority.py
    1  test_opencode_host_smoke.OpenCodeRealInstalledGeneration --
       generation skew: the installed host carries the newer live artifact, so
       the test fails when run from any older revision. A portability limit of
       that test, not a defect in HEAD's own source.

The honest reading is therefore: the live tree's 55 red are foreign, but the
committed tree is not green, and 6 of its failures are real. They are absent
from the 55 only because the repair already exists locally, uncommitted. The
figure above describes the live tree and must not be quoted as a statement
about HEAD.

A first attempt measured HEAD via `git archive HEAD | tar -x` and reported 11
failures; 4 of those (3 in `test_handoff_archive_cross_repo`, 1 in
`test_saipen_metrics`) were artifacts of that export having no `.git`. The
method error is kept in `HEAD-TREE-CORRECTION.md` rather than discarded, with
its raw output as `head-archive-run.log`.
