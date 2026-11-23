# Phase: SHIP

Publish Work. PUBLISH: action, not phase. Entry ONLY: saipen ship,
opted-in repo (origin + prior ship evidence), or goal + origin. Required
verification/REVIEW green.

Fixable before publication: SHIP -> BUILD -> VERIFY -> REVIEW -> SHIP.
BLOCKED needs human input/no safe fix. After commit/tag/push starts use recovery;
pushed Work never returns to BUILD.

## mode: no-publish

CORE §1.3: no commit/tag/push. It does NOT mean git is absent; check Git.
Run Board/README/version/junk/local metadata/core; omit tag equality; skip
remote classification/staging/ship gate.

LOG (DATE/E-ID/parent Event Graph), exactly:
RUN: ship vX.Y.Z -> skipped publish (no-publish: <reason>)
Reason: policy for working Git; no git ONLY if Git cannot answer.
Not failure; digest then DONE.

## Closure BEFORE Git scope

Opt-in tools/verification_policy.json admits current focused proof to SHIP,
not publication. Pending cohorts collect related edits. Full core-unit runs
once AFTER final batch content/metadata edits, before binding gate. Release
executor AND binding ship validator (6b.6) require full PASS for exact bytes/
baseline; focused cannot substitute. No repeat for members/unchanged REVIEW.

Closure differs from Git publication: only own_patch needs a personal diff.
Never block verification-only/cohort solely on inseparability

- own_patch: attributable delta; full procedure below.
  Foreign deltas: --paths refuses outside cohort; saipen scope refuses outside
  this root. At closure, verify: names carrying commit; state foreign publication.
- inherited_verified: NO delta; independently verify durable publication
  authority elsewhere. BUILD no-delta/VERIFY PASS/REVIEW PASS; then:
  saipen ticket done <T-###> --closure-mode inherited_verified --implementation-source <T-###|SRC-###|release:<id>>
  No invented diff/unrelated staging/empty release.
- cohort: shared verified batch, no fictional per-ticket blobs:
  saipen ticket done <T-###> --closure-mode cohort --closure-cohort C-### --paths <shared paths>
  Bind live registry bytes. saipen cohort ship C-### freezes paths once,
  uses exact release integrity, publishes, records shipped/release identity.
  Pending: evidence-complete, NOT published.

## Steps

0. Ticket every shipped unit (CORE §1.2 freshness/attribution).
   The shipped ticket was still in `## DOING` when this phase began; stays so.
   Terminal cohort/crew: DONE/task none, cohort registry authority.
1. Update release-facing README; choose semver bump.
2. Align canonical VERSION, root/discovered locale README badges (exactly once),
   newest CHANGELOG and vVERSION before push. Binding ship validator
   discovers kitchen mirrors; no duplicate list.
3. Apply .gitignore, secret, temporary-file/debug-output hygiene.
4. **Classify the remote BEFORE any external write.** Read origin;
   git ls-remote --heads --tags origin.
   Missing origin/remote commit+tag = first publish. Stop before ALL writes:
   next_action: WAIT: first-publish -- confirm repo name '<name>' and public/private before I push
   Goal never bypasses this gate.
5. After last metadata edit: tools/validate.py --gate core. Producer freshness
   gates consumption, not Core ship; Core signals, staged-set gate binds.
6a. **LOCAL. Touches no repository and no remote.** 0-5 only.
6b. **GIT.** Repository/remote writes, ordered:
   1. Read git status --porcelain=v1 -uall/staged set; git write-tree backs up
      pre-ship index.
   2. Attribute intended paths to Work/wave; any unattributed stops SHIP.
   3. Preserve user staging; exclude foreign paths. Stop unless isolated
      without changing their bytes.
   4. Stage ONLY the reviewed files this ship owns; explicit paths.
      **`git add .` and `git add -A` are
      forbidden here**.
   5. Re-read index; prove exact intended scope.
   6. Run `tools/validate.py --gate ship` NOW: nonempty index/discovered
      release paths; reject staged/working version divergence.
   7. git diff --cached --check.
   8. Commit exactly the staged scope; never -a/widening paths.
   9. **Push the branch.** Recheck first-publish immediately before branch AND tag:
      established continues; otherwise step 4.
   Gate/diff fail: no commit/tag/push. Restore owned index paths ONLY from
   backup tree, NEVER HEAD; foreign staging byte-identical. Return BUILD.
7. ONLY AFTER step 6b's branch push has LANDED (success or fetched remote
   branch = local), create vVERSION; push only:
   git push origin refs/tags/vVERSION:refs/tags/vVERSION
   Never --tags/--follow-tags. Branch push failure forbids tag push.
8. Event Graph LOG exactly: RUN: ship vX.Y.Z -> pushed HASH.

## Push recovery

Event Graph failure LOG: RUN: ship vX.Y.Z -> push FAILED <reason>.
No success claim; commit/tag stay local.

- Transient network/auth: one LOGged changed-condition retry.
  Second failure -> BLOCKED.
- Non-fast-forward: fetch/inspect incoming changes; read .saipen/release changes.
  Otherwise rebase, revalidate, recreate unpushed local tag on rebased HEAD, prove tag =
  HEAD, retry. prior completed-release tags are remote
  history requiring global force-push confirmation. Conflict: BLOCKED + files.
- Other non-transient/unsafe ambiguity -> BLOCKED; never force-push rejection.

Success/intentionally skipped publish: overwrite .saipen/kitchen/digest.md
with three short lines done:, remaining:, awaiting: (snapshot, not history).

Only SHIP's journaled ticket done atomically moves ## DOING -> ## DONE,
enters DONE. REVIEW never closes it.
Goal DONE: MAINTENANCE immediately.

Failure summary: fixable and pre-publish -> BUILD; classified push failure ->
recovery above; user decision or no known safe action -> BLOCKED with facts.
