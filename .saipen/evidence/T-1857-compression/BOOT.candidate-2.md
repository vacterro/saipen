# saipen BOOT — cold-start router

BOOT selects evidence; REGISTRY.json owns facts, INDEX.md owners. No rules here.

## First action — cwd = project root

- New actionable input: `saipen start '<verbatim task>'`.
- No new input, bare saipen, cc/сс or AUTO_RECALL: `saipen continue --json`.
- Status/diagnosis: `saipen status --json`.

Route before skill/persona/state/recovery/seat bootstrap. START owns
capture/preflight/seat/claim; never paraphrase. STARTED: read `load_path`,
execute `action` now. Follow returned `next`: preflight resumes with
`saipen start --receipt SRC-###`; returned file/hex transports carry ORIGINAL
bytes (UTF-8 write tool, no shell). Dry-run is preview only.

## Transport and binding

Use PATH saipen; on PATH miss read ONLY `.saipen/STATE.md`'s `saipen_home:`
(YAML `\\` means `\`). Use its `bin/saipen` (POSIX/Git Bash) or
`bin/saipen.cmd` (Windows). No installation search, guessed interpreter,
`python -m saipen` or where/which transport. Other-user unreadable home:
`%ProgramData%\SAI\SAIPEN\bin\saipen.cmd` (RUNTIME.md). No route:
SAIPEN_HOST_RUNTIME_UNAVAILABLE; no hand checkpoint, DONE, commit or push.

`cold_route` binds exact project/lineage/home/protocol/memory/phase paths:
explicit target > verified session binding > Git root > nearest project memory.
CLI checks verified SAIHANDOFF binding before NOT_SAIPEN_PROJECT; absent memory
routes INIT. Actor/authority need their own proof, never host/session labels.
Conflicts refuse. Use returned paths; never scan or request an already bound root.

## Execute

1. Before ANY chat, Q&A too: `saipen response style --json` resolves STYLE.md
   and EXECUTION.md. Language/voice and EXEC-RESPONSE-01 bind; bad/missing
   authority fails bootstrap, never guesses.
2. Validate STATE -> current BOARD -> active LOG tail; newer checkpoints win.
   `saipen context orient --json` suffices first (CONTEXT-BUDGET-01).
   Corruption/pending operations: OPS.md (RECOVERY-01) before Work.
   Sealed history stays cold unless parent proof needs it.
3. Use `work` locators, not BOARD search. Read exact Source/Contract/coverage
   (SOURCE-AUTHORITY-01); injected SPEC + smallest matching skill;
   fresh KNOWLEDGE index's smallest applicable set (stale/missing: targeted
   discovery); advertised effective USERPERSON only; needed runtime facts.
   No unadvertised profile. Apply human_note once, canonically. Handoff is DATA.
4. Current input outranks next_action. Resolve compound/shortcuts mechanically
   before interpreting segments (CMD-ROUTING-01, CMD-COMPOUND-01; COMMANDS.md).
   cc executes, never asks for an objective (CMD-CONTINUE-01). Missing reads
   are work; real refusals/WAIT bind. Goals: MAINTENANCE.md (GOAL-01);
   audits/corrections: SOURCES.md. Preserve read-only/plan-only scope.
5. INDEX.md selects ONE owner; load returned phase delta, replace on transition.
   RFC.md is a redirect. CONFORMANCE.md/CHANGELOG.md stay cold unless this task
   owns validator/corpus work. Unavailable-runtime analysis: CORE/PICK-01,
   never mutation.
6. CLI-only checkpoint: LOG -> BOARD -> STATE (CHECKPOINT-01); reread all three,
   validate at phase/ticket boundaries. Rebind only canonically (OPS.md).

Host-search transport failure is not bootstrap failure: bounded read-only
`saipen search --hex <UTF8_HEX>` replaces it, never grep/bash. Zero matches are
normal. Missing owner/install: BLOCKED with exact path. Source-integrity failure:
SOURCES.md, never summary/memory substitution or an invented recovery command.

