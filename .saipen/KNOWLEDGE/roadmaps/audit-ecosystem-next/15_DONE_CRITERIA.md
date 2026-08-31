# 15 — FINAL DONE CRITERIA

This roadmap is complete only when:

## Current backlog

1. Current audit/1 is closed with evidence.
2. Current audit/2 is closed with evidence.
3. Current audit/3 is closed with evidence.
4. No duplicate Work was generated during native inbox activation.

## Consumer

5. `cc` discovers new audit automatically.
6. Recovery and active Work still outrank audit.
7. Audit outranks unrelated queued TODO.
8. Audit outranks Improve.
9. Audit becomes normal Source-backed Work.
10. Closure requires evidence.
11. Changed same-path generation is never deleted.
12. Deletion is journaled and recoverable.

## Producer

13. One shared enqueue API exists.
14. IDs are monotonic.
15. Concurrent producers cannot collide.
16. Retry is idempotent.
17. Existing audit cannot be overwritten.
18. Programmatic producer cannot escape `audit/`.

## Provenance

19. Producer metadata survives intake.
20. Audit → SRC → Work → disposition trace survives file deletion.
21. Rejected audit is a valid closure.
22. Fix commit/version can be linked.
23. Producer feedback projection is read-only.

## SAIPAL bridge

24. SAIPAL can enqueue through a narrow capability.
25. SAIPAL needs no Core write access.
26. SAIPAL audit uses normal Source lifecycle.
27. No SAIPAL-specific maintainer logic exists.
28. Producer finding ID survives final closure.

## Operator

29. Primary workflow remains `cc`.
30. `next` remains read-only.
31. `status` remains compact.
32. No separate audit dashboard is required.

## Reliability

33. Fresh checkout green.
34. Core validator green.
35. Audit discovery tests green.
36. Source closure tests green.
37. Crash/idempotency tests green.
38. Concurrent enqueue tests green.
39. Manual/AUDAPACK/SAIPAL-like dogfood green.
40. No packaging artifact silently becomes protocol root truth.

## Final mental model

```text
ANY AUDIT PRODUCER
       ↓
safe enqueue or manual drop
       ↓
audit/N.md
       ↓
cc
       ↓
Source Receipt
       ↓
Work
       ↓
evidence / verify
       ↓
close
       ↓
safe delete
       ↓
durable disposition / provenance
```

Once this is true, begin SAIPAL Wave A from the separate SAIPAL founding roadmap.
