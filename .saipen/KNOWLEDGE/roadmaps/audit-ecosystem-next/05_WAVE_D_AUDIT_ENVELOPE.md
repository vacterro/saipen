# 05 — WAVE D: AUDIT ENVELOPE / PROVENANCE CONTRACT

## Goal

Define a small producer-neutral metadata envelope inside audit files.

The body remains Markdown and human-readable.

Do not force every audit producer into SAIPAL-specific schema.

## Required metadata

Recommended front matter or stable header fields:

- `audit_schema`
- `producer`
- `producer_version` if known
- `producer_item_id` if available
- `created_at`
- `severity` if producer supplies it
- `confidence` if producer supplies it
- `observed_project` if applicable
- `source_refs` if applicable
- `related_audit` / `amends_audit`
- `maintainer_verdict: PENDING`

## Trust rule

Producer metadata is a claim.

It is not canonical maintainer truth.

Example:

`severity: P0`

from SAIPAL means:

> SAIPAL assessed P0.

It does not mean SAIPEN must accept P0.

## Producer types

Initial known producer values may include:

- `human`
- `AUDAPACK`
- `SAIPAL`
- `SAIPEN`
- `unknown`

Do not hardcode model names as producer types.

## Backward compatibility

Plain Markdown audit files without envelope remain valid external audits.

Their producer is:

`unknown` or `human/manual`.

Do not require migration of old files merely to enable the new system.

## Body integrity

Exact bytes still define file generation identity.

Do not normalize producer Markdown before hashing.

## Minimal parsing

The deterministic engine may parse the small envelope.

It must not attempt to semantically understand arbitrary audit body prose.

## Wave D completion bar

1. Envelope schema exists.
2. Plain old Markdown still works.
3. Producer claims remain untrusted source claims.
4. Exact file hashing preserved.
5. Invalid envelope does not cause unsafe deletion.
6. SAIPAL template can fit without special-case engine code.
