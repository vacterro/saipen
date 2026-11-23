# Improve forensic evidence policy review

T-1803 / SRC-261:R030. Status: review and bounded class definition; no
producer-contract migration or consumer implementation is authorized here.

## Current behavior

`tools/saipen_engine/audit_manifest.py` declares contract version 3. Neither
`improve/` nor `improve-reconciliation/` is a default export directory. This
mission preserves that behavior and the file's pre-existing changes exactly.
An omitted report is unknown evidence, not an empty or completed audit.
The original requested cases were therefore read from the live AUDAPACK
instance, with its lineage and protected-byte hashes checked, rather than
inferred from its ZIP.

Minimal forensic evidence is useful: a snapshot should be able to identify
which seat and finding remains unresolved and which original bytes an
inspection would need. Exporting all Improve content is unnecessary and can
expose machine-local paths, private source observations or transient data.

## Proposed opt-in class: improve_forensics_v1

This is a bounded non-authoritative forensic adjunct, not execution authority
or a replacement for immutable original report bytes. A producer must select
explicit cycle identities; directory-wide discovery is not an export grant.

- At most 8 cycles, 32 seats and 128 findings; at most 2 MiB total and
  128 KiB per source/report. Exceeding a limit yields an explicit omission
  record, not a truncated document represented as complete.
- Carry cycle identity/status/schema, seat identity/role/availability,
  original report status, exact composite finding references, original
  SHA-256 hashes and explicit present/absent SWEEP state.
- Carry a bounded sanitized finding triple and canonical disposition when
  distribution permits it. Label every sanitized derivative as such and
  retain both original and sanitized digests; it can never satisfy the
  original-body verification requirement.
- Carry successor schema, immutable original-history bindings, pending or
  blocked findings, append-only event identities and native operation receipt
  identifiers/status/prefix hashes. Never include staged payload directories,
  live locks, authority keys or an invented successful receipt.
- Exclude credentials, private tokens, quarantine bodies, environment dumps,
  account profiles, nested checkpoints, runtime caches and all existing
  transient classes. Redact machine-local roots to explicit placeholders.
  Uncertain distribution safety omits content while preserving safe identity
  and a truthful reason; regex non-detection is not publication permission.
- Preserve original report/archive identity. Sanitization changes no live
  producer file, original source, finding, SWEEP or reconciliation record.
- An unavailable or malformed original remains UNKNOWN/BLOCKED. A portable
  adjunct never grants mutation, operator provenance or missing admission.

## Versioning and ownership

Adding this evidence class to the canonical manifest changes producer/consumer
semantics. It therefore requires an explicit contract-version transition
(v4 or the existing approved versioning owner), compatibility fixtures and an
independently admitted AUDAPACK consumer change. V3 producers and consumers
retain their present declarations; unknown versions/classes must refuse or
report unsupported evidence rather than silently applying a different policy.

T-1803 does not deploy that transition, change AUDAPACK code or enable broad
Improve-directory export. `manifest-policy-observation.json` records the
current actual classifier and proves audit_manifest.py is byte-identical to
this mission's preserved preimage.

Classifier clarification: `is_exportable()` is an exclusion predicate, not
directory selection. It returns true for otherwise safe Improve paths, but
v3's conditional/optional directory declarations do not select either Improve
tree. The observation records both decisions separately; predicate permission
alone must never be reported as evidence that a snapshot included a file.
