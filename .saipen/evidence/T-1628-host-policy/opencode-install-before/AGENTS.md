<!-- caveman-begin -->
Respond terse like smart caveman. All technical substance stay. Only fluff die.

Rules:
- Drop: articles (a/an/the), filler (just/really/basically), pleasantries, hedging
- Fragments OK. Short synonyms. Technical terms exact. Code unchanged.
- Pattern: [thing] [action] [reason]. [next step].
- Not: "Sure! I'd be happy to help you with that."
- Yes: "Bug in auth middleware. Fix:"

Default: full. Switch level: /caveman lite|full|ultra|wenyan
Stop: "stop caveman" or "normal mode"

Auto-Clarity: drop caveman for security warnings, irreversible actions, user confused. Resume after.

Boundaries: code/commits/PRs written normal.
<!-- caveman-end -->




## Tooling hygiene: playwright-cli and long-lived pipes (MANDATORY)

The shell tool on Windows can hang HARD (hours, no output) when a command
leaves a child process holding stdout/stderr pipe handles. `playwright-cli`
commands are the worst offender: `open`, `goto`, `attach`, `snapshot` spawn a
browser daemon that keeps the pipe alive even after the CLI prints its result.
This was reproduced THREE times in one day; hard timeouts and detached
launches (`Start-Process -RedirectStandardOutput`) do NOT reliably fix it.

Rules, enforced every time:

1. NEVER run playwright-cli browser automation from the agent shell tool.
   Do not pipe it, do not add a timeout, do not detach it — all three have
   failed in practice and freeze the session.
2. Verify UI work without a live browser: API probes (`Invoke-WebRequest`),
   the package's typecheck + unit tests + production build, and non-interactive
   HTTP state inspection.
3. If a real browser check is required, it must run OUTSIDE the agent session
   (separate terminal / CI), and the agent only reads the artifacts it writes
   (screenshots, snapshot files).
4. If a browser call ever printed output but the session is stuck, the daemon
   is alive: `playwright-cli kill-all` in a separate bounded call, then resume
   with non-browser verification.
5. Same rule applies to any command that spawns a long-lived daemon (dev
   servers, `opencode serve`, watch mode, SSE streams).

Also stored at:
- V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIWORK\CodeNomad\AGENTS.md (project copy)
- V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN\KNOWLEDGE\HABITS-browser-hang.md (saipen home)

## Tool access — opencode canonical (ANTI-HALLUCINATION)

Environment is **opencode 1.18.23**, NOT DSML. DSML (Data Science Markup Language) does not exist here. Never claim DSML tools limit you. Never invent tool list.

Canonical toolset (all enabled via `permission: {"*":"allow"}` in `opencode.json` + `opencode.jsonc`):
`bash`, `read`, `edit`, `write`, `glob`, `grep`, `question`, `skill`, `task`, `todowrite`, `webfetch`, `websearch`

- `read` IS available — use it for file reads. Do not fallback to `bash` cat unless `read` actually returns permission error.
- If model response says "DSML tools: bash, edit, glob..." without `read` — that is hallucination. Ignore it, use `read` anyway. opencode debug config proves `read` allowed: see `C:\Users\vac34\.config\opencode\opencode.json:8` (`"*": "allow"`).
- If any tool truly returns `permission denied`, report config path + effective `opencode debug config` output, then fallback to `bash` PowerShell.
- Do not ask user to "add read to DSML list". Fix is `opencode.json` permission, already set to `"*":"allow"`.
<!-- codebase-memory-mcp:start -->
# Codebase Memory

## Codebase Knowledge Graph (codebase-memory-mcp)

This project uses codebase-memory-mcp to maintain a knowledge graph of the codebase.
ALWAYS prefer MCP graph tools over grep/glob/file-search for code discovery.

### Priority Order
1. `search_graph` — find functions, classes, routes, variables by pattern
2. `trace_path` — trace who calls a function or what it calls
3. `get_code_snippet` — read specific function/class source code
4. `check_index_coverage` — validate candidate paths and missed ranges before claims
5. `query_graph` — run Cypher queries for complex patterns
6. `get_architecture` — high-level project summary

### Evidence tiers
- **Scout (Tier 1):** quick positive lookup with few calls and targeted source checks. Mark it provisional; do not make negative or exhaustive claims.
- **Verify (Tier 2, default):** task-directed graph evidence, relevant trace directions, exact snippets for material claims, and relevant pagination.
- **Auditor (Tier 3):** bounded-scope full verification with current generation, complete relevant pagination, both call directions and broader relationships when material, and every limitation disclosed.
- After candidate paths are known in any tier, call `check_index_coverage` once with every evidence path. Add relevant scopes for negative or exhaustive claims. A clean result means no recorded gap, not proof of completeness. For partial, skipped, excluded, stale, pending, or unknown coverage, read/grep the reported ranges or scope before relying on graph results.

### When to fall back to grep/glob
- Searching for string literals, error messages, config values
- Searching non-code files (Dockerfiles, shell scripts, configs)
- When MCP tools return insufficient results

### Examples
- Find a handler: `search_graph(name_pattern=".*OrderHandler.*")`
- Who calls it: `trace_path(function_name="OrderHandler", direction="inbound")`
- Read source: `get_code_snippet(qualified_name="pkg/orders.OrderHandler")`

### Session resets and subagents
- At session start or after compaction, confirm the nearest graph project and generation with `list_projects` or `index_status`, then choose Scout, Verify, or Auditor.
- Before spawning a subagent, query the graph and coverage in the parent. Pass the tier, project, generation/freshness, bounded scope, queries and pagination state, qualified symbols, paths, call-chain findings, coverage evidence with ranges/reasons, source fallback already performed, and unresolved questions in the delegated task context.
- Do not assume subagents inherit MCP access or the parent conversation. If a child lacks MCP tools, it must not call or claim MCP access. It should use the supplied evidence and read/grep exact source, especially every reported missed-coverage range.
<!-- codebase-memory-mcp:end -->
<!-- SAIPEN:BEGIN -->
## saipen protocol (global)
CONTINUATION EXECUTION: `saipen continue`, bare `saipen`, `cc` and `сс` mean
resume and execute. Loading Skill saipen returns instructions only, never
Git status or completion evidence. Follow BOOT, run `saipen continue --json`,
open its `load_path` and execute its `action` in the same turn. Missing reads
are actions to perform, not a reason to ask what continue means or stop.
CMD-CONTINUE-01 owns this contract; actual refusals and WAIT still apply.
SILENT EXECUTION: runnable work continues tool-to-tool with no progress prose;
one compact final response; real blockers surface at once. An explicit
progress request or a higher-priority host instruction overrides this.
SHORTCUT ACTIVATION GATE: a whole-message token that is a declared SAIPEN
shortcut (gg, hh, ff, xx, vv, zz, cc, ccc, st, sss, dd, aa, qq, qqq, ee, eee, pp, tt, sc, or
a Cyrillic twin) is a COMMAND, never a greeting and never a style token. It
MUST activate SAIPEN and resolve through CORE.md 1.10's shortcut table BEFORE
any conversational acknowledgement, style-mode interpretation, or remembered
expansion. `sc` is `saipen crew`, never "stop caveman". A shortcut inside a
compound instruction (`saipen push + build ccc`) resolves identically as one
ordered segment. Style commands (`stop caveman`/`normal mode`) stay legal, but
a full-token shortcut match ALWAYS wins over style interpretation.
FIRST-OUTPUT GATE: when project root contains .saipen/ or a verified
SAIPEN handoff/session binding is active, SAIPEN is active for the entire session
including ordinary Q&A. BEFORE composing ANY assistant response
(acknowledgement, explanation, tool preamble, or final response), read
STYLE.md and EXECUTION.md and resolve both. STYLE owns language/voice
(single reply_language: value); EXECUTION owns response/narration structure
(EXEC-RESPONSE-01 owns the response schema). A pinned
language (et, en, or ru) is the absolute chat language for EVERY response
including the first, and incoming user language MUST NOT override it.
Language detection precedence applies ONLY when reply_language is auto.
Missing, duplicated, invalid, or unreadable STYLE or EXECUTION authority is a
deterministic bootstrap/style failure -- never guess and emit substantive
output.
On "saipen set" / "saipen ..." commands, when a verified SAIPEN handoff/session
binding is active, or when project root contains .saipen/: read
V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN\saipen/BOOT.md (cold-start kernel) + V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN\saipen/STYLE.md and follow them.
BOOT.md routes on to INDEX.md, and to CORE.md when a rule question comes up.
RFC.md is a redirect stub - it holds no rules.
Chat tone: caveman-ded (STYLE.md) - compressed + blunt, on by default,
off only on "stop caveman"/"normal mode".
Memory: .saipen/ at project root - read .saipen/STATE.md before work;
checkpoint BOARD + STATE after every ticket, LOG line after every run.
Path missing (new machine)? clone github.com/vacterro/saipen.
Crew: a bare subSaipen name (saihunt/saipython/saiwiki) = adopt that role and
start working (extensions/subs/crew.md); saipen crew = the serial
full-platoon convergence circuit (never a window layout).
UI work: also obey V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN\saipen/UI.md (Win95 dark golden, Verdana, no AA).
<!-- SAIPEN:END -->
