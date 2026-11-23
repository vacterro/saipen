# ARCHITECTURE ACCEPTANCE INVARIANTS

STATUS: ARCHITECTURE SEED

Any future implementation derived from this architecture must preserve these.

## Standalone

1. Per-project SAIPEN works without the global dispatcher.
2. Per-project SAIPEN works without AUDAPACK.
3. Dispatcher works without portfolio provider using deterministic fallback.

## Identity

4. A project is selected by identity/lineage, not folder-name coincidence.
5. Conflicting project identity fails closed for mutation.

## Leases

6. One project cannot have two live mutating project leases in dispatcher v1.
7. Lease acquisition is atomic.
8. A stale lease cannot be silently reused across runtime/project generations.

## Explicit intent

9. Explicit `start PROJECT` never silently substitutes another project.
10. Generic dispatch may select another eligible project after lease conflict.

## Local truth

11. Dispatcher cannot manufacture local READY state.
12. Portfolio priority cannot rewrite BOARD/STATE/LOG.
13. Global lease does not bypass local ownership/authority checks.

## Optional context

14. Missing/stale portfolio data does not block Core.
15. Portfolio priority affects ordering only through scheduler policy.

## Worker behavior

16. Completed slice releases lease safely.
17. WAIT_OPERATOR is not auto-overridden.
18. No eligible work results in IDLE, not speculative ticket creation.
19. Continuous mode does not ask routine "continue?" confirmations.
20. Continuous mode does stop at genuine operator decisions.

## Safety

21. No wrong-repo mutation.
22. No lease theft from a live owner.
23. No quoted/model-supplied authority promoted to operator authority.
24. No direct canonical surgery as dispatcher recovery shortcut.

## Deferred concurrency

25. Same-project multi-worker mutation is out of scope for dispatcher v1.
