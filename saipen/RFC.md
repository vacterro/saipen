## 1. Normative Rules
The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in RFC 2119.

- Agent MUST read `STATE.md`, `BOARD.md`, and tail of `LOG.md` before execution.
- Agent MUST NOT rely on chat context for project state.
- Agent MUST degrade capabilities if host tools are missing.

## 2. File Model
- **STATE.md**: MUST contain frontmatter: `phase`, `task`, `next_action`, `blocker`, `agent`, `updated`. `next_action` MUST be an immediately executable command.
- **BOARD.md**: MUST track `status` (TODO/DOING/DONE), `needs:` (dependencies), and `owner` (claims).
- **LOG.md**: Append-only event graph. MUST use Event IDs (`[E-001]`) and MAY use `parent_id` (`[parent: E-001]`).
- **KNOWLEDGE/**: Directory for durable truths. MUST NOT contain event histories. Uses ADR pattern (`ADR-001.md`).
- **kitchen/**: Directory for intermediate, half-finished files, scratchpads, and work-in-progress data. Agents MUST store temporary work here to avoid cluttering the project root. If an agent terminates mid-task, the successor MUST inspect `kitchen/` to resume work seamlessly.

## 3. State Machine Transitions
`INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED | HUNT | ADD | CLEAN`

**Strict Transition Constraints:**
- **VERIFY**: MUST be executed. Failure loops back to `BUILD` (max 2 loops) or `SCOUT`. Success transitions to `REVIEW`.
- **MANUAL-VERIFY**: If `mode: manual-verify`, `VERIFY` MUST block and await human confirmation. Agent MUST NOT auto-transition to `REVIEW`.
- **DONE**: A ticket MUST NOT be marked `DONE` without a successful `VERIFY` (or human `MANUAL-VERIFY`).
- **HUNT**: Transition to `HUNT` MUST occur strictly when `BOARD.md` has no open `TODO` tickets without blockers, or when explicitly signaled by a failed verification loop. Agent MUST NOT hallucinate tasks during `HUNT`.
- **ADD**: Agent MUST evolve the software conservatively using a strict Decision Order:
  1. Missing bugfix? → STOP. Return to BUILD/HUNT.
  2. Missing complementary feature? (Bold → Italic) → Add it.
  3. Missing workflow step? (Open → Save As) → Add it.
  4. Missing UX consistency? (Toolbar action without shortcut) → Add it.
  5. Missing platform convention? → Add it.
  6. Minimal Delta satisfied? (No new patterns) → Continue.
  7. Existing Design Language preserved? → Continue.
  8. Product logically complete? → DONE.
  
  Agent MUST NOT invent speculative, experimental, or unrelated features. After every ADD, transition to VERIFY, then HUNT. Only if HUNT is clean may another ADD begin.
- **CLEAN**: Transition to `CLEAN` occurs when explicitly triggered by user via `saipen clean`. Agent MUST audit and prune stale tickets, orphaned files, and broken paths before returning to `DONE`.
- **DEFAULT BEHAVIOR**: The bare command `saipen` is an alias for `saipen continue`. If there are pending tickets on `BOARD.md`, the agent MUST resume work. If the user runs the protocol (e.g., `saipen` or `saipen continue`) and `BOARD.md` is empty (no open tickets), the agent MUST immediately transition to the `HUNT` phase to search for bugs. If `HUNT` finds nothing (clean), the agent MUST immediately transition to `ADD` to evolve the software.

## 4. Ticket Model (DAG)
- Tickets MUST define dependencies using `needs: [T-XXX]`.
- This is a strict Directed Acyclic Graph (DAG). Agents MUST NOT pick `TODO` tickets unless all `needs:` are marked `DONE`.

## 5. Claim / Ownership
- Agent sets `owner: <AgentID>` and `claim_time: <ISO8601>` on BOARD.
- Active owner: `claim_time` < 15 minutes old, or actively writing to `LOG.md`.
- Stale claims: `claim_time` > 15 minutes + no LOG activity → claim is forfeit.
- Conflicting writes: First successful filesystem commit wins.

## 6. Checkpointing
- MUST checkpoint after every ticket or before session termination.
- Update `BOARD.md`, set `STATE.md` explicit `next_action`, flush `LOG.md`. On-disk state MUST be atomic.

## 7. Recovery
- If `STATE.md` is stale but `LOG.md` or `BOARD.md` is newer, `git status` is ground truth.
- Rebuild `STATE.md` based on latest `LOG.md` entry and open DOING ticket.

## 8. Capability Negotiation (Two-Way Handshake)
1. **Protocol Demands**: `STATE.md` MAY define `requires: [filesystem, git, shell, python]`.
2. **Agent Capabilities**: Agent MUST evaluate host against requirements.
3. **Mode Lock**: Agent MUST write operating mode to `STATE.md` (`mode: full | read-only | no-publish | manual-verify`).
   - Missing Git: `mode: no-publish`. Agent MUST NOT transition to `SHIP`.
   - Missing Shell: `mode: manual-verify`.
   - Missing Filesystem Write: `mode: read-only`.

## 9. Workspace Hygiene
The protocol lives in the SAIPEN home; the project holds work, not protocol copies.
- Protocol files (`RFC.md`, `STYLE.md`, `UI.md`, `SKILL.md`, `phases/`) MUST NOT be copied into the project. Agents read them from the SAIPEN home; the pointer block in `AGENTS.md` gives the path.
- Project memory MUST live in `.saipen/` under canonical names only: `STATE.md`, `BOARD.md`, `LOG.md`, `KNOWLEDGE/`, `kitchen/`. Ad-hoc names (`CONTEXT.md`, `MEMORY.md`, `NOTES.md`) are non-conformant — fold their content into the canonical file (`CONTEXT` → `KNOWLEDGE/`, `MEMORY` → `LOG.md`) and delete the stray.
- Every `.md` MUST earn its place: one purpose, no duplication, no filler. On checkpoint, agent MUST prune generated litter (`__pycache__`, editor swaps, empty scaffold files) and MUST NOT create a file it will not maintain. Active intermediate work MUST be placed in `kitchen/`.
- Deliverables (client-facing outputs) live at project root and are exempt; they are work, not protocol.

## 10. Phase Loading
- When transitioning to a new phase (e.g., changing `phase: [name]` in `STATE.md`), the agent MUST read the corresponding phase rules strictly from `<SAIPEN_HOME>/phases/<phase>.md`.
- The agent MUST NOT attempt to load phases from the local project directory.
- If a phase is not found in the `<SAIPEN_HOME>/phases/` directory, the agent MUST transition to `BLOCKED` and await human intervention.
- The agent MUST NOT hallucinate, invent, or create new phase files under any circumstances.
