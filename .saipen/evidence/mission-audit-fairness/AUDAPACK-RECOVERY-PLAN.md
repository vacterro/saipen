# AUDAPACK: one recovery authorization decision

Status: **PLAN ONLY. Original AUDAPACK remains NO_GO.** Current read-only
recheck completed after T-1708's canonical local closure; results are below.
No recovery, new lineage, overwrite, reset, claim, or fabricated closure has run.

## Decision requested

Authorize a separate, source-preserving recovery copy at
`V:/___VAC/__K/__CODE/_PY/_AUDAPACK_RECOVERY_20261010`, with a fresh lineage
created by SAIPEN's existing canonical INIT operation. Preserve the original
`V:/___VAC/__K/__CODE/_PY/_AUDAPACK` in place, including its Git history,
current dirty bytes, complete `.saipen` namespace and forensic evidence.
The proposed destination was checked absent on 2026-10-10; check again at
execution and refuse if it already exists or resolves through a reparse point.

This is one decision about a new recovery epoch. It authorizes no publication,
old-root cutover, historical DONE attestation, event invention, or deletion.
Current chat steering does not already grant it: the priority amendment's
required outcome 6 explicitly says prepare the plan and STOP for authorization
when recovery requires a new lineage.

## Why the existing lineage has no admitted in-place repair

The original identity is `lineage-79944d6c0334416ebe1001e97de6c1cc` and HEAD is
`6c6d841df24e5c5d91870def931af99f0af4c81f`. Numbered history ends at E-3146;
the last operation-backed lifecycle floor is E-3131, committed operation
`finish-29deadc9792e498ca581916d8a22c785`. Twelve later parsed events have no
operation backing. Parents E-3133, E-3136 and E-3145 are absent from the
current complete active/sealed ledger. Nine terminal claims remain unsupported:
T-278 and T-292 through T-299. Both original T-299 rows must remain readable.

The current BOARD also has duplicate T-299, missing DOING/TODO headings and
unrecognized evidence fields; STATE claims DONE with task T-299 and an
untrusted last_event 3146. An unnumbered completion summary is not an event.
These bytes are already committed in Git, so simply dropping a working-tree
edit cannot restore integrity.

The actual recovery owner returned `HISTORY_LEDGER_CORRUPT`,
`FORENSICALLY_UNRECOVERABLE`, `READ_ONLY_DIAGNOSIS_ONLY`,
`safe_auto_repair_available: false`, `operator_decision_available: false`,
and `canonical_next_command: null`. It expressly forbids mutator probing.
The supported `recover quarantine-log-tail` route is advertised only when
its shared proof can cut a genuinely foreign suffix without reconstructing
truth; that proof did not establish an exit here. Neither a model-selected
floor nor reapplying an already committed old receipt is a supported repair.

The read-only milestone owner reports no current milestone, no parent and
`undo_available: false`; the milestone directory is absent. The INIT owner
refuses any root that already contains `.saipen/`. No existing command was
found that converts this corrupt active namespace into a new epoch in place.
Unavailable external backups remain unknown, not disproved.

## Authorized execution plan

1. Recheck original HEAD, refs, dirty state, lineage, pending/conflicting
   operations, all original protected bytes and source fingerprints. Bind the
   approval to these observations. Changed inputs or conflicting ownership
   stop execution; they do not get silently substituted.
2. Preserve a complete byte inventory and separate recovery copy of the
   original Git directory/history, tracked source files, untracked relevant
   source files, dirty bytes, entire `.saipen` namespace and existing forensic
   case. Verify every preserved file against its captured digest. Original
   paths stay intact. No checkout, reset, clean, move or deletion of the
   original repository is required.
3. Construct the separate recovery workspace from the preserved current
   source bytes and Git history. Keep the complete old lifecycle namespace
   as an identified legacy evidence bundle, outside the new active `.saipen`
   authority paths. Do not copy its unsupported closures into the new BOARD
   or append its missing events. Git history retains its original bad-core
   blobs; a new working namespace is not a rewrite of those commits.
4. Exercise canonical INIT and integrity checks on sacrificial fixtures
   before provisioning the recovery workspace. Negative controls must refuse
   an existing namespace, foreign/stale binding, corrupt journal, invalid
   source authority, and an unsupported closure; known-good fresh INIT must
   pass. Preserve test configuration and assertions. These controls are still
   execution prerequisites, not an assertion that AUDAPACK is recovered.
5. Only at the approved absent namespace, use the existing canonical command:

   ```powershell
   & 'V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN\bin\saipen.cmd' --project-root 'V:\___VAC\__K\__CODE\_PY\_AUDAPACK_RECOVERY_20261010' --agent saipen-cli init --json
   ```

   Record the actually allocated new lineage and INIT result. Never write the
   new canonical lifecycle files by hand. Publication remains excluded by
   the operator scope and the session's `no-publish` capability.
6. Bring source references forward as evidence under their original qualified
   lineage/receipt identities, never as invented current grants or DONE Work.
   The old npm-cache T-299 identity decision remains preserved; Widget receives
   no invented T-300. Allocate any genuinely new re-verification Work only
   through canonical intake after its exact scope and authority are established.
7. Independently run current native validation, lifecycle-authority assessment,
   complete-ledger validation, pending-operation scan, source-integrity checks
   and ownership/binding controls on the recovery workspace. Demonstrate a
   real admitted normal operation and a refused unauthorized operation with
   byte-preservation evidence. Compare all original bytes and Git refs again.
   Tests passing alone do not establish recovery.
8. Report exactly which root and lineage permit normal agent operations.
   The original root remains NO_GO unless a later separately approved cutover
   or in-place recovery mechanism is actually implemented and verified.
   Resume the original SRC-209 audit-fairness mission after this acceptance.

If canonical INIT or subsequent native integrity fails, stop with the actual
refusal and preserve the partial recovery copy. Do not relax validation,
manufacture a successful transition, or retry identical failures indefinitely.

## Preserved evidence and limits

The original forensic owner is T-1696, whose completed investigation did not
restore AUDAPACK. Evidence lives at `../AUDAPACK-T299-forensics/REPORT.md`;
its sealed acquisition records 8098 files and later source/copy comparisons.
The current bounded A04 matrix is `../cc-all-20261010/A04-MATRIX.md` and
`A04-current.json`, with raw status/recover/next/native output and unchanged
original core fingerprints:

| Original core | SHA-256 |
| --- | --- |
| STATE.md | a766ca86d185ea24d4b1818f4295ef839826bcc913347047abcecf8dfcf5cc50 |
| BOARD.md | 8bb2a5e68d474ee2ab22b834e6a94440d5389ea352d2969f5ad945cd04ca9952 |
| LOG.md | e414d4b54a3e99d9fa515945bf9d8be208581292889b3744edcb11466b0f7c7a |
| MANIFEST.json | 6bbb6ca8bed1502f04176d848f24ad12fdd58759e1946f0b2b27a5f023e0e050 |

The A04 native result was CURRENT_FAIL, 20 problems / 79 warnings; 32 focused
recovery-authority tests passed separately. That software result did not
repair the consumer. No external backup search, complete source-copy delivery,
new-lineage creation, or final recovery acceptance is claimed by this plan.

## Final current evidence, 2026-10-10

`AUDAPACK-20261010T1522Z.json` and its four raw command outputs bind the final
actual reads. HEAD, refs, reachable-history digest, index projection, dirty
state, tracked source bytes and the named protected namespaces all match
before/after. The only existing dirty entry remains the known Improve report.
All **8098 original files and 8098 sealed copies**, 16196 comparisons, match
their acquisition digests with zero differences. No external-backup claim is
made. Pending and conflicting operations remain empty; no milestone or undo
target exists.

Actual status refuses UNAUTHORIZED_LIFECYCLE_WRITE; recovery preview refuses
HISTORY_LEDGER_CORRUPT with FORENSICALLY_UNRECOVERABLE and no executable next
command; next refuses VALIDATION_FAILED. Actual native core remains
**CURRENT_FAIL: 20 problems / 79 warnings**. Authority remains UNAUTHORIZED,
floor E-3131, and normal agent operations at the original root are not permitted.
No missing event or successful lifecycle transition was invented.

The prerequisite owned SAIPEN transaction T-1708 is DONE through the canonical
COMMITTED no-publish release at 15:20Z. Its fresh complete family passed
6121/0/0 on unchanged source; its independent REVIEW repeated immutable
red/green controls, and SAIPEN's final native core passed 0 problems / 9
warnings at 15:22Z, receipt `receipt-31bff53923e5`. Native host verification
used the actual installed 1.18.35 x64 payload in the test-process PATH;
the unrelated default launcher postinstall stub and active ZAICODE host were
not rewritten. These results do not certify AUDAPACK recovery.

Current SAIPEN state is restored T-1705 at BUILD, unclaimed, with T-1703's
blocked REVIEW reservation preserved. No new active transaction was claimed
after the priority amendment. Original audit-fairness Work T-1709 / SRC-209
is deferred behind the explicit recovery decision. The amendment's automatic
projection created T-1710; it is parked AMENDMENT_ONLY, retains SRC-210 and
its event, and is neither executed nor falsely DONE. The amendment also links
to the existing recovery roadmap owner T-1702. No duplicate recovery Work is
being performed from that projection.

The next recovery action requires the one approval stated above. Until it
arrives, retain this plan and the original consumer in NO_GO. There is no
admitted mutating command for the corrupt original lineage to run now.
