# FUTURE GATE — SAIPEN AUDIT CONTRACT OMITS `.saipen/evidence/**`

Status: IMPLEMENTED by T-1373 (SRC-054, user-authorized 2026-09-16) -- see
RESOLUTION at the end. The record below is kept as written.

Recorded: 2026-09-16 by an opencode session bound to `_PROBLIP`
(lineage `lineage-1cdb16999979467cae251752806324f5`), during the PERF-001
closure-envelope repair (Problip T-21 / SRC-004, DEFECT C).

This document is a record of an external, mechanically reproduced defect. It is
not a claim that anything here has been fixed, and it must not be cited as
evidence for any coverage disposition. Do not implement it while an active
ticket holds this repository's DOING seat.

## DEFECT

`.saipen/evidence/**` is a first-class SAIPEN durable-evidence surface, but the
protocol's own audit-evidence contract never declares it. `saipen audit manifest
--write` therefore produces a `.saipen/MANIFEST.json` whose `evidence` block
omits `evidence`, so every faithful consumer -- AUDAPACK's
`audapack/saipen_evidence.py` included -- collects exactly the declared set and
silently drops the evidence directory.

Consequence observed live: a project can hold a persisted, authoritative closure
evidence file (`.saipen/evidence/PERF-001_WINDOWS_EVIDENCE.md`, referenced by LOG
E-048) that a downstream audit archive does not contain, while the archive still
reports `required_evidence_omitted: false` and a COMPLETE verdict -- because the
missing file was never DISCOVERED, so it can never be counted as an omission.

## MECHANICAL PROOF (read-only, reproduced 2026-09-16)

Against the live SAIPEN 8.0.1 tree and a real project:

```
from audapack import saipen_evidence as se
contract = se.read_contract(problip_root)
[(d.tier, d.path) for d in contract.dirs]
# -> [('conditional','logs'),('conditional','intake'),
#     ('conditional','archive/source'),('conditional','KNOWLEDGE'),
#     ('conditional','audit'),
#     ('optional','extensions'),('optional','kitchen'),('optional','saitranslate')]
# 'evidence' is ABSENT.

col = se.collect(problip_root, contract)
len(col.paths)                      # 115
'.saipen/evidence/PERF-001_WINDOWS_EVIDENCE.md' in col.paths   # False
(problip_root/'.saipen/evidence/PERF-001_WINDOWS_EVIDENCE.md').is_file()  # True

se.evaluate(col, included=set(col.paths))["required_evidence_omitted"]  # False
```

Adding `evidence` as a conditional `DirRule` and re-collecting picks the file up
immediately (`+1`, file present), proving the omission is the CONTRACT, not the
consumer and not the file.

## ROOT CAUSE

`tools/saipen_engine/audit_manifest.py`:

```
CONDITIONAL_DIRS = (
    (LOGS_DIR, True, 4000),
    ("intake", True, 8000),
    ("archive/source", True, 8000),
    ("KNOWLEDGE", True, 4000),
    ("audit", False, 500),
)
```

`evidence` is not present, so `build()` never emits a rule for it, so
`saipen_engine.evidence.EVIDENCE_ROOT` (`.saipen/evidence`) -- the store CORE.md
§ EVIDENCE-RETENTION-01 designates for durable, hashable proof artifacts
referenced by oversized LOG events' `detail_ref` -- is invisible to every audit
consumer that trusts the contract.

## BOUNDED FOLLOW-UP OPTION (choose ONE, later, per its own red control)

Make the protocol's audit-evidence contract declare the surface it already
owns:

* add `("evidence", True, <cap>)` to `CONDITIONAL_DIRS` in
  `tools/saipen_engine/audit_manifest.py`, matching the sibling conditional
  entries;

and, independently, harden omission accounting so a required artifact that
never entered discovery is still reportable rather than silently absent.

Required hostile controls:

* a red control proves the pre-fix contract collects zero files from
  `.saipen/evidence/` while the directory is non-empty;
* a project with a NON-empty `.saipen/evidence/` whose archive omits the files
  must report non-authoritative / `required_evidence_omitted`, not COMPLETE;
* a project with an absent or empty `.saipen/evidence/` is unaffected;
* the `GLOBAL_FILE_CEILING` containment bound still holds, and a symlinked
  `evidence/` is still never descended.

NON-GOALS: do not widen `.gitignore`; do not introduce an unrestricted ignored-
tree walk; do not let either the producer or the consumer synthesize or edit a
project's `.saipen/MANIFEST.json` outside the canonical
`saipen audit manifest --write` path; do not weaken fail-closed semantics.

## CONSUMER-SIDE NOTE (AUDAPACK, informational)

`_AUDAPACK/audapack/saipen_evidence.py` is contract-driven and behaves
correctly: it collects exactly what the manifest declares. It needs NO change
once the contract names `evidence`. The only AUDAPACK-side improvement the
originating mission suggested is an omission-accounting path for a
declared/referenced artifact that never reached the final archive -- which is
the second half of the bounded option above and is worth doing only once the
contract can actually declare the file.

## ORIGINATING MISSION

`_PROBLIP` T-21 / SRC-004, closure-envelope repair, DEFECT C -- "AUDAPACK does
not recognize the new evidence directory", with the explicit escape hatch: if
fixing the consumer is outside the originating repository/session, record the
defect explicitly and use the established cross-project handoff path rather than
editing unrelated code. This file is that record.

## RESOLUTION (T-1373 / SRC-054, 2026-09-16)

The user authorized the work as SRC-054 and it went further than the bounded
option above, because the regression it had to survive was regeneration, not
initial packing: the Problip repair declared `evidence` locally and the next
lifecycle run rewrote the manifest from `build()` and erased it.

* Contract: `tools/saipen_engine/audit_manifest.py` declares
  `("evidence", True, 4000)` in `CONDITIONAL_DIRS` and a new `references`
  block naming the closure records that cite evidence by path (STATE, BOARD,
  LOG, sealed `logs/*.md`, `intake/coverage/*.json`,
  `archive/source/*.coverage.json`) with byte/count bounds. `ensure()` reports
  `dropped_declarations` whenever a regeneration narrows declared evidence.
* Consumer: `_AUDAPACK/audapack/saipen_evidence.py` resolves citations as
  required evidence (tier `cited`), collects cited files a directory rule did
  not find, reports cited-but-omitted and cited-but-absent files in
  `omitted_required` with `cited_by`, degrades a truncated or unreadable
  citation discovery to PROTOCOL_INCOMPLETE, and applies the published rules
  to contracts that predate the `references` block (`consumer_default`).
* Proof: `.saipen/evidence/T-1373-evidence-surface-20260916/` (red/green pairs
  for both repositories, the Problip-equivalent end-to-end run 13/13, the live
  Problip pack).
* Not covered here: LOG/BOARD `detail_ref` targets under the non-exportable
  `recovery/` tree -- T-1374.
