# SRC-326 / T-1917 — premature handback: first measured evidence

Status: REPRODUCED at the canonical-verdict layer. NOT yet diagnosed at the
installed-host layer.

## What the canonical engine says right now

Measured on this project immediately after a BUILD turn reported
`NEXT EXACT ACTION: saipen continue` and the model turn ended:

```
$ saipen iteration --json
decision:                 AUTO_KICK
goal_complete:            false
executable_action_remains: true
operator_due:             false
requires_human:           false
canonical_task:           T-1915
phase:                    BUILD
next_action:              "PHASE BUILD T-1915"
route_reason:             finish
recall_decision:          AUTO_KICK
```

So the verdict that H01/H02/H03/H04/H11 ask about is NOT the failure point:

- `goal_complete: false` — the host had no licence to show completion;
- `operator_due: false`, `requires_human: false` — the turn did not end because a
  human decision was pending (H11 disproved on this evidence);
- `executable_action_remains: true` — authorized work existed.

## What that leaves

With AUTO_KICK returned and no human gate open, the remaining hypotheses are all
host-side: H01 (no callback), H02 (ignored verdict), H05/H06 (enqueue/dispatch),
H09 (post-render advisory hook only), H10 (advisory integration), H13
(automation disabled).

This session's host is Freebuff Desktop, whose integration is an account-skill
and hook surface, not the ZAICODE turn-completion callback. It provides no
documented MODEL_TURN_FINISHED → controller → dispatch path, so the observed
outcome (turn ends, operator re-prompts) is consistent with H01/H09/H10. That is
a statement about THIS host's wiring; it is NOT evidence about ZAICODE's.

## What this evidence does not establish

- It does not prove which transition ZAICODE skips (AC-18 still unmeasured).
- It does not prove the reference controller mis-acts; `test_t1619` reference
  behaviour is untouched by this evidence.
- `executor_assessed: false` / `executor_capabilities: null` is a real gap worth
  closing (A14), but it is not the handback cause: the verdict fired anyway.

## Next executable step for T-1917 (blocked behind T-1915 seat)

Reproduce the boundary in the reference controller with the LIVE verdict above as
input (`HostIterationController.on_model_turn_finished`), then determine whether
the controller's own dispatch path can be driven without a host — and where the
host contract must name the missing callback. Live ZAICODE acceptance stays
pending and must not be claimed from fixtures.
