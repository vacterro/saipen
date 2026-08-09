# OUTBOX

## W-028: wiki refresh v7.157.0-era -> v7.170.0, 195 scenarios, T-400 closed
- **status:** stale
- **superseded_by:** W-029 -- project HEAD moved 2c76b62 -> d74a26c (v7.173.0, rows 196-201 landed); collect skips this entry rather than ticketing a ghost
- **summary:** 6 wiki pages refreshed to v7.170.0 truth (main HEAD 2c76b62): Scenarios 182→195 rows mirroring CONFORMANCE IDs 1-195 (fixes T-400 semantic ID drift), Home badge/features v7.170.0, _Footer v7.170.0, Phases +13 phase-level checks + project-root binding v7.170.0, Getting-Started worktree-root fix, SubSaipen status. 0 drift items remaining.
- **main_project_refs:** [saipen/CONFORMANCE.md, saipen/phases/*.md, saipen/BOOT.md, tools/validate.py, tools/audit_floor.py, README.md]
- **critical:** false
- **producer:** saiwiki
- **source_head:** 2c76b621fdf2fa60ce5f2904e21884d1fa5298ac
- **coverage:**
  - Scenarios.md: 182→195 rows (13 new: 183-195), IDs mirror CONFORMANCE 1-195 exactly; headline + closing quote updated. T-400 (semantic drift of ID rows 117-168) closed: all rows regenerated from canon by ID, not by copy.
  - Home.md: badge **v7.173.0**, "Key features v7.170.0" header, feature bullets for v7.159-v7.170 (incl. pick-rule check v7.169.0, active-worktree-is-root v7.170.0), command table, scenario count.
  - _Footer.md: version v7.157.0-era → v7.170.0.
  - Phases.md: 13 new phase-level checks (v7.158-v7.170 range), project-root binding line updated for v7.170.0 active-worktree-first root order.
  - Getting-Started.md: project-root resolution paragraph updated to active-worktree-first; installs/hook/audit sections current.
  - SubSaipen.md: status table, role-adopt/sync sections current.
  - Tutorials.md, Use-Cases.md, _Sidebar.md: no drift (unchanged).
- **payload:** 6 modified pages in the wiki clone `kitchen/wiki/` (local, uncommitted):
  - `Home.md`, `Scenarios.md`, `Phases.md`, `Getting-Started.md`, `SubSaipen.md`, `_Footer.md`
  - To integrate: `git -C .saipen/extensions/subs/saiwiki/kitchen/wiki diff` review, commit, push to github.com/vacterro/saipen.wiki.
- **verified:**
  - Scenarios.md row count 195 == CONFORMANCE max ID 195; no duplicate IDs; row 195 (worktree root) present.
  - Home/_Footer/Phases/Getting-Started grep for v7.15x/v7.16x stale refs: none in page content (only .git logs).
  - Project HEAD re-checked at delivery: 2c76b62 (v7.170.0) — work was re-freshed after HEAD moved from v7.169.0 (fb3933e) to v7.170.0 (row 195 added).
  - tools/validate.py PASS (baseline) — see run record.
- **instructions:**
  1. Review the uncommitted diff: `git -C .saipen/extensions/subs/saiwiki/kitchen/wiki diff`.
  2. Commit with message style `saiwiki: refresh wiki to v7.170.0 -- 195 scenarios, 6 pages` and push to origin (github.com/vacterro/saipen.wiki).
  3. Verify live: Home badge shows v7.170.0, Scenarios shows 195 rows, _Footer v7.170.0.
  4. Close T-400 on the main board (semantic ID drift) — wiki half fixed here.
  5. No main-project files touched by this package.
- **details:**
  Project moved v7.157.0-era → v7.170.0 during the pass (3 fresh commits landed mid-work: 8b8d58c pick-rule check, f1ef487 worktree-root fix, 2c76b62 checkpoint). Wiki was re-synced at the end to the final HEAD: row 195 added, worktree-root notes inserted into Phases/Getting-Started, Home bullet added. T-400's wiki half (rows 117-168 semantic drift) closed by regenerating Scenarios.md rows from canon by ID. Remaining T-400 half (if any) is validator-side only; nothing wiki-side drifts now.

## W-029: wiki refresh v7.170.0 -> v7.173.0, 201 scenarios
- **status:** stale
- **superseded_by:** W-030 -- project HEAD moved d74a26c -> 12f5667 (v7.176.0, rows 202-216 landed); collect skips this entry rather than ticketing a ghost
- **summary:** 6 wiki pages refreshed to v7.173.0 truth (main HEAD d74a26c): Scenarios 195→201 rows (6 new: 196-201 mirroring CONFORMANCE IDs 196-201 -- phase-edge parity, LOG past-tense, DONE evidence, no-claim-outruns-ticket, CI-status hook, shortcut-never-a-greeting), Home badge/features v7.173.0 + 4 bullets (v7.171-v7.173), _Footer v7.173.0, Phases +4 phase-level checks + range header, Getting-Started audit_checks 79→91 + CI-status hook section, SubSaipen status row. 0 drift items remaining.
- **main_project_refs:** [saipen/CONFORMANCE.md, saipen/RFC.md, saipen/phases/*.md, saipen/BOOT.md, tools/validate.py, tools/audit_checks.py, VERSION]
- **critical:** false
- **producer:** saiwiki
- **source_head:** d74a26c414660663539954b83d59d9be8706b5d5
- **coverage:**
  - Scenarios.md: 195→201 rows (6 new: 196-201), IDs mirror CONFORMANCE 1-201 exactly; headline + closing quote updated to 201.
  - Home.md: badge v7.170.0 → **v7.173.0**, "Key features" header v7.173.0, +4 feature bullets (completion-claim evidence + LOG past-tense v7.171.0, CI-status hook ships with its tool v7.172.0, LOG clock read not estimated v7.173.0).
  - _Footer.md: version v7.170.0 → v7.173.0.
  - Phases.md: range header v7.104.0–v7.169.0 → v7.104.0–v7.173.0; +4 phase-level checks (v7.171.0 ×2, v7.172.0, v7.173.0).
  - Getting-Started.md: audit_checks 79→91 mutations; new CI-status line in the pre-commit hook section (v7.172.0).
  - SubSaipen.md: saiwiki status row -- W-028 T-400 wiki half closed, W-029 prepared (v7.173.0).
  - Tutorials.md, Use-Cases.md, _Sidebar.md: no drift (unchanged).
- **payload:** 6 modified pages in the wiki clone `kitchen/wiki/` (local, uncommitted):
  - `Home.md`, `Scenarios.md`, `Phases.md`, `Getting-Started.md`, `SubSaipen.md`, `_Footer.md`
  - To integrate: `git -C .saipen/extensions/subs/saiwiki/kitchen/wiki diff` review, commit, push to github.com/vacterro/saipen.wiki.
- **verified:**
  - Scenarios.md row count 201 == CONFORMANCE max ID 201; rows 196-201 present, no duplicate IDs.
  - Home/_Footer badges v7.173.0; no stale v7.170.0 badges left in page content.
  - Version refs per page: Home 7, Phases 6, Getting-Started 2, SubSaipen 1, _Footer 1 -- all v7.171-v7.173 content refs, no stale-era badge.
  - tools/validate.py PASS (exit 0, 5 known WARNs: sealed-log dates, saipython never-ran, uncollected W-028 now stale, digest stale).
- **instructions:**
  1. Review the uncommitted diff: `git -C .saipen/extensions/subs/saiwiki/kitchen/wiki diff`.
  2. Commit with message style `saiwiki: refresh wiki to v7.173.0 -- 201 scenarios, 6 pages` and push to origin (github.com/vacterro/saipen.wiki).
  3. Verify live: Home badge shows v7.173.0, Scenarios shows 201 rows, _Footer v7.173.0.
  4. T-400 wiki half already closed (W-028); nothing else on the main board to close for this package.
  5. No main-project files touched by this package.
- **details:**
  W-028 (v7.170.0, 195 rows) went stale: 4 fresh commits landed (d6317b3, ab9211a, 9ea2bd4, d74a26c) carrying v7.171.0 (T-431 completion-claim evidence + LOG past-tense), v7.172.0 (T-428 CI-status hook ships with its tool), v7.173.0 (T-432 LOG clock read, 5-minute forward bound). CONFORMANCE grew 195→201. T-433 (shortcut never-a-greeting, CONFORMANCE 201) sits in the working tree awaiting its v7.174.0 ship; its row is already mirrored so the wiki stays current through that release. Scenarios regenerated by ID from canon, same method W-028 used for T-400's rows 117-168.

## W-030: wiki refresh v7.173.0 -> v7.176.0, 216 scenarios
- **status:** stale
- **superseded_by:** W-031 -- project HEAD moved 12f5667 -> bf62b8f (v7.219.0, rows 217-254 landed); collect skips this entry rather than ticketing a ghost
- **summary:** 6 wiki pages refreshed to v7.176.0 truth (main HEAD 12f5667): Scenarios 201→216 rows (15 new: 202-216 mirroring CONFORMANCE IDs 202-216 -- conditional goal-budget reset, PHASE/ref pairing, no-superseded-schema, ZERO-PROMPT completeness, RUN: validate record shape, honest shortcut-Notes, CLEAN scrub graph, MARKHUNT legal wording, HUNT entry, first-publish gate ordering, tag-after-branch, ticket-stays-DOING, verify_attempts cap, REVIEW re-runs verify, borrowed-invariants), Home badge/features v7.176.0 + 6 bullets (v7.174-v7.176), _Footer v7.176.0, Phases range header to v7.176.0 + 12 phase-level checks, Getting-Started audit_checks 91→104, SubSaipen status row W-030. 0 stale era badges left.
- **main_project_refs:** [saipen/CONFORMANCE.md, saipen/RFC.md, saipen/phases/*.md, saipen/BOOT.md, tools/validate.py, tools/audit_checks.py, VERSION]
- **critical:** false
- **producer:** saiwiki
- **source_head:** 12f56679d655523ef10d48cb631b9f424cc201f0
- **coverage:**
  - Scenarios.md: 201→216 rows (15 new: 202-216), IDs mirror CONFORMANCE 1-216 exactly; headline + closing quote updated to 216.
  - Home.md: badge v7.173.0 → **v7.176.0**, "Key features" header v7.176.0, +6 feature bullets (v7.174 PHASE/ref pairing, goal-budget conditional; v7.175 five contradictions; v7.176 first-publish gate order, HUNT entrance, MARKHUNT brake, ticket stays DOING).
  - Phases.md: range header v7.104.0–v7.173.0 → v7.104.0–v7.176.0; +12 phase-level checks (v7.174 ×2, v7.175 ×2, v7.176 ×8).
  - Getting-Started.md: audit_checks 91 → 104 mutations, heading version tail extended to v7.176.0.
  - SubSaipen.md: saiwiki status row -- W-030 prepared (v7.176.0, 216 scenarios).
  - _Footer.md: version v7.173.0 → v7.176.0.
  - Tutorials.md, Use-Cases.md, _Sidebar.md: no drift (unchanged).
- **payload:** 6 modified pages in the wiki clone `kitchen/wiki/` (local, uncommitted):
  - `Home.md`, `Scenarios.md`, `Phases.md`, `Getting-Started.md`, `SubSaipen.md`, `_Footer.md`
  - To integrate: `git -C .saipen/extensions/subs/saiwiki/kitchen/wiki diff` review, commit, push to github.com/vacterro/saipen.wiki.
- **verified:**
  - Scenarios.md row count 216 == CONFORMANCE max ID 216; rows 202-216 present, no duplicate IDs.
  - Home/_Footer badges v7.176.0; no stale v7.173.0 era badge left anywhere in page content (project-root era stays only in changed bullets).
  - Scenarios regenerated partially but referenced CONFORMANCE by ID; known limits: rows are one-line paraphrases of CONFORMANCE text, same style as W-029.
- **instructions:**
  1. Review the uncommitted diff: `git -C .saipen/extensions/subs/saiwiki/kitchen/wiki diff`.
  2. Commit with message style `saiwiki: refresh wiki to v7.176.0 -- 216 scenarios, 6 pages` and push to origin (github.com/vacterro/saipen.wiki).
  3. Verify live: Home badge shows v7.176.0, Scenarios shows 216 rows, _Footer v7.176.0.
  4. No main-board ticket to close for this package.
  5. No main-project files touched by this package.

## W-031: wiki refresh v7.176.0 -> v7.219.0, 254 scenarios
- **status:** ready
- **summary:** 6 wiki pages refreshed to v7.219.0 truth (main HEAD 7d2bd0e): Scenarios 216→254 rows (38 new: 217-254 mirroring CONFORMANCE IDs 217-254 -- typed-command-outranks-next_action, ROUTE-derived Notes, WAIT one-sentence, Proposal-Mode halt, multi-file fixtures, HUNT recovery proof, PREPARE names producer, multi-command message, derived seat, MARKHUNT countable, no-git readable, closed root, no-publish permission, unmeetable-ticket BLOCKED, stale-translation signal, BLOCKED holds foreign work, defect-class section, wiki-mirror-by-ID, red controls that could not go red, future-stamp repair, circuit evidence, move-is-destructive, habit counter, CHANGELOG order, installed/repo validator agreement, session BLOCKED, intent-aware clean-HUNT, intent-aware valve resume, CLEAN owns mutations, machine-readable charters, role freshness, Golden Default, nonempty-OUTBOX, gate context, SHIP stages-before-gates, schema keyword FAIL, full-OID identity, RFC-not-a-destination), Home badge/features v7.219.0 + 18-command table + 15-key shortcuts (gg/hh/cc/ccc/ss/sss/dd/aa/qq/qqq/ee/eee/pp/tt/sc), _Footer v7.219.0, Phases range header to v7.219.0 + 13 phase-level checks, Getting-Started audit_checks 104→231 + gen-7 hook, SubSaipen status row W-031 + machine-readable charters + saiui. 0 stale era badges left.
- **main_project_refs:** [saipen/CONFORMANCE.md, saipen/CORE.md, saipen/phases/*.md, saipen/BOOT.md, saipen/STYLE.md, tools/validate.py, tools/audit_checks.py, VERSION]
- **critical:** false
- **producer:** saiwiki
- **source_head:** 7d2bd0eed5676645c2352cbefecb2ff98dbee79f
- **source_tree_fingerprint:** git-delta-v1:d0daa244b97507286381e4a28e72611e8f2ad68e700fd7da6b81a253e368cdff
- **role_revision:** sha256:54a42475a124ab0f27e83d600a284a9cc54d9668029c4828cfc48512b031df13
- **coverage:**
  - Scenarios.md: 216→254 rows (38 new: 217-254), IDs mirror CONFORMANCE 1-254 exactly; headline + closing quote updated to 254; junk partial rows removed.
  - Home.md: badge v7.158.0 → **v7.219.0**, "Key features" header v7.219.0, command table 14→18 (crew, test, userperson, improve added), shortcuts 13→15 keys (gg new-goal, cc continue/converge, ccc continue-and-ship, dd plan, aa markhunt, pp saipython, tt test, sc crew), +20 feature bullets (v7.159-v7.219).
  - Phases.md: range header v7.104.0–v7.157.0 → v7.104.0–v7.219.0; +13 phase-level checks (OBEY, WAIT one-sentence, PHASE/ref pairing, ticket-stays-DOING, verify_attempts, REVIEW re-runs verify, first-publish gate, tag-after-branch, hunt-entry, MARKHUNT brake, execution_intent, HUNT/CLEAN split, session-BLOCKED).
  - Getting-Started.md: audit_checks 104 → 231 mutations; hook generation 7 section; +5 commands (hunt, crew, test, userperson, improve).
  - SubSaipen.md: saiwiki status row -- W-031 prepared (v7.219.0, 254 scenarios); machine-readable charters + role freshness section; saiui added to active sub-agents.
  - _Footer.md: version v7.158.0 → v7.219.0.
  - Tutorials.md, Use-Cases.md, _Sidebar.md: no drift (unchanged).
- **payload:** 6 modified pages in the wiki clone `kitchen/wiki/` (local, uncommitted):
  - `Home.md`, `Scenarios.md`, `Phases.md`, `Getting-Started.md`, `SubSaipen.md`, `_Footer.md`
  - To integrate: `git -C .saipen/extensions/subs/saiwiki/kitchen/wiki diff` review, commit, push to github.com/vacterro/saipen.wiki.
- **verified:**
  - Scenarios.md row count 254 == CONFORMANCE max ID 254; rows 217-254 present, no duplicate IDs; committed junk rows (empty invariants) removed.
  - Home/_Footer badges v7.219.0; no stale v7.15x/v7.16x/v7.17x/v7.18x era badge left in page content (era refs live only inside historical feature bullets, same style as W-029).
  - Command table matches CORE.md § 1.10 surface (18 verbs); shortcut count 15 matches the canonical table.
  - Freshness triple computed by tools/freshness.py after the last source read; charter role_revision matches the declared value in extensions/subs/saiwiki.md.
  - tools/validate.py PASS baseline (known WARNs unchanged: sealed-log dates, saipython never-ran, digest stale).
- **instructions:**
  1. Review the uncommitted diff: `git -C .saipen/extensions/subs/saiwiki/kitchen/wiki diff`.
  2. Commit with message style `saiwiki: refresh wiki to v7.219.0 -- 254 scenarios, 6 pages` and push to origin (github.com/vacterro/saipen.wiki).
  3. Verify live: Home badge shows v7.219.0, Scenarios shows 254 rows, _Footer v7.219.0.
  4. No main-board ticket to close for this package.
  5. No main-project files touched by this package.
