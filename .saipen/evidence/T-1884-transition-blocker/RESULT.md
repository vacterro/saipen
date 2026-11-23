# T-1884 / SRC-309 — E10/E11: a transition must not inherit a blocker

The handoff's WORKSTREAM E asks for prevention at the source, not only repair
after the fact. Two of its clauses were measured as still broken after T-1883:

- **E10** "Verify that an old generic blocker is not inherited across an
  unrelated successful transition."
- **E11** "Ensure an interrupted transition does not leave an unowned
  `STATE.blocker`."

## The measured defect

`_plan_transition` (`tools/saipen_engine/operations.py`) built its owned-field
set as `{phase, next_action, transition_from, last_event, updated, agent}` and
never touched `blocker`. Two consequences, both measured on fixtures before the
fix:

| Case | Before |
|---|---|
| SHIP + `operator_required (continuation_authority) for REVIEW -> SHIP` → BUILD | `TRANSITIONED`, blocker still set in BUILD |
| BLOCKED + `HELD -- operator must decide before ship` → SCOUT | `TRANSITIONED`, blocker still set in SCOUT |
| SHIP + `HELD -- …` → BUILD | `TRANSITIONED` — **a genuine gate was ridden over** |

Because `binding_brake` treats a non-empty blocker as a hard stop in *every*
phase, each "successful" transition left the project refusing every
consequential verb. The deadlock arrived one step after the agent-written prose
instead of at it. The third row is the more serious one: the same missing rule
that let a stale field linger also let a real operator gate be bypassed by an
ordinary phase move.

## The rule

Placed in `_plan_transition` immediately after the owned-field construction, so
it runs before any bytes are written:

1. **Leaving `BLOCKED`** sets `blocker: none`. That field belongs to the phase
   being exited. (`_state_blocker_repairs` deliberately returns nothing for
   `BLOCKED` — the blocker is consistent there — so this half is stated
   explicitly rather than inferred from the classifier.)
2. **Any other destination** consults the ONE classifier `recover` already
   trusts, `_state_blocker_repairs`:
   - a `refuse` repair → the transition refuses with `OPERATOR_DECISION_REQUIRED`
     and the classifier's own `canonical_next_command`; the blocker is preserved
     verbatim;
   - a safe repair → `blocker: none` is added to the owned set, because no
     canonical verb authored the field and `recover` would clear it anyway.
     Making the operator run that command first is the manual-repair round trip
     the mission forbids.
3. **Moving INTO `BLOCKED`** is exempt: that phase is the field's home, so the
   blocker travels with it. Refusing there would strand a gated project with no
   canonical way to park.

The point of reusing `_state_blocker_repairs` rather than a second predicate is
that a transition and a recovery can never disagree about which blockers are
real. The classifier is causal (T-1883): a recognised class token or a causally
related `## BLOCKED` ticket is genuine; unrelated board inventory is not.

## Regression tests — `tools/test_t1884_transition_blocker_inheritance.py`

Seven tests, driving the real CLI through `--project-root` on disposable
projects:

| Test | Asserts |
|---|---|
| `test_e10_a_stale_blocker_is_not_inherited_by_the_next_phase` | SHIP→BUILD clears the stale blocker |
| `test_e11_leaving_blocked_clears_the_phase_own_blocker` | BLOCKED→SCOUT clears it |
| `test_a_held_gate_refuses_and_is_preserved` | `HELD` refuses, STATE bytes unchanged |
| `test_a_recognised_class_token_refuses_and_is_preserved` | `BLOCKED_EXTERNAL` refuses |
| `test_a_causally_related_blocked_ticket_refuses` | a `needs:`-related blocked ticket refuses |
| `test_an_unrelated_blocked_ticket_does_not_block_the_transition` | unrelated blocks do not veto |
| `test_a_clean_project_transitions_as_before` | normal transitions unaffected |

## Red control — `red-control.log`

The rule is removed from a throwaway copy of `operations.py`; the test bytes are
identical. Measured:

```
3/3 inheritance tests red
3/3 gate-ride-over tests red
1/1 clean-project test still green
RED CONTROL OK
```

The six reds are the honest count: the pre-fix code had both defects. The clean
project staying green is what proves the rule restored refusal authority rather
than manufacturing it.

## Wider sweep (all green, at the same tree)

```
test_t1884_transition_blocker_inheritance   7
test_*transition*                          19
test_t1729* (operator gate)                37
test_*reconcile*                           91
test_recovery_reachability                 85
test_*state*                               15
test_*board*                              141
test_*lifecycle*                           97
```

Focused gate: `PASS`, 175 ran, record
`.saipen/evidence/focused-unit/c6c4e71d5f4ea21d-20261024T151247579356Z.json`,
sha256 `f05d603b9c386a1c5e2b07bd19fd4eacb4161b1e018a26f16c199615d9b2a79c`,
tree fingerprint `c6c4e71d5f4ea21d`.

## What this does NOT claim

- **Deployment**: the installed runtimes remain stale. See
  `.saipen/evidence/T-1883-reconcile-causality/DEPLOYMENT_PARITY.md`; the same
  437 foreign dirty paths block the injector, now plus these two files.
- **Publication**: focused proof admits SHIP, not publication. The full family
  still carries the 55 foreign reds and a `red 0` baseline.
- **The live FastPrompter incident**: not verified, for the same reason given in
  the T-1883 result — its real STATE and BOARD were not available here.
- `ticket block` / `block-for` were not changed. They never write
  `STATE.blocker` on the active ticket (measured: parking T-1517 leaves
  `blocker: "none"` and records `blocker_scope: ticket` on the BOARD row), so
  they are not a source of unowned active-phase blockers.
