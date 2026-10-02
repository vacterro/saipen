# T-1389 adoption proof -- foreign injector/runtime provenance delta

Date: 2026-09-18. Subject: the worktree bytes of

    bootstrap/inject.ps1
    bootstrap/inject.sh
    tools/saipen_engine/runtime_bootstrap.py
    tools/test_t1389_foreign_delta_adoption.py (new adoption proof)

Classification source: `.saipen/evidence/T-1385-foreign-delta-inquest-20260917/`
(LEGIT_FOREIGN_ABANDONED, writer the Antigravity agent buffy under AUDAPACK
T-195, 2026-09-17 18:04Z).

## Delta identity

    inject.ps1             7fdcdacae6eecbd96a560dd1294305d397896435
                           == inquest blob, unchanged
    inject.sh              36c2882ecffeb35cef13c270f6d6b2bd21fa6ce0
                           == inquest blob, unchanged
    runtime_bootstrap.py   74662afb35ba134fa6fb0e20ae831068737ed032
                           == inquest blob f2942135 plus one E501 line wrap
                           (ruff line-length 100). The f-string message text
                           and the fail-closed branch semantics are identical.

## Focused proof (current bytes)

    python -m unittest tools.test_t1389_foreign_delta_adoption
    -> Ran 9 tests, OK

    A. an installed projection carrying MANIFEST.json without the provenance
       marker is refused, naming the marker and the supported injector;
    B. a marked installed projection resolves to its source;
    C. a source tree without a marker still resolves;
    D. the ps1 injector writes provenance for the ~/.agents skill surface and
       for every Antigravity plugin skill surface; the sh injector writes
       provenance for the ~/.agents skill surface.

Red controls pin the pre-delta injector blobs (ps1 edfb5db1, sh a291ad1d) and
prove both skipped the ~/.agents surface and the ps1 skipped the Antigravity
surface before the delta; the blobs are read with `git cat-file` and the tests
skip only if the objects are absent from the repository.

## Adjacent families

    tools.test_runtime_bootstrap             green
    tools.test_runtime_generation_identity   green
    tools.test_inject_digest                 one red, inherited:
        test_the_two_transports_agree -- worktree autocrlf CRLF vs the
        snapshot's CRLF comparison; red at the pre-delta baseline too.

## Lint and validator

    python -m ruff check tools/ tests/   -> All checks passed (ruff 0.16.0)
    python tools/validate.py             -> 1 FAIL: the untracked new test
        file named by the copy-tree inventory (clears on commit);
        30 warnings, every one owned by another slug.

## Verifier notes (why the adoption test file changed in this ticket)

The adoption test is new in this ticket; its first green run required three
fixture repairs, each recorded here because the verifier changed before its
pre-fix red control was exercised:

- `_resolve_bash()` probes candidate `bash` binaries by execution. On this
  host `shutil.which("bash")` resolves `C:\Windows\system32\bash.exe`, the WSL
  stub, which exits 1 with no distribution; Git Bash at
  `C:\Program Files\Git\bin\bash.exe` executes. The sh tests were unrunnable
  before the probe and the skip is now honest (real bash or skipped).
- `_mini_source` extends `_MINI_MANIFEST` with `managed_dirs`,
  `phase_docs.files` and the `saipen/phases` copy tree, and copies the
  canonical `bootstrap/cli_launcher.py`. The pre-delta sh injector validates
  the manifest and renders the launcher before it reaches any skill surface;
  without these the red control aborted at manifest validation instead of
  reaching the surface it exists to prove.
- Unused import and stale `noqa` directives removed for the canonical ruff
  surface.

The assertions and the pinned pre-delta blobs are unchanged; the red control
still runs the pre-delta injector and proves the skill surface is skipped.

## Core-unit A/B (hermetic runs: SAIPEN host carriers stripped)

    baseline (HEAD bytes, delta and test file absent) Ran 2791, 39 red
    with delta, run 2                                Ran 2800, 38 red

    PATCH_OWNED = 0
    UNKNOWN     = 0
    PRE_EXISTING = 38  (byte-identical test identities in both runs)

Run 1 with delta carried 40 red: its one extra identity
`test_a_foreign_owner_refusal_says_who_owns_the_seat`
(`test_t1363_zero_manual_entry`) passes isolated, passes in the module run,
and passes in run 2. Its sibling `test_start_never_steals_a_live_foreign_seat`
is red in the baseline and run 1 and green in run 2 and isolated. The family
flakes under full-suite load on identical subjects, touches none of this
delta's surfaces, and is classified ENVIRONMENTAL.

## Inherited red identities (run 2 == baseline)

    test_a_finish_with_no_verify_boundary_routes_to_the_edge_not_the_checkpoint (test_refusal_routes)
    test_a_live_doing_ticket_still_refuses_with_the_flag (test_explicit_claim)
    test_a_redundant_flag_writes_no_stepped_over_claim (test_explicit_claim)
    test_an_oversized_verify_becomes_a_compact_row_pointing_at_the_receipt (test_t1363_zero_manual_entry)
    test_audit_core003_converge_target_controls_resume_without_writes (test_intent_audit_fixes) (target='crew')
    test_audit_core003_converge_target_controls_resume_without_writes (test_intent_audit_fixes) (target='ship')
    test_audit_core003_goal_cc_and_continue_route_identically_without_writes (test_intent_audit_fixes)
    test_audit_core003_normal_cc_enters_done_convergence (test_intent_audit_fixes)
    test_coverage_count_mismatch_refuses (test_recovered_attribution)
    test_coverage_work_disagrees_with_tombstone_refuses (test_recovered_attribution)
    test_current_tombstone_is_not_byte_identical_to_original (test_recovered_attribution)
    test_explicit_claims_a_ticket_the_pick_rule_would_refuse (test_explicit_claim)
    test_illegal_phase_names_the_edge_that_leaves_the_phase_it_is_in (test_refusal_routes)
    test_line_endings_alone_are_not_drift (test_install_drift)
    test_linked_work_not_done_refuses (test_recovered_attribution)
    test_missing_recovery_record_refuses (test_recovered_attribution)
    test_missing_verification_on_implemented_refuses (test_recovered_attribution)
    test_newer_generation_refuses (test_recovered_attribution)
    test_no_test_module_races_a_concurrent_gate_on_a_constant_timeout (test_concurrency_independence)
    test_non_requirement_requirement_id_refuses (test_recovered_attribution)
    test_one_unknown_actionable_requirement_refuses (test_recovered_attribution)
    test_positive_fixture_attributes_to_linked_work (test_recovered_attribution)
    test_release_stays_blocked_with_carried_residue (test_recovered_attribution)
    test_requirement_without_linked_work_refuses (test_recovered_attribution)
    test_source_still_active_refuses (test_recovered_attribution)
    test_split_linked_work_refuses (test_recovered_attribution)
    test_strict_finding_identity_is_unchanged_by_attribution (test_recovered_attribution)
    test_the_flag_reaches_the_engine_through_the_cli (test_explicit_claim)
    test_the_same_refusal_from_scout_names_the_edge_out_of_scout (test_refusal_routes)
    test_the_two_transports_agree (test_inject_digest)
    test_tombstone_closure_counts_change_refuses (test_recovered_attribution)
    test_tombstone_linked_work_change_refuses (test_recovered_attribution)
    test_tombstone_not_closed_refuses (test_recovered_attribution)
    test_tombstone_source_sha_change_refuses (test_recovered_attribution)
    test_undocumented_tombstone_field_refuses (test_recovered_attribution)
    test_untampered_interrupted_close_settles_idempotently (test_audit_2026_08_28_all3)
    test_without_the_flag_the_pick_rule_is_unchanged (test_explicit_claim)
    test_work_delta_carries_residue_through_t160 (test_recovered_attribution)
