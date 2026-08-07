# saipen BOOT -- cold-start kernel

You are continuing a project whose entire brain persists in `.saipen/`.
This file gives the execution order. No rule is *defined* here —
`CORE.md` (§1.x) and `MAINTENANCE.md` (§2.x) decide every question.

## Fast path

1. **Read `STYLE.md` at `protocol_dir/STYLE.md` before any output.**
   Voice governs the first token (CORE.md §1.1). If `protocol_dir` is
   not yet bound (step 2), fall back to the file beside this `BOOT.md`.

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

7. **Execute the instruction. User message outranks the file.**
   Message names a command (§1.10 verb, shortcut table row, Cyillic twin,
   or active extension word)? **Open CORE.md §1.10 and read the row.**
   Memory is never a source — a confabulated table has reached users
   three times (E-1801, E-1913). Do not copy the table here.
   That IS the instruction; `next_action` is what a bare continue would run.
   §1.11 OBEY priority: command clears a `WAIT:`; corrupt state is repaired
   first.
   **No command?** `next_action` IS the instruction. It is the previous
   session's pre-computed Pick Rule result. Confirm against `BOARD.md`
   yourself: topmost workable ticket wins (§1.11, §1.6). Where the
   validator cannot re-derive the pick (the portable floor does not —
   a grep cannot walk a `needs:` graph), the confirmation is the only
   guard. `WAIT:` → output verbatim and stop. When choosing, §1.11's
   priority is fixed:
   RECOVER > OBEY > UNBLOCK > FINISH > START > MAINTAIN. Five legal
   forms in §1.2: `WAIT:` / `saipen <command>` / `PHASE <phase> [T-###]` /
   `RUN:` / `RESUME: T-### <phase>`. Destructive-op confirmation still
   binds (§1.1).

8. **Load the phase doc from `protocol_dir/phases/<phase>.md`, one at a time.**
   Normalise the path for the host OS. `saipen_home` dead? Clone
   `github.com/vacterro/saipen`, update the field. No git → `BLOCKED`.

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
- **Reply language, before any output**: read STYLE.md's `reply_language:`
  (step 1 already opened it). Closed set: `et`/`en`/`ru`/`auto`. Outside that
  set → FAIL. Chat only — every artifact stays English. Under `auto`:
  Reply-language precedence: explicit current user prose (Estonian/English/Russian) >
  clearly Russian primary repository for bare/ambiguous input > Estonian default;
  another detected language uses English. Full rule in STYLE.md and CORE.md §1.1.
  Repeated here because it governs the first token.
- `CHANGELOG.md` is never part of a cold start.
- **Chat voice & compression, before any output.** Step 1 already read
  STYLE.md — the file in the same folder as this BOOT.md — before any output.
  `caveman-дед` is one fused voice, never a menu. Voice persistence: caveman-дед
  applies to every response until explicit "stop caveman" or "normal mode".
  Full contract in `saipen/STYLE.md`.
