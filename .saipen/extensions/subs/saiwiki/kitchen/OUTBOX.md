# OUTBOX

## WIKI-008: v7.103.0 drift scan — 5 releases since last wiki refresh
- **status:** reviewed
- **collected_by:** main agent (direct apply — full 8-page refresh)
- **collected_at:** 2026-07-29T12:00:00Z
- **summary:** Project evolved from v7.98.0 to v7.103.0 (5 releases: v7.99.0–v7.103.0). 31 CONFORMANCE rows added (68→99). Major themes: validator linted + mojibake repair, subSaipen liveness checks, doc inventory + citation resolution, portable floor audit, adapter boot-order fix, push-claim verification. 6 wiki pages need light refresh.
- **main_project_refs:** [VERSION (7.98.0→7.103.0), CHANGELOG.md (v7.99.0–v7.103.0 blocks), saipen/CONFORMANCE.md (rows 68→99), tools/validate.py (+601 lines), tools/audit_floor.py (new, 213 lines), extensions/adapters/*.md (all 9 updated), extensions/schemas/board.schema.json (+21), extensions/schemas/log.schema.json (+18), extensions/subs/PROTOCOL.md (+3), extensions/subs/TEMPLATE/STATE.md (next_action fix), bootstrap/inject.sh (+16, cygpath-w), .github/workflows/release.yml (new release guard), .github/workflows/validate.yml (ruff step), KNOWLEDGE/traps.md (+83), KNOWLEDGE/decisions.md (+6), ruff.toml (new)]
- **critical:** false
- **severity:** P3
- **details:**
  **Working tree at v7.103.0** (commit `3efc567`). 1 file dirty: `saipen/UI.md` (color palette changes, uncommitted). Wiki at committed v7.98.0 (from W-017/W-018 pushes).

  **RELEASES COVERED (v7.98.0 → v7.103.0):**

  **v7.99.0 — validator linted for the first time**
  - `tools/validate.py` (1418 lines) had never been linted. 14 ruff items found, including 9 cp1251-mangled section signs inside its own FAIL messages — valid UTF-8, so its own U+FFFD corruption check could never catch them. Repaired; doc text lint now catches that byte sequence too.
  - CI gained a `ruff` step; `ruff.toml` carries a written reason for every disabled rule.
  - Push-claim verification: `STATE.next_action` mentioning "pushed" while commits sit local-only now FAILs.
  - SubSaipen review: saipython flagged as spawned-never-run (5 open tickets, 0 done, empty OUTBOX). saitranslate SAIT-002 left at `status: ready` after collection → WARNs.
  - CONFORMANCE rows 69–71. 43rd scenario fixture: saiwiki-outbox-cycle.

  **v7.100.0 — standing fixtures, schema alignment, doc inventory**
  - `tests/validate.sh`/`.ps1` portable floor gained audit: `tools/audit_floor.py` (213 lines) — breaks a scratch project 20 ways per check, asserts both halves go red.
  - Descriptive schemas (board.schema.json, log.schema.json) re-aligned with RFC § 1.2 — log had made [E-###] optional and capped text at 120 chars (declared 54 of 72 live lines invalid).
  - OUTBOX status vocabulary unified across PROTOCOL.md § 2 table, outbox.schema.json, and validate.py (all three disagreed).
  - `next_action` prefix check promoted from WARN to FAIL. Three red fixtures.
  - Doc inventory: all 184 shipped documents accounted for. Found orphan fixture README at phantom path tracked since `00c7557`.
  - No document may cite a version that has not shipped.
  - CONFORMANCE rows 72–88.

  **v7.101.0 — exemptions, citations, coverage**
  - `KNOWLEDGE/traps.md`/`decisions.md` both taught a WAIT-at-DONE rule superseded 9 releases earlier. `.saipen/KNOWLEDGE/` added to checks.
  - Citation resolution: every `§ N.N` and `phases/*.md` in a shipped doc must name something that exists. 103 docs scanned, 0 dangling.
  - TEMPLATE/STATE.md next_action fixed (was prefix-less → every spawned sub born non-conformant).
  - `phases/done.md` next_action fixed.
  - Unreachable WARN category (`unknown-field`) collapsed to FAIL.
  - Gate-stuck-red guard: `phases/verify.md` now requires a control with known result before reporting any negative.
  - CONFORMANCE rows 89–96.

  **v7.102.0 — adapter boot order fixed**
  - 7 of 9 platform adapters never mentioned `BOOT.md` — sent cold agents at ~100 KB RFC.md instead of the 4 KB BOOT kernel. All 9 now carry boot order.
  - Adapter cross-ref check validates `saipen/` paths exist.
  - Release guard proved itself: a mis-tagged release failed on the tag-vs-VERSION check in 16 seconds.
  - `KNOWLEDGE/traps.md`: git tag chaining trap recorded (never chain `git tag` after a bare `;`).
  - CONFORMANCE rows 97–98.

  **v7.103.0 — text lint widened**
  - cp1251 mojibake lint walked a curated 4 files. Expanded to all shipped docs (KNOWLEDGE/, extensions/, fixture READMEs). Found a mangled arrow in `traps.md` itself.
  - 5 mojibake sequences recognized (was 1).
  - CONFORMANCE row 99.

  **WIKI PAGES AFFECTED:**

  **1. Home.md** — Version badge: `v7.98.0` → `v7.103.0`. Key features section needs update: CI badge now on README; ruff/CI pipeline details; doc inventory + citation resolution as new capabilities. Features dated "2026-07-28" → "2026-07-29".

  **2. Scenarios.md** — Headline: "68 behavioral conformance scenarios" → "99". 31 new rows to add to advanced table (rows 68–99). Key new rows: push-claim verification (69), subSaipen liveness (71), release tag guard (72), OUTBOX vocab alignment (74), doc inventory (83), citation resolution (89), knowledge checks (90), adapter boot order (97), prescribed next_action sweep (98), mojibake lint (99).

  **3. SubSaipen.md** — New subSaipen checks in validate.py: liveness WARN for spawned-never-run; TEMPLATE next_action fix; PROTOCOL.md +3 lines (OUTBOX `stale` status formalized). saipython status: "spawned, never run" relevant to sub lifecycle docs.

  **4. Getting-Started.md** — `inject.sh` cygpath-w fix for Windows users (no more dead paths in CLAUDE.md). GUIDE.md WAIT category list now shows full 7-category vocabulary inline. CI badge on README.

  **5. Phases.md** — verify.md gained gate-stuck-red guard. done.md next_action fixed. Multiple phase files touched across v7.99.0–v7.103.0.

  **6. _Footer.md** — `v7.98.0` → `v7.103.0`.

  **NOT AFFECTED (accurate or unchanged):** _Sidebar.md (no version badge, links only). Tutorials.md, Use-Cases.md — structural content unchanged; minor additions (audit_floor, citation resolution) are validator-internal, not user-facing feature doc material.

  **RECOMMENDATION:** Light refresh (P3). 6 pages, ~20 min total. Bump version badges, add rows 68–99 to Scenarios table, update Home features with v7.99.0–v7.103.0 highlights, refresh SubSaipen with new validate.py checks. No full regeneration needed.
