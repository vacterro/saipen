# T-1829 external blocker re-measured 2026-10-22 (read-only)

Prior blocker text claimed: 'GitHub normal access refuses account-suspended HTTP 403 and GitLab returns not our ref.'

MEASURED NOW:
- git ls-remote --heads github-backup SUCCEEDS: 740 refs returned (main=55f278cde46fb8, plus accepted-debt-rebind, backup/cc-all-20261021T222419Z).
- The 403 account-suspension condition no longer holds. That part of the blocker is stale.
- git ls-remote origin main still returns 4f03d79f7ec8da4f3ad458128cc7da81e5ee5dce (GitLab, not our ref) -- unchanged.
- GitHub does NOT carry our HEAD 025bf596c683464788ab698248e8a3c5eb44dfec (grep count 0 in 740 refs).
- git fsck --connectivity-only --no-dangling: 112 missing objects, including missing commit 380b30f6374f31e37d10919d1a4ded36be9dc598. Unchanged from the recorded 112.
- The missing parent is absent from the real object database: cat-file --batch-all-objects lists 15612 objects and contains 380b30f6... zero times. So it is genuine corruption, not a stale commit-graph ref.
- git fetch --no-tags github-backup main FAILS both with and without core.commitGraph: 'did not send all necessary objects'. No additive recovery is available from that remote.

CONCLUSION: the blocker is narrower than recorded, not resolved. GitHub access is restored; the missing objects are still missing and no reachable remote can supply them. No history was rewritten and no object was manufactured.
