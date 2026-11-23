# ZAICODE immutable-ledger forensic result — SRC-238 / T-1740

## Verdict

BLOCKED on the original incident mechanism, not on proven current ledger damage.
Current canonical live history is valid: **5050 parsed legal events**, tail 5051,
zero duplicate, parent, ordering or syntax failures. All six cited records exist
at the exact reported LOG-004 lines. LOG-004 SHA256 matches the supplied baseline.
The configured source and registered machine parsers agree, as do an independent
parser and the mutation loader on a byte-identical disposable copy.

**No ZAICODE file was repaired or rewritten, and no ZAICODE continuation was run.**
No recovery or safe-resume acceptance is claimed. The original failing invocation,
host/session binding and contemporaneous kernel are still unidentified. The user
places the incident around 10–11 local on 2026-10-13 (approximately 07–08 UTC).

## Authority and runtime

- Canonical root: `V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_ZAICODE`.
- Identity: `lineage-b0732ed2f98947b9a3c97bfe71427eca`; target HEAD `a308593121453b1d713533fcfd0ec565c10c438e`.
- STATE is DONE / task none / blocker none / last_event 5051. It is unchanged.
- There are zero DOING claims and zero unresolved/conflicting recovery journals.
  This does not prove which process held an OS writer lock during the incident;
  no lock file was treated as evidence of a live owner.
- Source home: `V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN`, HEAD `025bf596c683464788ab698248e8a3c5eb44dfec`
  with a pre-existing dirty tree. A Git HEAD alone is not the executing kernel.
- Configured user launcher: `C:/Users/vac34/bin/saipen.cmd`; it invokes the user
  Python 3.11.9 and the source home's tools/saipen.py.
- Direct source-home launcher uses the bundled Python and that same source entry.
- Machine launcher invokes registered runtime
  `C:/ProgramData/SAI/SAIPEN/runtime/5b10b65725983c48` with bundled Python 3.11.9.
  Registration generation is
  `gen-sha256:5b10b65725983c48a81c426ca62d0239237e57cd5bbe0d9550ada67e35fe5170`,
  installed `2026-10-12T15:27:57Z`, version 8.1.0.
- Measured log.py SHA256 is identical in source and machine runtime:
  `a6287bbfd40d19bb4958008dc7a0602f191796ba3fa64ffc94c676c9af2951e0`.
- `authority.json` preserves exact launcher text/hashes and current metadata
  hashes. These are configured routes, not proof of which route failed earlier.
- Historical admission/session restrictions remain unknown without the failing
  carrier. The handoff grants read-only forensic work and no target mutation,
  restoration, kernel correction or continuation. That boundary was honored.

## Complete live segment inventory

Every path below exists. Numeric sealed discovery finds LOG-001 through LOG-004
and the active LOG.md; no newer numeric segment was observed in this capture.
Encoding/BOM comes from the installed codec; all file hashes are exact raw bytes.

| Absolute canonical path | Bytes | SHA256 | Encoding / BOM hex | First..last event | Parsed | Rejected |
|---|---:|---|---|---|---:|---:|
| V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_ZAICODE\.saipen\logs\LOG-001.md | 214259 | 9d77443ef6269f798f4e3ddceac0bfd9e249a73f2e3ca0ce2df0b44713003b36 | utf-8 / none | 1..867 | 866 | 0 |
| V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_ZAICODE\.saipen\logs\LOG-002.md | 70365 | de23495e9525a2979258363cd2de0513fd038fa9bf8d36b0127604f2ab21569e | utf-8 / none | 868..1156 | 289 | 0 |
| V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_ZAICODE\.saipen\logs\LOG-003.md | 418556 | d1f1dde8a9f6331de4bfe1c470b0104a131dc01124ece5f7e0f3c4f36b803839 | utf-8 / none | 1157..2466 | 1310 | 0 |
| V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_ZAICODE\.saipen\logs\LOG-004.md | 706539 | b5371837efc745ed8101d9c99d4fbcb112eb93abf017f66fc7b155c7bc9843ca | utf-8 / none | 2467..4674 | 2208 | 0 |
| V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_ZAICODE\.saipen\LOG.md | 118277 | f7b97f367fedac88e5ddf8a8d2edf74eab80b238deba61a58696341394e57de7 | utf-8 / none | 4675..5051 | 377 | 0 |

Supplied historical LOG-004 SHA256:
`b5371837efc745ed8101d9c99d4fbcb112eb93abf017f66fc7b155c7bc9843ca`.
Live comparison: MATCH. Historical hashes for the other segments and active
LOG were not supplied, so no claim of complete historical snapshot byte equality
is made. Current live-to-disposable-copy equality is separately proven for all
469 captured files by `capture-manifest.json`.

| Event | Exact live location | UTF-8 line bytes |
|---|---|---:|
| E-3133 | V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_ZAICODE\.saipen\logs\LOG-004.md:667 | 988 |
| E-3134 | V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_ZAICODE\.saipen\logs\LOG-004.md:668 | 204 |
| E-3136 | V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_ZAICODE\.saipen\logs\LOG-004.md:670 | 782 |
| E-3137 | V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_ZAICODE\.saipen\logs\LOG-004.md:671 | 586 |
| E-3145 | V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_ZAICODE\.saipen\logs\LOG-004.md:679 | 676 |
| E-3146 | V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_ZAICODE\.saipen\logs\LOG-004.md:680 | 259 |

## Reproduction and classification

All requested log.py symbols were inspected directly: history_paths,
read_history_snapshot, read_history_routing_summary, parse_log_line,
snapshot_contract_errors and history_contract_errors. The actual mutation
reader, read_history_snapshot_and_logs_digest, was inspected and measured too.

Source full snapshot and routing summary hash: `cc6e3a968dcdda3c`.
Disposable source mutation-loader hash: `cc6e3a968dcdda3c`;
5050 events, zero contract errors. Machine copy agrees under its own bundled
interpreter. The sealed dependency is
`delete-tree-sha256:b01c21f438a0885d7b2df68eb6561f2a03ac77151e8f45c85479eaa2867d7f36`.
That exact digest also exists in the committed original T-319 finish operation
`finish-4e77c05c4d31478ebbb7e73e6df1d1ed` as its sealed-history read precondition.

Independent physical-line parsing checks the same bytes for syntax, uniqueness,
ordering and parent existence. It also returns 5050 events and zero errors.
Before/after source hashes and segment membership remain stable. This rules out
the alleged physical absence, malformed records and segment-discovery failure
**for the measured current bytes**. It does not prove what an earlier process
read, which root it bound, or whether its export/read was consistent.

Recovery classification: **CASE A for current live ledger health**. Restoration
is not indicated by this evidence. Original incident classification A–F remains
NOT_REPRODUCED / UNKNOWN. Calling it a false validator regression, wrong root,
historical record loss or race would exceed the evidence.

Bounded carrier search found no original matching refusal in today's local Codex
session (which belongs to this SAIPEN inspection), the two ZAICODE Claude project
stores, current OpenCode tool-record database, or the inspected ZAICODE/FreeBuff
log stores. This is not an exhaustive search across other accounts or host homes.
Only the supplied refusal text and approximate time bind the original incident.

## Negative controls and verification

`negative-controls.json` records nine rejected disposable-copy conditions:
missing parent, duplicate ID, reorder, forged parent, modified sealed record,
foreign ledger substitution, wrong lineage, stale captured history and incomplete
restoration. A valid original copy is the positive control.

The first four are rejected by the published structural ledger predicate.
Legal text changes can remain syntactically valid: modified-sealed and stale
controls are rejected by the existing committed sealed-dependency digest,
and wrong lineage by the existing journal identity predicate. These checks
do not pretend that parsing alone authenticates history. They are predicate
controls, not proof of an approved restoration transaction.

Existing runtime effect-path/control suites were executed without source edits:

| Command (from SAIPEN home) | Result |
|---|---|
| python -B -m unittest discover -s tools -p test_reconcile_history_ledger_blocked.py -v | 13 PASS |
| python -B -m unittest discover -s tools -p test_t1514_portable_history_evidence.py -v | 6 PASS |
| python -B -m unittest discover -s tools -p test_recovery_noop_targets.py -v | 10 PASS |
| python -B -m unittest discover -s tools -p test_project_root_session_binding.py -v | 20 PASS |
| python -B -m unittest discover -s tools -p test_t1640_log_seal.py -v | 27 PASS |

Total: **76 tests PASS**. These include real stale-plan refusal, cross-lineage
refusal, zero-write corruption refusal and interrupted-materialization checks.
They do not authorize recovery, prove the missing original invocation or replace
ZAICODE's full admission/conformance checks. No new runtime implementation or
full-family/release PASS is claimed for this forensic Work.

## Acceptance audit and permitted next action

1. Actual missing-parent mechanism: **UNPROVEN**; original carrier missing.
2. Baseline/live hashes: **VERIFIED within supplied baseline scope**, all current
   segments inventoried; only LOG-004 has a supplied historical digest.
3. Installed launcher revision: **current configured routes VERIFIED**; the
   incident's actual launcher/kernel remains **UNPROVEN**.
4. Canonical identity: **VERIFIED** from the live identity and root.
5. Fabricated historical evidence: **none**. Faults exist only in labeled copies.
6. Operator data modification: **none by this inspection**. Original metadata
   and ledgers were read only; local forensic/SAIPEN tracking artifacts were written.
7. Authorized recovery: **NOT GRANTED / NOT RUN**.
8. Full ledger validation after recovery: **NOT ACHIEVED**; pre-recovery ledger
   validation is green, and no restoration occurred.
9. Event identities: **current complete ledger consistent**, no IDs altered.
10. Continuation after approval: **NOT RUN**; no approval exists.

Permitted next action: the ZAICODE host/launcher owner must supply or locate the
original invocation, working directory/root carrier, stderr and kernel identity
for the 10–11 window. Compare that read with this frozen evidence before deciding
whether a separately admitted SAIPEN runtime correction is needed. No history
overwrite, fabricated parent repair, unapproved recover/continue, application
change, Queue/UI work, session cleanup, reset or validator weakening is justified.

Residual risk is unresolved historical binding/read behavior and unexamined host
admission/policy, not demonstrated damage in the current ledger. **ZAICODE work
is not certified or authorized to resume by this report.** SRC-238 remains ACTIVE;
T-1740 must not be marked DONE from the green parser result.

Graph coverage is stale/excluded for material engine paths; evidence relies on
direct current source reads and measured bytes. The JSON carriers retain exact
paths, hashes, parser results, copied scope and limitations for independent review.
