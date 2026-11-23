# Investigation Report: Missing Canonical Evidence Sidecar (SRC-229 / T-1731)

## Executive Summary
- **Classification**: `RECOVERED_VERIFIED`
- **Subject**: Missing canonical evidence sidecar `.saipen/recovery/log-detail/E-3286-f56793e5c6d3f9370cd1be66.json` cited by Wintage ledger.
- **Outcome**: The cited record and its companion `.LOG.md` file were located in a durable verified AUDAPACK unpack source, verified against the canonical committed checkpoint journal receipt, and restored to their canonical location on disk in the Wintage project tree.

## Scope Findings

### 1. Absence Verification on Live Tree
- Inspection of the live Wintage working tree (`V:/___VAC/__K/__CODE/_TAMPERMONKEY/_WIN95THEME/Wintage`) confirmed that `.saipen/recovery/log-detail/E-3286-f56793e5c6d3f9370cd1be66.json` and `.LOG.md` were absent on disk.
- AUDAPACK export truthfully reported `status: PROTOCOL_INCOMPLETE`, `reason: evidence_absent_on_disk`.

### 2. Original Ledger Citation and Journal Precedent
- **Ledger citation**: Wintage `.saipen/logs/LOG-004.md` (sealed from active `.saipen/LOG.md` at `E-3583`):
  ```markdown
  - 05.10.26 20:56 [E-3286] [parent: E-3285] [T-415] [agent: saipen-cli] [op: checkpoint-d898f0b0e66644ea92a33f4c18909e6d] RUN: verify -> PASS [target: T-415] ...
  ```
- **Committed journal receipt**: Wintage `.saipen/recovery/settled/checkpoint-d898f0b0e66644ea92a33f4c18909e6d/operation.json`:
  ```json
  {
    "op_id": "checkpoint-d898f0b0e66644ea92a33f4c18909e6d",
    "operation": "checkpoint",
    "created_at": "2026-10-05T20:56:03Z",
    "agent": "saipen-cli",
    "status": "COMMITTED",
    "targets": [
      {
        "path": ".saipen/recovery/log-detail/E-3286-f56793e5c6d3f9370cd1be66.LOG.md",
        "action": "write",
        "after_hash": "f56793e5c6d3f937",
        "applied": true
      },
      {
        "path": ".saipen/recovery/log-detail/E-3286-f56793e5c6d3f9370cd1be66.json",
        "action": "write",
        "after_hash": "e58b4717fde5d63b",
        "applied": true
      }
    ]
  }
  ```

### 3. Durable Verified Recovery Source and Provenance
- **Location**: `V:/___VAC/__K/__CODE/_HTML/_SAI_WEBSITE/_src_unpack/wintage/.saipen/recovery/log-detail/`
- **Provenance**: Created from an earlier AUDAPACK export package created at `2026-10-07T03:09:53.384827` from Wintage (`_AUDAPACK_MANIFEST.json` schema v3).
- **Manifest references**: Cited in `_AUDAPACK_MANIFEST.json` at line 496 (`included_files`) and line 1129 (`references.citations`).

### 4. Integrity and Hash Proof
Both recovered files match the canonical journal targets:
1. `.saipen/recovery/log-detail/E-3286-f56793e5c6d3f9370cd1be66.LOG.md`:
   - Size: 1239 bytes
   - SHA-256: `f56793e5c6d3f9370cd1be66751a12b788e9832fa346f755d9eb74e1fad3fa15`
   - Canonical 16-hex prefix in journal: `f56793e5c6d3f937` (EXACT MATCH)
2. `.saipen/recovery/log-detail/E-3286-f56793e5c6d3f9370cd1be66.json`:
   - Size: 839 bytes
   - SHA-256: `e58b4717fde5d63ba7f3a129fc181e05a0a8cef7de3880df9472804488b29468`
   - Canonical 16-hex prefix in journal: `e58b4717fde5d63b` (EXACT MATCH)
   - Metadata confirms:
     - `event_id`: "E-3286"
     - `ticket_id`: "T-415"
     - `operation_id`: "checkpoint-d898f0b0e66644ea92a33f4c18909e6d"
     - `original_event_sha256`: "f56793e5c6d3f9370cd1be66751a12b788e9832fa346f755d9eb74e1fad3fa15"
     - `original_event_bytes`: 1239

### 5. Canonical Validator Outcome
- Execution of canonical validator `tools/validate.py` in Wintage root:
  - Exit code 0, "Validation complete. Agent is conformant." (57 warnings, 0 errors).
  - The canonical validator distinguishes missing evidence from exporter omissions: the validator checks structural protocol rules and ledger format, while the AUDAPACK export gate explicitly enforces on-disk existence of cited evidence sidecars. No synthetic PASS was fabricated.

### 6. Wintage T-916 in BUILD Evaluation
- As noted in SRC-229, the export showed Wintage T-916 in BUILD with last_event E-3494.
- Examination of current Wintage state reveals Wintage has since advanced through and completed T-916 (current phase: DONE, last_event: 4117).
- The BUILD state was an in-progress operational state at the moment the snapshot was taken, not an engine deadlock or failure. No rewrite of T-916 or intervention was required.

### 7. Corrective Tickets
- No corrective code tickets needed.
- Restoring the genuine byte-identical files into Wintage `.saipen/recovery/log-detail/` resolves the absent record.
- Durable store tracking policies in `.gitignore` are already enforced by SAIPEN T-1668.
