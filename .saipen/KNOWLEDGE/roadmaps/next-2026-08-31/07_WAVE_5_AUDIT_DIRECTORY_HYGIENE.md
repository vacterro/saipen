# 07 — WAVE 5: LIVE AUDIT DIRECTORY / TRANSPORT HYGIENE

## Goal

Make `audit/` a clean runtime inbox, not a storage attic.

## Current condition

The directory contains:

- live canonical `2.md`;
- many unpacked roadmap reference files.

The scanner correctly ignores noncanonical files.

That behavior must remain.

But reference packs should not normally live in the runtime inbox.

## Rule

`audit/` is for canonical producer inputs and minimal supporting runtime metadata only.

Roadmap ZIP contents belong elsewhere.

## Migration

After `audit/2.md` closes:

- move durable roadmap/reference material to KNOWLEDGE if genuinely useful;
- otherwise remove package-extraction leftovers through normal hygiene rules.

Do not convert them into numbered audits.

Do not let CLEAN delete user-owned material without ownership proof.

## Packaging boundary

AUDAPACK manifests and roadmap pack internals must not alter repository-root law.

Document/export a clear transport boundary.

## Completion bar

1. canonical inbox remains numbered-only for semantic intake;
2. noncanonical reference files are ignored by engine;
3. live inbox no longer serves as roadmap storage;
4. packaging artifacts do not fail repository validation;
5. no user-owned file is deleted without proof.
