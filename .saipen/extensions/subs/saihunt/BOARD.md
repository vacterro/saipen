# Board
## DOING

## TODO

## DONE
- [x] HUNT-001 full 6-category sweep @40242f3: clean except 2 stale kitchen files (markhunt relics, delete free)

## BLOCKED
- [ ] [MARKHUNT] HUNT-002 `last_event` chicken-and-egg — field is RECOMMENDED, recovery (§ 1.5) doesn't read it, so it stays perpetually absent. Recovery rebuilds STATE from LOG tail but has no way to detect STATE/LOG desync without `last_event`. Circular: not required → not populated → not checkable → not required. | blocker: unvetted audit — RFC § 1.2 `last_event` vs § 1.5 recovery procedure; CONFORMANCE row 45 describes the field, recovery section doesn't reference it
- [ ] [MARKHUNT] HUNT-003 goal-wave double-count fragility — `add.md` increments `goal_waves` on cycle completion, `plan.md` must REMEMBER not to re-increment when entered from ADD's `RETURN PLAN`. No persistent flag carries the caller identity across the transition. A crash between ADD's RETURN and PLAN's execution loses context → PLAN double-counts the wave. | blocker: unvetted audit — `phases/add.md` § 3 vs `phases/plan.md` § After-PLAN carve-out; no STATE.md field records "was entered from ADD"
- [ ] [MARKHUNT] HUNT-004 HUNT→DONE transition hierarchy tension — PROTOCOL.md § 1 adds `HUNT -> DONE` for subSaipen, but RFC § 1.6 transition table lists `HUNT -> ADD | PLAN | SCOUT | BLOCKED` only. RFC § 1.1 says RFC.md wins over all extensions. Validator accepts it, but the hierarchy rule is technically violated: an extension adding a transition to Core's table. | blocker: unvetted audit — extensions/subs/PROTOCOL.md § 1 vs RFC § 1.6 transition table vs RFC § 1.1
- [ ] [MARKHUNT] HUNT-005 MANIFEST.md `last_collect` silently stale — protocol § 5 says updated on every `saipen sub collect`, but no tool enforces it. `saipen sub collect saitranslate` ran and did not update the field. Optional means optional → never updated → field is always stale → useless as a staleness signal. | blocker: unvetted audit — extensions/subs/PROTOCOL.md § 5 `last_collect` field vs actual collect behavior (tested: saitranslate collect on 2026-07-30 did not update MANIFEST.md)
- [ ] [MARKHUNT] HUNT-006 `mode: read-only` Core/sub list drift — two lists exist (7 phases for Core § 1.3, 4 phases for sub § 1), validated by `tools/validate.py`. But the validator's check only runs at validation time — nothing prevents a sub-agent booting with a stale RFC copy from applying the wrong (Core's) list to itself and refusing to PLAN. | blocker: unvetted audit — extensions/subs/PROTOCOL.md § 1 vs RFC § 1.3; the textual instruction is the only enforcement, no runtime guard
