# SAIPEN Conformance

Implementations MUST pass self-check across three vectors:
1. **Repo Validation**: `STATE.md`, `BOARD.md`, `LOG.md`, and `KNOWLEDGE/` MUST conform to the shapes RFC.md § 1.2 defines, enforced today by `tests/validate.sh` / `validate.ps1`. `extensions/schemas/*.json` are a forward-looking reference for a future external validator, not machine-enforced yet -- see `extensions/schemas/README.md`.
2. **Session Validation**: `BOARD.md`'s `needs:` graph MUST be acyclic AND every reference MUST resolve to a ticket that actually exists on the board -- a dangling reference is worse than a cycle, since nothing else catches it. `LOG.md` graph parent-child links MUST resolve.
3. **Phase Contract Validation**: Stated `mode` MUST legally permit the current `phase` (RFC.md § 1.3). `phase` MUST be one of the fourteen enum values RFC.md § 1.6 defines, and any phase-to-phase transition MUST be legal per § 1.6's transition table.

## TEST-001: The Continuation Test
Any release of this protocol MUST pass the gold standard test:
1. Cold agent (zero chat history).
2. Execute `saipen continue` (or equivalent bootstrap command).
3. Agent MUST: read `next_action` and execute it instantly WITHOUT asking for context.
If the agent asks "What should I do?", the protocol has failed. A `next_action: WAIT: <specific question>` (RFC.md § 1.2) does NOT fail this test -- asking one exact, pre-determined question instantly is the executable action; the failure mode is vague context-seeking, not a specific authorization gate.

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
| 11 | Goal objective exit | N/A -- `goal_exit` was evaluated and rejected (`.saipen/kitchen/SAIPEN_GAP_MATRIX.md`); `goal_mode` never exits on board-empty, so there is no "objective exit" behavior to test |
| 12 | Extension absence does not block | `extension-absence` |
| 13 | Unresolved LOG parent | N/A -- deliberately not validator-enforced (same reasoning as Event ID uniqueness: this repo's own LOG.md has real historical numbering resets from the vac -> vacskill -> SAIPEN rename that a naive resolver would immediately misflag; see `SAIPEN_GAP_MATRIX.md` G-05/G-06) |
| 14 | Invalid phase transition | `invalid-phase-transition` -- conceptual only; `STATE.md` doesn't track phase history, so this can't be automated without new scope |
| 15 | Invalid mode-phase combination | `invalid-mode-phase-combination` |
