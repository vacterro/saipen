# 09 — WAVE 7: MAINTAINER DISPOSITION / CLOSED LOOP

## Goal

Preserve producer provenance through normal SAIPEN closure.

## Desired chain

```text
producer item
→ audit/N.md
→ Source Receipt
→ Work
→ maintainer evidence
→ disposition
→ optional fix commit/version
```

## No second closure system

Use existing Source Contract/Coverage.

A producer audit may be:

- confirmed;
- rejected;
- duplicate;
- already fixed;
- not applicable;
- test-only;
- engine fix;
- adapter fix;
- docs clarification;
- no change.

Map to existing terminal semantics where possible.

## File deletion

Deleting consumed `audit/N.md` must not destroy provenance.

Source archive/tombstone retains:

- audit hash;
- producer;
- producer item ID;
- Work;
- closure outcome.

## Read-only producer feedback

Expose compact result suitable for SAIPAL:

- audit ID/hash;
- producer item ID;
- receipt;
- Work;
- final maintainer outcome;
- fix commit/version if known.

No broad project data export.

## Completion bar

1. producer provenance survives file deletion;
2. maintainer rejection is valid closure;
3. fix version can be linked;
4. feedback is read-only;
5. producer cannot self-approve.
