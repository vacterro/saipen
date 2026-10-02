<!-- SAIPEN KNOWLEDGE CARD v1 -->
kind: trap
scope: reverify receipts, integrity digests, receipt selectors, closure evidence
trigger: a digest-verified record reader filters receipts by mutable body fields before validating their integrity digest
status: active
evidence: T-1517, tools/test_t1517_reverify_integrity.py
supersedes: none

# A selector edit can hide a corrupt newest receipt

Validate a receipt's integrity digest before filtering by body fields such as `work`; otherwise editing a selector can hide a corrupted newer receipt and expose older PASS evidence.

Why:
In T-1517, an intact PASS and a newer FAIL were written for the same Work. Editing only the newer receipt's `work` field made the reader skip it before checking its digest, so the older PASS resurfaced as closure evidence. Checking integrity first fails closed. This is distinct from editing the verdict and applies anywhere mutable fields choose which durable record is authoritative.
