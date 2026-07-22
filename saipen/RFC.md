# SAIPEN Protocol (RFC)

## Part 1: CORE (Continuation Protocol)

### 1.1 Normative Rules
The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in RFC 2119.

- Agent MUST read `STATE.md`, `BOARD.md`, and tail of `LOG.md` before execution. All three, and `KNOWLEDGE/`/`kitchen/`, live under `.saipen/` at the project root -- later mentions in this document may drop the prefix for brevity, the location never changes.
- Agent MUST NOT rely on chat context for project state.
- Agent MUST degrade capabilities if host tools are missing.
- Agent MUST NOT write secrets (API keys, tokens, passwords, private credentials) into `STATE.md`, `BOARD.md`, `LOG.md`, `KNOWLEDGE/`, `.saipen/kitchen/`, or `.saitranslate/kitchen/` -- every one of these is scratch or committed content meant to be read by other agents, kitchen files included. A secret discovered mid-task gets redacted in whatever gets written (`sk-***`, not the real value) and the user gets told to rotate it, same as any other finding.
- Agent MUST NOT perform a destructive operation without explicit user confirmation, unless the active ticket itself pre-authorizes it AND the operation is reversible. Destructive includes at minimum: force-push, branch deletion, history rewrite, schema/database drop, mass file deletion, user data deletion, and any irreversible migration. This governs SAIPEN's own operation (SHIP, CLEAN, and any phase that touches disk or git) -- it does not relax or replace whatever confirmation discipline the operating agent's own platform already enforces, it is the floor every SAIPEN-conformant agent MUST meet regardless of vendor.

### 1.2 File Model
- **STATE.md**: MUST contain frontmatter: `phase`, `task`, `next_action`, `blocker`, `agent`, `saipen_version`, `mode`, `updated`. `saipen_version` (integer) records which protocol version wrote this state, and doubles as the version guard below -- one field, not two (v7.23.0 collapsed a separate `schema_version` that never earned its own complexity in practice; re-split if a real case for independent shape-versioning ever actually arises). `saipen_home` (string) is a recognized MAY field: § 1.7's bootloader pointer, the absolute path to the SAIPEN home on the machine that last checkpointed -- MAY be absent on states written before v7.25.0. `next_action` MUST be an immediately executable command -- this includes the exact form `WAIT: <the specific question or decision needed>`, which counts as executable because "ask this exact thing and stop" is itself an unambiguous action. `WAIT:` is legal ONLY for a manual-verify gate, a destructive-operation confirmation, a first-publish confirmation, the user's own explicit brake, or -- narrowly -- `INIT` bootstrap when `BOARD.md` is empty and no project goal exists anywhere yet (`phases/init.md`): that bootstrap `WAIT:` MUST ask for the first goal or raw backlog only, never for context `STATE.md`/`BOARD.md`/`LOG.md` would otherwise already provide. Never a stand-in for "figure out project context," which the agent is already required to get from `STATE.md`/`BOARD.md`/`LOG.md`, not the user. `mode` is written per § 1.3 capability negotiation. `task` MAY be the literal string `none`. `blocker` MUST be non-empty when `phase: BLOCKED` -- a blocked state with no stated reason is not conformant. `updated` MUST be ISO-8601 **UTC** specifically (`Z` suffix or `+00:00`, never a local offset) -- Recovery's "STATE stale vs LOG/BOARD" comparison (§ 1.5) silently miscompares across agents in different timezones otherwise. MAY contain `goal_mode: true|false` (default `false`) — see § 2.4. While `goal_mode: true`, MUST also carry `goal_waves` and `goal_tickets` (integers, both start at `0`) — the persisted safety-valve counters § 2.4 defines; absent/cleared once `goal_mode` returns to `false`.
- **Version guard**: If a project's `saipen_version` is HIGHER than what this agent's own copy of RFC.md defines as current, a newer protocol wrote this state and this agent is running a stale copy -- it MUST NOT silently proceed or rewrite the value downward. Degrade to `mode: read-only` and report the mismatch, or `BLOCKED` if even reading isn't safe, until the RFC copy is refreshed.
- **BOARD.md**: MUST track ticket status via section headings `## DOING` / `## TODO` / `## DONE` / `## BLOCKED`. Every ticket line MUST follow this exact shape: `- [ ] T-### description`, checkbox `[ ]` open / `[x]` done / `[/]` in-progress, optionally followed by any of ` | needs: T-###,T-###`, ` | owner: AgentID`, ` | claim_time: ISO8601`, ` | blocker: facts + dead ends`, ` | verify: <command or criterion>` (`phases/plan.md`'s "independently verifiable" ticket shape, made concrete on the ticket itself) as space-pipe-separated fields -- only the fields that apply, in any order. **Changing a ticket's status MUST move its line: cut from the old heading, paste under the new one. A ticket MUST NOT appear under two headings at once, and MUST NOT be left duplicated under its old section.** `T-###` IDs MUST be unique and MUST NOT be reused once assigned, even after the ticket is `DONE` or pruned. A literal `|` inside `description` MUST be escaped as `\|` -- unescaped, it is indistinguishable from a field separator. `## BLOCKED` holds ticket-level blocks only (`phases/verify.md`'s debug cap: facts + dead ends noted via the `| blocker:` field) — distinct from session-level `STATE.phase: BLOCKED` (§ 1.6, `phases/blocked.md`), which is reserved for when no ticket anywhere on the board is workable. The Pick Rule (§ 1.6) only ever selects from `## TODO`, so a `## BLOCKED` ticket is automatically excluded without extra filtering logic. **Cyclic `needs:`** (CONFORMANCE.md requires the graph stay acyclic): on detection, the agent MUST move every ticket in the cycle to `## BLOCKED` with `| blocker: dependency cycle: T-###,T-###,...`, LOG a `DEC` line, and continue with other workable tickets -- never pick from inside a known cycle. **Dangling `needs:`** (a referenced `T-###` doesn't exist anywhere on the board) is worse than a cycle, not milder -- a cycle at least gets caught by acyclic-graph checking, but a reference to a ticket that was never real just leaves the Pick Rule permanently unsatisfiable with zero signal anywhere that anything is wrong. Same remedy: move the ticket to `## BLOCKED` with `| blocker: needs nonexistent T-###`, LOG a `DEC` line, keep working other tickets.
- **LOG.md**: Append-only event graph. Every line MUST follow this exact
  shape, in this order: `- DATE [E-###] [parent: E-###] [T-###] TAXONOMY: text`.
  - `DATE` MUST be human-readable `DD.MM.YY HH:mm` (not ISO-8601 -- that
    lives only in `STATE.md updated`). Agent MUST use the real current time,
    never a placeholder (`XX`, `TODO`, etc. are non-conformant).
  - `[E-###]` (numeric Event ID) is MUST, always -- phase names
    (`[HUNT]`, `[BUILD]`) are NOT a substitute and MUST NOT appear here.
    IDs MUST be unique and MUST increase monotonically -- never reused,
    never assigned out of order.
  - `[parent: E-###]` is MAY (links the event graph; omit for a fresh root). When present, it MUST reference an `E-###` that already exists earlier in the file -- a dangling parent breaks the graph Recovery (§ 1.5) depends on.
  - `[T-###]` (ticket reference) is MAY -- omit for ticket-less events
    (HUNT sweeps, SHIP, session-level DEC/RUN), or write the literal
    `[T-none]` to mark ticket-lessness explicitly (equally legal -- it
    distinguishes "no ticket" from "forgot the field", and established
    practice already used it; ratified v7.24.0). Any other non-numeric
    value in this position is non-conformant.
  - `[agent: <id>]` (writer identity, same id convention as `STATE.md
    agent:`) is MAY, placed after the ticket ref and before the taxonomy.
    Single-agent sessions SHOULD omit it -- `STATE.md agent:` already says
    who's working, repeating it per line is noise.
  - `TAXONOMY` MUST be exactly one of: `RUN` (command executed, result),
    `DEC` (decision made, why), `H` (hypothesis, test, verdict). No other
    label is conformant -- a phase name is not a taxonomy value.
  - Commentary voice (STYLE.md) wraps AROUND this exact skeleton; it never
    changes the skeleton's shape.
  - When a phase doc instructs "LOG exactly `RUN: X`" (or `DEC:`/`H:`) as a
    fixed format, that fixed text is the `TAXONOMY: text` portion only --
    the full skeleton above (`DATE`, `[E-###]`, etc.) always still applies.
    No phase doc's fixed-format instruction is ever license to write just
    the bare taxonomy:text fragment as the whole line.
- **KNOWLEDGE/**: Directory for durable truths. MUST NOT contain event histories -- that is the actual constraint, not the filename. Two valid shapes, pick whichever fits the content: a living reference doc with a descriptive name (`architecture.md`, `traps.md`) that gets edited in place as understanding improves, or a numbered ADR (`ADR-001.md`, `ADR-002.md`, ...) recording one immutable decision + its reasoning, never edited once written. Either way: durable truth, never a log of events.
- **kitchen/**: Directory for intermediate, half-finished files, scratchpads, and work-in-progress data. Agents MUST store temporary work here to avoid cluttering the project root. If an agent terminates mid-task, the successor MUST inspect `kitchen/` to resume work seamlessly. `TRANSLATE` (§ 2.1) keeps its own, separate `.saitranslate/kitchen/` — never shared with this one.

### 1.3 Capability Negotiation (Two-Way Handshake)
1. **Protocol Demands**: `STATE.md` MAY define `requires: [filesystem, git, shell, python]`.
2. **Agent Capabilities**: Agent MUST evaluate host against requirements.
3. **Mode Lock**: Agent MUST write operating mode to `STATE.md` (`mode: full | read-only | no-publish | manual-verify`).
   - Missing Git: `mode: no-publish`. Agent MUST NOT transition to `SHIP`.
   - Missing Shell: `mode: manual-verify`.
   - Missing Filesystem Write: `mode: read-only`. Agent MUST NOT transition to `BUILD`, `SHIP`, `CLEAN`, `TRANSLATE`, or make any `ADD`/`HUNT` change beyond reporting findings -- every phase that would write to disk is out of reach. The agent MAY still read, analyze, and report; it advises, it does not act.
4. **Optional Parallel Execution**: `subagents` (parallel task/agent
   spawning) is never required and never gates a phase or sets `mode`.
   Its trigger is independence, not speed -- `HUNT`'s 6 signal categories
   (`phases/hunt.md`) don't depend on each other's results, so where
   subagents are available they MAY run concurrently instead of in turn.
   Absence MUST fall back silently to sequential execution -- same result.

### 1.4 Claim & Ownership
- Claiming a ticket = moving it to `## DOING` with `owner: <AgentID>` and `claim_time: <ISO8601 UTC>` set on its line. When one agent is provably alone on a project (the common single-agent case), the fields are OPTIONAL -- but any agent that even suspects it is not alone MUST set both on every ticket it picks.
- **Active claim**: `claim_time` less than 15 minutes old. The owner MUST refresh `claim_time` before it goes stale while holding the ticket: at every checkpoint (§ 1.5), AND as a standalone `BOARD.md`-only touch at least every 10 minutes of continuous mid-ticket work. Checkpoints alone cannot carry this duty -- § 1.5 checkpoints fire after tickets, so a 40-minute ticket would starve its own claim mid-work and make theft of a live ticket legal (v7.28.0 tied refresh to checkpoints only; fixed v7.30.0). Liveness is decided by reading `BOARD.md` alone; a recent `LOG.md` line stamped `[agent: <owner>]` (§ 1.2) MAY serve as supporting evidence, never as the primary test. (The pre-v7.28.0 "or actively writing to LOG.md" test was undecidable -- a shared file's mtime can't attribute activity to any particular owner).
- **Stale claim**: `claim_time` 15+ minutes old -> forfeit. The next agent MAY take the ticket over: LOG a `DEC` line recording the takeover (old owner, observed staleness), set its own `owner:`/`claim_time`, and inspect `kitchen/` for the predecessor's half-done work (§ 1.2) before redoing anything from scratch.
- A `## DOING` ticket carrying NO `owner:`/`claim_time` at all is unclaimed by definition (a crashed single-agent session, or pre-claim history): any agent MAY adopt it the same way -- LOG the `DEC`, check `kitchen/`, continue the work.
- **Conflicting claim writes**: the first write that lands in `BOARD.md` wins -- but whole-file saves mean a concurrent second save can silently clobber the first, so "landing" MUST be verified, never assumed: after writing a claim, re-read `BOARD.md` and confirm your claim actually survived. Your claim is absent or overwritten -> you lost, whatever the wall-clock order was; re-read and pick a different ticket -- never re-assert a claim over the winner's.
- **Concurrency boundary**: Core's safety model is claim-serialized tickets with ONE agent writing `.saipen/` at any instant. Two-plus agents making uncoordinated concurrent checkpoints is outside Core's envelope -- `E-###` allocation races and last-writer-wins `STATE.md` are exactly why (the validator catches that wreckage after the fact; nothing in Core prevents it up front, by design -- SPEC.md: a state protocol, not a distributed consensus algorithm). An agent that observes `STATE.md` with `agent:` other than itself and `updated:` fresher than the claim window MUST assume a live concurrent session: work only tickets it claims under this section's rules.

### 1.5 Checkpointing & Recovery
- **Checkpointing**: MUST checkpoint after every ticket or before session termination. Three separate files cannot be written as one atomic transaction, so order stands in for atomicity: **(1)** append the `LOG.md` event, **(2)** write `BOARD.md` (temp file + rename), **(3)** write `STATE.md` (temp file + rename) *last* -- `STATE.md` is the commit pointer. A crash between any two steps always leaves `STATE.md` truthfully behind `LOG.md`/`BOARD.md`, never ahead of them, which is exactly the condition Recovery below already knows how to fix. Writing `STATE.md` first (or in any other order) can leave it claiming something `BOARD.md` doesn't yet reflect -- a crash Recovery would not reliably catch.
- **Dirty tree on continuation**: uncommitted project changes at cold-start are a NORMAL protocol state, never an anomaly to warn the user about -- work commits at `SHIP`, not per checkpoint, so an in-flight ticket's edits are uncommitted by design. Before touching anything, the agent MUST attribute them: cross-reference `git status`/`git diff --stat` against the open `DOING` ticket's scope, the `LOG.md` tail, and `kitchen/`. Attributable to the in-flight ticket -> that IS the ticket's work-so-far: continue or adopt it (§ 1.4) and let the changes fold into that ticket's eventual commit -- no warning, no ceremony. NOT attributable to any ticket (the user's own manual edits, another tool's output) -> leave them exactly as they are: MUST NOT commit, revert, stash, or clean someone else's uncommitted work -- silently reverting it is user-data deletion (§ 1.1), and committing it stamps authorship over changes nobody reviewed. Only when unattributed changes sit in the very files the next action must touch does the agent stop and ask -- that is § 1.1's existing destructive-op confirmation gate, not a new `WAIT:` category.
- **Recovery**: If `STATE.md` is stale but `LOG.md` or `BOARD.md` is newer, `git status` is ground truth where git is available. Without git (`mode: no-publish`, § 1.3, or no repo at all) -- fall back to filesystem modification timestamps on `LOG.md`/`BOARD.md`/`STATE.md` themselves: whichever of the three was written most recently, cross-referenced against the Checkpointing write order above (LOG, then BOARD, then STATE last), tells you how far a crash got without needing git at all. One § 1.4 caveat on that heuristic: a standalone `claim_time` refresh legitimately touches `BOARD.md` with no `STATE.md` write after it, mimicking a crash between checkpoint steps 2 and 3 -- before rebuilding anything, check whether `BOARD.md`'s difference from what `STATE.md`/`LOG.md` imply is claim fields only; if so, that is a live claim being kept fresh, not a crash. Before overwriting a corrupt or stale `STATE.md`, copy it to `.saipen/recovery/<timestamp>-STATE.md` -- Recovery reconstructs from evidence, it does not destroy evidence. Rebuild `STATE.md` based on latest `LOG.md` entry and open DOING ticket. If the recovered `STATE.md` shows (or `LOG.md` shows a `DEC` pivot line for) `goal_mode: true`, `goal_waves`/`goal_tickets` MUST be rebuilt too -- count wave/ticket-completion events in `LOG.md` since that pivot line, never assume `0`. Losing the count on recovery is exactly the failure § 2.4's safety valve exists to prevent.

### 1.6 Core State Machine & Ticket DAG
`INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`

- **Ticket DAG**: Tickets MUST define dependencies using `needs: [T-XXX]`. **Pick Rule**: Agents MUST NOT pick a `TODO` ticket unless all its `needs:` are marked `DONE`, and MUST NOT pick a ticket under another agent's active claim (§ 1.4) -- the claim rule existed since v1 but the Pick Rule never referenced it, so a rule-following agent could legally grab a freshly-claimed ticket (fixed v7.28.0).
- **VERIFY**: MUST be executed. Failure retries within VERIFY itself, not a phase transition -- `phases/verify.md`'s own cap (3 dead hypotheses or 2 failed fix cycles) moves the ticket to `## BLOCKED` on `BOARD.md` and the agent picks up other workable tickets instead. Success transitions to `REVIEW`.
- **MANUAL-VERIFY**: If `mode: manual-verify`, `VERIFY` MUST block and await human confirmation. Agent MUST NOT auto-transition to `REVIEW`.
- **DONE**: A ticket MUST NOT be marked `DONE` without a successful `VERIFY` (or human `MANUAL-VERIFY`).

**Phase enum** (every legal `STATE.md phase:` value): `INIT`, `PLAN`, `SCOUT`, `BUILD`, `VERIFY`, `REVIEW`, `SHIP`, `DONE`, `BLOCKED`, `VALIDATE`, `HUNT`, `ADD`, `CLEAN`, `TRANSLATE`.

**Transition table** -- a quick-reference index, not a second source of truth. Each phase's own `phases/*.md` is authoritative; if this table and a phase doc ever disagree, the phase doc wins and this table is the one that's wrong:

```text
INIT      -> PLAN | BLOCKED
PLAN      -> SCOUT | BLOCKED
SCOUT     -> BUILD | BLOCKED
BUILD     -> VERIFY | BLOCKED
VERIFY    -> REVIEW | BLOCKED
REVIEW    -> SHIP | BUILD | BLOCKED
SHIP      -> DONE | BLOCKED
DONE      -> PLAN | HUNT | ADD | BLOCKED
VALIDATE  -> PLAN | SCOUT | BLOCKED
HUNT      -> ADD | PLAN | SCOUT | BLOCKED
ADD       -> VERIFY | PLAN | SCOUT | HUNT | DONE | BLOCKED
CLEAN     -> DONE | BLOCKED
TRANSLATE -> DONE | BLOCKED
BLOCKED   -> PLAN | SCOUT
```

- `CLEAN`, `TRANSLATE`, and `VALIDATE` are entered by explicit user command (`saipen clean` / `saipen translate` / `saipen validate`, § 1.10) from ANY phase -- they are not chain-specific like the rows above, the same way `saipen stop` isn't. Once entered, their own row above governs what they can transition to next.
- `HUNT -> PLAN | SCOUT` (the findings case, distinct from the clean-board case which always goes to `ADD`) is stated explicitly in `phases/hunt.md` itself: findings that get ticketed go to `PLAN`, or straight to `SCOUT` for a small/obvious one.
- `saipen status` MUST NOT change `phase` -- it is read-only (§ 1.10).
- `saipen stop` checkpoints and halts; it is not itself a phase transition (§ 1.10).
- Maintenance phases (`HUNT`/`ADD`/`CLEAN`/`TRANSLATE`) MUST NOT be required for Core continuation -- the Core chain (`INIT` through `DONE`/`BLOCKED`) is fully self-contained; a cold agent running Core alone never needs to reach them.

### 1.7 Workspace Hygiene
The protocol lives in the SAIPEN home; the project holds work, not protocol copies.
- `saipen set` in project root MUST NOT copy phases or scripts into the project. It MUST write a bootloader to `.saipen/STATE.md` pointing to the canonical `saipen/` home path -- concretely, the `saipen_home` frontmatter field (§ 1.2): the absolute path this bootstrap read the protocol from. A successor agent on the same machine finds the protocol through it; a successor on a different machine that finds the path dead clones github.com/vacterro/saipen and updates the field at its next checkpoint. (This field existed only as an unimplemented sentence in this section until v7.25.0 -- states written before then legally lack it.)
- Phase transitions MUST load the authoritative Markdown files directly from the global `saipen/phases/` directory via absolute path.

### 1.8 Batch Input Parsing (The "No Rush" Rule)
If the user provides a raw list or backlog of multiple features, tasks, or bug reports, the agent MUST NOT attempt to implement them all in a single pass. The agent MUST parse the list into individual `TODO` tickets on `BOARD.md` and execute them surgically, strictly one by one. "One by one" governs BUILD scope -- one ticket's changes per edit pass, never several tickets' code mixed into one -- not cadence. It does NOT mean pausing between tickets: under `goal_mode` (§ 2.4) tickets still flow without stopping; outside `goal_mode`, the normal per-ticket checkpoint (§ 1.5) still applies exactly as always.

- **Trailing Extrapolation ('etc.')**: If a user prompt, backlog list, or feature request contains "etc.", "etcetera", "and so on", "и т.д.", or similar phrasing, the agent MUST interpret it as an explicit instruction for "similar additions" — inferring and creating tickets for obvious missing workflow steps, complementary features, or logical extensions required to complete the pattern (aligning with § 2.3).

### 1.9 Extension Discovery
- `extensions/<name>/` **in the consuming project's own root** (not the SAIPEN home) is an optional, project-attached phase hook (e.g. `security`, `performance`) that the project's own author creates and maintains -- `saipen set` / `init.md` and the injector do NOT auto-populate it, the same way they never auto-populate a project's `tests/`. Each extension's own `README.md` states which phase it attaches to and what it requires there.
- On entering a phase, the agent MUST check whether the *project's* `extensions/<name>/` exists for that phase before proceeding. If it exists, its README's instructions apply for that phase. If it is absent, the phase proceeds exactly as its `phases/*.md` doc describes, with zero extension overhead. Absence MUST NOT block a phase transition -- extensions layer on top of Core, they never gate it.
- If an extension IS present but its own stated requirements aren't met on this host (a scanner binary missing, an API key unset) -- and Core's own safety/correctness isn't at stake -- the agent MUST degrade: skip what that requirement blocks, note it plainly in the phase's findings, and continue. If proceeding without it would be genuinely unsafe (the extension exists specifically because this project needs that check, and it silently can't run), the agent MUST go `BLOCKED` instead of pretending the check happened. Either way, an extension MUST NOT overwrite or weaken Core normative behavior -- it can only add checks on top of Core, never relax what Core already requires.
- The `extensions/security/` and `extensions/performance/` folders inside the SAIPEN home itself are reference *examples* for a project author to copy and adapt -- the same role `extensions/templates/` plays for `.saipen/` boilerplate. They are not live hooks the SAIPEN home reads on its own behalf; nothing discovers them unless a project author has replicated the pattern into their own project root.
- `extensions/schemas/` is a distinct, non-behavioral case: descriptive JSON Schemas held for a future external validator, explicitly not read by any agent today (see `extensions/schemas/README.md`). It is not a phase hook and this section does not apply to it.

### 1.10 Command Surface
The complete set of recognized user-facing commands. Phase-affecting ones are defined in full where cited; `status` and `stop` are defined here because they are meta/control operations, not phase transitions -- they can be invoked from any phase and MUST NOT be treated as work themselves.
- `saipen set` / `saipen init` -- bootstrap `.saipen/` (§ 1.7, `phases/init.md`).
- `saipen continue` / bare `saipen` -- read `STATE.md`/`BOARD.md`/tail of `LOG.md`, execute `next_action` immediately, no rebriefing (§ 1.1, § 2.1 DEFAULT BEHAVIOR, `CONFORMANCE.md` TEST-001).
- `saipen goal <text>` -- pivot to a new objective, run to completion (§ 2.4).
- `saipen clean` -- deep repository scrub (`phases/clean.md`).
- `saipen translate` -- isolated translation build (`phases/translate.md`).
- `saipen ship` -- explicit SHIP trigger (`phases/ship.md`); SHIP also fires implicitly per that phase's other stated conditions.
- `saipen validate` -- explicit VALIDATE trigger (`phases/validate.md`): run the conformance script, fix structural corruption if found (shape only -- a malformed line, missing frontmatter field, wrong heading; never a rewrite of `LOG.md`'s historical event content or any other file's real content), transition to `PLAN` or `SCOUT` per that phase's own rules.
- `saipen status` -- MUST read `BOARD.md` and `STATE.md` and report current phase, the in-flight ticket, and what's queued next. MUST NOT write to any file or perform any work -- read-only, no exceptions, regardless of `goal_mode`.
- `saipen stop` -- MUST checkpoint immediately per § 1.5 (flush `LOG.md`, update `BOARD.md`, set an explicit resumable `next_action`), then halt and return control to the user. MUST NOT leave a ticket mid-edit. Overrides `goal_mode` -- it is the user's manual brake and always wins.

Any command not listed here that appears in a `phases/*.md` doc without a matching definition in this section is non-conformant; add it here before relying on it. If the user types `saipen <word>` and `<word>` matches none of the above and isn't plausibly free-text for `goal`/bare `continue`, the agent MUST NOT invent behavior for it -- list the recognized commands and stop.

---

## Part 2: MAINTENANCE (Autonomous Evolution)

### 2.1 Autonomous Transitions
When the Core state machine reaches a halt (no pending tickets), the Maintenance layer MAY take over.

- **DEFAULT BEHAVIOR**: The bare command `saipen` is an alias for `saipen continue`. If there are pending tickets on `BOARD.md`, the agent MUST resume work.
- **ZERO-PROMPT AUTO-TRANSITION**: If the user runs the protocol and `BOARD.md` is empty, the agent MUST NOT ask the user for instructions or permission (e.g., "Should I hunt or add?"). It MUST silently and autonomously transition to the `HUNT` phase. If `HUNT` finds nothing (clean), the agent MUST immediately transition to `ADD`.
- **HUNT**: Transition to `HUNT` MUST occur strictly when `BOARD.md` has no open `TODO` tickets without blockers, or when explicitly signaled by a failed verification loop. Agent MUST NOT hallucinate tasks during `HUNT`.
- **CLEAN**: Transition to `CLEAN` occurs when explicitly triggered by the user via `saipen clean` (or just `clean`). The agent MUST instantly set `phase: CLEAN` in `STATE.md`, load `saipen/phases/clean.md`, and execute it. Agent MUST audit and prune stale tickets, orphaned files, and broken paths before returning to `DONE`.
- **TRANSLATE**: Transition to `TRANSLATE` occurs when explicitly triggered by the user via `saipen translate` (or just `translate`). The agent MUST instantly set `phase: TRANSLATE` in `STATE.md`, load `saipen/phases/translate.md`, and execute it. Agent MUST operate exclusively within a `.saitranslate/` folder at the project root to build, maintain, and update the 32-language core translation system + bonus voice. It MUST treat the main software strictly as a read-only reference.

### 2.2 Evolutionary ADD
- **ADD**: Agent MUST NOT invent speculative, experimental, or unrelated features. Agent MUST evaluate additions strictly using the following logic:

  ```pseudocode
  FOR priority IN [
    "bugfix", 
    "complementary_feature (Bold->Italic)", 
    "workflow_step (Open->Save_As)", 
    "ux_consistency", 
    "platform_convention"
  ]:
    IF exists(priority):
      IF priority == "bugfix":
        RETURN HUNT
      IF satisfies(minimal_delta) AND satisfies(existing_design_language):
        IMPLEMENT(priority)
        RETURN VERIFY
      ELSE:
        TICKET(priority)
        RETURN PLAN_or_SCOUT
  
  RETURN DONE
  ```
  
  After every ADD implementation, agent MUST transition to VERIFY, then HUNT. Only if HUNT is clean may another ADD begin.

### 2.3 The Industrial Completion Rule
When the user requests one step of a well-known user workflow, the agent SHOULD evaluate whether the remaining steps are expected by modern software conventions -- this evaluation is a judgment call, not mechanical. If the evaluation concludes yes, the agent MUST implement the minimal coherent set rather than the isolated feature -- once triggered, this is a discipline requirement, not optional.

- **Evaluate over blindly adding**: If asked for "Apply", the agent evaluates "Save", "Cancel", and "OK". It rejects irrelevant additions (e.g., "Save As").
- **The smallest complete solution wins**: The agent MUST complete the minimal coherent set for the requested workflow. It MUST NOT expand into massive related epics (e.g., "Export" justifies "Import", but does NOT justify building "Cloud Sync").
- **Complete before you extend**: Finish the requested workflow to its logical end before proposing a different one (e.g., "Login" implies "Logout" and wrong-password handling — not OAuth or SSO). Completion is preferred over expansion — the agent SHOULD preserve user expectations before introducing new capabilities.

### 2.4 Goal Mode (Autonomous Execution)
`saipen goal <text>` is an explicit, run-scoped opt-in that (a) sets a new high-level objective, superseding whatever was queued, and (b) runs that objective to completion with minimal interruption — through the Maintenance layer (§ 2.1), not just the current ticket wave. "Run-scoped," not "session-scoped": the persisted `goal_waves`/`goal_tickets` counters (below) mean a `saipen goal` run survives a crash or a fresh chat session mid-run — it ends only via this section's own Exit conditions, never by a session simply restarting. It is NOT the default — `saipen <text>` and bare `saipen continue` retain today's behavior.

- **Entry (the pivot)**: A `DOING` ticket in flight MUST be checkpointed cleanly, not abandoned mid-edit — LOG a `DEC` line noting the pivot, then leave it `TODO`. Existing `TODO` tickets MUST NOT be deleted; they are demoted below the new objective's tickets (board order = priority = law, § 1.6). `PLAN` runs for the new objective and inserts its tickets at the top. Agent MUST set `goal_mode: true`, `goal_waves: 0`, `goal_tickets: 0` in `STATE.md`, then proceed directly into `SCOUT` for the first new ticket without pausing to ask "shall I continue?".
- **Continuation**: While `goal_mode: true`, the agent MUST advance `SCOUT → BUILD → VERIFY → REVIEW` across successive tickets without stopping between them, subject to the caps below. `REVIEW` MUST re-run `PLAN` for the next wave automatically if the board defines one.
- **Board-empty is not exit**: When `BOARD.md` empties (a wave finishes), the agent MUST NOT stop or wait for a human — it falls straight through into the § 2.1 Autonomous Transitions exactly as under bare `saipen`: `HUNT`, then `ADD` if clean, then `HUNT` again, indefinitely. `goal_mode` remains `true` across this whole loop; a clean `HUNT` or one completed `ADD` ticket is a *waypoint*, never a stopping point.
- **SHIP exception**: The `saipen ship` gate in the SHIP phase is satisfied by an active `goal_mode: true` for subsequent ships to an existing `origin`. Agent MUST auto-push without re-confirming per ship. **First publish of a brand-new repository still MUST confirm name and public/private with the user** — creating a new public artifact is a one-way door goal mode does not waive.
- **Safety valve counters MUST persist, not just be counted in-context**: a long `goal_mode` run is expected to span more than one agent process — crashes, restarts, a different agent/machine picking up mid-run. Counting "how many waves so far" purely in the current context window silently loses the count on every restart, defeating the valve entirely for exactly the long runs it exists to protect. `STATE.md` MUST carry `goal_waves` (increment by 1 each time `PLAN` runs for a new wave, and each time a `HUNT`→`ADD` cycle completes) and `goal_tickets` (increment by 1 each time a ticket passes `VERIFY`) — both bumped and checkpointed (§ 1.5) at the moment they change, so any agent resuming this run reads the true count directly from `STATE.md`, never by re-deriving it from `LOG.md` scrollback.
- **Safety valve**: A single `saipen goal` invocation MUST NOT process more than 3 waves (`goal_waves`, planned tickets and HUNT/ADD cycles counted together) or 20 tickets (`goal_tickets`), whichever comes first. On hitting this ceiling, the agent MUST stop, write a full BOARD/STATE checkpoint, and report progress — the user re-invokes `saipen goal` to continue.
- **Unchanged under Goal Mode**: All existing caps still apply verbatim (3 dead hypotheses / 2 fix cycles per ticket in VERIFY; 2 review passes per finding in REVIEW). Goal Mode MUST NOT skip `VERIFY` or `REVIEW` — autonomy applies to *continuation between steps*, never to the correctness gates themselves. Destructive ops outside the ship/publish path (force-push, schema drop, deleting user data) still require explicit confirmation unless the ticket itself pre-authorizes them.
- **Exit**: `goal_mode` MUST be set back to `false` in `STATE.md` ONLY when: `ADD` itself gracefully concludes because the product is mature and logically complete (`phases/add.md`), the agent hits `BLOCKED`, or the safety valve triggers. A momentarily empty `BOARD.md` is never, by itself, an exit condition. On exit, `goal_waves`/`goal_tickets` MUST be cleared -- they describe the run that just ended, not a running lifetime total. Final report: tickets done/verified/shipped, any blocked, next action -- distinguish tickets that came from the user's original ask from ones picked up along the way (pre-existing backlog demoted below it, or `HUNT`/`ADD` findings), so the user can tell what actually happened without re-deriving it from `LOG.md`. No new persisted field is needed for this -- board order at Entry already carries it; it only needs to make it into the report.
