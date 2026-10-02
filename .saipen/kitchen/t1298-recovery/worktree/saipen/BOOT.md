# saipen BOOT -- cold-start router

BOOT defines no protocol rule. It decides what evidence and which single owner
must be loaded next. Rule IDs and machine facts live in `REGISTRY.json`; the
human ownership map lives in `INDEX.md`.

## Cold route

1. **Load `STYLE.md` beside this BOOT.md before user-visible output.** Its
   `reply_language:` value and style contract govern the first token. Invalid or unreadable style
   authority is a bootstrap failure, never permission to guess.

2. **Bind the project and installation.** Explicit target wins; otherwise use
   the Git worktree root, then the nearest ancestor containing `.saipen/`.
   Project memory is exactly `<project_root>/.saipen/`. Bind `saipen_home` from
   the loaded skill/STATE anchor, then resolve `protocol_dir` as either
   `<saipen_home>/saipen` or `<saipen_home>`. Do not scan for another install.
   If neither layout contains this file, route to BLOCKED. A root without
   `.saipen/` routes to INIT.

3. **Read and validate `.saipen/STATE.md`.** Check the registry-owned STATE
   shape, phase and `last_event`/style bindings. Corrupt or contradictory state
   routes to recovery before any ordinary work (`RECOVERY-01`, `OPS.md`). A
   legacy readable schema is upgraded only through the next canonical
   checkpoint. Files outrank model memory.

4. **Activate only applicable context.**

   - Skill injection present: load its SPEC and the smallest matching skill.
   - Active Work names a receipt: load the exact source, current Contract and
     coverage (`SOURCE-AUTHORITY-01`, `SOURCES.md`).
   - Current objective matches project knowledge: use `.saipen/KNOWLEDGE/INDEX.md`
     when fresh, then load only the smallest relevant active card/file set;
     missing/stale INDEX falls back to targeted discovery and is never authority.
   - USERPERSON is advertised by the effective context: load that effective
     profile before discretionary choices; otherwise create and warn nothing.
   - Runtime identity/capabilities are needed: query the runtime projection and
     load `RUNTIME.md`.

5. **Read `.saipen/BOARD.md`, then the active `LOG.md` tail.** Sealed log
   segments stay cold unless a parent-chain check needs them. Apply a pending
   `human_note` once through the canonical operation. If another actor wrote a
   newer checkpoint, discard remembered state and use the files.

6. **Resolve current input before persisted continuation.**

   Current input wins: the user's own message outranks the file. A persisted
   `next_action` is the
   previous checkpoint's pre-computed pick; where the mechanical router cannot
   re-derive it, confirm it against BOARD. Immediate means without asking, never without looking.

   - **Compound input first:** delegate lexical ordering and chain disposition
     to the mechanical resolver and `COMMANDS.md` before interpreting a segment.
   - A recognized command/shortcut resolves mechanically from `REGISTRY.json`.
     Human semantics come from `COMMANDS.md` (`CMD-ROUTING-01`,
     `CMD-COMPOUND-01`), never from CORE command prose.
   - A substantial audit, mission, specification, review handoff or correction
     is captured before interpretation; route details to `SOURCES.md`.
   - An actionable objective routes to goal execution in `MAINTENANCE.md`
     (`GOAL-01`). Read-only or plan-only requests retain that scope.
   - With no new instruction, ask the deterministic router for the current
     action. If the engine is unavailable, apply the registry/CORE Pick and
     routing invariants (`PICK-01`). A persisted `WAIT:` is returned verbatim.

7. **Load one owner, not the library.** Use `INDEX.md` to select the exact rule
   owner. For a command, load `COMMANDS.md`; for mechanics/recovery, `OPS.md`;
   for source authority, `SOURCES.md`; for execution/output policy,
   `EXECUTION.md`; for goal/autonomous behavior, `MAINTENANCE.md`; for a global
   state invariant only, `CORE.md`. `CONFORMANCE.md` and `CHANGELOG.md` are
   excluded from routine execution.

8. **Load exactly one phase delta.** Use the phase returned by the current
   route and open `phases/<phase>.md`. Replace it when the phase changes. Never
   infer a phase from stale remembered state.

9. **Checkpoint canonically.** Mutations use the mechanical operation layer.
   The checkpoint owner is `CHECKPOINT-01`: LOG, then BOARD, then STATE; read
   all three back and run the validator at ticket/phase boundaries. Never edit
   a dead `saipen_home` pointer by guesswork; route rebind through the command
   and operation owners.

## Routing failures

- Missing/unreadable owner or installation: BLOCKED with the exact path.
- Source integrity/coverage failure: `SOURCES.md` decides; never continue from
  a summary or memory.
- Recovery or pending operation: `OPS.md` decides before normal routing.
- Unknown command: resolve registered extensions, then show the mechanical
  command list; never invent a meaning.
- `CONFORMANCE.md` remains excluded unless the current task explicitly owns a
  conformance-corpus/validator change.

`CHANGELOG.md` is never part of cold start. `CONFORMANCE.md` is never routine
context. `STYLE.md` governs every chat response; artifacts remain professional.
