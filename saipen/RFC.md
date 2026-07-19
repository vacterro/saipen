# SAIPEN Protocol (RFC)

## Part 1: CORE (Continuation Protocol)

### 1.1 Normative Rules
The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in RFC 2119.

- Agent MUST read `STATE.md`, `BOARD.md`, and tail of `LOG.md` before execution.
- Agent MUST NOT rely on chat context for project state.
- Agent MUST degrade capabilities if host tools are missing.

### 1.2 File Model
- **STATE.md**: MUST contain frontmatter: `phase`, `task`, `next_action`, `blocker`, `agent`, `updated`. `next_action` MUST be an immediately executable command. MAY contain `goal_mode: true|false` (default `false`) — see § 2.4.
- **BOARD.md**: MUST track `status` (TODO/DOING/DONE), `needs:` (dependencies), and `owner` (claims).
- **LOG.md**: Append-only event graph. MUST use Event IDs (`[E-001]`) and MAY use `parent_id` (`[parent: E-001]`).
- **KNOWLEDGE/**: Directory for durable truths. MUST NOT contain event histories. Uses ADR pattern (`ADR-001.md`).
- **kitchen/**: Directory for intermediate, half-finished files, scratchpads, and work-in-progress data. Agents MUST store temporary work here to avoid cluttering the project root. If an agent terminates mid-task, the successor MUST inspect `kitchen/` to resume work seamlessly.

### 1.3 Capability Negotiation (Two-Way Handshake)
1. **Protocol Demands**: `STATE.md` MAY define `requires: [filesystem, git, shell, python]`.
2. **Agent Capabilities**: Agent MUST evaluate host against requirements.
3. **Mode Lock**: Agent MUST write operating mode to `STATE.md` (`mode: full | read-only | no-publish | manual-verify`).
   - Missing Git: `mode: no-publish`. Agent MUST NOT transition to `SHIP`.
   - Missing Shell: `mode: manual-verify`.
   - Missing Filesystem Write: `mode: read-only`.
4. **Optional Parallel Execution**: `subagents` (parallel task/agent
   spawning) is never required and never gates a phase or sets `mode`.
   Its trigger is independence, not speed -- `HUNT`'s 6 signal categories
   (`phases/hunt.md`) don't depend on each other's results, so where
   subagents are available they MAY run concurrently instead of in turn.
   Absence MUST fall back silently to sequential execution -- same result.

### 1.4 Claim & Ownership
- Agent sets `owner: <AgentID>` and `claim_time: <ISO8601>` on BOARD.
- Active owner: `claim_time` < 15 minutes old, or actively writing to `LOG.md`.
- Stale claims: `claim_time` > 15 minutes + no LOG activity → claim is forfeit.
- Conflicting writes: First successful filesystem commit wins.

### 1.5 Checkpointing & Recovery
- **Checkpointing**: MUST checkpoint after every ticket or before session termination. Update `BOARD.md`, set `STATE.md` explicit `next_action`, flush `LOG.md`. On-disk state MUST be atomic.
- **Recovery**: If `STATE.md` is stale but `LOG.md` or `BOARD.md` is newer, `git status` is ground truth. Rebuild `STATE.md` based on latest `LOG.md` entry and open DOING ticket.

### 1.6 Core State Machine & Ticket DAG
`INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`

- **Ticket DAG**: Tickets MUST define dependencies using `needs: [T-XXX]`. Agents MUST NOT pick `TODO` tickets unless all `needs:` are marked `DONE`.
- **VERIFY**: MUST be executed. Failure loops back to `BUILD` (max 2 loops) or `SCOUT`. Success transitions to `REVIEW`.
- **MANUAL-VERIFY**: If `mode: manual-verify`, `VERIFY` MUST block and await human confirmation. Agent MUST NOT auto-transition to `REVIEW`.
- **DONE**: A ticket MUST NOT be marked `DONE` without a successful `VERIFY` (or human `MANUAL-VERIFY`).

### 1.7 Workspace Hygiene
The protocol lives in the SAIPEN home; the project holds work, not protocol copies.
- `saipen set` in project root MUST NOT copy phases or scripts into the project. It MUST write a bootloader to `.saipen/STATE.md` pointing to the canonical `saipen/` home path.
- Phase transitions MUST load the authoritative Markdown files directly from the global `saipen/phases/` directory via absolute path.

---

## Part 2: MAINTENANCE (Autonomous Evolution)

### 2.1 Autonomous Transitions
When the Core state machine reaches a halt (no pending tickets), the Maintenance layer MAY take over.

- **DEFAULT BEHAVIOR**: The bare command `saipen` is an alias for `saipen continue`. If there are pending tickets on `BOARD.md`, the agent MUST resume work. If the user runs the protocol (e.g., `saipen` or `saipen continue`) and `BOARD.md` is empty (no open tickets), the agent MUST immediately transition to the `HUNT` phase to search for bugs. If `HUNT` finds nothing (clean), the agent MUST immediately transition to `ADD` to evolve the software.
- **HUNT**: Transition to `HUNT` MUST occur strictly when `BOARD.md` has no open `TODO` tickets without blockers, or when explicitly signaled by a failed verification loop. Agent MUST NOT hallucinate tasks during `HUNT`.
- **CLEAN**: Transition to `CLEAN` occurs when explicitly triggered by user via `saipen clean`. Agent MUST audit and prune stale tickets, orphaned files, and broken paths before returning to `DONE`.
- **TRANSLATE**: Transition to `TRANSLATE` occurs when explicitly triggered by user via `saipen translate`. Agent MUST operate exclusively within `.saipen/kitchen/translation/` to build, maintain, and update the 22-language core translation system + bonus voice, without modifying the main software.

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
  
  RETURN DONE
  ```
  
  After every ADD implementation, agent MUST transition to VERIFY, then HUNT. Only if HUNT is clean may another ADD begin.

### 2.3 The Industrial Completion Rule
When the user requests one step of a well-known user workflow, the agent SHOULD evaluate whether the remaining steps are expected by modern software conventions. If so, it SHOULD implement the minimal coherent set rather than the isolated feature.

- **Evaluate over blindly adding**: If asked for "Apply", the agent evaluates "Save", "Cancel", and "OK". It rejects irrelevant additions (e.g., "Save As").
- **The smallest complete solution wins**: The agent MUST complete the minimal coherent set for the requested workflow. It MUST NOT expand into massive related epics (e.g., "Export" justifies "Import", but does NOT justify building "Cloud Sync").
- **Complete before you extend**: Finish the requested workflow to its logical end before proposing a different one (e.g., "Login" implies "Logout" and wrong-password handling — not OAuth or SSO). Completion is preferred over expansion — the agent SHOULD preserve user expectations before introducing new capabilities.

### 2.4 Goal Mode (Autonomous Execution)
`saipen goal <text>` is an explicit, session-scoped opt-in that (a) sets a new high-level objective, superseding whatever was queued, and (b) runs that objective to completion with minimal interruption — through the Maintenance layer (§ 2.1), not just the current ticket wave. It is NOT the default — `saipen <text>` and bare `saipen continue` retain today's behavior.

- **Entry (the pivot)**: A `DOING` ticket in flight MUST be checkpointed cleanly, not abandoned mid-edit — LOG a `DEC` line noting the pivot, then leave it `TODO`. Existing `TODO` tickets MUST NOT be deleted; they are demoted below the new objective's tickets (board order = priority = law, § 1.6). `PLAN` runs for the new objective and inserts its tickets at the top. Agent MUST set `goal_mode: true` in `STATE.md`, then proceed directly into `SCOUT` for the first new ticket without pausing to ask "shall I continue?".
- **Continuation**: While `goal_mode: true`, the agent MUST advance `SCOUT → BUILD → VERIFY → REVIEW` across successive tickets without stopping between them, subject to the caps below. `REVIEW` MUST re-run `PLAN` for the next wave automatically if the board defines one.
- **Board-empty is not exit**: When `BOARD.md` empties (a wave finishes), the agent MUST NOT stop or wait for a human — it falls straight through into the § 2.1 Autonomous Transitions exactly as under bare `saipen`: `HUNT`, then `ADD` if clean, then `HUNT` again, indefinitely. `goal_mode` remains `true` across this whole loop; a clean `HUNT` or one completed `ADD` ticket is a *waypoint*, never a stopping point.
- **SHIP exception**: The `saipen ship` gate in the SHIP phase is satisfied by an active `goal_mode: true` for subsequent ships to an existing `origin`. Agent MUST auto-push without re-confirming per ship. **First publish of a brand-new repository still MUST confirm name and public/private with the user** — creating a new public artifact is a one-way door goal mode does not waive.
- **Safety valve**: A single `saipen goal` invocation MUST NOT process more than 3 waves (planned tickets and HUNT/ADD cycles counted together) or 20 tickets, whichever comes first. On hitting this ceiling, the agent MUST stop, write a full BOARD/STATE checkpoint, and report progress — the user re-invokes `saipen goal` to continue.
- **Unchanged under Goal Mode**: All existing caps still apply verbatim (3 dead hypotheses / 2 fix cycles per ticket in VERIFY; 2 review passes per finding in REVIEW). Goal Mode MUST NOT skip `VERIFY` or `REVIEW` — autonomy applies to *continuation between steps*, never to the correctness gates themselves. Destructive ops outside the ship/publish path (force-push, schema drop, deleting user data) still require explicit confirmation unless the ticket itself pre-authorizes them.
- **Exit**: `goal_mode` MUST be set back to `false` in `STATE.md` ONLY when: `ADD` itself gracefully concludes because the product is mature and logically complete (`phases/add.md`), the agent hits `BLOCKED`, or the safety valve triggers. A momentarily empty `BOARD.md` is never, by itself, an exit condition. Final report: tickets done/verified/shipped, any blocked, next action.
