# saipen BOOT -- cold-start kernel

You are continuing a project whose entire brain persists in `.saipen/`.
This file gives the execution order. No rule is *defined* here —
`CORE.md` (§1.x) and `MAINTENANCE.md` (§2.x) decide every question.

## Fast path

1. **Read `STYLE.md` — the file in the same folder as this `BOOT.md` — before any output.**
   Voice governs the first token (CORE.md §1.1). `protocol_dir` is
   resolved in step 2; if not yet bound, the file beside this `BOOT.md`
   needs no resolution and answers the same question either layout.

2. **Bind `project_root`, resolve `protocol_dir`, read `.saipen/STATE.md`.**
   Explicit target wins; else Git (`git rev-parse --show-toplevel` +
   `--git-common-dir`); else nearest ancestor with `.saipen/`. A linked
   worktree with its own `.saipen/` IS its own root. Keep the binding:
   every checkpoint path is `<project_root>/.saipen/...`. `saipen_home`
   points to the protocol install (CORE.md §1.1).

   **Resolve `protocol_dir` from `saipen_home`:**
   - `<saipen_home>/saipen/BOOT.md` exists → `protocol_dir = <saipen_home>/saipen`
   - `<saipen_home>/BOOT.md` exists → `protocol_dir = <saipen_home>`
   - Neither → `phase: BLOCKED` immediately.

   Normative docs load from `protocol_dir`; tools/schemas/templates/VERSION
   from `saipen_home`. No other path derivation is conformant.

   **Anchors, never discovery.** `protocol_dir`/`saipen_home` come from
   where this `BOOT.md` actually loaded (the skill path in the system
   prompt, or a bound STATE's `saipen_home:` field) — never from scanning
   the workspace, its parents, or its siblings; the SAIPEN home is often a
   sibling of the workspace. Never `find`/glob for `BOOT.md` or `.saipen/`
   outside the bound root. `.saipen/` means exactly
   `<project_root>/.saipen/`; absent there means the project is NOT
   bootstrapped → INIT (§1.7), never "no saipen state, skip the protocol" —
   STYLE.md still governs the first token.

3. **Validate STATE before executing anything.**
   Every field CORE.md §1.2's required set names must be present
   (read it there — this file does not copy it). `transition_from` is
   omitted only on fresh INIT. Missing/corrupt → RECOVER per §1.5 first.
   Confirm `STATE.phase` is in §1.6's phase enum.
   **LOG ahead of STATE after a crash is NORMAL** (checkpoint writes LOG first).
   `schema_version` below current is readable legacy: WARN, upgrade next
   checkpoint. `last_event` mismatch → Recovery. `style_contract` mismatch →
   state that skipped step 1.

3a. **Skill injection** (if `.saipen/extensions/skill_injection/SPEC.md` exists).
    Detect problem class, match smallest skill from platform registry,
    inject context. Eject on class shift. Base protocol outranks.

4. **Read `.saipen/BOARD.md`, then tail of `.saipen/LOG.md`.**
   Sealed history in `.saipen/logs/LOG-NNN.md`; load only for `parent:`
   chain walks. Use the active LOG tail for `last_event` freshness.

5. **Distrust your own memory.** `STATE.agent` not you, or `STATE.updated`
   newer than your last write → your memory is stale. Files win (CORE.md §1.1).

6. **`human_note:` set?** Apply, clear, LOG trace: `DEC: applied human_note: <text>`
   or `DEC: human_note -> T-###`. One-shot, not standing law.

7. **Execute the instruction. The user's own message outranks `next_action` and defers to § 1.11's OBEY priority: the user's own message outranks the file.**
   Message names a command (§1.10 verb, shortcut table row, Cyillic twin,
   or active extension word)? **Open CORE.md §1.10 and read the row.**
   Memory is never a source for it — a confabulated table has reached users
   three times (E-1801, E-1913). Do not copy the table here: a second copy drifts
   and defeats the read-the-source rule. (§1.1's gate rejects a restatement.)
   That IS the instruction; `next_action` is what a bare continue would run.
   §1.11 OBEY priority: command clears a `WAIT:`; corrupt state is repaired
   first.
   **Actionable user objective?** If the user provides a natural-language actionable request (e.g., "fix this bug", "implement X", "continue work") rather than a bare command, treat it as a new goal-driven execution. Map the objective to `execution_intent: goal` in `STATE.md` (and reset counters per MAINTENANCE.md § 2.4), plan the work, and drive it to COMPLETE or BLOCKED per CORE.md § 1.12. No `/goal` command is required. Explicit read-only or plan-only requests must remain read-only.
   **No command and no new objective?** `next_action` IS the instruction. It is the previous
   session's pre-computed Pick Rule result. Confirm against `BOARD.md`
   yourself: topmost workable ticket wins (§1.11, §1.6). Where the
   validator cannot re-derive the pick (the portable floor does not —
   a grep cannot walk a `needs:` graph), the confirmation is the only
   guard. Immediate means without asking, never without looking.
   `WAIT:` → output verbatim and stop. When choosing, §1.11's
   priority is fixed:
   RECOVER > OBEY > UNBLOCK > FINISH > START > MAINTAIN. Five legal
   forms in §1.2: `WAIT:` / `saipen <command>` / `PHASE <phase> [T-###]` /
   `RUN:` / `RESUME: T-### <phase>`. Destructive-op confirmation still
   **SAIOPS is the preferred projection when it is available.** In
   `mode: full` with working Python, the deterministic mechanical router is
   TRUSTWORTHY (NITRO dogfood III, T-591): run `saipen status` then
   `saipen next` and execute the routed action -- the persisted
   `next_action` remains canonical recovery evidence and the fallback, but a
   cold full-mode agent does not re-derive the Pick Rule by hand when the
   engine already computed it (and WAIT/user-brake/BLOCKED/recovery all
   outrank START in the router). Load the phase doc from the ROUTED action
   (`saipen next`'s `load`), never from a stale persisted phase echo. When
   Python/SAIOPS is unavailable, fall back to the manual path unchanged -- a
   repository must remain cold-readable without the engine.
   binds (§1.1).

8. **Load the phase doc from `protocol_dir/phases/<phase>.md`, one at a time.**
   Normalise the path for the host OS. `saipen_home` dead? Do NOT edit
   `STATE.md` by hand and do not guess a home. Install/clone SAIPEN at an
   explicit candidate path, then run the ONE mechanical rebind operation
   `saipen rebind-home <candidate>`: it proves the candidate (readable
   `VERSION`, compatible major, `BOOT` layout, required protocol files),
   journals a single narrowly-owned `STATE.saipen_home` pointer update with
   truthful LOG evidence, and preserves phase/task/board. Only if the engine
   is unavailable (no Python/SAIOPS) does the manual path apply: clone
   `github.com/vacterro/saipen` and update the field, with no git → `BLOCKED`.

9. **Checkpoint after every ticket, phase transition, and before stop.**
   LOG (append) → `BOARD.md` → `STATE.md`, that order (§1.5). **Read back
   all three.** `STATE.md` must carry §1.2's required set. Run
   `tools/validate.py` where available. Write `schema_version` from
   `state.schema.json`'s `x-current-schema-version`, `last_event` from
   highest `E-###`, `style_contract` from STYLE.md's boot marker.

## Anything else

- Unrecognized `saipen <word>` → check extensions/project (§1.9), then list commands.
  Never guess.
- Rule questions → `INDEX.md` first. Do NOT read `CORE.md`/`MAINTENANCE.md` blindly.
  **STYLE.md is NOT on the rule-question list.** **CONFORMANCE.md is NEVER read**
  unless debugging a validator failure.
- `agent:` is inherited from STATE.md, not invented. Change it only for a
  genuinely different actor; LOG a `DEC` naming both.
- **Reply language, before any output**: read STYLE.md's `reply_language:` (step 1 already opened it). Closed set: `et`/`en`/`ru`/`auto`. Outside that set → FAIL. Chat only — every artifact stays English. Under `auto`: Reply-language precedence: explicit current user prose (Estonian/English/Russian) > clearly Russian primary repository for bare/ambiguous input > Estonian default; another detected language uses English. Full rule in STYLE.md and CORE.md §1.1. Repeated here because it governs the first token.
- `CHANGELOG.md` is never part of a cold start.
- **Chat voice & compression, before any output.** Step 1 already read STYLE.md — the file in the same folder as this BOOT.md — before any output. `caveman-дед` is one fused voice, never a menu. Voice persistence: caveman-дед applies to every response until explicit "stop caveman" or "normal mode". Full contract in `saipen/STYLE.md`.
