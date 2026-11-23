# SAIHANDOFF audit-layer triage (SRC-274 / SRC-275 / SRC-276)

Read-only triage. These three receipts are forensic audits of *other* sessions.
None of them authorizes execution in this repository; SRC-274 says so in its
own words ("This audit is not execution authorization"), and each names a
corrective owner per finding.

Measured: 2026-10-20, during T-1821's family run (read-only window).

## Why they cannot simply be "worked"

`SRC-274`, `SRC-275` and `SRC-276` each carry a contract with
`"clauses": []` — zero clauses at every interpretation revision. Their coverage
files have `requirements: {}`. There is nothing to mark VERIFIED and nothing to
dispose of, so the usual clause-by-clause closure path does not apply.

What each body does carry is a finding list with an explicit owner per finding.
The SAIPEN-owned items are the only ones this repository could implement, and
only as *new admitted work with its own source*, because the audits themselves
declare they are not authorization:

> **Next exact action (planning only):** SAIPEN agent prepares an admitted P0
> issue for immutable improve-report authority and an independent P1 issue for
> stale cross-ticket checkpoints.
> — SRC-274, "Corrective ownership and execution order"

So the correct disposition of these three audit layers is *triage into owned
work*, not execution inside the audit ticket.

## SRC-274 (AUDAPACK session) — SAIPEN-owned items

| Finding | What the audit demands | State measured today |
| --- | --- | --- |
| F-01 P0 | improve report authority keys are producer-attested/immutable; stale report cannot be restamped by hand | **partly built.** `improve.write_sweep_entry` refuses `CONFIRMED` when `_freshness_errors` finds a stale `source_head`/`source_tree_fingerprint`, and that predicate requires the tree fingerprint to carry a `git-delta-v1:`/`no-git-tree-v1:` mechanical prefix. It does not yet bind acceptance to a journaled RUN snapshot, so a *correct* restamp of both fields to the current tree still passes. |
| F-02 P1 | `continue` must not silently substitute persisted Work for a fresh substantial handoff | open; no typed admit/queue/refuse verdict for a new objective arriving mid-Work |
| F-03 P1 | cross-ticket checkpoint CAS: refuse a stale phase decision with a typed reason and zero LOG/BOARD/STATE writes | **not present.** No `STALE_WORK_CONTEXT` symbol exists anywhere in `tools/`. |
| F-04 P1 | canonical runtime-home failover verdict with build identity; else refuse mutations but keep read-only diagnosis | open |
| F-05 P1 | preserve authenticated user provenance instead of downgrading to `model_supplied` at engine admission | **partly built** (T-1822 carrier binding landed); blocked on the host side, see T-1819/T-1822 |
| F-06 P2 | expose stable machine-readable response policy | **built** — `response_surface` with `render_boundary`/`response_errors`/`REASON_BUDGETS`; T-1821 fixed its Markdown delivery |
| F-09 P2 | compound input took `continue` before the new task | open |

## SRC-275 (same session, independent read) — SAIPEN-owned items

Same session as SRC-274, so the findings overlap heavily. Its distinct
SAIPEN asks:

* effect-level protected-root write firewall across `Bash`/`Edit`/`Write` and
  child interpreters while `FORENSICALLY_UNRECOVERABLE` /
  `READ_ONLY_DIAGNOSIS_ONLY` is active. The lexicon exists
  (`reconcile.py`, `operations.py`, `log.py` carry both markers); what is not
  shown is a pre-tool effect gate that refuses the write *before* it lands.
* engine-vs-consumer execution isolation: require a Work/owner receipt before
  shared-runtime modification.
* `improve` provenance per RUN, append-only on refresh.
* typed closure outcomes `ALREADY_CLOSED` / `RESIDUE_SETTLED` /
  `ARCHIVE_VERIFIED` / `REPAIR_APPLIED`.
* typed owner/disposition per finding (`ENGINE_INTERNAL`,
  `OPERATOR_DECISION`, `UNAVAILABLE_EXTERNAL`) with linked ENGINE Work.

## SRC-276 (SMART VAC session) — SAIPEN-owned items

* goal → blocked finding → existing owner Work routing without creating a
  duplicate ticket through `start`.
* stable ticket cardinality when the same `cc` repeats.
* read-only evidence inventory reconstructed only from semantically complete
  trusted tombstone/intake + journal; never empty sidecars for PASS.
* resolver for witness provenance + project lineage + scoped operator decision;
  reject existing-but-non-authorizing `E`/`SRC` refs; log `KNOWN`/`UNKNOWN`.
* typed owner/disposition per finding.

## What this means for T-1815 / T-1816 / T-1817

Each of the three tickets is linked one-to-one to one of these audits
(`SRC-274→T-1815`, `SRC-275→T-1816`, `SRC-276→T-1817`) with zero clauses. They
cannot reach a clause-verified DONE because there is no clause to verify.

Two honest options, and the operator should pick one rather than have the agent
guess:

1. **Consume the audit**: record the triage above as the ticket's evidence,
   disposition the source as an advisory audit whose corrective items were
   routed to owning work (some already exist: F-06/T-1821, F-05/T-1822), and
   close the ticket as an audit-consumed layer rather than an implemented fix.
2. **Convert to work**: extract the SAIPEN-owned findings that are still open
   (F-01 remainder, F-02, F-03, F-04, F-09, plus SRC-275/276 items) into new
   admitted tickets with their own sources, and close the audit layer only when
   those tickets exist.

Option 2 is the only one that produces code for the open P0/P1 items, but it
requires creating new sources and tickets — a scope change the operator has to
authorize, because these audits explicitly withhold that authorization.

## Not SAIPEN work at all

SRC-274 F-02 (ZAICODE side), F-04 (ZAICODE executable routing), F-06 (host
enforcement), F-08 (projection counters), F-07 (AUDAPACK pixel AA), and the
SAITULS staging contract in SRC-275 are other owners' corrective work. They are
recorded here only so the split is visible; this repository must not patch them.
