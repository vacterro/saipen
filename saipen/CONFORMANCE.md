# SAIPEN Conformance

Implementations MUST pass self-check across three vectors:
1. **Repo Validation**: `STATE.md`, `BOARD.md`, `LOG.md`, and `KNOWLEDGE/` MUST conform to the shapes RFC.md § 1.2 defines, enforced by `tools/validate.py` (canonical -- validates STATE.md against `extensions/schemas/state.schema.json` directly, plus graph checks: E-### uniqueness/monotonicity, parent resolution), with `tests/validate.sh` / `validate.ps1` as the frozen portable floor for hosts without Python. `board.schema.json`/`log.schema.json` remain descriptive reference -- see `extensions/schemas/README.md`.
2. **Session Validation**: `BOARD.md`'s `needs:` graph MUST be acyclic AND every reference MUST resolve to a ticket that actually exists on the board -- a dangling reference is worse than a cycle, since nothing else catches it. `LOG.md` graph parent-child links MUST resolve.
3. **Phase Contract Validation**: Stated `mode` MUST legally permit the current `phase` (RFC.md § 1.3). `phase` MUST be one of the fourteen enum values RFC.md § 1.6 defines, and any phase-to-phase transition MUST be legal per § 1.6's transition table.

## TEST-001: The Continuation Test
Any release of this protocol MUST pass the gold standard test:
1. Cold agent (zero chat history).
2. Execute `saipen continue` (or equivalent bootstrap command).
3. Agent MUST: read `next_action` and execute it instantly WITHOUT asking for context.
If the agent asks "What should I do?", the protocol has failed. A `next_action: WAIT: <specific question>` (RFC.md § 1.2) does NOT fail this test -- asking one exact, pre-determined question instantly is the executable action; the failure mode is vague context-seeking, not a specific authorization gate. This includes the bootstrap `WAIT:` `INIT` produces on a brand-new project (RFC § 1.2's fifth `WAIT:` category, `phases/init.md`) -- asking for the first project goal or raw backlog is the same kind of specific question, not vague context-seeking, and doesn't fail this test either: nothing in `STATE`/`BOARD`/`LOG` could have answered it instead, since none of them have any history yet.

## Scenario Coverage
`tests/scenarios/` holds one fixture directory per concept below. Structural
fixtures include a `.saipen/` that `tests/validate.sh`/`validate.ps1` runs
against directly; behavioral ones are README-only where the assertion is
about agent decision-making, not file shape -- there is nothing to validate
mechanically. "Covered by" names the actual fixture; entries with no
fixture state why, not silently.

| # | Concept | Covered by |
|---|---------|------------|
| 1 | Cold continuation | This section (TEST-001 above) + this repo's own live `.saipen/` -- no separate fixture adds anything a dedicated one wouldn't just duplicate. |
| 2 | Corrupt STATE recovery | `resume-after-crash`, `stale-state-reconciliation` |
| 3 | Dependency cycle | `dependency-cycle` |
| 4 | Dangling `needs:` reference | `dangling-needs-reference` |
| 5 | Stale claim forfeiture | `multi-agent-claim-conflict` |
| 6 | Goal counter crash recovery | `goal-counter-recovery` |
| 7 | Manual-verify gate | `manual-verify-fallback` |
| 8 | No-publish restriction | `no-git-ship-denial` |
| 9 | Read-only restriction | `read-only-restriction` |
| 10 | Board-empty maintenance transition | `board-empty-maintenance-transition` -- behavioral, no fixture |
| 11 | Goal objective exit | N/A -- `goal_exit` was evaluated and rejected three times (recorded in `.saipen/KNOWLEDGE/decisions.md` and CHANGELOG v7.13.1/v7.19.1); `goal_mode` never exits on board-empty, so there is no "objective exit" behavior to test |
| 12 | Extension absence does not block | `extension-absence` |
| 13 | Unresolved LOG parent | Enforced by `tools/validate.py` since v7.24.0 (parent must resolve to an earlier `E-###`; IDs unique + monotonic). The old excuse -- historical numbering resets a naive resolver would misflag -- died with v7.24.0's user-approved ledger repair; this repo's own LOG.md now passes the check it once couldn't. |
| 14 | Invalid phase transition | `invalid-phase-transition` -- conceptual only; `STATE.md` doesn't track phase history, so this can't be automated without new scope |
| 15 | Invalid mode-phase combination | `invalid-mode-phase-combination` |
| 16 | Ticket-level BLOCKED (non-cycle failure), work continues | `blocked-ticket` |
| 17 | Fresh INIT bootstrap from `templates/` | `fresh-init` -- behavioral, no `.saipen/` yet by definition (that's what INIT creates) |
| 18 | Evolutionary ADD feature symmetry (§ 2.2) | `add-feature-symmetry` -- behavioral, no fixture |
| 19 | Unclaimed DOING adoption (RFC § 1.4, v7.28.0) | `unclaimed-doing-adoption` -- behavioral, README-only |
| 20 | Clean tree after ticket-level BLOCKED (`phases/verify.md`, v7.27.0) | `blocked-ticket-clean-tree` -- behavioral, README-only |
| 21 | Dirty tree on continuation (RFC § 1.5, v7.29.0) | `dirty-tree-continuation` -- behavioral, README-only |
