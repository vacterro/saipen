SAIPEN

MISSION: AUDAPACK isolated recovery epoch and verified continuation.

OPERATOR AUTHORIZATION:
Authorize creation of the separate AUDAPACK recovery workspace at:

V:\___VAC\__K\__CODE\_PY\_AUDAPACK_RECOVERY_20261010

Authorize a new SAIPEN lineage through the existing canonical INIT route only after all specified preconditions pass.

This authorization does NOT permit:
- Modification or deletion of the original AUDAPACK.
- Historical event reconstruction or invented receipts.
- Reclassifying unsupported DONE claims as verified.
- Automatic consumer cutover.
- Publication, push, reset, clean, or destructive Git operations.
- Bypassing native validation or lifecycle authority.
- Unrelated external workspace or account changes.

OWNER: SAIPEN agent.

CURRENT ESTABLISHED BASELINE:

SAIPEN:
- T-1708 DONE.
- Full family: 6121 passed, zero failures.
- Native core: 0 problems, 9 warnings.
- Canonical state: T-1705, BUILD.
- T-1703 blocked REVIEW reservation preserved.
- T-1709 / SRC-209 remains open.
- T-1710 / SRC-210 is AMENDMENT_ONLY, not DONE.
- Audit starvation remains unresolved.

AUDAPACK:
- Original project remains NO_GO.
- Original lineage:
  lineage-79944d6c0334416ebe1001e97de6c1cc
- Original Git HEAD:
  6c6d841df24e5c5d91870def931af99f0af4c81f
- Last operation-backed lifecycle floor: E-3131.
- Missing journal parents: E-3133, E-3136, E-3145.
- Nine unsupported terminal claims.
- Duplicate T-299 identities.
- Native validation: 20 problems, 79 warnings.
- Recovery preview: FORENSICALLY_UNRECOVERABLE.
- No canonical in-place repair command.
- Previous preservation evidence: 8098 originals,
  8098 sealed copies, zero reported mismatches.

Do not treat these historical observations as current
until independently rechecked.

EXECUTION QUEUE

PHASE 0: LIVE PREFLIGHT

1. Establish the running SAIPEN installation identity,
   actual project roots, HEAD, dirty tree, live owner,
   pending transactions and lifecycle state.

2. Independently verify the current AUDAPACK original:
   - Original lineage and HEAD.
   - Git refs and reachable object history.
   - Working-tree and index state.
   - Tracked and relevant untracked source bytes.
   - Entire existing .saipen namespace.
   - Protected core hashes.
   - Preservation manifest and original file digests.
   - No conflicting writer or pending operation.

3. Refuse execution if the original differs from the
   approved baseline or the recovery destination exists,
   including reparse points, junctions and symlinks.

4. Ensure the destination cannot resolve to the original
   repository or share mutable Git storage with it.

5. Record exact pre-operation fingerprints.

STOP on any unexplained discrepancy.

PHASE 1: RECOVERY GUARDRAILS

Inspect the existing canonical INIT implementation:

tools/saipen_engine/init_project.py
tools/saipen.py

Do not create a replacement INIT implementation.

Before operating on AUDAPACK, exercise isolated fixtures:

A. Fresh valid initialization succeeds.
B. Existing .saipen namespace refuses initialization.
C. Foreign or stale project binding refuses admission.
D. Corrupt historical ledger cannot gain authority.
E. Unsupported DONE claim remains unverified.
F. Failed or partial initialization cannot be mistaken
   for a successfully recovered consumer.
G. Unauthorized mutation is refused without changing
   protected bytes.

Inspect _init_command for optional mailbox provisioning.
Do not silently provision unrelated external workspaces.
If unavoidable external side effects exceed this approval,
STOP and request a separate operator decision.

Preserve unchanged test assertions and negative controls.

PHASE 2: ISOLATED COPY

Create a genuine, independent recovery copy.

Preserve:
- Original source bytes.
- Git history, refs and current dirty content.
- Relevant untracked source.
- Original complete .saipen history.
- Forensic preservation manifests and supporting evidence.

The original lifecycle namespace must remain available
as legacy forensic evidence but must not occupy the new
active .saipen authority namespace.

Never present historical BOARD, STATE or LOG claims as
newly admitted lifecycle events.

Never rewrite the original repository or its history.

Copy verification must compare captured digests with
actual destination bytes, not just file counts.

Check linked Git storage, junctions, hardlinks, symlinks,
external worktree references and other aliasing risks.

STOP if preservation cannot be proven.

PHASE 3: CANONICAL INIT

Run the real, currently installed SAIPEN canonical INIT
against the approved recovery root only.

Use the existing global --project-root and --agent options.

Do not hand-write STATE, BOARD, LOG or IDENTITY.

Capture:
- INIT command and exit code.
- Actual generated lineage.
- Original lineage.
- Canonical initialized files.
- Runtime and installation identity.
- Destination fingerprints.
- Any additional initialization side effects.

Require the new lineage to differ from the original.

On failure, preserve the partial workspace as evidence.
Do not retry through manual protocol editing.

PHASE 4: INDEPENDENT ACCEPTANCE

Independently validate the recovery workspace:

1. Native core validation.
2. Complete lifecycle-ledger validation.
3. New-lineage identity and binding.
4. Pending/conflicting operation scan.
5. Source and Git integrity.
6. Protected namespace ownership.
7. Normal canonical operation admission.
8. Unauthorized operation refusal.
9. Preservation of original project and Git refs.

Test one genuinely authorized, small canonical recovery
verification operation. Do not fabricate historical tasks
to manufacture a positive result.

The following do not constitute acceptance:
- INIT_COMPLETED alone.
- A passing unit-test suite alone.
- A readable BOARD alone.
- A successful Git status.
- A human-written DONE statement.

Report the independent final authority verdict.

If acceptance fails:
- Keep the original NO_GO.
- Do not enable normal recovery-root agents.
- Preserve evidence.
- Report the precise failed gate.

If acceptance passes:
- Mark only the new root and new lineage as eligible.
- Keep the original root NO_GO.
- No automatic cutover or publication.
- Do not import old DONE status as current Work.

PHASE 5: CONTROLLED CONTINUATION

After recovery acceptance, return to the existing
SAIPEN SRC-209 / T-1709 audit-fairness mission.

First re-evaluate its real dependency and admission gates,
including T-1705, T-1703 and T-1707.

Do not override current ownership or priority rules.

Once admitted:
- Establish durable named audit first-seen order.
- Prevent perpetual starvation behind P2 BOARD work.
- Preserve numeric audit ordering.
- Preserve blocked audit identities.
- Admit only eligible audits.
- Produce real receipt and Work evidence.
- Consume audit files only after proven closure.
- Resume the oldest genuinely eligible audit.

T-1710 remains parked as AMENDMENT_ONLY.
Do not duplicate SRC-209's implementation.
Do not silently close SRC-210.

FINAL REPORT

Return:
1. Original root and lineage status.
2. Recovery root and actual new lineage.
3. Original/copy integrity comparison.
4. Canonical INIT outcome.
5. Independent native and lifecycle verdicts.
6. Negative-control results.
7. Any original or recovery-root mutations.
8. Explicit GO/NO_GO for each root.
9. SRC-209 dependency and fairness state.
10. Exact next admitted action or STOP reason.

ACCEPTANCE:
A verified isolated recovery without modifying the
original, without inventing historical authority and
without bypassing canonical protocol enforcement.

Never declare cc all completed while recovery or audit
fairness remains unresolved.
