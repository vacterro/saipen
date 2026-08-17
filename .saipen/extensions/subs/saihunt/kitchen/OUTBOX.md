# OUTBOX

## HUNT-7: disposition of MARKHUNT findings HUNT-002..006
- **status:** reviewed
- **summary:** Five audit findings dispositioned; each already resolved in current RFC/tooling, no code change required.
- **main_project_refs:** [saipen/CORE.md, saipen/phases/add.md, saipen/phases/plan.md, extensions/subs/PROTOCOL.md, tools/saipen_engine/subs.py]
- **critical:** false
- **severity:** P2
- **producer:** saihunt
- **source_head:** 23bebeafdcd1a2d972ebcde50b0521ca7f26435e
- **source_tree_fingerprint:** git-delta-v1:71ab59334fc886858b6f44df6cfad66034ae0c8d8b8bad676409177b6d9b9811
- **role_revision:** sha256:4edb04181cb07e0946afd06fbe711166fa9dcc403e56b52e9be3844f0a71b0a5
- **coverage:** HUNT-002 last_event recovery; HUNT-003 goal_waves carve-out; HUNT-004 HUNT->DONE subSaipen carve-out; HUNT-005 MANIFEST last_collect enforcement; HUNT-006 phase-list named-constants + drift detector
- **payload:** No main-project change. Disposition recorded in saihunt BOARD ## DONE (HUNT-002..006 moved from ## BLOCKED with rationale).
- **verified:** PASS -- manual audit of CORE.md S1.5 recovery sets last_event, add.md/plan.md goal_waves carve-out, PROTOCOL.md S1 HUNT->DONE subSaipen note, subs.py sub_collect last_collect write path
- **instructions:** None required; no artifact to integrate. Crew may advance past SC-2.
- **details:** HUNT-002 RESOLVED: CORE.md S1.5 (line 243) orders Recovery to set last_event to the highest real E-### across sealed+active LOG; S1.2 requires last_event at schema_version 3. HUNT-003 RESOLVED: add.md RETURN PLAN carve-out + plan.md lines 30-34 forbid re-incrementing goal_waves when PLAN entered from ADD RETURN PLAN; Recovery rebuilds counters by counting DEC: goal_waves lines. HUNT-004 RESOLVED BY DESIGN: PROTOCOL.md S1 documents HUNT->DONE subSaipen-only carve-out; validate.py accepts it. HUNT-005 RESOLVED: subs.py sub_collect -> _manifest_with_collects writes MANIFEST last_collect; _durable_collect_witness dedups on it. HUNT-006 RESOLVED: PROTOCOL.md S1 both phase-ban lists are named constants and the validate drift detector compares them; residual (sub booting stale RFC copy) out of scope since sub loads synced local PROTOCOL.md.
