# T-2029 / SRC-398 — FINAL REPORT

SAIHANDOFF — SAIPEN ZAICODE RUNTIME AND MAINTENANCE AUTHORITY UNBLOCK
Measured on this machine, 2026-11-05. Evidence: `.saipen/evidence/T-2029-runtime-repair/`.

CURRENT_WORK: T-2029, all six SRC-398 clauses dispositioned; five VERIFIED with
receipts, R004 BLOCKED. Local change set: 22 lines in
`tools/saipen_engine/host_integration.py` plus one oracle, closed own_patch,
publication pending.

INSTALLED_RUNTIME_GENERATION: `MACHINE_RUNTIME_READY`,
gen-sha256:481789cd34cc6f29c59581cd5f98d1da63fb7119b28092c4ecb4090a00d0ac4a,
identical to the canonical source generation. Before the repair:
MACHINE_RUNTIME_STALE, gen-sha256:be78d49b47d0e9d7...

ZAICODE_NATIVE_INGRESS: installed and current. `saipen host doctor --json`:
`zaicode` runtime `current`, hook `current`, instruction `current`,
`delegated_root` = `_ZAICODE\.zaicode\home\.zcode\skills\saipen`. Host state
`INSTALLED_UNVERIFIED` — the host exposes no channel through which SAIPEN could
verify a session. No prompt ingress was attested.

BROKER_HEALTH: live. `authority.running: true`, `generation_current: true`,
pid 29316, endpoint `\\.\pipe\saipen-authority-...`, identity supported.
Admission policy `degraded` (source: operator, `C:\Users\vac34\.saipen\authority.json`).

SCHEDULER_TRANSPORT: absent. `installed_host_acceptance.py --json` =>
`HOST_DISPATCH_UNAVAILABLE`, `scheduler_supported: false`, `session_bound: false`,
`host_dispatch_endpoint: false`, `host_scheduler_dispatch_cmd: false`. SAIPEN's
dispatch routes (`tools/saipen_engine/host_dispatch.py:1108,1173`) are a native
callable, `HOST_SCHEDULER_DISPATCH_CMD`, or `HOST_DISPATCH_ENDPOINT`; installed
ZAICODE exposes none.

CURRENT_MAINTENANCE_GOAL: `self-maintenance-core` — "Continuous SAIPEN
Self-Maintenance and Defect Elimination", authorization_scope MAINTENANCE,
current_status ACTIVE.

GOAL_PIVOT_MATCH: no. The committed goal pivot names a different objective.
`saipen goal propose` refuses `PROPOSAL_OBJECTIVE_MISMATCH`; the refusal is
preserved and no pivot was minted from model text.

GENUINE_OPERATOR_APPROVAL: not obtained, and not claimed. No native-origin
operator event exists for this objective.

STANDING_GRANT_PROOF: none. The release grant path independently reports
`BLOCKED_AUTHORITY_GATE`.

REAL_SUCCESSOR_TURNS: none. No authenticated `HOST_ACCEPTED`, `TURN_STARTED` or
`TURN_COMPLETED` receipt; no successor turn was observed or simulated.

NEXT_ELIGIBLE_MAINTENANCE_WORK: none claimable. Every remaining Board row is
blocked on an operator decision, a publication, or the missing scheduler; no new
work is manufactured from status checks.

BOARD_COUNT_RECONCILIATION: `.saipen/BOARD.md` holds 135 DONE, 118 BLOCKED, 1
DOING, 0 TODO. The recovery `continue --json` `parked_work` list is exactly 118.
The earlier "77 blocked" was a filtered subset, never the Board total. No
genuinely external task was reclassified as executable.

RELEASE_SECURITY_NONREGRESSION: intact. `test_release_approval_contract.py` and
`test_isolated_release.py` pass (12 tests, focused receipt
`2d61560dfd20d8db-20261105T191716231301Z`). Transaction binding, stale packet
rejection, PTY impersonation refusal and immutable commit resolution are
untouched. The isolated ship packet now names exactly the reviewed 2-file scope.

SHARED_INDEX_PRESERVED: yes. The shared index still carries its pre-existing
foreign staged paths (864 at the isolated-ship packet); this ticket added nothing
to it, ran no `git add`, and pushed nothing.

ONE_EXACT_OPERATOR_ACTION: send the goal entry for the registered objective, then
approve the resulting capsule:

    saipen goal Autonomously discover, evaluate, and repair verified
    regressions, test failures, and maintenance backlog to preserve a healthy
    repository

    saipen goal propose
    saipen goal authorize --file <capsule>

TRUE_STOP_REASON: the remaining prerequisite is host-owned and human-owned. No
installed ZAICODE exposes a scheduler dispatch transport, so SAIPEN cannot start
the next model turn; and no genuine operator goal entry exists for the
maintenance objective, so no legitimate standing grant can be minted.

NEXT_WAKE_CONDITION: any of — (a) an operator goal entry for the registered
objective followed by an approved capsule; (b) `HOST_SCHEDULER_DISPATCH_CMD` or
`HOST_DISPATCH_ENDPOINT` set by the host so a dispatch returns a
broker-authenticated receipt; (c) a genuine operator release authorization grant
for the pending publication.

## Defect found and fixed in this ticket

`host_integration.py::_health_is_current` accepted a health record written before
a repair rewrote the runtime, because the hook file stays byte-identical. A
repaired host therefore replayed `HOOK_STALE` with the action `saipen host
repair` forever — the repeated WAIT loop SRC-398 §6 forbids. The record is now
bounded by the runtime provenance marker as well. Deliberate red control:
`test_a_repair_does_not_replay_the_verdict_it_repaired` fails on the pre-fix gate
and passes after.

## Verification

Full core-unit family on the integrated bytes, cited in the T-2029 verify cycle:
`CORE-UNIT-EVIDENCE PASS family:unit ran:9043 red:3 new_red:0 fixed:0
fingerprint:2d61560dfd20d8db record:.saipen/evidence/core-unit/2d61560dfd20d8db-20261105T185547539752Z.json`.
The 3 red are the declared baseline. This is not a claim that 9043 tests passed;
it is 9043 run with 3 known baseline failures and zero new.
