# SRC-236 / T-1738: SAITULS reconciliation verification

Status: BLOCKED_EXTERNAL. Original acceptance is not satisfied. SRC-236 must
remain ACTIVE; neither Work completion nor audit consumption is justified.

The previous report claimed completion from protocol rules and the audit's
baseline without measuring the target. Its preimage is preserved in
`REPORT.before-verification.md`. This report supersedes those unsupported claims;
historical BUILD event E-14950 remains unchanged.

## Current target evidence

Root: `V:/___VAC/__K/__CODE/__SAITULS`.
HEAD: `5f0dc0c6abe1f9a0a34487d87f56fb129410cb7f`; 98 tracked dirty paths.
`observation.json`, `target-board.md`, `target-state.md`, and the copied
`target-core-receipt.json` preserve the measured evidence.

- The current BOARD has one physical T-282 record under TODO, not two records.
  It has four canonical headings and the current parser reports no errors.
  The audit's duplicate/PARTIAL premise is stale. No deletion is now needed.
- T-282 partial evidence exists and distinguishes simulated, disposable Windows,
  unexecuted process-termination, and power-loss limits. It does not prove DONE
  or hardware acceptance.
- SRC-099 body digest matches its metadata, which links to T-282. Neither
  the live compacted BOARD row nor its preserved full record contains a
  `source_receipts` field. Complete source linkage remains unproven.
- T-260 is SCOUT with a persisted `WAIT: blocked`, not phase PAUSED. E-3003
  records reconciliation of unsupported PAUSED. E-3009 records a bounded
  power-loss-ceiling decision for T-282; E-3011 retains T-260's wider operator
  boundary. These observations do not prove independently authorized
  satisfaction of the original literal PAUSED acceptance.
- E-3001, E-3002, SRC-099 and partial evidence remain present. E-3002 is a
  historical RUN claim, not an authenticated lifecycle transition.

Canonical target validation was actually executed:

    bin/saipen.cmd --project-root V:/___VAC/__K/__CODE/__SAITULS validate --json

It returned exit 1, `CONFORMANCE_UNHEALTHY`, `CURRENT_FAIL`: **29 problems,
41 warnings**, receipt `receipt-66261157f63a` at 2026-10-13T07:29:00.481477Z.
Failures include invalid/incomplete sources and unproven DONE closure evidence.
Structural preflight passed; that does not establish protocol conformance.
This diagnostic wrote a conformance receipt in the target. No target Work,
STATE, BOARD, LOG, source, product, publication or deployment mutation was run.

## Clause disposition

| Clause | Disposition | Evidence and limit |
|---|---|---|
| R001 | VERIFIED | Live root, HEAD, tracked dirty count, STATE and target receipt measured. |
| R002 | VERIFIED | Read actual SRC-099 body/meta, BOARD/full record, partial evidence and E-3001..E-3011. |
| R003 | VERIFIED | Current parser rejects PARTIAL tickets; duplicate/PARTIAL controls fail; valid control passes. |
| R004 | VERIFIED | Actual T-282 is open TODO; delivery prose and historical RUN do not prove DONE. |
| R005 | VERIFIED | No current duplicate requires mutation; no foreign repair authority manufactured. |
| R006 | VERIFIED | Protected inputs hash-identical before/after collection; E-3001/E-3002 present. |
| R007 | NOT_APPLICABLE | Current target has no duplicate to remove. No historical removal transaction asserted. |
| R008 | BLOCKED | Uniqueness/headings pass; complete source linkage and conformance remain unproven. |
| R009 | VERIFIED | Exactly one T-282 record and discoverable partial evidence measured. |
| R010 | VERIFIED | No target DONE, hardware acceptance or unrelated lifecycle mutation performed. |
| R011 | BLOCKED | Live phase is SCOUT/WAIT; literal PAUSED acceptance and separate authorization unproven. |
| R012 | BLOCKED | Actual target protocol validation fails with 29 problems; no publication/deployment. |

Eight clauses VERIFIED, one genuinely NOT_APPLICABLE, three BLOCKED. Parser
rules and the SAIPEN core-unit family cannot replace failed target validation.

## Controls, authority and continuation

`python -B .saipen/evidence/T-1738-saituls-audit/observe.py` executes in-memory
valid/duplicate/PARTIAL controls against the current parser and records exact
target-input hashes. It writes artifacts only in this evidence directory.
It copies the actual failed receipt without reinterpreting that gate as PASS.

Graph tools/ and target protocol memory are excluded or stale; conclusions use
current direct reads and executed controls. CORE owns identity/lifecycle;
OPS section 12 owns diagnostic foreign observation; SOURCES owns nonterminal
BLOCKED coverage and original acceptance.

AUTHORITY_REQUIRED for additional SAITULS repair or lifecycle decisions. An
authorized target owner must resolve source/conformance failures and provide
current evidence or an explicit acceptance amendment for PAUSED. Re-evaluate
this existing Work then. Do not hand-edit target memory, invent DONE, close
SRC-236 or consume its audit layer to clear the queue.
