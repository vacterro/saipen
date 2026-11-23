# T-1883 DEPLOYMENT_PARITY — measured, blocked on foreign source

The handoff requires: "If the source is repaired but installed runtime remains
stale, report deployment as incomplete." This records the measurement and the
exact reason, so nobody re-derives it.

## Measurement

| Surface | reconcile.py | sha256 (16) |
|---|---|---|
| source tree | 3842 lines | `5379166af65017af` |
| runtime `76a5995cbf99aacc` | 3763 lines | `3055495a4303dada` |
| runtime `d838d464759d97d3` | 3763 lines | `3055495a4303dada` |

Both installed runtimes carry the pre-fix line:

```
352:    if live_blocked or cls is not None:
```

and zero occurrences of `_causally_related_blocks`. **Deployment is INCOMPLETE.**
An operator running the installed `saipen` still hits the original deadlock.

## Why it cannot be completed from here

The canonical installer path is `bootstrap/inject.ps1`, reached through
`saipen_engine.runtime_bootstrap._invoke_installer`, and the scheduled injector
refuses to publish an edited protocol by design:

```
autoinject.injection_blockers() ->
  condition: DIRTY_SOURCE
  blocked:   True
  path_count: 440
  detail: "440 injected-surface path(s) differ from HEAD; the scheduled
           injector refuses to publish an edited protocol, so every installed
           home stays on the last committed generation"
```

Of those 440 paths, **437 are not this Work's**: `saipen/*.md`,
`saipen/REGISTRY.json`, `saipen/COMMANDS.md`, `extensions/adapters/*`,
`bootstrap/*`, and other `tools/` files that other actors are editing in this
worktree concurrently. Committing them would take ownership of changes this
ticket did not review and did not make, and the mission explicitly forbids
"silently moving or unstaging another actor's files".

This Work's three paths are:

- `tools/saipen_engine/reconcile.py` (modified)
- `tools/test_recovery_reachability.py` (modified)
- `tools/test_t1883_reconcile_causality.py` (untracked, new)

## What would clear it

A commit whose scope is this Work's three paths, followed by the canonical
installer. That is publication authority this ticket does not have: T-1883
closed under `own_patch` closure, and the mission's anti-regression list forbids
"publishing without the established publication authority". The 437 foreign
paths must be committed or reverted by whoever owns them first — the guard
measures the whole injected surface, not one ticket's slice.

## What IS proven

The repair is correct and complete in source: focused gate PASS 189 ran at
fingerprint `646179cb`, red control 8/8 with all five security tests green, and
the end-to-end before/after at the pipeline level (see `e2e-repro.log`,
`red-control.log`, `RESULT.md`). Nothing in this directory claims the operator
is running it yet.
