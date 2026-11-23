# T-1943 / SRC-342 — closure report, re-measured 2026-10-29

Supersedes the 2026-10-27 disposition in `CLOSURE-REPORT.md`, which recorded
R008 as "NOT ENQUEUED" and R006 as blocked on two operator actions. Both
statements were measured again and both were wrong. Every row below cites what
was measured today, on `HEAD 66ef622a43ab59512735ac78ce10d1250e26f9df`.

```text
STATUS: PARTIAL — 8 of 9 clauses VERIFIED. R005 alone remains BLOCKED on one
        human action. No forged authorization, no STATE hand-edit, no
        uncommitted-source deployment.

CANONICAL SAIPEN HEAD: 66ef622a43ab59512735ac78ce10d1250e26f9df

EXISTING TICKET / OWNER: T-1943 (owner saipen-cli), from SRC-342. The campaign
        it belongs to is T-424 / T-1859 / T-1882; T-1933, T-1935, T-1868 and
        T-1859 own the hook-sealing behaviour and stay green. Nothing here
        duplicates SRC-339 or re-opens a DONE row.

ROOT CAUSE REPRODUCED: YES on 2026-10-27 (three defects: objective binding,
        authorize-goal classification, campaign-scope enum). All three remain
        fixed at HEAD and are re-pinned by the suites below.

NATIVE CONTINUE: 5/5. `cc`, `cc all`, `cc please`, `/goal cc all`, and prose
        each declare `continue` when classified by the INSTALLED hook bytes
        (C:/Users/vac34/.zcode/hooks/saipen-guard.py), not by a fixture copy.
        Evidence: remeasure-20261029/r001-control-matrix.txt

NATIVE GOAL: 4/4. `gg <objective>`, `gg build the thing`, `saipen goal x`,
        `/goal gg x` each declare `goal`. Negative half: a bare `gg`, a
        multiline body opening with `gg`, `ggg x`, `hh x` and `goal of this
        is X` all stay `continue`. Same file.

NATIVE AUTHORIZE-GOAL: unchanged from 2026-10-27 and still green: both
        spellings (pasted capsule, `saipen goal authorize --file <capsule>`)
        resolve to the same exact bytes through `grant_capsule_text`; hostile
        paths (absolute, `..`, escaping the project, missing, wrong arity)
        refuse. test_t1943_goal_objective_binding 18/18.

WORKER REGISTRATION / BROKER: 48/48 green (test_t1844_origin_broker). The
        contract refuses a model issuer, a matching-session env impostor, a
        borrowed proof, a host process posing as a worker, a transplanted live
        worker, PID reuse, broken ancestry, redelivery with changed text and an
        unregistered delivering worker.

PERSISTENT GRANT: MECHANISM PROVEN, AUTHORITY ABSENT.
        The writer and reader now agree: `grant_fields(until=
        "continuous_maintenance")` writes, `parse_state` reads it back, and
        `is_continuous_maintenance` / `continuous_maintenance_proven` reach the
        proof path (test_t1943_campaign_scope_roundtrip 10/10).
        The grant itself does not exist and cannot be manufactured here.
        Measured: STATE carries `continuation_authority operator_required`,
        `authority_until budget`, `safety_valve_mode hard_wait`,
        `goal_ingress` absent; 23 committed `goal_entry` receipts exist and
        NONE carries `goal_authority` metadata; the LOG holds ZERO
        `goal pivot --` DEC events. A correctly-shaped persistent claim written
        in memory is still refused by `prove` with "persistent authority does
        not name the current goal pivot" — shape without evidence is not
        authority. Evidence: remeasure-20261029/r005-blocker.txt

20-TICKET POSITIVE CONTROL: MECHANISM PROVEN, LIVE CROSSING NOT OBSERVED.
        15/15 green (test_t1864_autonomous_valve): a PROVEN grant clears the
        checkpoint itself; an unproven claim still waits; an unreadable grant
        journal degrades to the human boundary. What has never happened on this
        tree is a real crossing under a real grant, because no such grant has
        ever existed.

BOUNDED NEGATIVE CONTROL: HELD. test_t1864_autonomous_valve's
        `test_a_consumer_bounded_grant_still_waits_for_its_operator` asserts
        `goal_tickets: 20` and `WAIT: safety valve`. 15/15.

OTHER SECURITY NEGATIVE TESTS: HELD. Multiline handoff opening with `gg` -> no
        authority; bare `goal <words>` -> no authority; `ggg`/`hh` -> none;
        capsule traversal or foreign drive path -> none; unreadable capsule ->
        GRANT_CAPSULE_UNREADABLE and nothing spent; a hand-edited STATE
        claiming `operator_persistent` without a committed grant -> refused.
        `.saipen/STATE.md` was never hand-edited, `goal_tickets` never reset,
        `authority_source` never altered, `hard_wait` never bypassed.

CANONICAL COMMIT: REQUIRED HALF IS SATISFIED. The shipped adapter
        `extensions/adapters/zaicode/saipen-guard.py` is COMMITTED at HEAD:
        `git show HEAD:...` hashes to 7864a6d8209809b9…, the same digest the
        worktree carries, and `git status --porcelain` on it is empty. The
        integration contract `extensions/adapters/zaicode.md` is tracked and
        committed too. This was the outstanding item on 2026-10-27 and it is
        now done.
        Evidence: remeasure-20261029/hook-identity.txt

SCOPED DEPLOYMENT: SATISFIED. `python tools/install_host_guard.py zaicode
        --check` answers installed:true current:true configured:true
        problems:[] root_current:true. The installed hook is BYTE-IDENTICAL to
        the committed adapter (cmp clean, 31593 bytes both sides, one sha256).
        The 2026-10-27 report's drift row (installed 4317be7f/26630B vs
        canonical 7864a6d8/31593B) and its "host doctor says zaicode BROKEN"
        line are both obsolete: `saipen host doctor` now reports broken:[] and
        hook:"current". The host's only remaining state is STALE_RUNTIME
        against the skill RUNTIME generation, which is a different surface from
        the hook and is caused by six engine files another session is currently
        editing — not by this ticket and not by the adapter.

INSTALLED HOOK GENERATION + HASH: EQUAL. installed
        7864a6d8209809b91345da5ebfb6f3f17910779ca953cea94e261458f886b408
        (31593 B) == canonical worktree == committed HEAD blob. One digest,
        three surfaces.

LIVE ZAICODE NATIVE ACCEPTANCE: NOT ACHIEVED, and named as such. No native
        ZAICODE `UserPromptSubmit` event carrying an operator origin has been
        observed on this tree. Every green above exercises the installed
        artifact and the canonical engine; per section 6 that is necessary and
        insufficient.

SAIPEN INBOX RECEIPT FOR MISROUTED INCIDENT: ALREADY SATISFIED — this is the
        2026-10-27 report's factual error. The incident
        `audit/SAIHANDOFF_ZAICODE_20261026_1424_VALVE_AND_INGRESS_BLOCKER.md`
        (sha256 2b8979aaaeb1a65cc63d2528c3b382c65adf469f7af295c282b667bd6b102d42)
        IS in SAIPEN's registry: it is SRC-339, same digest, received
        2026-10-26T17:26:45Z, consumed by the journaled audit inbox at E-18499
        under op `audit-consume-5975be5b45cd262f` with coverage 7/7, archived
        and tombstoned CLOSED with 0 unresolved. Section 3's condition ("check
        whether it already exists; if not, enqueue") is therefore answered: it
        already exists, and re-enqueuing would duplicate a closed receipt. The
        original file and its digest are preserved untouched, and no accepted
        intake record was altered. R008 flipped to VERIFIED on E-18499.

REMAINING BLOCKER: ONE human action. SRC-342 R005 / section 6: an intentional
        native user action must establish `operator_persistent` authority for
        this exact project and goal, observable through `saipen status`, and a
        normal checkpoint must then continue under it without forged
        authorization. This is the same live event T-1859 AC-01 owns. It cannot
        be produced by any seat: the grant requires a carrier-witnessed
        operator origin walked by `goal_authority.prove`, and fabricating one
        is exactly what SRC-342 section 5 forbids.

NEXT EXACT ACTION: (a) in the running ZAICODE UI, on this project, submit one
        genuine `gg <objective>` or `saipen goal authorize --file <capsule>`
        carrying the intended maintenance goal; (b) confirm
        `saipen status --json` answers continuation_authority
        operator_persistent with a goal_ingress binding and
        authority_until continuous_maintenance; (c) drive the next 20-ticket
        checkpoint under it and record the observed continuation. On that
        sealed goal_entry plus its mechanical checkpoint, R005 flips VERIFIED
        and T-1943 is DONE. Until then STATUS stays PARTIAL.
```

## Suites green (14, re-run today)

Focused record `55177ee2199b5b6f-20261029T222608299927Z` — 9 modules, 140 tests:

test_t1943_goal_objective_binding (18) · test_t1943_campaign_scope_roundtrip (10)
· test_t1943_adapter_artifact_tracking (5) · test_t1933_zaicode_goal_seal (16)
· test_t1868_zaicode_ingress (8) · test_t1859_zaicode_seal (8)
· test_t1935_zaicode_hook_ownership (12) · test_t1844_origin_broker (48)
· test_t1864_autonomous_valve (15)

R005 mechanism, 5 more modules, 68 tests: test_t1494_continuation_authority (19,
including `test_authorized_persistent_goal_crosses_every_cap_without_a_human_grant`
which crosses 20/21/28/50/100 on one grant) · test_t1704_legacy_goal_authority
(28) · test_t1875_maintenance_wiring (11) ·
test_campaign_continuation_assessment (7) · test_t1857_budget_owner (3).

208 tests, 0 failures, 0 errors, 0 skips.
Logs: `remeasure-20261029/suites.txt`, `remeasure-20261029/r005-mechanism.txt`

## What changed in this pass

| Item | 2026-10-27 report said | measured 2026-10-29 |
| --- | --- | --- |
| R006 first half (commit the adapter) | "NOT MADE, commit owed" | committed at HEAD, digest equal on all three surfaces |
| R006 second half (integration contract) | not listed as delivered | `extensions/adapters/zaicode.md` tracked and committed, covers actions / input forms / authority status / blocker codes |
| R008 (misrouted incident) | "NOT ENQUEUED, deliberately not faked" | already SRC-339, same digest, CLOSED 0 unresolved at E-18499 |
| installed hook | 4317be7f / 26630 B, drifted | 7864a6d8 / 31593 B, byte-identical to canonical |
| host verdict | "zaicode BROKEN" | `broken: []`, hook `current`; only STALE_RUNTIME on the skill runtime |
| R001 | terminal in REVIEW, recorded BLOCKED | VERIFIED on a 16-case control matrix run against the installed bytes |
| R005 | BLOCKED | still BLOCKED — the one honest remainder |

No file in this ticket's delta was invented: R006 and R008 moved because the
evidence already existed and the 2026-10-27 record had not been re-measured.
