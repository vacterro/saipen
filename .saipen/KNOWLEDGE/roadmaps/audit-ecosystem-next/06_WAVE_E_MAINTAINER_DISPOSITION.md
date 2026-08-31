# 06 — WAVE E: MAINTAINER DISPOSITION LOOP

## Goal

Allow a producer finding to be traced through the SAIPEN maintainer result.

Do not create a second closure system.

Use existing Source Receipt / Coverage / Work closure semantics.

## Desired provenance

```text
producer finding
→ audit/N.md
→ SRC-NNN
→ Work T-NNN
→ maintainer evidence
→ disposition
→ optional fix commit/version
```

## Maintainer outcome

A produced audit may be:

- confirmed;
- partially confirmed;
- duplicate;
- already fixed;
- not applicable;
- rejected;
- superseded;
- redirected to engine/adapter/docs/test/no-change.

Use existing Source Coverage dispositions where possible.

Do not invent a parallel status vocabulary unless a real semantic gap exists.

## Producer linkage

Persist compact linkage metadata:

- producer;
- producer_item_id;
- audit number/hash;
- Source Receipt;
- Work;
- final maintainer outcome;
- fix version/commit if known.

## Audit deletion does not erase provenance

After `audit/N.md` is safely consumed and deleted, the closure chain must remain reconstructable from Source archives/tombstones and LOG evidence.

## Feedback export

Provide a small read-only result projection that an external producer such as SAIPAL may later consume.

Example conceptual result:

```json
{
  "audit_id": 18,
  "producer": "SAIPAL",
  "producer_item_id": "PAL-0042",
  "receipt_id": "SRC-055",
  "work_id": "T-1301",
  "disposition": "REJECTED_FINDING",
  "fix_commit": null
}
```

Do not expose unrelated project secrets.

## Wave E completion bar

1. Producer ID survives intake.
2. Audit → SRC → Work trace survives file deletion.
3. Maintainer rejection is a valid closure.
4. Fix commit may be linked.
5. External result projection is read-only.
6. Existing Source closure remains authority.
