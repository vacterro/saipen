# T-1957 REVIEW -- independent re-measurement, scope audit, and the edges I probed

## Re-run, not re-quoted

REVIEW executed the oracles again on the same tree after the VERIFY checkpoint,
adding the registry-parity oracle that this ticket did not modify:

```
$ python -B -m unittest tools.test_instruction_loader_contracts tools.test_host_bootstrap tools.test_adapter_parity
Ran 53 tests in 77.409s
OK
```

The third module matters: `test_adapter_parity` cross-checks the registry against
the installers and uninstallers, so it is an independent reader of the same
registry edit. It stayed green without being touched.

## Scope audit

```
 M extensions/adapters/registry.json
 M tools/autoinject.py
 M tools/test_host_bootstrap.py
 M tools/test_instruction_loader_contracts.py
```

Four files, one reason each, and no others. Two things were deliberately NOT
changed and each is a decision, not an omission:

**`instruction_surfaces` (the installer's write list) still holds
`~/.knowledge.md`.** The measured 0.2.34 CLI does not read it, so it looks like
dead weight. It stays because an operator running an older CLI still gets
activation from it, and because writing a harmless file is a different act from
*reporting delivery* from it. The behaviour changed is the report; the bytes on
disk did not move, so no home needs re-writing and there is no migration.

**`bootstrap/inject.ps1` and `project_block.py` are untouched.** The installer
already writes every declared surface, so it inherits the superset. The project
block owner already refuses to create a file, which is what closed the
"installer writes a root `AGENTS.md`" branch of the ticket's either/or.

## Edges I probed, because the new branch can shrink a list to empty

The `not-applicable` row is excluded from the overall status. If *every* loader
were project-scoped, that list would be empty, so I executed both shapes rather
than reasoning about them:

```
all-project, no write surfaces          -> absent  [P: not-applicable]
all-project WITH a write surface        -> stale   [P: not-applicable]
```

Both are defensible and neither is reachable today (FreeBuff keeps a home-scoped
CLI loader, which is why its verdict is still meaningful): nothing written means
nothing installed, and something written that no loader reads is genuinely
stale. I chose to leave the fallbacks as they fall rather than introduce a fifth
status token -- `current|stale|absent|unknown` is the vocabulary
`instruction_status`, `protocol_admission` and `host_integration` all branch on,
and adding a token to serve an unreachable shape would be an unproven change
riding on this ticket.

## The self-audit: where this ticket would be wrong if I were sloppy

**Inheriting T-1427's CLI measurement.** The ticket was filed about the desktop.
Had I accepted its framing, I would have fixed one loader and left the other
declaring `~/.knowledge.md` -- still `current`-by-a-file-nothing-reads, still
the defect class T-1427 exists to prevent. SCOUT re-measured the CLI out of
`freebuff.exe` 0.2.34 instead of trusting a 2026-09 note, and found it wrong
too. That is the single most load-bearing fact in this ticket.

**A test that got greener by being weakened.** `test_33`'s pre-fix injector
control used to pass by proving "the desktop cannot see `.knowledge.md`". Under
the measured contract the pre-fix home reaches *neither* loader. That is a
strictly sharper red, but it is also a *different proposition*, so I rewrote the
assertion text to name what it now proves instead of letting a passing test
imply the older claim. A control that silently changes what it controls is
worse than no control.

**A rule I invented that turned out false.** My first registry test demanded the
installer write *every* surface the verdict reads, and it failed on `.CLAUDE.md`
-- correctly, because that is a fallback the loader only opens when
`.AGENTS.md` is absent. The invariant that actually holds is narrower and truer:
the installer must write the surface each loader reads **first**, since that is
the one a stale copy shadows. I rewrote the test to that and it passes for the
right reason rather than being loosened until it did.

**`absent` masquerading as `stale`, and vice versa.** Removing `.knowledge.md`
from the read list made an installed-but-blind home report `absent`, which would
have *softened* the T-1426 verdict. The install-presence signal now keys on the
declared write surfaces, and
`test_an_uninstalled_adapter_without_any_surface_is_absent` still passes, so the
two states remain distinct.

## What this ticket does not claim

It does not claim FreeBuff Desktop now receives activation in this repository.
It does not: this repo has no root `AGENTS.md`, and
`saipen host instructions` still reports `PROJECT_BLOCK_ABSENT` -- correctly,
because creating that file is the operator's or a separate ticket's decision,
not a freshness fix. What this ticket establishes is narrower and verifiable:
the registry no longer names surfaces the shipped code does not read, and the
verdict no longer reports `current` on their strength.

## Verdict

Criterion 1 is byte-evidenced for both loaders. Criterion 2 is proven by a red
control that reproduces the HEAD defect on this real home. Criterion 3 is green
across 53 tests in three modules, with the stale control intact and the pinned
pre-fix subject still exhibiting the defect. Scope is four files with one reason
each; the two non-changes are recorded decisions; both reachable edge shapes were
executed. **REVIEW approves SHIP.**
