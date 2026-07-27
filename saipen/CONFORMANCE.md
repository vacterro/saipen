# SAIPEN Conformance

Implementations MUST pass self-check across three vectors:
1. **Repo Validation**: `STATE.md`, `BOARD.md`, `LOG.md`, and `KNOWLEDGE/` MUST conform to the shapes RFC.md § 1.2 defines, enforced by `tools/validate.py` (canonical -- validates STATE.md against `extensions/schemas/state.schema.json` directly, plus graph checks: E-### uniqueness/monotonicity, parent resolution), with `tests/validate.sh` / `validate.ps1` as the frozen portable floor for hosts without Python. `board.schema.json`/`log.schema.json` remain descriptive reference -- see `extensions/schemas/README.md`.
2. **Session Validation**: `BOARD.md`'s `needs:` graph MUST be acyclic AND every reference MUST resolve to a ticket that actually exists on the board -- a dangling reference is worse than a cycle, since nothing else catches it. `LOG.md` graph parent-child links MUST resolve.
3. **Phase Contract Validation**: Stated `mode` MUST legally permit the current `phase` (RFC.md § 1.3). `phase` MUST be one of the sixteen enum values RFC.md § 1.6 defines, and any phase-to-phase transition MUST be legal per § 1.6's transition table.

## TEST-001: The Continuation Test
Any release of this protocol MUST pass the gold standard test:
1. Cold agent (zero chat history).
2. Execute `saipen continue` (or equivalent bootstrap command).
3. Agent MUST: read `next_action` and execute it instantly WITHOUT asking for context.
If the agent asks "What should I do?", the protocol has failed. A `next_action: WAIT: <specific question>` (RFC.md § 1.2) does NOT fail this test -- asking one exact, pre-determined question instantly is the executable action; the failure mode is vague context-seeking, not a specific authorization gate. This includes the bootstrap `WAIT:` `INIT` produces on a brand-new project (RFC § 1.2's fifth `WAIT:` category, `phases/init.md`) -- asking for the first project goal or raw backlog is the same kind of specific question, not vague context-seeking, and doesn't fail this test either: nothing in `STATE`/`BOARD`/`LOG` could have answered it instead, since none of them have any history yet.

## Scenario Coverage
`tests/scenarios/` holds one fixture directory per concept below. Behavioral
ones are README-only where the assertion is about agent decision-making, not
file shape -- there is nothing to validate mechanically. "Covered by" names
the actual fixture; entries with no fixture state why, not silently.

| # | Concept | Covered by |
|---|---------|------------|
| 1 | Cold continuation | This section (TEST-001 above) + this repo's own live `.saipen/` -- no separate fixture adds anything a dedicated one wouldn't just duplicate. |
| 2 | Corrupt STATE recovery | `resume-after-crash`, `stale-state-reconciliation` |
| 3 | Dependency cycle | `dependency-cycle` |
| 4 | Dangling `needs:` reference | `dangling-needs-reference` |
| 5 | Stale claim forfeiture | `multi-agent-claim-conflict` |
| 6 | Goal counter crash recovery | `goal-counter-recovery` |
| 7 | Manual-verify gate | `manual-verify-fallback` |
| 8 | No-publish restriction -- git-dependent *steps* are skipped (no commit/tag/push, never a false "pushed"), but `SHIP` itself stays reachable and still closes the ticket to `DONE` (RFC § 1.3, `phases/ship.md`'s no-publish branch, v7.66.0) | `no-git-ship-denial` -- behavioral, README-only (folder name predates v7.66.0, when this asserted the opposite) |
| 9 | Read-only restriction | `read-only-restriction` |
| 10 | Board-empty maintenance transition | `board-empty-maintenance-transition` -- behavioral, no fixture |
| 11 | Goal objective exit | N/A -- `goal_exit` was evaluated and rejected three times (recorded in `.saipen/KNOWLEDGE/decisions.md` and CHANGELOG v7.13.1/v7.19.1); `goal_mode` never exits on board-empty, so there is no "objective exit" behavior to test |
| 12 | Extension absence does not block | `extension-absence` |
| 13 | Unresolved LOG parent | Enforced by `tools/validate.py` since v7.24.0 (parent must resolve to an earlier `E-###`; IDs unique + monotonic). The old excuse -- historical numbering resets a naive resolver would misflag -- died with v7.24.0's user-approved ledger repair; this repo's own LOG.md now passes the check it once couldn't. |
| 14 | Invalid phase transition | `invalid-phase-transition` -- automated via `transition_from` in STATE.md; `tools/validate.py` checks every non-self transition against RFC § 1.6's table (v7.82.0) |
| 15 | Mode-phase restrictions -- `read-only` MUST NOT enter `BUILD`/`SHIP`/`CLEAN`/`TRANSLATE` (RFC § 1.3), the only such ban still live since v7.66.0 freed `no-publish` + `SHIP` | `read-only-restriction` (fails as intended); `invalid-mode-phase-combination` is now the inverse regression guard -- it asserts `no-publish` + `SHIP` stays legal, since re-adding that ban already shipped once |
| 16 | Ticket-level BLOCKED (non-cycle failure), work continues | `blocked-ticket` |
| 17 | Fresh INIT bootstrap from `templates/` | `fresh-init` -- behavioral, no `.saipen/` yet by definition (that's what INIT creates) |
| 18 | Evolutionary ADD feature symmetry (§ 2.2) | `add-feature-symmetry` -- behavioral, no fixture |
| 19 | Unclaimed DOING adoption (RFC § 1.4, v7.28.0) | `unclaimed-doing-adoption` -- behavioral, README-only |
| 20 | Clean tree after ticket-level BLOCKED (`phases/verify.md`, v7.27.0) | `blocked-ticket-clean-tree` -- behavioral, README-only |
| 21 | Dirty tree on continuation (RFC § 1.5, v7.29.0) | `dirty-tree-continuation` -- behavioral, README-only |
| 22 | Parallel TRANSLATE doesn't stomp shared STATE (RFC § 2.1, `phases/translate.md`, v7.34.0) | `parallel-translate-isolation` -- behavioral, README-only |
| 23 | Dual-location extension conflict resolved, never merged/guessed (RFC § 1.9, v7.36.0) | `extension-dual-location-conflict` -- behavioral, README-only |
| 24 | Dual-location TRANSLATE conflict resolved, never merged/guessed (RFC § 2.1, v7.37.0) | `translate-dual-location-conflict` -- behavioral, README-only |
| 25 | `saipen sub spawn` / parallel TRANSLATE both refuse on a project with no `.saipen/` yet, instead of silently triggering INIT (RFC § 1.9 v7.36.0, § 2.1 v7.37.0) | `spawn-requires-init` -- behavioral, README-only |
| 26 | HUNT skip requires an exact HEAD-hash match; mtime/diff-timing is never a substitute for actually running the six categories (`phases/hunt.md`, v7.41.0) | `hunt-skip-requires-exact-hash-match` -- behavioral, README-only |
| 27 | MARKHUNT records findings without fixing/capping, unlike HUNT (`phases/markhunt.md`) | `markhunt-dry-record-only` -- behavioral, README-only |
| 28 | VERIFY hysteresis: a ticket blocked a second time escalates to session-level `BLOCKED` instead of spending a fresh retry budget (`phases/verify.md`) | `verify-hysteresis-second-block` -- behavioral, README-only |
| 29 | SubSaipen `STATE.md` shape + policy (schema-valid, `mode: read-only`, no write-requiring `phase`) checked by `tools/validate.py`, not just the main project's own `STATE.md` (`extensions/subs/PROTOCOL.md` § 1/§ 8, v7.49.0) | Enforced directly by `tools/validate.py` -- no separate fixture; the repo's own four live instances under `.saipen/extensions/subs/` exercise the pass case every run. The walk also covers the shipped library at `extensions/subs/`, which since v7.84.0 holds only `TEMPLATE/` and shared reference files -- instance state moved out to `.saipen/`, so that half of the walk now guards against instance state reappearing there rather than checking anything, which is the intended end state, not a dead check |
| 30 | `read-only` reaches `MARKHUNT`/`PREPARE`/`VALIDATE` only in report-only form -- findings/handoff/corruption are reported in chat, never written (no `## BLOCKED` tickets, no `kitchen/`, no structural repair) (RFC § 1.3) | `read-only-audit-phases` -- behavioral, README-only |
| 31 | `stop` preserves the goal counters; `saipen continue`/bare `saipen` resume them unchanged, but bare `saipen goal` deliberately resets `goal_waves`/`goal_tickets` to `0` for a fresh valve budget (RFC § 1.10 / § 2.4) | `stop-goal-counter-semantics` -- behavioral, README-only |
| 32 | `goal_waves` is not double-counted when `ADD` RETURNs to `PLAN` -- the cycle's wave is counted once at ADD's RETURN, and the follow-on `PLAN` skips its own increment for that same cycle (RFC § 2.4, `phases/plan.md`/`add.md`) | `goal-waves-no-double-count` -- behavioral, README-only |
| 33 | A fixer-type subSaipen (saipython) emits a tested patch through OUTBOX, having cloned targets into its own `kitchen/pen/` and verified there in phase `VERIFY` -- it still never writes the main tree and never enters `BUILD`/`SHIP` (`mode: read-only`, enforced by `tools/validate.py`); the main agent applies the patch through Core gates (`extensions/subs/PROTOCOL.md` § 9) | `fixer-subsaipen-patch-outbox` -- behavioral, README-only |
| 34 | Cold continuation via `saipen/BOOT.md` -- the compact kernel reads STATE -> BOARD -> active LOG tail, executes `next_action`, and loads the phase doc on demand without pulling the full RFC; TEST-001 passes on BOOT + STATE + BOARD + tail alone (`saipen/BOOT.md`, RFC § 1.1) | `boot-cold-start-kernel` -- behavioral, README-only |
| 35 | `human_note:` optional STATE field -- a one-line human nudge read on continue (BOOT step 4) and cleared once applied; never a ticket or goal, and one that implies work becomes a real `TODO` instead of living in `STATE.md` (RFC § 1.2) | `human-note-nudge` -- behavioral, README-only |
| 36 | Human digest -- `saipen ship` and `saipen stop` (over)write `.saipen/kitchen/digest.md` (done/remaining/awaiting, three lines) so the human reads one snapshot instead of scrolling `LOG.md` (`phases/ship.md`, RFC § 1.10) | `human-digest-on-exit` -- behavioral, README-only |
| 37 | MARKHUNT closure self-test -- completion is verified against its manifest (`vectors:` 5/5, `cursor: done`, `head_end` == current HEAD, `findings:` == the `[MARKHUNT]` tickets written) before it may reach `DONE`; the enriched completion line (`N findings, V/5 vectors, @head`) keeps coverage auditable after `kitchen/` is swept -- the checkable closure HUNT gets from its hash line, which MARKHUNT previously lacked (`phases/markhunt.md`, closes T-136) | `markhunt-closure-self-test` -- behavioral, README-only |
| 38 | LOG segmentation -- `E-###` stays globally unique and monotonic, and `[parent: E-###]` resolves, across sealed `.saipen/logs/LOG-<NNN>.md` segments plus the active `LOG.md` treated as one sequence, not just within whichever file is currently open (RFC § 1.2, v7.53.0) | Enforced directly by `tools/validate.py` -- no separate fixture, this repo's own live `.saipen/LOG.md` + `.saipen/logs/LOG-001.md` (2 segments) already exercise the pass case every run |
| 39 | Shipped-library integrity -- `tools/validate.py` checks the subSaipen states in `extensions/subs/` (what `saipen sub spawn` copies and the injector distributes), not only this project's live `.saipen/extensions/subs/` instances; a concrete `saipen_home` in a shipped template is a FAIL, since that file reaches every user (v7.72.0) | Enforced directly by `tools/validate.py` -- the repo's own three library examples plus its live instance exercise it every run |
| 40 | Board soft cap -- `BOARD.md` is read on every cold start (RFC § 1.1, `BOOT.md` step 2), so growth past ~16 KB WARNs and points at `phases/clean.md`'s board scrub. No sealing machinery, unlike `LOG.md`: the board is prunable rather than append-only, and closed tickets already live permanently in `LOG.md`/`CHANGELOG.md` (RFC § 1.2, v7.72.0) | Enforced directly by `tools/validate.py` -- caught this repo's own 28 KB board on the run that introduced it |
| 41 | `saipen status` answers the question actually being asked -- alongside phase/ticket/queue it reports what is waiting on a human, what is claimed but unproven, the last recorded conformance result, and staleness; and it states facts without pronouncing the project healthy or ready (RFC § 1.10, v7.82.0) | `status-answers-the-real-question` -- behavioral, README-only |
| 42 | LOG timestamp UTC freshness -- `tools/validate.py` WARNs if the last LOG entry's timestamp is >3h from current UTC time. Prevents local-clock drift from corrupting the audit trail Recovery depends on (RFC § 1.2 mandates UTC, v7.82.0) | Enforced directly by `tools/validate.py` |
| 43 | DONE+WAIT auto-transition guard -- `tools/validate.py` WARNs if `phase: DONE` with empty `## TODO`, no `[MARKHUNT]` blockers, and `next_action` starts with `WAIT:` (not safety-valve § 2.4). Catches the ZERO-PROMPT AUTO-TRANSITION violation where agent stops to ask instead of proceeding to HUNT/ADD (RFC § 2.1, v7.82.0) | Enforced directly by `tools/validate.py` |



| 43 | Checkpoint self-confirmation -- after writing `STATE.md` (§ 1.5 step 3) the agent re-reads it and confirms all eight required fields survived, the same re-read-after-write discipline § 1.4 already mandates for claims. A checkpoint missing `next_action` fails TEST-001 outright and is not a checkpoint (RFC § 1.5, `BOOT.md` step 7, v7.84.0) | `checkpoint-self-confirmation` -- behavioral, README-only |
