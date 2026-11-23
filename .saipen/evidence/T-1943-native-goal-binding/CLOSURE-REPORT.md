# T-1943 / SRC-342 — closure report

Format per SRC-342 section 6. Every row cites what was MEASURED on 2026-10-27,
not what was intended.

```text
STATUS: BLOCKED_EXTERNAL — R001-R005, R007, R008, R009 discharged with evidence;
        R006 and the section-6 DONE bar remain blocked on one human action.

CANONICAL SAIPEN HEAD: 025bf596c683464788ab698248e8a3c5eb44dfec
        (chore(t1601): record T-1601 DONE, 2026-10-05)
        Worktree dirty: 43746 paths before this ticket's staging.

EXISTING TICKET / OWNER: T-1943 (this ticket, owner saipen-cli), created from
        SRC-342. Reconciled against T-424 (the original ZAICODE goal-action
        report), T-1859 (authenticated ingress deadlock, AC-01 [LIVE]
        BLOCKED_EXTERNAL) and T-1882 (DONE, regression baseline). T-1933,
        T-1935, T-1868, T-1859 already own the hook's sealing behaviour and
        stay green; this ticket did not overwrite them.

ROOT CAUSE REPRODUCED: YES — three distinct defects, each measured before the
        fix and again after:
        (a) R003 objective binding: the broker hashed the raw command line into
            `goal_target` while the CLI hashed the objective, so `prepare_goal`
            could never match. Measured: `gg cc all` -> goal-bdb9..., 
            `saipen goal cc all` -> goal-925b..., `/goal gg cc all` ->
            goal-943c..., versus the objective's goal-ca391cacb96efa10.
        (b) R002 authorize-goal classification: `saipen goal authorize --file
            <capsule>` — the CLI's OWN documented spelling — was parsed as a
            GOAL whose objective was the literal string
            `authorize --file <path>`. The capsule was never verified.
        (c) R006 campaign scope: `grant_fields(..., until="continuous_maintenance")`
            emitted a state that `parse_state` read back as
            `{"phase": "CORRUPT", "corrupt_detail": "authority_until outside its
            closed enum"}`. The registry's `goal_authority.until` enum lacked a
            member that `GRANT_SCOPES` and `state.schema.json` both carry, so
            writer and reader disagreed. `continuous_maintenance_proven` could
            never be true on this tree.

NATIVE CONTINUE: classified `continue` by the shipped hook for `cc`, `cc all`,
        `/goal cc all`, `saipen goal` (bare), a bare `goal <words>` and every
        prose shape. Proven by test_t1943_goal_objective_binding (18 tests),
        test_t1933_zaicode_goal_seal (16), test_t1868_zaicode_ingress (8).

NATIVE GOAL: classified `goal` for `gg <objective>`, `saipen goal <objective>`,
        `saipen gg <objective>`, `/goal gg <objective>`, `/saipen goal
        <objective>`. All five spellings now bind ONE target
        (goal-ca391cacb96efa10) because one parser owns the grammar:
        `cold_recovery.goal_objective_text`, which the hook delegates to and the
        broker calls. A multiline body — even one opening with `gg <words>` — is
        refused, per section 4.

NATIVE AUTHORIZE-GOAL: classified `authorize-goal` for both spellings: the
        pasted capsule document and `saipen goal authorize --file <capsule>`.
        Both resolve to the SAME exact bytes (`grant_capsule_text`), which is
        the only thing `authorize_goal_continuation` compares against
        `goal_authority.current_binding`. Hostile paths refuse: absolute,
        `..` traversal, escaping the project, missing file, unreadable bytes,
        wrong arity. A missing capsule is reported as GRANT_CAPSULE_UNREADABLE
        rather than silently downgraded to `continue`.

WORKER REGISTRATION / BROKER: R004 reproduced nothing new. The existing
        contract already refuses a model issuer, a matching-session env
        impostor, a borrowed proof, a host process posing as a shared worker, a
        transplanted live worker, PID reuse, broken ancestry, redelivery with
        changed text, and an unregistered delivering worker:
        test_t1844_origin_broker — 48 tests, all green. The hook registers its
        OWN pid (not its parent) for the reason T-1859 measured.

PERSISTENT GRANT: MECHANISM NOW REACHABLE, AUTHORITY NOT OBSERVED.
        The mechanical half is fixed and proven: a campaign grant is now
        writable AND readable, and `is_continuous_maintenance` /
        `continuous_maintenance_proven` reach the proof path instead of
        failing on shape. Proven by test_t1943_campaign_scope_roundtrip (10),
        test_t1875_maintenance_wiring (11), test_campaign_continuation_assessment
        (7), test_t1864_autonomous_valve, test_t1857_budget_owner.
        The AUTHORITY half has not been observed: this is a genuine human
        action (R006 + section 6), not a code defect. See REMAINING BLOCKER.

20-TICKET POSITIVE CONTROL: mechanism proven, live crossing not observed.
        `trip_checkpoint` clears a tripped cap under a PROVEN persistent grant
        and still refuses an unproven claim or an unreadable journal
        (test_t1864_autonomous_valve: the owner names the authority it renews;
        an unproven persistent grant still waits; an unreadable grant journal
        degrades to the human boundary). The three-wave and 20-ticket sites both
        checkpoint rather than WAIT under a proven grant. What has NEVER
        happened on this tree is a real 20-ticket crossing under a real
        operator_persistent grant, because no such grant has ever existed here.

BOUNDED NEGATIVE CONTROL: HELD. A bounded goal still stops at the cap:
        `test_t1864_autonomous_valve.test_a_consumer_bounded_grant_still_waits_for_its_operator`
        asserts `goal_tickets: 20` and `WAIT: safety valve` for a consumer
        project. `test_t1943_campaign_scope_roundtrip.NothingWasWidened` proves
        the new enum member did not loosen the tuple: a bounded state carrying
        `continuous_maintenance` is still refused with "inconsistent
        scope/valve tuple", an invented scope is still "outside its closed
        enum", and a persistent grant without `goal_ingress` is still refused.

OTHER SECURITY NEGATIVE TESTS: multiline handoff opening with `gg` -> no
        authority; bare `goal <words>` -> no authority; `ggg`/`hh` near-misses
        -> no authority; capsule path `../../../etc/passwd` or
        `C:/Windows/win.ini` -> no authorization; capsule with extra argv ->
        none; unreadable capsule -> GRANT_CAPSULE_UNREADABLE and nothing spent;
        a hand-edited STATE claiming `operator_persistent` without a committed
        grant -> WAIT_AUTHORITY (test_campaign_continuation_assessment C13).
        `.saipen/STATE.md` was NEVER hand-edited, `goal_tickets` was never
        reset, `authority_source` was never altered and `hard_wait` was never
        bypassed.

CANONICAL COMMIT: NOT MADE. Commits require operator authorization (see
        REMAINING BLOCKER). Everything is staged, not committed; the adapter
        artifact is now in the INDEX, which is what R007 asks for as a
        precondition ("commit and verify the canonical adapter before
        refreshing any vendored bundle"). The validator's
        `runtime manifest names a file git does not track:
        extensions/adapters/zaicode/saipen-guard.py` FAIL is GONE; staging is
        what removed it, and a commit is still owed.

SCOPED DEPLOYMENT: `saipen host repair --host zaicode --dry-run` was run.
        It reports the current state and then states in its own output:
        "DRY RUN: no install, no authority restart, no machine runtime write".
        No other host was touched, no broker was restarted, no ZAICODE process
        was stopped. A real repair was NOT run, because doing so would publish
        uncommitted canonical source — exactly what R007 forbids.

INSTALLED HOOK GENERATION + HASH: DRIFTED, and named as such.
        canonical: sha256 7864a6d8209809b91345da5ebfb6f3f17910779ca953cea94e261458f886b408
                   (31593 bytes, working tree)
        installed: sha256 4317be7fc0175157d1248b34f7717ab8316566a787301e8c82d94984d4359315
                   (26630 bytes, ~/.zcode/hooks/saipen-guard.py, 2026-10-26 21:04)
        `saipen host doctor` answers: zaicode BROKEN — "the hook is installed but
        the runtime it needs is missing". Registry declares
        hook_artifact + hook_installer + hook_config_surface as expected.

LIVE ZAICODE NATIVE ACCEPTANCE: NOT ACHIEVED. No native ZAICODE event carrying
        `UserPromptSubmit` was observed sealing an operator origin on this
        tree. Every green above is a fixture exercising the shipped artifact
        and the canonical engine — necessary, and explicitly insufficient per
        section 6.

SAIPEN INBOX RECEIPT FOR MISROUTED INCIDENT: NOT ENQUEUED, and deliberately
        not faked. Measured: `audit/SAIHANDOFF_ZAICODE_20261026_1424_VALVE_AND_
        INGRESS_BLOCKER.md` exists only in the ZAICODE project
        (sha256 2b8979aaaeb1a65cc63d2528c3b382c65adf469f7af295c282b667bd6b102d42)
        and is NOT in SAIPEN's intake registry. SRC-342 section 3 says to ask
        the authorized producer/operator workflow to enqueue it. Producing that
        receipt myself would be the caller-signed ingress SRC-342 R005 forbids,
        so the original file is preserved untouched and the step is left open
        with the exact digest above.

REMAINING BLOCKER: ONE human action, plus one operator authorization.
        1. R006 / section 6 DONE bar: "an authentic user-initiated persistent
           grant is observed through the installed native ZAICODE host and
           SAIPEN subsequently continues a normal checkpoint under that grant
           without forged authorization". This needs a real operator to submit
           a genuine `gg <objective>` (or a real capsule) in the running
           ZAICODE UI against a project with an active bounded goal, after the
           canonical adapter is committed and the scoped repair is run. Same
           blocker as T-1859 AC-01 [LIVE]; it cannot be manufactured, and the
           protocol forbids simulating it.
        2. Commit authorization: this tree holds 43k dirty paths including 206
           foreign pre-staged paths owned by another actor. Staging T-1943's
           files is safe and done; COMMITTING is an operator decision and is
           what R007 ultimately requires before any bundle refresh.

NEXT EXACT ACTION: (a) operator commits the staged T-1943 delta; (b) run
        `saipen host repair --host zaicode` against the committed adapter;
        (c) operator sends one genuine `gg <objective>` in the ZAICODE UI;
        (d) this ticket closes on the observed sealed goal_entry and the
        subsequent mechanical checkpoint. Until (c), STATUS stays PARTIAL.
```

## Files changed by this ticket

| File | Change |
| --- | --- |
| `tools/saipen_engine/cold_recovery.py` | one goal-objective parser (`goal_objective_text`); multiline bodies refused; `authorize` is not an objective |
| `tools/saipen_engine/operator_origin.py` | `goal_target` derives from the objective, not the command line |
| `extensions/adapters/zaicode/saipen-guard.py` | delegates to the canonical parser; `_goal_objective_local` fallback matches it; `_grant_file` classifies the CLI's `--file` spelling; `grant_capsule_text` resolves both spellings to the same bytes |
| `extensions/adapters/zaicode.md` | the R009 integration contract: supported actions, exact input forms, authority answers, blocker codes, scoping and known limits |
| `saipen/REGISTRY.json` | `goal_authority.until` gains `continuous_maintenance`, the member `GRANT_SCOPES` and the schema already had |
| `tools/test_t1943_goal_objective_binding.py` | 18 tests: one target per objective, nothing promoted by accident, both authorize-goal spellings, hostile paths |
| `tools/test_t1943_adapter_artifact_tracking.py` | 5 tests: every declared `hook_artifact` is a repository file (R007) |
| `tools/test_t1943_campaign_scope_roundtrip.py` | 10 tests: the campaign grant is writable, readable and provable; nothing widened |

## Suites green (13)

test_t1943_campaign_scope_roundtrip (10) · test_t1943_goal_objective_binding (18)
· test_t1943_adapter_artifact_tracking (5) · test_t1875_maintenance_wiring (11)
· test_campaign_continuation_assessment (7) · test_t1864_autonomous_valve
· test_t1857_budget_owner · test_t1933_zaicode_goal_seal (16)
· test_t1868_zaicode_ingress (8) · test_t1859_zaicode_seal (8)
· test_t1935_zaicode_hook_ownership (12) · test_t1844_origin_broker (48)
· test_cold_recovery

Logs: `.saipen/evidence/T-1943-native-goal-binding/*.log`
Environment record: `.saipen/evidence/T-1943-native-goal-binding/R001-environment.txt`

## Final disposition (2026-10-27)

T-1943 was transitioned REVIEW, decided by `checkpoint DEC T-1943`, and
closed with `saipen ticket block T-1943 --scope ticket`. It is NOT DONE:
SRC-342 R006's authority half and the section-6 bar require a genuine
operator-initiated grant observed through the installed native host.

Delivered and committed-to-index: R001-R005, R007, R008, R009.
Not delivered by design: R006's live half, because the only route would be a
forged operator action or uncommitted-source deployment, both forbidden by
SRC-342 section 5.
