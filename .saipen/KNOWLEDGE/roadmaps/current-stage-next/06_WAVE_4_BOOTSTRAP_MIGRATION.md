# 06 — WAVE 4: BOOTSTRAP MIGRATION + LIVE AUDIT DIRECTORY HYGIENE

## Goal

Enable the native inbox without duplicating the three current manually-owned audit files.

## W4.1 — Reconcile current canonical numbered layers

At activation time inspect:

- `audit/1.md`
- `audit/2.md`
- `audit/3.md`

For each exact generation determine:

- existing Source Receipt;
- existing Work;
- source state;
- file hash;
- cleanup eligibility.

Bind rather than recapture.

## W4.2 — Closed legacy cleanup dogfood

Expected:

- audit/1 and audit/2 may already be Source CLOSED;
- audit/3 is current implementation source.

Use the new native cleanup engine to delete closed unchanged audit/1 and audit/2.

This is the first real proof of deletion safety.

No naked manual unlink.

## W4.3 — Close audit/3, then consume itself safely

After the inbox feature passes VERIFY/REVIEW and audit/3 source is CLOSED:

the inbox may safely consume/delete `audit/3.md` using its own journaled path.

This is the strongest dogfood case.

## W4.4 — Noncanonical roadmap files

The live `audit/` folder currently contains the previous roadmap pack as noncanonical filenames.

The scanner must ignore them.

For repository hygiene:

move/reference-pack content out of the live inbox to an appropriate non-runtime location, or remove it from the project if it is only transport material.

Do not convert those files into Work.

Do not rename them to numbers.

## W4.5 — Prevent recurrence

Document operational rule:

> Roadmap ZIPs are reference artifacts. Do not unpack their internal files into the live `audit/` inbox.

If a roadmap itself is intended as an audit, place one deliberate numbered audit file, not the whole pack.

## Completion bar

1. No duplicate receipt/work for audit/1..3.
2. Closed legacy files removed only by native cleanup.
3. audit/3 can be safely self-consumed after closure.
4. Live audit folder contains only intended inbox files.
5. Noncanonical reference files never became Work.
6. Migration event/provenance survives deletion.
7. T-1224 DONE.
