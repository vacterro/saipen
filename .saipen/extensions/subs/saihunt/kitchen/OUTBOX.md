# OUTBOX

## MARKHUNT-001: logical flaw audit — 5 findings across protocol docs
- **status:** reviewed
- **collected_by:** main agent
- **collected_at:** 2026-07-30T10:15:00Z
- **summary:** Deep dry audit of SAIPEN protocol for logical flaws. 5 found across RFC, phase docs, PROTOCOL.md, and MANIFEST.md.
- **main_project_refs:** [saipen/RFC.md, saipen/phases/plan.md, saipen/phases/add.md, saipen/phases/verify.md, extensions/subs/PROTOCOL.md, .saipen/extensions/subs/MANIFEST.md]
- **critical:** false
- **severity:** P2
- **details:**
  5 logical flaws identified — each a self-contradiction or circular dependency in the protocol design:

  **LFC-001: last_event chicken-and-egg** — field is RECOMMENDED, recovery (§ 1.5) doesn't read it, so it stays perpetually absent. Recovery rebuilds STATE from LOG tail but has no way to detect STATE/LOG desync without last_event. Circular: not required → not populated → not checkable → not required.

  **LFC-002: goal-wave double-count fragility** — add.md increments goal_waves on cycle completion. plan.md must NOT re-increment when entered from ADD's RETURN PLAN. No persistent flag carries the caller identity across the transition. A crash between ADD's RETURN and PLAN's execution loses context → PLAN double-counts the wave.

  **LFC-003: HUNT→DONE hierarchy tension** — PROTOCOL.md adds HUNT->DONE for subSaipen. RFC § 1.6 lists only HUNT->ADD/PLAN/SCOUT/BLOCKED. RFC § 1.1 says RFC.md wins. Extension adding transitions to Core's table is technically a hierarchy violation, even if practically correct.

  **LFC-004: MANIFEST last_collect never enforced** — protocol § 5 says updated on every collect. No tool enforces it. Live test on saitranslate collect (2026-07-30) confirmed: field not updated. Optional → never updated → always stale → useless as staleness signal.

  **LFC-005: read-only mode list runtime gap** — two lists exist (7 phases Core § 1.3, 4 phases sub § 1). Validator checks at validation time. No runtime guard prevents a sub booting with a stale RFC copy from applying Core's 7-phase ban to itself and refusing to PLAN.

  **Closure:** 5/5 vectors covered. head_end matches head_start (ac37c91). All findings accounted for on BOARD.md.

## HUNT-001: clean sweep, 1 finding
- **status:** reviewed
- **summary:** 6-category HUNT sweep clean — 1 finding: 2 stale kitchen files deleted
- **main_project_refs:** [.saipen/kitchen/markhunt_integration_plan.md, .saipen/kitchen/markhunt_progress.md]
- **critical:** false
- **severity:** P3
- **details:**
  6 categories scanned. No failing tests, no unverified commits, no stale code TODOs, no silent failures, no symmetry gaps, no orphan code. Finding: 2 stale files in `.saipen/kitchen/` (markhunt_integration_plan.md 3366 bytes, markhunt_progress.md) — owning tickets T-178/T-179/T-180/T-181 all DONE 2026-07-26, content superseded. Deleted per hunt.md "delete free" rule. Collected 2026-07-27.
