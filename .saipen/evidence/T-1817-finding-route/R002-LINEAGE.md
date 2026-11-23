# SRC-276 R002 / F-01+F-02: routing and the T-62 lineage, adjudicated

Read-only. Both observations below come from the target's own canonical
documents; nothing in
`V:/___VAC/__K/__CODE/_PY/_SMART_VAC_MEDIA_COMPRESSOR` was written.

## F-02: what T-62 actually was

The finding claims a duplicate long-term tracking record was minted for a
subject T-57 already owned. The target's LOG proves the sequence exactly:

| when | event | ticket | what it did |
|---|---|---|---|
| 05:03 | E-690 | T-62 | unblocked: register E-371 provenance + diagnose SRC-003 |
| 05:05 | E-693 | T-62 | `DEC: E-371 handled by canonical Decision B accepted legacy debt AD-000001` |
| 05:05 | E-694 | T-62 | BUILD -> VERIFY: **"SRC-003 routed to T-57"** |
| 05:05 | E-699 | T-62 | finished from SHIP |
| 05:09 | E-700 | T-57 | unblocked: reconstruct the SRC-003 bundle |
| 05:10 | E-705 | T-57 | verify PASS: SRC-003 `CLOSED`, 4 of 4 VERIFIED, 0 unresolved |
| 05:10 | E-709 | T-57 | finished from SHIP |

So T-62 was **not** a duplicate that took over T-57's subject. It carried the
E-371 accepted-debt half, and its own VERIFY line routed the SRC-003 half to the
ticket that already owned it. Both records closed through their real
SHIP chain. No fictional DONE exists on either.

That makes the historical duplicate **reconciled by the target's own record**,
not by assertion here. What F-02 demanded -- "explicitly reconcile T-62
duplicate or umbrella lineage without fictional DONE" -- is satisfied by
E-693/E-694 naming the split and by the two independent finish operations.

## F-01: the routing gap that let the duplicate happen at all

The engine had no finding-level resolver: from
`CONFORMANCE_UNHEALTHY / ENGINEERING_REQUIRED / action: null` there was no
mechanical way to name the Work that already owned the subject, so the agent's
only visible move was `saipen start`. That is what produced SRC-011/T-62.

`saipen_engine/finding_route.py` now answers it, read-only, and
`probe-route.py` ran it against both real boards:

**This project, SRC-276 closed-archive finding** ->
`ROUTED_TO_OWNER T-1817` (`linked-source-work`), route
`saipen ticket claim T-1817`. A continuation discovering this finding is now
told to use the existing owner.

**The target project, SRC-003 closed-archive finding** ->
`DONE_ONLY`, owner `null`, no route. Candidates T-47 (linked-source-work) and
T-48/T-49/T-50 (declared-receipt-work) are all `## DONE`. That is the correct
answer twice over: the subject is genuinely tracked, and a closed Work is
history rather than a queue slot, so nothing is silently reopened.

## What is NOT claimed

The resolver prevents a *mechanical* duplicate. It does not police an agent
that ignores its answer and starts anyway -- no engine rule can. What it removes
is the `action: null` dead end that made starting look like the only move.

The `DONE_ONLY` answer here is not a repair of the target's history: T-57's
bundle was already reconstructed by the target's own agent on 20.10 at 05:10,
and this session did not touch it.
