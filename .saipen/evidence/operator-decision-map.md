# Operator decision map -- 145 blocked tickets, grouped by the decision that lifts them

- measured: 2026-11-17, from `.saipen/BOARD.md` (275 rows: 130 DONE, 0 DOING, 145 open/blocked)
- method: keyword census over each row's `blocker:` prose; bounded, not a per-ticket adjudication.
  The engine's own status (`todo 0`, `workable none`) is the authority on schedulability.

## The four decisions with real leverage

| # | decision | tickets lifted | note |
|---|---|---|---|
| 1 | authenticated ZAICODE ingress / fresh operator carrier | 17: T-1651, T-1664, T-1740, T-1794, T-1822, T-1857, T-1863, T-2010, T-2011, T-2012, T-2018, T-2022, T-2029, T-2041, T-2060, T-2061, T-2062 | the SRC-390/SRC-415/SRC-416 class; also the prerequisite chain behind the GC fix (T-2062) |
| 2 | publication staging / 8.1.1 generation install (T-2058 gate A EX-000053 binding, gate B crew exclusion) | 9: T-1816, T-1817, T-2058, T-2073, T-2074, T-2075, T-2078, T-2079, T-2080 | clears the 29-file untracked manifest class (see CONFORMANCE-DIAGNOSIS.md) and the CURRENT_FAIL receipt |
| 3 | MARKHUNT triage (`phases/markhunt.md:30` explicit triage) | 8: T-1307..T-1314 | a single sweep decision, no engineering |
| 4 | SRC-401/402/403 operator reissue (model_supplied receipts) | 2 direct: T-2042, T-2043; T-2041 in class 1 | receipts were quarantined/retired; reissue restores authority |

## Already-terminal classes that need no decision

- `PERMANENT_WARNING_OWNER` -- T-406, T-407, T-1119: the condition can never be met; parked by design.
- `HELD` -- T-442, T-473, T-575, T-1257, T-1719: held behind declared prerequisites.
- `INVALID OR AMBIGUOUS` / `SUPERSEDED` restatements from 02.10.26 -- T-1155, T-1172, T-1195, T-1564, T-1566, T-1321: not Work.
- `OUT_OF_SCOPE` / `PAUSED by operator` / `DEFERRED_BY_OPERATOR` / `PRIORITY_STEERING` -- T-1323, T-1426, T-1428, T-1722, T-1723, T-1724, T-1621: operator has steered them away; nothing to do.
- Self-named non-work probes -- T-2002, T-2008, T-1838: accidental admissions with no work owed.

## Remaining singles

The other ~90 blocked rows each carry their own named external clause (SRC-### requirement,
host capability, real operator witness, sequenced dependency). They are listed one per row on
the BOARD with their clause id; none is agent-actionable without the named external input, and
none is duplicated here.

## What this means for a next session

No ticket is runnable (`status --json`: todo 0, doing 0, top_workable none), so the honest next
action is the operator's pick among decisions 1-4. Decision 2 is the one that also unblocks the
crew circuit's SC-7 (its closure list is T-2062, T-2044, T-2058): T-2058 is decision 2, T-2062 is
decision 1, and T-2044 needs SRC-404 reissue (retired INVALID/ORPHANED_RECEIPT).

The six review tickets (T-2073, T-2074, T-2075, T-2078, T-2079, T-2080) are closed as a class
under PROTOCOL.md sec. 4 with DECs E-21514..E-21521 and annexes under `.saipen/evidence/T-20xx-review/`.
They are terminal review dispositions; do not re-litigate them per ticket.
