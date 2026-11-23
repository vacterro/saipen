# T-2029 — SRC-398 runtime and maintenance-authority unblock

Measured on this machine, 2026-11-05. Every claim below names the command that
produced it; snapshots sit beside this file.

## 1. Installed runtime repaired (SRC-398 clause 2)

Before: `python tools/saipen.py host doctor --json` reported

- `machine_runtime.code = MACHINE_RUNTIME_STALE`, generation
  `gen-sha256:be78d49b47d0e9d7...` against canonical
  `gen-sha256:625cc2c5ab55e192...`;
- ten installed hosts in `STALE_RUNTIME`, including `zaicode` and
  `zcode-production`, each with `action: saipen host repair`.

Action: the canonical `saipen host repair` (no hand edit, no source-only
substitute), then `saipen host repair --host claude --profile
C:\Users\vac34\.claude-account2` for the second Claude profile.

After (`doctor-after-repair.json`, `machine-runtime-status.json`):

- `machine_runtime.code = MACHINE_RUNTIME_READY`,
  `generation == canonical_generation`
  (`gen-sha256:481789cd34cc6f29...` after the fix below);
- `doctor.ok = true`, `needs_action = []`;
- every installed host carries `runtime: current` and `hook: current` —
  including `zaicode`. The default Claude profile reads `HEALTHY_VERIFIED`
  (its last prompt was admitted by the host authority); the others read
  `INSTALLED_UNVERIFIED`.
- The live authority broker is running with `generation_current: true`
  (restarted from the canonical root after the profile repair stopped it).

`INSTALLED_UNVERIFIED` is the honest ceiling for the rest: the doctor says so
in `reasons` — the host exposes no channel through which SAIPEN could verify a
session. It is not a defect, and it is not a claim that a session was verified.

## 2. Defect found and fixed while repairing

`tools/saipen_engine/host_integration.py::_health_is_current` accepted a health
record written BEFORE a repair rewrote the runtime. A runtime repair leaves the
hook file byte-identical, so the hook's mtime was the only bound the gate had,
and the pre-repair record — naming the same hook — still passed.

Consequence, measured on this machine: after a successful repair the host read
`DEGRADED_UNVERIFIED` with `reasons: The installed host hook is not the current
SAIPEN generation. (HOOK_STALE)` and `action: saipen host repair` — the doctor
asking for the repair it had just performed. That is the repeated WAIT loop
SRC-398 §6 forbids.

Fix: the health record is now bounded by the installed runtime's provenance
marker as well (`_runtime_facts` records `installed_at`; `_health_is_current`
takes the newest bound). An absent marker or absent hook keeps the previous
permissive behaviour, so no installation loses evidence.

Negative control: `tools/test_t1624_host_integration.py::StateModelTests::
test_a_repair_does_not_replay_the_verdict_it_repaired`. Proven failing on the
pre-fix gate (`DEGRADED_UNVERIFIED != INSTALLED_UNVERIFIED`) and passing after;
the pre-fix subject was restored for the proof and then replaced byte-identically.

## 3. Host scheduler transport — dependency, not a defect (SRC-398 clause 2)

`python tools/installed_host_acceptance.py --json`
(`installed-host-acceptance.json`) reports
`verdict: HOST_DISPATCH_UNAVAILABLE`, `scheduler_supported: false`,
`session_bound: false`, both `transport.host_dispatch_endpoint` and
`transport.host_scheduler_dispatch_cmd` false, and the reason "no
host-scheduler transport is registered: a request is durable
(DISPATCH_REQUEST_PERSISTED) but no host started it; the authority broker is
live, so an authenticated receipt remains possible".

SAIPEN's dispatch routes are a native callable, `HOST_SCHEDULER_DISPATCH_CMD`,
or `HOST_DISPATCH_ENDPOINT`
(`tools/saipen_engine/host_dispatch.py:1108,1173`). The installed ZAICODE
exposes none of them, and no authenticated `HOST_ACCEPTED` / `TURN_STARTED` /
`TURN_COMPLETED` receipt exists. No successor turn is claimed; a green SAIPEN
unit test is not evidence about the host.

## 4. Operator approval — one real operator action (SRC-398 clause 3)

`goals` holds one `ACTIVE` goal, `self-maintenance-core`
("Continuous SAIPEN Self-Maintenance and Defect Elimination"), whose objective
differs from the committed goal pivot.

`python tools/saipen.py goal propose --json`
(`goal-propose-refusal.json`) refuses with `PROPOSAL_OBJECTIVE_MISMATCH` and
names the one action:

    saipen goal Autonomously discover, evaluate, and repair verified
    regressions, test failures, and maintenance backlog to preserve a healthy
    repository

and then `saipen goal propose` (read-only) followed by
`saipen goal authorize --file <capsule>`. No capsule was minted here: the
refusal is the correct behaviour and was preserved.

## 5. Board count reconciliation (SRC-398 clause 5)

`.saipen/BOARD.md`: `## DONE` 135 rows, `## BLOCKED` 118 rows, `## DOING` 1,
`## TODO` 0. `git status`-era reports of "77 blocked" were a filtered subset;
the recovery `continue --json` `parked_work` list is exactly 118, matching the
Board. Nothing was reclassified to manufacture work.

## 6. Release security preserved (SRC-398 clauses 1, 6)

`tools/test_release_approval_contract.py` and `tools/test_isolated_release.py`
pass unchanged (12 tests): transaction binding, stale-packet rejection, PTY
impersonation refusal and immutable commit resolution are untouched by this
change, whose diff is 22 lines in `host_integration.py` plus one oracle. No
release packet was reopened.

The shared Git index still holds foreign staged paths pre-dating this ticket;
it was not touched, and no push was attempted.
