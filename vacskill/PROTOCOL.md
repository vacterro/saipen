# Agent Session Protocol (ASP) Specification (v6.0.0)

## 1. Abstract
VACSKILL defines a portable, file-backed project session protocol for LLM agents. Implementations MAY vary. The on-disk contract MUST remain stable. This protocol allows disparate agents to collaborate, hand off state, and recover from crashes with zero amnesia by treating the `.vacskill/` directory as the single source of truth.

## 2. Scope
This document specifies the core state machine, file schemas, memory layout, capability negotiation, and recovery semantics. It bounds what an agent MUST do to be considered conformant. Voice, personality, and platform-specific bridging logic are explicitly out of scope.

## 3. Normative Rules
The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED",  "MAY", and "OPTIONAL" in this document are to be interpreted as described in RFC 2119.
- An agent MUST read the `STATE.md`, `BOARD.md`, and tail of `LOG.md` before taking action.
- An agent MUST NOT rely on its chat context window for project state.
- `STYLE.md` and `UI.md` define non-normative voice and visual themes; they SHALL NOT override protocol logic.
- An agent MUST degrade its capabilities safely if tools (e.g., git, shell) are missing.

## 4. File Model
The protocol relies on four canonical files inside `.vacskill/`:
- **STATE.md**: Answers "What do I do right now?". MUST contain frontmatter: `phase`, `task`, `next_action`, `blocker`, `agent`, `updated`. The `next_action` MUST be an immediately executable command (e.g., `pytest tests/`), NOT a vague intent.
- **BOARD.md**: Answers "What task am I picking up?". MUST track `status` (TODO/DOING/DONE), `needs:` (dependencies), and `owner` (claims).
- **LOG.md**: Answers "Why did we come to this point?". Append-only event graph. MUST be one event per line (DEC, RUN, H). MUST use Event IDs (`[E-001]`) and MAY use `parent_id` (`[parent: E-001]`) to form a decision graph instead of a linear list.
- **KNOWLEDGE/**: Answers "What is the durable truth of this project?". Directory for durable truths. MUST NOT contain event histories. Major architectural decisions MUST be recorded here using the Architecture Decision Record (ADR) pattern (e.g. `ADR-001.md`).

*Formal schemas for these files are defined in `extensions/schemas/`.*


## 5. State Machine
Agents MUST follow the strict phase transition model:
`INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`

**Transitions:**
- **INIT**: Bootstraps the `.vacskill/` directory. Exit: `PLAN`.
- **PLAN**: Analyzes goals and creates tasks on the BOARD. Exit: `SCOUT`.
- **SCOUT**: Reads code, builds context. Exit: `BUILD`.
- **BUILD**: Edits files. Exit: `VERIFY`.
- **VERIFY**: Runs tests. Failure loops back to `BUILD` (max 2 loops) or `SCOUT`. Cap hit → `BLOCKED`. Success → `REVIEW`.
- **REVIEW**: Validates diffs against constraints. P0/P1 failure → `BUILD`. Success → `SHIP`.
- **SHIP**: Finalizes and publishes. Exit: `DONE`.

## 6. Ticket Model
Tasks (Tickets) govern execution. An agent MUST NOT execute arbitrary work not listed on `BOARD.md`.
- Tickets MUST define dependencies using `needs: [T-XXX]`.
- Agents MUST only pick TODO tickets where all `needs:` are marked DONE.

## 7. Claim / Ownership
To prevent race conditions in multi-agent environments:
- An agent claims a ticket by setting `owner: <AgentID>` and `claim_time: <ISO8601>` on the BOARD ticket.
- Active owner: `claim_time` < 15 minutes old, or agent actively writing to `LOG.md`.
- Stale claims: If `claim_time` > 15 minutes and no LOG activity, another agent MAY claim the ticket.
- Conflicting writes: The agent that successfully commits to the filesystem wins.

## 8. Checkpointing
Agents MUST checkpoint their work.
- **When**: After every completed ticket, or before terminating a session.
- **How**: Update `BOARD.md` to reflect task status, update `STATE.md` with the explicit `next_action`, and flush `LOG.md`.
- Dying agents get no "goodbye" turn. The on-disk state MUST be atomic.

## 9. Recovery
Crash recovery is a first-class state:
- If `STATE.md` is stale but `LOG.md` or `BOARD.md` is newer, the agent MUST read `git status` as the ground truth for in-flight edits.
- The agent SHALL rebuild `STATE.md` based on the latest `LOG.md` entry and the current open DOING ticket on the BOARD.

## 10. Capability Negotiation (Two-Way Handshake)
Capability negotiation is two-way. The protocol specifies demands; the agent matches them.
1. **Protocol Demands**: `.vacskill/STATE.md` MAY define `requires: [filesystem, git, shell, python]`.
2. **Agent Capabilities**: Before engaging, the agent MUST evaluate its host environment against these requirements.
3. **Mode Lock**: The agent MUST write its operating mode back to `STATE.md` (`mode: full | read-only | no-publish | manual-verify`).
- **Missing Git**: `mode: no-publish`. Agent MUST NOT transition to `SHIP`.
- **Missing Shell**: `mode: manual-verify`. `VERIFY` MUST degrade to manual user verification.
- **Missing Filesystem Write**: `mode: read-only`. Agent operates in advisory mode.
The agent adapts; it MUST NOT hallucinate competence.

## 11. Adapter Contract
Adapters (e.g., for Claude, Aider, OpenCode) MUST be thin translation layers. They SHALL NOT implement business logic. They MUST simply instruct the model to read this `PROTOCOL.md` file and obey it.

## 12. Conformance
Implementations MUST be able to pass a self-check:
- State schema is valid.
- Board dependencies are acyclic.
- Log is strictly append-only.
- Knowledge contains no event data.
- Agent successfully resumes from stale state.
If requested by the user via `vacskill validate`, the agent MUST run this conformance check.

**TEST-001: The Continuation Test**
Any release of this protocol MUST pass the gold standard test:
1. Cold agent (zero chat history).
2. Execute `/vacskill continue`.
3. Agent MUST: understand phase, pick ticket, read `next_action`, and execute it instantly WITHOUT asking the user for context.
If the agent asks "What should I do?", the protocol has failed.

## 13. Commands
The following commands route to specific phases or actions:
| Command | Action |
|---|---|
| `vacskill stop` | Checkpoint + handoff |
| `vacskill status` | Report only, change nothing |
| `vacskill validate` | execute validate.md |
| `vacskill ship` | review.md -> ship.md |

## 14. Extensions
Extensions MAY add new phases or ticket metadata, provided they do not conflict with sections 3-10. Unknown frontmatter keys MUST be ignored by core implementations.

## 15. Change Control
Changes to this protocol MUST strictly bump the semantic version (MAJOR.MINOR.PATCH) in `VERSION` and document the change in `CHANGELOG.md`. The on-disk schema contract dictates the MAJOR version.