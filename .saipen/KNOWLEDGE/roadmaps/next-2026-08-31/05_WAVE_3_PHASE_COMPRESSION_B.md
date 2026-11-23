# 05 — WAVE 3: PHASE COMPRESSION B — COMPLETE ALL 16 DELTAS

## Goal

Finish the actual `audit/2.md` requirement:

> every phase contains only its semantic delta, with total corpus approximately <=70 KB or a justified variance.

Do not force 70 KB through unsafe deletion.

## Group B — safety / medium phases

Prioritize:

- verify ~10.2 KB
- add ~8.1 KB
- hunt ~7.5 KB
- prepare ~5.6 KB

Conservative target band:

- verify ~6–7 KB
- add ~4.5–5.5 KB
- hunt ~4.5–5.5 KB
- prepare ~3.5–4.5 KB

VERIFY is safety-sensitive.

No compression without regression proof for:

- pass/fail;
- retries;
- caps;
- unavailable verifier;
- manual verification;
- false-green prevention.

## Group C — remaining phases

Review:

- done
- plan
- init
- review
- validate
- build
- scout
- blocked

Target them by duplication, not by arbitrary line count.

Small phases may already be near optimal.

Do not mutilate a clear 1.2 KB BLOCKED phase to save 80 bytes.

## Standard structure

Where useful converge toward:

- Purpose
- Entry
- Required reads
- Procedure
- Exit
- Failure / Blocked
- Rule references

But structure itself is not a reason to add boilerplate.

Compact consistency matters more than identical headings.

## Global phase contract

Shared invariants belong in their canonical owner.

Do not create a giant new shared phase document.

## R003 interpretation

"consistent structure" means predictable semantic sections/ordering, not necessarily identical heading count.

Define a validator or structural golden that checks the actual intended contract.

## Narration independence

Add a real protocol-level test proving phase lifecycle is not dependent on user-visible narration.

This closes R010 only when it actually exercises phase transitions/checkpoints.

## MAINTENANCE cross-cleanup

After HUNT/MARKHUNT/CLEAN ownership is clear:

remove duplicated phase procedure from MAINTENANCE where evidence proves duplication.

Do not weaken maintenance autonomy/safety-valve semantics.

## Final corpus gate

Measure exact bytes.

Desired:

<= ~70 KB.

If the safe semantic floor is slightly above 70 KB:

record a justified variance with:

- exact total;
- which documents remain large;
- why the remaining bytes are unique normative content;
- proof that further deletion would reduce clarity/correctness rather than duplication.

The source text explicitly permits justified variance.

Do not turn "~70 KB" into a destructive absolute.

## Close SRC-013

Only after every R001..R017 is truthfully terminal:

- close Source Receipt;
- finish T-1223;
- allow native Audit Inbox to perform hash-guarded journaled cleanup of `audit/2.md`.

No manual unlink.

## Completion bar

1. all 16 phases preserved;
2. DFA unchanged unless separately ratified;
3. all phase semantics regression-proven;
4. R003 truthfully proven;
5. R010 truthfully proven;
6. R016 gates green;
7. R017 clean checkout green;
8. R008 <=~70 KB or justified variance;
9. SRC-013 CLOSED;
10. audit/2 deleted only by native inbox cleanup.
