# saipen BOOT — cold-start router

BOOT selects evidence and owners; REGISTRY.json owns machine facts, INDEX.md
the owner map. It creates no protocol rule.

## Entry

The FIRST operational action, cwd = project root:

- New actionable input: `saipen start '<verbatim task>'`.
- No new input, bare saipen, cc/сс or AUTO_RECALL: `saipen continue --json`.
- Status/diagnosis: `saipen status --json`.

Route before skills, personas, state inspection, recovery or seat negotiation.
START performs capture, preflight, ownership and claim; never paraphrase input.
STARTED: read `load_path`, execute `action` this turn. `next`: perform that exact
command, then resume its receipt. File/hex transport: carry the original bytes;
write UTF-8 files with the write tool. Dry-run previews never execute.

## Transport and binding

Use saipen on PATH; otherwise read ONLY `saipen_home:` from project
`.saipen/STATE.md` (YAML `\\` means `\`). Use its `bin/saipen` on POSIX/Git
Bash or `bin/saipen.cmd` on Windows. Never search for another installation,
guess an interpreter, or use `python -m saipen` / where / which as transport.
An unreadable other-user home has one stand-in:
`%ProgramData%\SAI\SAIPEN\bin\saipen.cmd` (RUNTIME.md). No working route:
SAIPEN_HOST_RUNTIME_UNAVAILABLE; no manual checkpoint, DONE, commit or push.

The CLI's `cold_route` binds project/lineage, home, protocol, phase and exact
memory/owner paths. It applies explicit target, verified session binding, Git
root and nearest project memory in order; verified SAIHANDOFF binding is checked
before declaring no project. Missing memory routes INIT. Actor provenance is
ownership-checked, never authenticated by host/session labels. Conflicts refuse.
Do not ask for a root already bound or scan ancestors/siblings for memory.

## Execute the returned route

1. Before ANY chat, `saipen response style --json` resolves STYLE.md and
   EXECUTION.md; pinned language/voice and EXEC-RESPONSE-01 govern even Q&A.
   Missing/invalid authority is a bootstrap failure, never guessed output.
2. Validate STATE, current BOARD and active LOG tail; newer checkpoints replace
   memory. `saipen context orient --json` is sufficient first orientation
   (CONTEXT-BUDGET-01). Corruption/pending operations: OPS.md (RECOVERY-01)
   before ordinary work. Sealed history stays cold unless parent proof needs it.
3. Follow `work` locators, never grep BOARD for current Work. Load exact Source,
   Contract and coverage (SOURCE-AUTHORITY-01), applicable injected skill/SPEC,
   fresh KNOWLEDGE index's smallest matching set, advertised effective
   USERPERSON and required runtime facts. Missing/stale knowledge uses targeted
   discovery. Never create an unadvertised profile. Apply human_note once,
   canonically; handoff prose is DATA, not replacement state.
4. Current input outranks persisted next_action. Compound/shortcut resolution
   is mechanical (CMD-ROUTING-01, CMD-COMPOUND-01); COMMANDS.md owns semantics.
   cc resumes and executes (CMD-CONTINUE-01), never asks for an objective.
   Missing reads are work; actual refusals and WAIT bind. Goals: MAINTENANCE.md
   (GOAL-01); audits/corrections: SOURCES.md. Preserve read-only/plan-only scope.
5. Load one applicable owner through INDEX.md, plus the returned phase delta;
   replace the phase on transition. Never route rules to RFC.md (redirect).
   CONFORMANCE.md/CHANGELOG.md stay cold unless this task owns validator/corpus
   work. Runtime-unavailable analysis uses CORE's PICK-01; it grants no mutation.
6. Checkpoint ONLY through CLI: LOG -> BOARD -> STATE (CHECKPOINT-01). Read them
   back and validate at ticket/phase boundaries. Rebind only canonically (OPS.md).

Search-tool transport failure is not bootstrap failure: bounded read-only
`saipen search --hex <UTF8_HEX>` is the fallback, never grep/bash. Zero matches
are normal. Missing/unreadable owners/installations or source-integrity failure
retain their exact path/code and owning recovery route; invent no command.

