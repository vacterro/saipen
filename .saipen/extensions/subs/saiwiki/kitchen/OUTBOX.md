# OUTBOX

## WIKI-007: v7.98.0 drift scan — wiki 5 pages stale after drift hunt
- **status:** reviewed
- **summary:** Project evolved from v7.97.0 to v7.98.0 (drift hunt release). 5 wiki pages need minor refresh: Home (v7.98.0 badge, CONFORMANCE 67), Scenarios (row 67), SubSaipen (subs README no longer "Not yet field-tested", new validate.py guards), _Footer (version bump). Light refresh — not a full regeneration.
- **main_project_refs:** [VERSION (7.97.0→7.98.0), CHANGELOG.md (v7.98.0 block), saipen/CONFORMANCE.md (row 66→67), tools/validate.py (self-transition guard, sub next_action checks, adapter cross-ref check), extensions/subs/README.md ("Not yet field-tested"→"Running in production"), .saipen/extensions/subs/saihunt/STATE.md (HUNT→DONE), .saipen/extensions/subs/saipython/STATE.md (next_action: RESUME: prefix)]
- **critical:** false
- **severity:** P3
- **details:**
  **Working tree at v7.98.0** (uncommitted). Wiki at committed v7.97.0 (`0e99a90`).

  **CHANGED (what the drift hunt fixed):**
  - `VERSION`: 7.97.0 → 7.98.0
  - `CONFORMANCE.md`: Row 67 added — "Hunt mode expands to surfaces outside the drift detector" (subs README, sub next_action prefixes, self-transition validation, adapter cross-ref check)
  - `extensions/subs/README.md`: "Not yet field-tested" → "Running in production on this repo since v7.84.0. Four live instances..."
  - `tools/validate.py`:
    • Self-transition guard: validates source phase is known enum (was skipping all validation)
    • Sub next_action check: enforces RFC § 1.2 prefix/WAIT-category rules on sub STATEs
    • Adapter cross-ref check: every `saipen/` path in adapters/*.md must exist
  - `saihunt/STATE.md`: phase HUNT → DONE (no live tickets, all work complete)
  - `saipython/STATE.md`: next_action gained `RESUME:` prefix (was bare prose)
  - `saitranslate/kitchen/` + `guides/`: 29 non-Core locale refreshes (SAIT-003)

  **WIKI PAGES AFFECTED:**

  **1. Home.md** — Version badge: `v7.97.0` → `v7.98.0`. Key features section references "v7.97.0" → v7.98.0. CI truth section accurate (already added in W-015). CONFORMANCE 66→67 implied (scenarios section). Minor.

  **2. Scenarios.md** — Headline: "66 behavioral conformance scenarios" → "67" (row 67 added). New row to add to advanced table: "67 | Drift hunt expansion | subs README, sub next_action, self-transitions, adapter paths all validated".

  **3. SubSaipen.md** — Active sub-agents table: add note that sub next_action is now validated by validate.py. Add note about self-transition guard and adapter cross-ref check. Status no longer references "Not yet field-tested" (already removed in W-015, but subs README change reinforces production readiness).

  **4. _Footer.md** — `v7.97.0` → `v7.98.0`.

  **5. _Sidebar.md** — No version badge, links only. No change needed.

  **NOT AFFECTED (accurate):** Getting-Started.md, Phases.md, Tutorials.md, Use-Cases.md — all contain v7.97.0+ features and the v7.98.0 changes are validator/internal, not user-facing features.

  **RECOMMENDATION:** Light refresh (P3). 5 pages, ~15 min total. After the working tree is committed, bump version badge, add row 67, update SubSaipen guards section. No regeneration needed.

## WIKI-005: wiki drift audit — v7.97.0 vs wiki at v7.64-era
- **status:** reviewed
- **summary:** Project evolved from ~v7.64 to v7.97.0 (17 releases) since last wiki update. 8 wiki pages stale: Home, Getting-Started, Phases, Scenarios, Tutorials, Use-Cases, SubSaipen, Sidebar. Major deltas: WAIT categories, portable floor, CI truth, subs/PROTOCOL rewrite, RFC diet, CONFORMANCE resync.
- **main_project_refs:** [saipen/RFC.md (+142/-52), saipen/CONFORMANCE.md (+51/-26), saipen/BOOT.md (+138/-120), tools/validate.py (+735/-450), extensions/subs/PROTOCOL.md (+81/-0), saipen/phases/* (8 files touched), CHANGELOG.md (+233)]
- **critical:** false
- **severity:** P2
- **details:**
  Full audit of wiki drift since last saiwiki update (27.07.26). Key findings:

  **1. WAIT category system (v7.93.0)**
  - RFC gained closed 7-word WAIT vocabulary + membership check
  - Core guides updated to 
  - Phases wiki page needs WAIT category tables

  **2. Portable floor (v7.94.0-v7.97.0)**
  - validate.sh and validate.ps1 now probe all 9 RFC §1.2 fields
  - Read-only ban covers INIT/PLAN/ADD/BUILD/SHIP/CLEAN/TRANSLATE
  - cross-document drift detector added
  - Getting-Started and Tutorials pages need portable-script coverage

  **3. CI truth (v7.97.0)**
  - validate.yml header rewritten — trigger is PR-only (zero PRs ever), real gate is pre-commit hook
  - validate.ps1 added as pwsh step
  - Home page CI badge section stale

  **4. SubSaipen protocol rewrite**
  - subs/PROTOCOL.md: Core-shape copies removed, pointers + sub-specific delta only
  - saiwiki, saihunt, saitranslate, saipython all updated
  - SubSaipen wiki page needs protocol-section refresh

  **5. RFC diet + CONFORMANCE resync (v7.93.0)**
  - RFC 102682 → 100359 bytes, 4 incident narratives moved to tests/scenarios/
  - CONFORMANCE 20589 → 19746 bytes, 60 rows with unique IDs
  - Cross-document anchor checks added

  **6. Phase files touched (8 of 16)**
  - add.md, blocked.md, build.md, clean.md, init.md, plan.md, review.md, ship.md, translate.md, verify.md
  - Phases wiki page needs re-sync

  **RECOMMENDATION:** Wiki refresh is warranted. Estimated effort: 6 pages × 15-30 min each. Priority: P2 (wiki is supplementary, not a checkpoint dependency).

## WIKI-006: maintenance scan + verify — v7.97.0 deep audit
- **status:** reviewed
- **summary:** Full maintenance scan of project vs wiki. 1 validate FAIL found: saitranslate STATE phase=TRANSLATE under mode=read-only (RFC § 1.3). Wiki-relevant content drift confirmed across 8 pages. No structural wiki defects, but all pages need content refresh.
- **main_project_refs:** [.saipen/extensions/subs/saitranslate/STATE.md, saipen/RFC.md, tools/validate.py, saipen/phases/*, CHANGELOG.md]
- **critical:** false
- **severity:** P2
- **details:**
  **VALIDATE FAILURE (cross-sub):** `tools/validate.py` reports 1 FAIL:
  `.saipen/extensions/subs/saitranslate/STATE.md` has `phase: TRANSLATE` with
  `mode: read-only`. RFC § 1.3 prohibits a read-only subSaipen from entering
  TRANSLATE. This is saisWiki's detection, not saisWiki's fix — saitranslate
  needs its own correction cycle.

  **WIKI PAGE DRIFT (detailed per page):**

  **1. Home.md** — stale tagline reference; CI section still describes
  pre-v7.97.0 workflow; version badge shows v7.64-era; saicrew mention
  predates PROTOCOL.md rewrite; no coverage of goal_waves/goal_tickets caps;
  no coverage of cross-document drift detector.

  **2. Getting-Started.md** — portable floor (validate.sh/validate.ps1) not
  mentioned; no WAIT category table; no MARKHUNT phase coverage; no
  subs/PROTOCOL.md changes; no §1.7 workspace hygiene rules.

  **3. Phases.md** — 8 of 16 phase files changed since wiki was written.
  Missing: WAIT category vocabulary (§ 1.2), read-only ban list expansions,
  ADD's two implementation paths, CLEAN's structural repair rules,
  HUNT's subagent dispatch, SHIP's no-publish branch, goal_waves counter
  LOG mandate, MARKHUNT cite-evidence rule.

  **4. Scenarios.md** — 4 incident narratives moved from RFC to
  tests/scenarios/ (v7.93.0); new scenarios added: checkpoint-self-
  confirmation, determinism-invariants, returning-agent-stale-memory,
  safety-valve-is-a-pause, subsaipen-blocked-not-guessed,
  write-confirmed-by-readback. None reflected.

  **5. Tutorials.md** — no coverage of: portable floor scripts, WAIT categories,
  cross-document drift detection, goal_mode execution flow, 
  vs  distinction.

  **6. Use-Cases.md** — missing: subSaipen collect flow, OUTBOX patch protocol,
  valve trip recovery, RECOVER vs FINISH distinction, safe-hunt-skip hash rule.

  **7. SubSaipen.md** — PROTOCOL.md rewritten from Core-shape copies to
  pointers+delta. saihunt/saitranslate/saipython/saisWiki all updated since
  wiki. OUTBOX format now validated by tools/validate.py (status/summary/
  critical checks). No patch-with-evidence protocol coverage.

  **8. _Sidebar.md / _Footer.md** — version stale; tagline may need update;
  no CHANGELOG link or recent release mentions.

  **POSITIVE FINDINGS:**
  - tools/validate.py PASSes everything except the saitranslate issue
  - All 32 locale badges match VERSION 7.97.0
  - CONFORMANCE 66 rows, unique+monotonic IDs
  - No BOARD structure defects
  - LOG format clean (4 segments)
  - All subSaipen OUTBOX entries well-formed

  **RECOMMENDATION:**
  Two work items:
  1. saitranslate STATE fix (read-only → DONE, by saitranslate or Core)
  2. Wiki refresh: 8 pages need regeneration from current v7.97.0 sources.
     Estimated 4-6 hours for full rewrite (caveman style, ded examples, flags).
