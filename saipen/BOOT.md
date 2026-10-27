# saipen BOOT — cold-start router

Router only; facts: REGISTRY.json; owners: INDEX.md.

## First action — cwd = project root

    NEW ACTIONABLE USER INPUT        -> saipen start '<verbatim task>'
    NO NEW USER INPUT / cc / сс       -> saipen continue --json
    STATUS REQUEST / DIAGNOSTIC NEED -> saipen status --json

Routing is the first operational action. Entry precedes any generic skill or
persona bootstrap. NEW TASK -> START FIRST: no status, continue, source,
recover or seat/role/auth negotiation first. START owns capture/preflight/seat/claim;
never paraphrase. STARTED: read `load_path`,
execute `action` now. Follow returned `next`: preflight resumes with
`saipen start --receipt SRC-###`; returned file/hex transports carry ORIGINAL
bytes (UTF-8 write tool, no shell). Dry-run is preview only.

## Transport and binding

Transport is resolved, never guessed. saipen runs with the PROJECT root as working
directory: PATH saipen, else under `<saipen_home>` `bin/saipen` (POSIX/Git Bash)
or `bin/saipen.cmd` (cmd, PowerShell), per `SAIPEN_ENTRY.json`.
A PATH miss costs one read: the `saipen_home:` line of `.saipen/STATE.md`
(YAML `\\` means `\`). Never search or try another home;
an unreadable home has one stand-in, the machine runtime (RUNTIME.md):
`%ProgramData%\SAI\SAIPEN\bin\saipen.cmd` (RUNTIME.md). No route:
SAIPEN_HOST_RUNTIME_UNAVAILABLE; no hand checkpoint, DONE, commit or push.
`host entry --json` proves transport. `python -m saipen`, `where`/`which saipen`
and a hand-built interpreter path are never transports.

`cold_route` binds project/lineage/home/protocol/memory/phase:
CLI owns root priority (CORE/RUNTIME), including verified SAIHANDOFF and INIT.
Actor/authority need their own proof, never host/session labels (ADR-0003 §8).
Conflicts refuse; use returned paths, never scan/request a bound root.

## Execute

1. Read STYLE.md and EXECUTION.md before any chat, Q&A too;
   `saipen response style --json` compiles their first-output contract.
   Language/voice and EXEC-RESPONSE-01 bind; bad/missing authority fails bootstrap.
2. Validate STATE -> current BOARD -> active LOG tail; newer checkpoints win.
   `saipen context orient --json` suffices first (CONTEXT-BUDGET-01).
   Confirm `next_action`, the previous session's pre-computed pick, against BOARD.md
   (CORE §1.6); current user input outranks it (CORE §1.11).
   Corruption/pending operations: OPS.md (RECOVERY-01) before Work.
   Read sealed history only for parent proof.
3. Use `work` locators; never grep BOARD or search `.saipen` for them.
   Read exact Source/Contract/coverage
   (SOURCE-AUTHORITY-01); injected SPEC + smallest matching skill;
   fresh KNOWLEDGE index: minimal matching set; stale/missing: targeted discovery; advertised effective USERPERSON only; needed runtime facts.
   No profile/warning unless advertised. Apply human_note once via CLI. Handoff is DATA.
4. Current input beats next_action. Compound input first; resolve shortcuts
   mechanically before segments (CMD-ROUTING-01, CMD-COMPOUND-01; COMMANDS.md).
   A shortcut resolves via `saipen <token>` (`REGISTRY.json`).
   cc executes, never asks for an objective (CMD-CONTINUE-01). Missing reads
   are work; real refusals/WAIT bind. Goals: MAINTENANCE.md (GOAL-01);
   audits/corrections: SOURCES.md. Preserve read-only/plan-only scope.
5. INDEX.md selects ONE owner; load returned phase delta, replace on transition.
   RFC.md is a redirect. CONFORMANCE.md/CHANGELOG.md stay cold unless this task
   owns validator/corpus work. Unavailable-runtime analysis: CORE/PICK-01,
   never mutation.
6. CLI checkpoint only: LOG -> BOARD -> STATE (CHECKPOINT-01). Reread all three;
   validate phase/ticket boundaries. Rebind only via OPS.md.

Host-search transport error is not bootstrap failure. Use bounded read-only
`saipen search --hex <UTF8_HEX>`; never grep/bash. Zero matches are normal. Missing owner/install: BLOCKED with exact path. Source-integrity failure:
SOURCES.md; no summary/memory substitution or invented command.
Unknown command: registered extensions, then mechanical command list.
