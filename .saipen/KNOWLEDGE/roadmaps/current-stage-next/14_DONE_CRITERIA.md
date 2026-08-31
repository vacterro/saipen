# 14 — FINAL DONE CRITERIA

This roadmap is complete only when all are true.

## Baseline

1. Current validator green.
2. `_AUDAPACK_MANIFEST.json` no longer causes repository-root drift.
3. LOG ancestry valid.
4. historical Improve linkage valid.
5. fresh checkout reproduces.

## Current audits

6. audit/1 source closed with evidence.
7. T-1222 DONE.
8. old W4 tickets reconciled.
9. audit/2 source closed with evidence.
10. T-1223 DONE.
11. phase corpus materially compressed without phase collapse.
12. audit/3 source closed with evidence.
13. T-1224 DONE.

## Native inbox

14. numbered scan implemented.
15. current legacy audit generations bound without duplication.
16. active Work outranks audit.
17. audit outranks ordinary TODO.
18. audit outranks Improve.
19. Source Intake is reused.
20. evidence required for closure.
21. changed generation protected.
22. deletion journaled/recoverable.
23. audit/1..3 cleanup performed by native mechanism, not manual unlink.
24. noncanonical roadmap files never became Work.

## Producer API

25. shared enqueue exists.
26. IDs monotonic.
27. concurrent producers safe.
28. retry idempotent.
29. no overwrite/path escape.
30. AUDAPACK can migrate to it without SAIPEN depending on AUDAPACK.

## HUSH

31. real HUSH runtime exists.
32. REGISTRY status truthful.
33. `hush cc` semantic parity proven.
34. mandatory interaction preserved.

## SAIPAL readiness

35. producer-neutral envelope works.
36. synthetic SAIPAL audit uses normal lifecycle.
37. producer item ID survives closure.
38. maintainer rejection supported.
39. disposition feedback read-only.
40. no automatic protocol edit loop.

## Operational closure

41. BOARD cleaned enough for practical operation.
42. LOG sealed when needed.
43. existing non-audit backlog resumes normally.
44. Audit Inbox empty means normal Pick Rule, not permanent audit mode.
45. no new roadmap wave is required merely to keep `cc` functioning.

Final operator mental model:

```text
manual / AUDAPACK / SAIPAL
        ↓
audit enqueue
        ↓
audit/N.md
        ↓
cc
        ↓
Source
        ↓
Work
        ↓
verify + evidence
        ↓
close
        ↓
safe delete
        ↓
normal backlog / next audit
```
