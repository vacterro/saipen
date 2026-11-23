# Phase: SHIP

Publish reviewed Work: metadata -> exact-scope commit -> branch push -> tag
push -> atomic finish. PUBLISH is action, not phase. Entry ONLY: saipen ship,
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
(T-1302/FastPrompter). Choose first:

- own_patch: attributable delta; full procedure below.
  Foreign deltas: --paths refuses outside cohort; saipen scope refuses outside
  this root. At closure, verify: names carrying commit; state foreign publication.
- inherited_verified: NO delta; independent proof, durable publication
  authority elsewhere. BUILD no-delta, VERIFY PASS, REVIEW PASS; then:
  saipen ticket done <T-###> --closure-mode inherited_verified --implementation-source <T-###|SRC-###|release:<id>>
  No invented diff/unrelated staging/empty release.
- cohort: shared verified batch, no fictional per-ticket blobs:
  saipen ticket done <T-###> --closure-mode cohort --closure-cohort C-### --paths <shared paths>
  Bind live registry bytes. saipen cohort ship C-### freezes paths once,
  uses exact release integrity, publishes, records shipped/release identity.
  Pending: evidence-complete, NOT published.

## Steps

0. Ticket every shipped unit; active Work stays ## DOING (CORE §1.2 freshness/
   attribution). Terminal cohort/crew: DONE/task none, cohort registry authority.
1. Update release-facing README; choose semver bump.
2. Before push align canonical VERSION, root/all discovered locale README badges
   (exactly once), newest CHANGELOG and vVERSION tag.
   Binding ship validator discovers kitchen mirrors; no second list.
3. Apply .gitignore, secret, temporary-file/debug-output hygiene.
4. Before ANY external write: read origin, git ls-remote --heads --tags origin.
   Missing origin/remote commit+tag = first publish. Stop before ALL writes:
   next_action: WAIT: first-publish -- confirm repo name '<name>' and public/private before I push
   Goal never bypasses this gate.
5. After last metadata edit: tools/validate.py --gate core. Producer freshness
   gates consumption, not Core ship. Core signals; staged-set gate binds.
6a. LOCAL: steps 0-5 only; no repository/remote touched.
6b. **GIT.** Repository/remote writes, ordered:
   1. Read git status --porcelain=v1 -uall/staged set; git write-tree backs up
      pre-ship index.
   2. Attribute intended paths to Work/wave; any unattributed stops SHIP.
   3. Preserve user staging; exclude foreign paths. Stop unless isolated
      without changing their bytes.
   4. Explicit reviewed owned paths ONLY; git add . / git add -A forbidden.
   5. Re-read index; prove exact intended scope.
   6. tools/validate.py --gate ship NOW: nonempty index/discovered release
      paths; reject staged/working version divergence.
   7. git diff --cached --check.
   8. Commit exact staged scope; never -a/widening paths.
   9. Push branch. Recheck first-publish immediately before branch AND tag:
      established continues; otherwise step 4.
   Gate/diff fail: no commit/tag/push. Restore owned index paths ONLY from
   backup tree, NEVER HEAD; foreign staging byte-identical. Return BUILD.
7. ONLY after branch push LANDED (success or fetched remote branch = local),
   create vVERSION; push only:
   git push origin refs/tags/vVERSION:refs/tags/vVERSION
   Never --tags/--follow-tags. Branch push failure forbids tag push.
8. Event Graph LOG exactly: RUN: ship vX.Y.Z -> pushed HASH.

## Push recovery

Event Graph failure LOG: RUN: ship vX.Y.Z -> push FAILED <reason>.
No success claim; commit/tag stay local.

- Transient network/auth: one LOGged changed-condition retry.
  Second failure -> BLOCKED.
- Non-fast-forward: fetch/inspect incoming changes; read .saipen/release changes.
  Otherwise rebase, revalidate, recreate local tag on rebased HEAD, prove tag =
  HEAD, retry. Step 7 kept tag unpushed; prior completed-release tags are remote
  history requiring global force-push confirmation. Conflict: BLOCKED + files.
- Other non-transient/unsafe ambiguity -> BLOCKED; never force-push rejection.

Success/intentionally skipped publish: overwrite .saipen/kitchen/digest.md
with three short lines done:, remaining:, awaiting:. Snapshot, not history.

Only SHIP's journaled ticket done atomically moves ## DOING -> ## DONE,
enters DONE. REVIEW never closes it.
Goal DONE: MAINTENANCE immediately.

Cap: 3 dead hypotheses OR 2 failed fix cycles -> canonical ticket block
(## BLOCKED, | blocker:). Each failed cycle increments | verify_attempts: N
(absent=0); preserve BOARD/LOG history. ticket unblock requires lifting decision,
clears blocker/resets current attempt budget; identical retries forbidden.

Workable TODO: leave this blocked, route to its SCOUT/BUILD.
None: session BLOCKED + concrete WAIT: (phases/blocked.md).

Before switching: preserve/remove ONLY this attempt's partial edits. Git:
save git diff to .saipen/kitchen/failed/T-###.patch; restore owned tracked paths
only; move proven attempt-created untracked files beside it. No blanket
git clean/unrelated dirt changes. Record mid-attempt commit in blocker.
No Git: copy edits there, report remaining partial changes.
Reversible recovery; authorization/checkpoints: CORE/OPS.
