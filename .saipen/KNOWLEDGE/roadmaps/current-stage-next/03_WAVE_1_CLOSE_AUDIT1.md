# 03 — WAVE 1: CLOSE `audit/1.md` SEMANTICALLY

## Goal

Finish the current Load Topology / Conformance audit using evidence.

Most implementation appears already present. Verify instead of redoing.

## Required proof

At minimum prove:

- BOOT is routing-only and within intended budget;
- INDEX reflects actual owner graph;
- cold budget <=20 KB;
- every declared profile is actually measured;
- load profile machine ownership exists;
- conformance corpus = 256/256;
- CONFORMANCE human view is compact and parity-verified/generated;
- stale CORE §1.10 command ownership references are gone where applicable;
- registry authority is truthful;
- phase docs were not accidentally semantically compressed during W4.

## Size evidence

Record current actual bytes.

Do not use targets as evidence.

## Closure

Close the Source Receipt only when all actionable audit/1 clauses are terminal with evidence.

Finish T-1222 through normal phase gates.

## IMPORTANT — DO NOT DELETE `audit/1.md` YET

The native Audit Inbox deletion protocol does not exist yet.

Mark the closed legacy audit generation as:

`legacy_closed_pending_inbox_cleanup`

or the closest bounded equivalent.

Preserve:

- path;
- exact SHA-256;
- receipt;
- Work;
- closure evidence.

This allows Wave 3 to dogfood safe cleanup instead of manually unlinking the file.

## Completion bar

1. T-1222 DONE.
2. audit/1 source CLOSED.
3. Exact audit/1 digest recorded.
4. File intentionally retained pending native inbox cleanup.
5. No W4 duplicate tickets remain actionable.
