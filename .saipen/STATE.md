---
phase: DONE
task: T-105
next_action: "PHASE_DOCS_FIX_DIRECTIVE_PART2.md T-105 done -- found a real bug, not just wording, in add.md's evaluation pseudocode: the minimal_delta/design_language IF had no ELSE, so an existing-but-non-minimal opportunity silently fell through the loop to RETURN DONE, falsely declaring the product mature even though step 3's own prose already assumed a ticket-it-and-PLAN path existed. Added the missing ELSE (ticket + RETURN PLAN_or_SCOUT), spelled out the two implementation paths in prose, clarified bugfix->RETURN HUNT means ADD delegates rather than improvising a fix. Also gave the mature-exit branch its own explicit goal_mode/counter-clearing (RFC § 2.4's Exit rule previously lived only in RFC, never at the point in add.md where it actually needs to happen), separated from the generic per-cycle wave-increment bullet so they don't double-fire. Local commit only, no tag/push (Prime Rule 7). Awaiting operator 'Execute T-106 only.'"
blocker: none
saipen_version: 7
schema_version: 1
agent: claude-sonnet-5
requires:
  - filesystem
  - git
mode: full
goal_mode: false
updated: 2026-07-21T00:42:00Z
---
