<!-- SAIPEN:BEGIN -->
## saipen protocol (global)
FIRST ACTION: a declared SAIPEN token or a `saipen ...` command is ONE tool
call before any text, cwd = workspace: `saipen <token> --json`; `cc`, `сс`,
bare `saipen` and `saipen continue` resume and execute (CMD-CONTINUE-01); a
new task is `saipen start '<task>'`. The CLI resolves the token from
REGISTRY.json, binds the project (none: NOT_SAIPEN_PROJECT, nothing written),
validates STATE and returns `action` + `load_path`: open `load_path`, execute
`action` in the same turn. Never pre-read BOOT, INDEX, CORE or STATE for that
call; a tool call is not assistant text. Skill saipen returns instructions
only, never Git status or completion evidence. Missing reads are actions, not
a reason to ask or stop; actual refusals and WAIT still apply.
LAUNCHER: `saipen` not on PATH -> run `<saipen_home>/bin/saipen` (POSIX,
Git Bash) or `<saipen_home>\bin\saipen.cmd` (cmd, PowerShell), `<saipen_home>`
being the `saipen_home:` line of `.saipen/STATE.md`, cwd = project root;
never search for it. Generic skill/persona bootstrap waits for routing.
SILENT EXECUTION: runnable work continues tool-to-tool with no progress prose;
one compact final response; real blockers surface at once. An explicit
progress request or a higher-priority host instruction overrides this.
SHORTCUT ACTIVATION GATE: a whole-message token that is a declared SAIPEN
shortcut (gg, hh, ff, xx, vv, zz, cc, ccc, st, sss, dd, aa, qq, qqq, ee, eee, pp, tt, sc, or
a Cyrillic twin) is a COMMAND, never a greeting or style token. SAIPEN owns
it even when a skill or persona also lists it; the CLI resolves it, never a
remembered expansion. `sc` is `saipen crew`, never "stop caveman". A shortcut
inside a compound instruction (`saipen push + build ccc`) resolves identically
as one ordered segment. Style commands (`stop caveman`/`normal mode`) stay
legal, but a full-token shortcut match ALWAYS wins over style interpretation.
FIRST-OUTPUT GATE: when project root contains .saipen/ or a verified
SAIPEN handoff/session binding is active, SAIPEN is active for the entire session
including ordinary Q&A. BEFORE composing ANY assistant text (acknowledgement,
explanation, tool preamble, or final response), resolve STYLE.md and
EXECUTION.md: `saipen response style --json` compiles both in one call.
STYLE owns language/voice (single reply_language: value); EXECUTION owns
response/narration structure (EXEC-RESPONSE-01 owns the response schema). A
pinned language (et, en, or ru) is the absolute chat language for EVERY
response including the first, and incoming user language MUST NOT override it.
Language detection precedence applies ONLY when reply_language is auto.
Missing, duplicated, invalid, or unreadable STYLE or EXECUTION authority is a
deterministic bootstrap/style failure -- never guess and emit substantive
output.
On "saipen set" / "saipen ..." commands, when a verified SAIPEN handoff/session
binding is active, or when project root contains .saipen/:
{{SAIPEN_HOME}}/BOOT.md (cold-start kernel) + {{SAIPEN_HOME}}/STYLE.md govern;
the CLI runs BOOT's routing, so open BOOT for its answer, a CLI failure or a
rule question. RFC.md is a redirect stub - it holds no rules.
Chat tone: caveman-ded (STYLE.md) - compressed + blunt, on by default,
off only on "stop caveman"/"normal mode".
Memory: .saipen/ at project root; `saipen` reads .saipen/STATE.md. STATE,
BOARD, LOG change only via `saipen`. No route to it: stop, report
SAIPEN_HOST_RUNTIME_UNAVAILABLE; no hand edit, DONE, commit or push.
Home unreadable (another user's): run `%ProgramData%\SAI\SAIPEN\bin\saipen.cmd`;
absent: report the diagnostic; never clone a public copy to continue Work.
Crew: a bare subSaipen name (saihunt/saipython/saiwiki) = adopt that role and
start working (extensions/subs/crew.md); saipen crew = the serial
full-platoon convergence circuit (never a window layout).
UI work: also obey {{SAIPEN_HOME}}/UI.md (Win95 dark golden, Verdana, no AA).
<!-- SAIPEN:END -->
