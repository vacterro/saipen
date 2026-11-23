# T15 — RELEASE CUT / DOCUMENTATION

Priority: final
Depends on: T14

## Release only when

- full Windows pytest green;
- CI matrix green;
- Widget suite green;
- Ruff green;
- compileall green;
- real one-click smoke green;
- real six-run smoke green.

## Documentation

Update:
- README / README.ru
- Architecture-and-Bridge
- Audit-Campaign-Engine
- Auto3 pipeline
- UI wiki

Document one user workflow first:

`Select project -> START AUDIT -> AUDIT READY`

Then a small advanced section:
- WAITING
- BLOCKED
- CANCEL
- DETAILS

Do not lead the documentation with lease/state-machine internals.

## Version

Choose the next version based on actual shipped scope.

This feature is large enough for a coherent minor milestone if all six-run transparency work lands, but do not bump solely because this roadmap proposes it.

## Ship evidence

Record actual:
- commit
- version
- test counts
- Windows browser versions
- six-run smoke duration
- known limitations
